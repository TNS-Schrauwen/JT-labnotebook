use crate::classifier::extension_map::{classify_extension, FileCategory, FileClassification};
use crate::classifier::pipeline_stage::PipelineStage;
use std::collections::HashMap;
use std::fmt;
use std::path::{Path, PathBuf};


#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId(pub usize);

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeKind {

    Directory,
    File(FileMetadata),
}


#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileMetadata {

    pub size: u64,

    pub extension: Option<String>,

    pub content_hash: Option<String>,

    pub classification: FileClassification,

    pub pipeline_stage: Option<PipelineStage>,

    pub sample_name: Option<String>,
}


#[derive(Debug, Clone)]
pub struct TreeNode {

    pub id: NodeId,

    pub name: String,

    pub relative_path: PathBuf,

    pub parent: Option<NodeId>,

    pub children: Vec<NodeId>,

    pub kind: NodeKind,

    pub depth: usize,
}


#[derive(Debug)]
pub struct DirectoryTree {

    nodes: Vec<TreeNode>,

    root: NodeId,

    path_index: HashMap<PathBuf, NodeId>,
}


#[derive(Debug, Default)]
pub struct TreeStatistics {
    pub total_files: usize,
    pub total_directories: usize,
    pub total_size: u64,
    pub max_depth: usize,
    pub classification_counts: Vec<(FileCategory, usize)>,
}

impl DirectoryTree {

    pub fn new(root_name: &str) -> Self {
        let root_node = TreeNode {
            id: NodeId(0),
            name: root_name.to_string(),
            relative_path: PathBuf::from(""),
            parent: None,
            children: Vec::new(),
            kind: NodeKind::Directory,
            depth: 0,
        };

        let mut path_index = HashMap::new();
        path_index.insert(PathBuf::from(""), NodeId(0));

        Self {
            nodes: vec![root_node],
            root: NodeId(0),
            path_index,
        }
    }


    pub fn root(&self) -> NodeId {
        self.root
    }

    pub fn get(&self, id: NodeId) -> &TreeNode {
        &self.nodes[id.0]
    }

    pub fn get_mut(&mut self, id: NodeId) -> &mut TreeNode {
        &mut self.nodes[id.0]
    }

    pub fn get_by_path(&self, path: &Path) -> Option<&TreeNode> {
        self.path_index.get(path).map(|id| &self.nodes[id.0])
    }

    pub fn id_by_path(&self, path: &Path) -> Option<NodeId> {
        self.path_index.get(path).copied()
    }

    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    pub fn add_directory(&mut self, relative_path: &Path, depth: usize) -> NodeId {
        if let Some(existing) = self.path_index.get(relative_path) {
            return *existing;
        }

        let id = NodeId(self.nodes.len());
        let name = relative_path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        let parent_path = relative_path
            .parent()
            .unwrap_or(Path::new(""))
            .to_path_buf();
        let parent_id = self.path_index.get(&parent_path).copied();

        let node = TreeNode {
            id,
            name,
            relative_path: relative_path.to_path_buf(),
            parent: parent_id,
            children: Vec::new(),
            kind: NodeKind::Directory,
            depth,
        };

        self.nodes.push(node);
        self.path_index.insert(relative_path.to_path_buf(), id);

        if let Some(pid) = parent_id {
            self.nodes[pid.0].children.push(id);
        }

        id
    }

    pub fn add_file(
        &mut self,
        relative_path: &Path,
        depth: usize,
        metadata: FileMetadata,
    ) -> NodeId {
        let id = NodeId(self.nodes.len());
        let name = relative_path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        let parent_path = relative_path
            .parent()
            .unwrap_or(Path::new(""))
            .to_path_buf();
        let parent_id = self.path_index.get(&parent_path).copied();

        let node = TreeNode {
            id,
            name,
            relative_path: relative_path.to_path_buf(),
            parent: parent_id,
            children: Vec::new(),
            kind: NodeKind::File(metadata),
            depth,
        };

        self.nodes.push(node);
        self.path_index.insert(relative_path.to_path_buf(), id);

        if let Some(pid) = parent_id {
            self.nodes[pid.0].children.push(id);
        }

        id
    }

    pub fn iter_dfs(&self) -> DfsIterator<'_> {
        DfsIterator {
            tree: self,
            stack: vec![self.root],
        }
    }

    pub fn iter_files(&self) -> impl Iterator<Item = &TreeNode> {
        self.nodes
            .iter()
            .filter(|n| matches!(n.kind, NodeKind::File(_)))
    }

    pub fn iter_directories(&self) -> impl Iterator<Item = &TreeNode> {
        self.nodes
            .iter()
            .filter(|n| matches!(n.kind, NodeKind::Directory))
    }

    pub fn children(&self, id: NodeId) -> Vec<&TreeNode> {
        self.nodes[id.0]
            .children
            .iter()
            .map(|child_id| &self.nodes[child_id.0])
            .collect()
    }

    pub fn parent(&self, id: NodeId) -> Option<&TreeNode> {
        self.nodes[id.0].parent.map(|pid| &self.nodes[pid.0])
    }

    pub fn ancestors(&self, id: NodeId) -> Vec<&TreeNode> {
        let mut result = Vec::new();
        let mut current = self.nodes[id.0].parent;
        while let Some(pid) = current {
            result.push(&self.nodes[pid.0]);
            current = self.nodes[pid.0].parent;
        }
        result
    }

    pub fn siblings(&self, id: NodeId) -> Vec<&TreeNode> {
        if let Some(parent_id) = self.nodes[id.0].parent {
            self.nodes[parent_id.0]
                .children
                .iter()
                .filter(|child_id| **child_id != id)
                .map(|child_id| &self.nodes[child_id.0])
                .collect()
        } else {
            Vec::new()
        }
    }

    pub fn statistics(&self) -> TreeStatistics {
        let mut stats = TreeStatistics::default();
        let mut category_counts: HashMap<FileCategory, usize> = HashMap::new();

        for node in &self.nodes {
            match &node.kind {
                NodeKind::Directory => {
                    stats.total_directories += 1;
                }
                NodeKind::File(meta) => {
                    stats.total_files += 1;
                    stats.total_size += meta.size;
                    *category_counts
                        .entry(meta.classification.category)
                        .or_insert(0) += 1;
                }
            }
            if node.depth > stats.max_depth {
                stats.max_depth = node.depth;
            }
        }

        let mut sorted_counts: Vec<_> = category_counts.into_iter().collect();
        sorted_counts.sort_by(|a, b| b.1.cmp(&a.1));
        stats.classification_counts = sorted_counts;

        stats
    }

    pub fn print_tree(&self, max_depth: usize, show_classification: bool) {
        self.print_node(self.root, "", true, max_depth, show_classification);
    }

    fn print_node(
        &self,
        id: NodeId,
        prefix: &str,
        is_last: bool,
        max_depth: usize,
        show_classification: bool,
    ) {
        let node = &self.nodes[id.0];

        if node.depth > max_depth {
            return;
        }

        let connector = if node.depth == 0 {
            ""
        } else if is_last {
            "└── "
        } else {
            "├── "
        };

        let classification_str = if show_classification {
            match &node.kind {
                NodeKind::Directory => " 📁".to_string(),
                NodeKind::File(meta) => {
                    let icon = meta.classification.category.icon();
                    let stage = meta
                        .pipeline_stage
                        .as_ref()
                        .map(|s| format!(" [{}]", s))
                        .unwrap_or_default();
                    let sample = meta
                        .sample_name
                        .as_ref()
                        .map(|s| format!(" <{}>", s))
                        .unwrap_or_default();
                    format!(" {}{}{}", icon, stage, sample)
                }
            }
        } else {
            String::new()
        };

        let size_str = match &node.kind {
            NodeKind::File(meta) => {
                format!(
                    " ({})",
                    humansize::format_size(meta.size, humansize::BINARY)
                )
            }
            NodeKind::Directory => String::new(),
        };

        println!(
            "{}{}{}{}{}",
            prefix, connector, node.name, size_str, classification_str
        );

        let child_prefix = if node.depth == 0 {
            String::new()
        } else if is_last {
            format!("{}    ", prefix)
        } else {
            format!("{}│   ", prefix)
        };

        let children = &node.children;
        for (i, child_id) in children.iter().enumerate() {
            let is_last_child = i == children.len() - 1;
            self.print_node(
                *child_id,
                &child_prefix,
                is_last_child,
                max_depth,
                show_classification,
            );
        }
    }
}

pub struct DfsIterator<'a> {
    tree: &'a DirectoryTree,
    stack: Vec<NodeId>,
}

impl<'a> Iterator for DfsIterator<'a> {
    type Item = &'a TreeNode;

    fn next(&mut self) -> Option<Self::Item> {
        let id = self.stack.pop()?;
        let node = &self.tree.nodes[id.0];

        for child_id in node.children.iter().rev() {
            self.stack.push(*child_id);
        }

        Some(node)
    }
}

impl fmt::Display for TreeNode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match &self.kind {
            NodeKind::Directory => write!(f, "{}/", self.name),
            NodeKind::File(_) => write!(f, "{}", self.name),
        }
    }
}