use std::collections::HashMap;
use std::fmt;

use once_cell::sync::Lazy;


#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FileCategory {

    RawSequencing,
    Alignment,
    VariantCall,
    Reference,
    Annotation,
    Quantification,
    QualityControl,
    Workflow,
    Configuration,
    Log,
    Documentation,
    TabularData,
    Figure,
    Archive,
    Script,
    Container,
    Index,
    Intermediate,
    Phylogenetics,
    Unknown,
}

impl FileCategory {
    pub fn icon(&self) -> &'static str {
        match self {
            Self::RawSequencing => "🧬",
            Self::Alignment => "🎯",
            Self::VariantCall => "🔬",
            Self::Reference => "📖",
            Self::Annotation => "🏷️",
            Self::Quantification => "📊",
            Self::QualityControl => "✅",
            Self::Workflow => "⚙️",
            Self::Configuration => "🔧",
            Self::Log => "📋",
            Self::Documentation => "📝",
            Self::TabularData => "📈",
            Self::Figure => "🖼️",
            Self::Archive => "📦",
            Self::Script => "💻",
            Self::Container => "🐳",
            Self::Index => "🔑",
            Self::Intermediate => "⏳",
            Self::Phylogenetics => "🌳",
            Self::Unknown => "❓",
        }
    }
}


#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileClassification {
    pub category: FileCategory,
    pub description: &'static str,
    pub typically_large: bool,
    pub is_binary: bool,
}


static EXTENSION_MAP: Lazy<HashMap<&'static str, FileClassification>> = Lazy::new(|| {
    let mut m = HashMap::new();

    m.insert("fastq", FileClassification { category: FileCategory::RawSequencing, description: "FASTQ sequencing reads", typically_large: true, is_binary: false });
    m.insert("fq", FileClassification { category: FileCategory::RawSequencing, description: "FASTQ sequencing reads", typically_large: true, is_binary: false });
    m.insert("fast5", FileClassification { category: FileCategory::RawSequencing, description: "Oxford Nanopore signal data", typically_large: true, is_binary: true });
    m.insert("pod5", FileClassification { category: FileCategory::RawSequencing, description: "Oxford Nanopore POD5 signal data", typically_large: true, is_binary: true });
    m.insert("sra", FileClassification { category: FileCategory::RawSequencing, description: "SRA archive", typically_large: true, is_binary: true });
    m.insert("ab1", FileClassification { category: FileCategory::RawSequencing, description: "Sanger sequencing trace", typically_large: false, is_binary: true });
    m.insert("bam", FileClassification { category: FileCategory::Alignment, description: "Binary Alignment Map", typically_large: true, is_binary: true });
    m.insert("sam", FileClassification { category: FileCategory::Alignment, description: "Sequence Alignment Map", typically_large: true, is_binary: false });
    m.insert("cram", FileClassification { category: FileCategory::Alignment, description: "Compressed Reference Alignment Map", typically_large: true, is_binary: true });
    m.insert("vcf", FileClassification { category: FileCategory::VariantCall, description: "Variant Call Format", typically_large: false, is_binary: false });
    m.insert("bcf", FileClassification { category: FileCategory::VariantCall, description: "Binary Variant Call Format", typically_large: false, is_binary: true });
    m.insert("gvcf", FileClassification { category: FileCategory::VariantCall, description: "Genomic VCF", typically_large: false, is_binary: false });
    m.insert("maf", FileClassification { category: FileCategory::VariantCall, description: "Mutation Annotation Format", typically_large: false, is_binary: false });
    m.insert("fa", FileClassification { category: FileCategory::Reference, description: "FASTA sequence", typically_large: true, is_binary: false });
    m.insert("fasta", FileClassification { category: FileCategory::Reference, description: "FASTA sequence", typically_large: true, is_binary: false });
    m.insert("fna", FileClassification { category: FileCategory::Reference, description: "FASTA nucleic acid", typically_large: true, is_binary: false });
    m.insert("ffn", FileClassification { category: FileCategory::Reference, description: "FASTA nucleotide coding regions", typically_large: false, is_binary: false });
    m.insert("faa", FileClassification { category: FileCategory::Reference, description: "FASTA amino acid", typically_large: false, is_binary: false });
    m.insert("dict", FileClassification { category: FileCategory::Reference, description: "Sequence dictionary", typically_large: false, is_binary: false });
    m.insert("gff", FileClassification { category: FileCategory::Annotation, description: "General Feature Format", typically_large: false, is_binary: false });
    m.insert("gff3", FileClassification { category: FileCategory::Annotation, description: "GFF version 3", typically_large: false, is_binary: false });
    m.insert("gtf", FileClassification { category: FileCategory::Annotation, description: "Gene Transfer Format", typically_large: false, is_binary: false });
    m.insert("bed", FileClassification { category: FileCategory::Annotation, description: "Browser Extensible Data", typically_large: false, is_binary: false });
    m.insert("bedgraph", FileClassification { category: FileCategory::Annotation, description: "BedGraph format", typically_large: false, is_binary: false });
    m.insert("bigwig", FileClassification { category: FileCategory::Annotation, description: "BigWig format", typically_large: true, is_binary: true });
    m.insert("bw", FileClassification { category: FileCategory::Annotation, description: "BigWig format", typically_large: true, is_binary: true });
    m.insert("wig", FileClassification { category: FileCategory::Annotation, description: "Wiggle format", typically_large: false, is_binary: false });
    m.insert("counts", FileClassification { category: FileCategory::Quantification, description: "Count matrix", typically_large: false, is_binary: false });
    m.insert("h5ad", FileClassification { category: FileCategory::Quantification, description: "AnnData HDF5", typically_large: true, is_binary: true });
    m.insert("loom", FileClassification { category: FileCategory::Quantification, description: "Loom single-cell format", typically_large: true, is_binary: true });
    m.insert("mtx", FileClassification { category: FileCategory::Quantification, description: "Matrix Market format", typically_large: false, is_binary: false });
    m.insert("html", FileClassification { category: FileCategory::QualityControl, description: "HTML report", typically_large: false, is_binary: false });
    m.insert("zip", FileClassification { category: FileCategory::Archive, description: "ZIP archive", typically_large: false, is_binary: true });
    m.insert("nf", FileClassification { category: FileCategory::Workflow, description: "Nextflow script", typically_large: false, is_binary: false });
    m.insert("smk", FileClassification { category: FileCategory::Workflow, description: "Snakemake rule file", typically_large: false, is_binary: false });
    m.insert("wdl", FileClassification { category: FileCategory::Workflow, description: "Workflow Description Language", typically_large: false, is_binary: false });
    m.insert("cwl", FileClassification { category: FileCategory::Workflow, description: "Common Workflow Language", typically_large: false, is_binary: false });
    m.insert("yaml", FileClassification { category: FileCategory::Configuration, description: "YAML configuration", typically_large: false, is_binary: false });
    m.insert("yml", FileClassification { category: FileCategory::Configuration, description: "YAML configuration", typically_large: false, is_binary: false });
    m.insert("toml", FileClassification { category: FileCategory::Configuration, description: "TOML configuration", typically_large: false, is_binary: false });
    m.insert("json", FileClassification { category: FileCategory::Configuration, description: "JSON data", typically_large: false, is_binary: false });
    m.insert("ini", FileClassification { category: FileCategory::Configuration, description: "INI configuration", typically_large: false, is_binary: false });
    m.insert("cfg", FileClassification { category: FileCategory::Configuration, description: "Configuration file", typically_large: false, is_binary: false });
    m.insert("config", FileClassification { category: FileCategory::Configuration, description: "Configuration file", typically_large: false, is_binary: false });
    m.insert("conf", FileClassification { category: FileCategory::Configuration, description: "Configuration file", typically_large: false, is_binary: false });
    m.insert("log", FileClassification { category: FileCategory::Log, description: "Log file", typically_large: false, is_binary: false });
    m.insert("err", FileClassification { category: FileCategory::Log, description: "Error log", typically_large: false, is_binary: false });
    m.insert("out", FileClassification { category: FileCategory::Log, description: "Output log", typically_large: false, is_binary: false });
    m.insert("md", FileClassification { category: FileCategory::Documentation, description: "Markdown document", typically_large: false, is_binary: false });
    m.insert("rst", FileClassification { category: FileCategory::Documentation, description: "reStructuredText", typically_large: false, is_binary: false });
    m.insert("txt", FileClassification { category: FileCategory::Documentation, description: "Text file", typically_large: false, is_binary: false });
    m.insert("csv", FileClassification { category: FileCategory::TabularData, description: "Comma-separated values", typically_large: false, is_binary: false });
    m.insert("tsv", FileClassification { category: FileCategory::TabularData, description: "Tab-separated values", typically_large: false, is_binary: false });
    m.insert("xlsx", FileClassification { category: FileCategory::TabularData, description: "Excel spreadsheet", typically_large: false, is_binary: true });
    m.insert("xls", FileClassification { category: FileCategory::TabularData, description: "Excel spreadsheet (legacy)", typically_large: false, is_binary: true });
    m.insert("png", FileClassification { category: FileCategory::Figure, description: "PNG image", typically_large: false, is_binary: true });
    m.insert("svg", FileClassification { category: FileCategory::Figure, description: "SVG vector graphic", typically_large: false, is_binary: false });
    m.insert("pdf", FileClassification { category: FileCategory::Figure, description: "PDF document", typically_large: false, is_binary: true });
    m.insert("jpg", FileClassification { category: FileCategory::Figure, description: "JPEG image", typically_large: false, is_binary: true });
    m.insert("jpeg", FileClassification { category: FileCategory::Figure, description: "JPEG image", typically_large: false, is_binary: true });
    m.insert("tiff", FileClassification { category: FileCategory::Figure, description: "TIFF image", typically_large: false, is_binary: true });
    m.insert("tif", FileClassification { category: FileCategory::Figure, description: "TIFF image", typically_large: false, is_binary: true });
    m.insert("gz", FileClassification { category: FileCategory::Archive, description: "Gzip compressed", typically_large: true, is_binary: true });
    m.insert("tar", FileClassification { category: FileCategory::Archive, description: "Tar archive", typically_large: true, is_binary: true });
    m.insert("bz2", FileClassification { category: FileCategory::Archive, description: "Bzip2 compressed", typically_large: true, is_binary: true });
    m.insert("xz", FileClassification { category: FileCategory::Archive, description: "XZ compressed", typically_large: true, is_binary: true });
    m.insert("zst", FileClassification { category: FileCategory::Archive, description: "Zstandard compressed", typically_large: true, is_binary: true });
    m.insert("py", FileClassification { category: FileCategory::Script, description: "Python script", typically_large: false, is_binary: false });
    m.insert("r", FileClassification { category: FileCategory::Script, description: "R script", typically_large: false, is_binary: false });
    m.insert("rmd", FileClassification { category: FileCategory::Script, description: "R Markdown notebook", typically_large: false, is_binary: false });
    m.insert("sh", FileClassification { category: FileCategory::Script, description: "Shell script", typically_large: false, is_binary: false });
    m.insert("bash", FileClassification { category: FileCategory::Script, description: "Bash script", typically_large: false, is_binary: false });
    m.insert("pl", FileClassification { category: FileCategory::Script, description: "Perl script", typically_large: false, is_binary: false });
    m.insert("ipynb", FileClassification { category: FileCategory::Script, description: "Jupyter notebook", typically_large: false, is_binary: false });
    m.insert("sif", FileClassification { category: FileCategory::Container, description: "Singularity container image", typically_large: true, is_binary: true });
    m.insert("simg", FileClassification { category: FileCategory::Container, description: "Singularity container image", typically_large: true, is_binary: true });
    m.insert("bai", FileClassification { category: FileCategory::Index, description: "BAM index", typically_large: false, is_binary: true });
    m.insert("csi", FileClassification { category: FileCategory::Index, description: "CSI index", typically_large: false, is_binary: true });
    m.insert("tbi", FileClassification { category: FileCategory::Index, description: "Tabix index", typically_large: false, is_binary: true });
    m.insert("fai", FileClassification { category: FileCategory::Index, description: "FASTA index", typically_large: false, is_binary: false });
    m.insert("idx", FileClassification { category: FileCategory::Index, description: "Generic index", typically_large: false, is_binary: true });
    m.insert("nwk", FileClassification { category: FileCategory::Phylogenetics, description: "Newick tree format", typically_large: false, is_binary: false });
    m.insert("tree", FileClassification { category: FileCategory::Phylogenetics, description: "Phylogenetic tree", typically_large: false, is_binary: false });
    m.insert("treefile", FileClassification { category: FileCategory::Phylogenetics, description: "Phylogenetic tree", typically_large: false, is_binary: false });
    m.insert("nex", FileClassification { category: FileCategory::Phylogenetics, description: "Nexus format", typically_large: false, is_binary: false });

    m
});


pub fn classify_extension(extension: Option<&str>) -> FileClassification {
    let ext = match extension {
        Some(e) => e.to_lowercase(),
        None => {
            return FileClassification {
                category: FileCategory::Unknown,
                description: "No extension",
                typically_large: false,
                is_binary: false,
            };
        }
    };


    if let Some(classification) = EXTENSION_MAP.get(ext.as_str()) {
        return classification.clone();
    }

    FileClassification {
        category: FileCategory::Unknown,
        description: "Unknown file type",
        typically_large: false,
        is_binary: false,
    }
}


pub fn classify_filename(filename: &str) -> FileClassification {
    let lower = filename.to_lowercase();

    let compound_patterns: &[(&str, FileClassification)] = &[
        (".fastq.gz", FileClassification { category: FileCategory::RawSequencing, description: "Compressed FASTQ reads", typically_large: true, is_binary: true }),
        (".fq.gz", FileClassification { category: FileCategory::RawSequencing, description: "Compressed FASTQ reads", typically_large: true, is_binary: true }),
        (".vcf.gz", FileClassification { category: FileCategory::VariantCall, description: "Compressed VCF", typically_large: false, is_binary: true }),
        (".gvcf.gz", FileClassification { category: FileCategory::VariantCall, description: "Compressed gVCF", typically_large: false, is_binary: true }),
        (".bed.gz", FileClassification { category: FileCategory::Annotation, description: "Compressed BED", typically_large: false, is_binary: true }),
        (".gff.gz", FileClassification { category: FileCategory::Annotation, description: "Compressed GFF", typically_large: false, is_binary: true }),
        (".fa.gz", FileClassification { category: FileCategory::Reference, description: "Compressed FASTA", typically_large: true, is_binary: true }),
        (".fasta.gz", FileClassification { category: FileCategory::Reference, description: "Compressed FASTA", typically_large: true, is_binary: true }),
        (".tar.gz", FileClassification { category: FileCategory::Archive, description: "Tar gzip archive", typically_large: true, is_binary: true }),
    ];

    for (pattern, classification) in compound_patterns {
        if lower.ends_with(pattern) {
            return classification.clone();
        }
    }

    let special_names: &[(&str, FileClassification)] = &[
        ("dockerfile", FileClassification { category: FileCategory::Container, description: "Docker container definition", typically_large: false, is_binary: false }),
        ("snakefile", FileClassification { category: FileCategory::Workflow, description: "Snakemake workflow", typically_large: false, is_binary: false }),
        ("makefile", FileClassification { category: FileCategory::Workflow, description: "Makefile build script", typically_large: false, is_binary: false }),
        ("readme", FileClassification { category: FileCategory::Documentation, description: "README documentation", typically_large: false, is_binary: false }),
        ("nextflow.config", FileClassification { category: FileCategory::Configuration, description: "Nextflow configuration", typically_large: false, is_binary: false }),
    ];

    for (name, classification) in special_names {
        if lower == *name || lower.starts_with(name) {
            return classification.clone();
        }
    }

    let ext = std::path::Path::new(filename)
        .extension()
        .and_then(|e| e.to_str());
    classify_extension(ext)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_common_bioinformatics_files() {
        assert_eq!(classify_extension(Some("fastq")).category, FileCategory::RawSequencing);
        assert_eq!(classify_extension(Some("bam")).category, FileCategory::Alignment);
        assert_eq!(classify_extension(Some("vcf")).category, FileCategory::VariantCall);
        assert_eq!(classify_extension(Some("nf")).category, FileCategory::Workflow);
        assert_eq!(classify_extension(Some("bed")).category, FileCategory::Annotation);
        assert_eq!(classify_extension(Some("bai")).category, FileCategory::Index);
    }

    #[test]
    fn test_classify_compound_extensions() {
        assert_eq!(classify_filename("sample1.fastq.gz").category, FileCategory::RawSequencing);
        assert_eq!(classify_filename("variants.vcf.gz").category, FileCategory::VariantCall);
        assert_eq!(classify_filename("genome.fa.gz").category, FileCategory::Reference);
    }

    #[test]
    fn test_classify_special_filenames() {
        assert_eq!(classify_filename("Dockerfile").category, FileCategory::Container);
        assert_eq!(classify_filename("Snakefile").category, FileCategory::Workflow);
        assert_eq!(classify_filename("nextflow.config").category, FileCategory::Configuration);
    }

    #[test]
    fn test_unknown_extension() {
        assert_eq!(classify_extension(Some("xyz123")).category, FileCategory::Unknown);
        assert_eq!(classify_extension(None).category, FileCategory::Unknown);
    }
}