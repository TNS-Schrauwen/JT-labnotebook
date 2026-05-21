use crate::classifier::extension_map::classify_extension;
use crate::classifier::pipeline_stage::infer_pipeline_stage;
use crate::classifier::sample_detector::detect_sample_name;
use crate::scanner::entry::FileEntry;
use crate::tree::arena::{DirectoryTree, FileMetadata, NodeId};
use std::path::{Path, PathBuf};
use tracing::{debug, trace};

pub struct TreeBuilder;

impl TreeBuilder {

    pub fn build_from_entries(root_path: &Path, entries: &[FileEntry]) -> DirectoryTree {
        let root_name = root_path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_else(|| "/".to_string());

        let mut tree = DirectoryTree::new(&root_name);

        debug!(
            entries = entries.len(),
            root = %root_path.display(),
            "Building directory tree"
        );

        let mut sorted_entries: Vec<&FileEntry> = entries.iter().collect();
        sorted_entries.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));

        for entry in &sorted_entries {
            Self::ensure_parent_dirs(&mut tree, &entry.relative_path);

            let classification = classify_extension(entry.extension.as_deref());
            let pipeline_stage = infer_pipeline_stage(
                &entry.relative_path,
                entry.extension.as_deref(),
                &classification,
            );
            let sample_name = detect_sample_name(&entry.relative_path);

            let depth = entry.relative_path.components().count();

            let metadata = FileMetadata {
                size: entry.size,
                extension: entry.extension.clone(),
                content_hash: entry.content_hash.clone(),
                classification,
                pipeline_stage,
                sample_name,
            };

            tree.add_file(&entry.relative_path, depth, metadata);

            trace!(
                path = %entry.relative_path.display(),
                "Added file to tree"
            );
        }

        Self::sort_children(&mut tree);

        debug!(
            nodes = tree.len(),
            "Directory tree built"
        );

        tree
    }

    fn ensure_parent_dirs(tree: &mut DirectoryTree, file_path: &Path) {
        let mut accumulated = PathBuf::new();

        let components: Vec<_> = file_path.components().collect();
        for (i, component) in components.iter().enumerate() {
            if i == components.len() - 1 {
                break;
            }

            accumulated = accumulated.join(component.as_os_str());
            let depth = i + 1;
            tree.add_directory(&accumulated, depth);
        }
    }

    fn sort_children(tree: &mut DirectoryTree) {
        let node_count = tree.len();
        for i in 0..node_count {
            let children = tree.get(crate::tree::arena::NodeId(i)).children.clone();
            if children.is_empty() {
                continue;
            }

            let mut dirs: Vec<NodeId> = Vec::new();
            let mut files: Vec<NodeId> = Vec::new();

            for child_id in &children {
                let child = tree.get(*child_id);
                match &child.kind {
                    crate::tree::arena::NodeKind::Directory => dirs.push(*child_id),
                    crate::tree::arena::NodeKind::File(_) => files.push(*child_id),
                }
            }

            dirs.sort_by(|a, b| {
                let a_name = &tree.get(*a).name;
                let b_name = &tree.get(*b).name;
                a_name.cmp(b_name)
            });
            files.sort_by(|a, b| {
                let a_name = &tree.get(*a).name;
                let b_name = &tree.get(*b).name;
                a_name.cmp(b_name)
            });

            let mut sorted = dirs;
            sorted.extend(files);

            tree.get_mut(crate::tree::arena::NodeId(i)).children = sorted;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::scanner::entry::FileEntry;
    use chrono::Utc;
    use std::path::PathBuf;

    fn make_entry(path: &str, size: u64) -> FileEntry {
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
            content_hash: None,
            permissions: 0o644,
            inode: 1,
            device: 1,
        }
    }

    #[test]
    fn test_build_simple_tree() {
        let entries = vec![
            make_entry("data/sample1.fastq.gz", 1000),
            make_entry("data/sample2.fastq.gz", 2000),
            make_entry("results/output.bam", 5000),
            make_entry("scripts/pipeline.nf", 500),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);

        assert_eq!(tree.len(), 8);

        let stats = tree.statistics();
        assert_eq!(stats.total_files, 4);
        assert_eq!(stats.total_directories, 4);
        assert_eq!(stats.total_size, 8500);
    }

    #[test]
    fn test_deep_tree() {
        let entries = vec![
            make_entry("a/b/c/d/file.txt", 100),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);

        assert_eq!(tree.len(), 6);

        let stats = tree.statistics();
        assert_eq!(stats.max_depth, 5);
    }

    #[test]
    fn test_tree_relationships() {
        let entries = vec![
            make_entry("data/reads.fastq", 1000),
            make_entry("data/aligned.bam", 5000),
        ];

        let tree = TreeBuilder::build_from_entries(Path::new("/project"), &entries);

        let data_node = tree.get_by_path(Path::new("data")).unwrap();
        assert_eq!(data_node.children.len(), 2);

        let reads_id = tree.id_by_path(Path::new("data/reads.fastq")).unwrap();
        let siblings = tree.siblings(reads_id);
        assert_eq!(siblings.len(), 1);
        assert_eq!(siblings[0].name, "aligned.bam");
    }
}