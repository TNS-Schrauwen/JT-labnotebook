use crate::tree::arena::NodeId;
use std::fmt;
use std::path::PathBuf;


#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RelationshipType {

    DerivedFrom,

    IndexOf,

    SameSample,

    DuplicateOf,

    PairedWith,

    ProducedBy,
}


#[derive(Debug, Clone)]
pub struct FileRelationship {

    pub source: PathBuf,

    pub target: PathBuf,

    pub relationship_type: RelationshipType,

    pub confidence: f64,

    pub reason: String,
}

impl fmt::Display for FileRelationship {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let arrow = match self.relationship_type {
            RelationshipType::DerivedFrom => "→",
            RelationshipType::IndexOf => "🔑→",
            RelationshipType::SameSample => "≈",
            RelationshipType::DuplicateOf => "=",
            RelationshipType::PairedWith => "⟷",
            RelationshipType::ProducedBy => "←",
        };

        write!(
            f,
            "{} {} {} ({:.0}% {})",
            self.source.display(),
            arrow,
            self.target.display(),
            self.confidence * 100.0,
            self.reason
        )
    }
}