use crate::classifier::extension_map::FileCategory;
use crate::classifier::pipeline_stage::PipelineStage;
use crate::tree::arena::{DirectoryTree, FileMetadata, NodeId, NodeKind, TreeNode};
use std::path::Path;

impl DirectoryTree {

    pub fn find_by_extension(&self, ext: &str) -> Vec<&TreeNode> {
        let ext_lower = ext.to_lowercase();
        self.iter_files()
            .filter(|node| {
                if let NodeKind::File(meta) = &node.kind {
                    meta.extension.as_deref() == Some(ext_lower.as_str())
                } else {
                    false
                }
            })
            .collect()
    }

    pub fn find_by_category(&self, category: FileCategory) -> Vec<&TreeNode> {
        self.iter_files()
            .filter(|node| {
                if let NodeKind::File(meta) = &node.kind {
                    meta.classification.category == category
                } else {
                    false
                }
            })
            .collect()
    }

    pub fn find_by_pipeline_stage(&self, stage: PipelineStage) -> Vec<&TreeNode> {
        self.iter_files()
            .filter(|node| {
                if let NodeKind::File(meta) = &node.kind {
                    meta.pipeline_stage == Some(stage)
                } else {
                    false
                }
            })
            .collect()
    }

    pub fn find_by_sample(&self, sample_name: &str) -> Vec<&TreeNode> {
        let sample_lower = sample_name.to_lowercase();
        self.iter_files()
            .filter(|node| {
                if let NodeKind::File(meta) = &node.kind {
                    meta.sample_name
                        .as_ref()
                        .map(|s| s.to_lowercase() == sample_lower)
                        .unwrap_or(false)
                } else {
                    false
                }
            })
            .collect()
    }

    pub fn all_sample_names(&self) -> Vec<String> {
        let mut samples: Vec<String> = self
            .iter_files()
            .filter_map(|node| {
                if let NodeKind::File(meta) = &node.kind {
                    meta.sample_name.clone()
                } else {
                    None
                }
            })
            .collect();

        samples.sort();
        samples.dedup();
        samples
    }

    pub fn find_duplicates(&self) -> Vec<Vec<&TreeNode>> {
        use std::collections::HashMap;

        let mut hash_groups: HashMap<&str, Vec<&TreeNode>> = HashMap::new();

        for node in self.iter_files() {
            if let NodeKind::File(meta) = &node.kind {
                if let Some(hash) = &meta.content_hash {
                    hash_groups.entry(hash.as_str()).or_default().push(node);
                }
            }
        }

        hash_groups
            .into_values()
            .filter(|group| group.len() > 1)
            .collect()
    }

    pub fn find_orphans(&self) -> Vec<&TreeNode> {
        self.iter_files()
            .filter(|node| {
                if let NodeKind::File(meta) = &node.kind {
                    meta.sample_name.is_none()
                        && meta.pipeline_stage.is_none()
                        && meta.classification.category == FileCategory::Unknown
                } else {
                    false
                }
            })
            .collect()
    }

    pub fn directory_size(&self, dir_path: &Path) -> u64 {
        if let Some(dir_id) = self.id_by_path(dir_path) {
            self.subtree_size(dir_id)
        } else {
            0
        }
    }

    fn subtree_size(&self, id: NodeId) -> u64 {
        let node = self.get(id);
        match &node.kind {
            NodeKind::File(meta) => meta.size,
            NodeKind::Directory => {
                node.children.iter().map(|child| self.subtree_size(*child)).sum()
            }
        }
    }

    pub fn directory_file_count(&self, dir_path: &Path) -> usize {
        if let Some(dir_id) = self.id_by_path(dir_path) {
            self.subtree_file_count(dir_id)
        } else {
            0
        }
    }

    fn subtree_file_count(&self, id: NodeId) -> usize {
        let node = self.get(id);
        match &node.kind {
            NodeKind::File(_) => 1,
            NodeKind::Directory => {
                node.children
                    .iter()
                    .map(|child| self.subtree_file_count(*child))
                    .sum()
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scanner::entry::FileEntry;
    use crate::tree::builder::TreeBuilder;
    use chrono::Utc;
    use std::path::PathBuf;

    fn make_entry(path: &str, size: u64, hash: Option<&str>) -> FileEntry {
        FileEntry {
            relative_path: PathBuf::from(path),
            absolute_path: PathBuf::from(format!("/project/{}", path)),
            size,
            mtime: Utc::now(),
            extension: Path::new(path)
                .extension()
                .and_then(|e| e.to_str())
                .map(|s| s.to_lowercase()),
            is_symlink: false,
            content_hash: hash.map(|s| s.to_string()),
            permissions: 0o644,
            inode: 1,
            device: 1,
        }
    }

    #[test]
    fn test_find_by_extension() {
        let entries = vec![
            make_entry("data/sample1.fastq", 1000, None),
            make_entry("data/sample2.fastq", 2000, None),
            make_entry("results/output.bam", 5000, None),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);
        let fastq_files = tree.find_by_extension("fastq");
        assert_eq!(fastq_files.len(), 2);
    }

    #[test]
    fn test_find_duplicates() {
        let entries = vec![
            make_entry("file1.txt", 100, Some("abc123")),
            make_entry("file2.txt", 100, Some("abc123")),
            make_entry("file3.txt", 200, Some("def456")),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);
        let dupes = tree.find_duplicates();
        assert_eq!(dupes.len(), 1);
        assert_eq!(dupes[0].len(), 2);
    }

    #[test]
    fn test_directory_size() {
        let entries = vec![
            make_entry("data/a.txt", 100, None),
            make_entry("data/b.txt", 200, None),
            make_entry("other/c.txt", 50, None),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);
        assert_eq!(tree.directory_size(Path::new("data")), 300);
        assert_eq!(tree.directory_size(Path::new("other")), 50);
    }
}