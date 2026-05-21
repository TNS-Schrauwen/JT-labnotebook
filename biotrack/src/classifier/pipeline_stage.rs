use crate::classifier::extension_map::{FileCategory, FileClassification};
use std::fmt;
use std::path::Path;


#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum PipelineStage {
    RawData,
    QualityControl,
    Trimming,
    Alignment,
    PostAlignment,
    VariantCalling,
    Annotation,
    Quantification,
    Analysis,
    Results,
}

impl fmt::Display for PipelineStage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::RawData => write!(f, "raw"),
            Self::QualityControl => write!(f, "qc"),
            Self::Trimming => write!(f, "trim"),
            Self::Alignment => write!(f, "align"),
            Self::PostAlignment => write!(f, "post-align"),
            Self::VariantCalling => write!(f, "variants"),
            Self::Annotation => write!(f, "annotate"),
            Self::Quantification => write!(f, "quant"),
            Self::Analysis => write!(f, "analysis"),
            Self::Results => write!(f, "results"),
        }
    }
}


pub fn infer_pipeline_stage(
    path: &Path,
    extension: Option<&str>,
    classification: &FileClassification,
) -> Option<PipelineStage> {

    if let Some(stage) = infer_from_directory(path) {
        return Some(stage);
    }


    if let Some(stage) = infer_from_filename(path) {
        return Some(stage);
    }


    infer_from_category(classification, extension)
}


fn infer_from_directory(path: &Path) -> Option<PipelineStage> {
    let path_str = path.to_string_lossy().to_lowercase();


    for component in path.components() {
        let dir_name = component.as_os_str().to_string_lossy().to_lowercase();

        match dir_name.as_str() {

            "raw" | "raw_data" | "rawdata" | "reads" | "fastq" | "fastqs" => {
                return Some(PipelineStage::RawData);
            }

            "qc" | "quality" | "fastqc" | "multiqc" | "quality_control" => {
                return Some(PipelineStage::QualityControl);
            }

            "trimmed" | "trim" | "filtered" | "clean" | "cleaned" => {
                return Some(PipelineStage::Trimming);
            }

            "aligned" | "alignment" | "alignments" | "mapped" | "mapping" | "bam" | "bams" => {
                return Some(PipelineStage::Alignment);
            }

            "dedup" | "recal" | "bqsr" | "markdup" | "realigned" => {
                return Some(PipelineStage::PostAlignment);
            }

            "variants" | "vcf" | "vcfs" | "calls" | "snps" | "indels" | "mutations" => {
                return Some(PipelineStage::VariantCalling);
            }

            "annotated" | "annotation" | "annotations" | "vep" | "snpeff" | "funcotator" => {
                return Some(PipelineStage::Annotation);
            }

            "counts" | "quantification" | "quant" | "expression" | "salmon" | "kallisto" | "htseq" | "featurecounts" => {
                return Some(PipelineStage::Quantification);
            }

            "analysis" | "deseq2" | "edger" | "differential" | "enrichment" | "gsea" => {
                return Some(PipelineStage::Analysis);
            }

            "results" | "output" | "outputs" | "final" | "figures" | "plots" | "report" | "reports" => {
                return Some(PipelineStage::Results);
            }
            _ => {}
        }
    }


    if path_str.contains("/publish/") || path_str.contains("/publishdir/") {
        return Some(PipelineStage::Results);
    }

    None
}


fn infer_from_filename(path: &Path) -> Option<PipelineStage> {
    let filename = path.file_stem()?.to_string_lossy().to_lowercase();


    if filename.contains("_trimmed")
        || filename.contains("_trim")
        || filename.contains("_filtered")
        || filename.contains("_clean")
        || filename.contains(".trimmed")
        || filename.contains("_fastp")
    {
        return Some(PipelineStage::Trimming);
    }

    if filename.contains("_sorted")
        || filename.contains("_aligned")
        || filename.contains("_mapped")
        || filename.contains(".sorted")
        || filename.contains("_markdup")
        || filename.contains("_dedup")
    {
        return Some(PipelineStage::PostAlignment);
    }

    if filename.contains("_fastqc")
        || filename.contains("multiqc")
        || filename.contains("_metrics")
        || filename.contains("_stats")
    {
        return Some(PipelineStage::QualityControl);
    }

    None
}

fn infer_from_category(
    classification: &FileClassification,
    _extension: Option<&str>,
) -> Option<PipelineStage> {
    match classification.category {
        FileCategory::RawSequencing => Some(PipelineStage::RawData),
        FileCategory::Alignment => Some(PipelineStage::Alignment),
        FileCategory::VariantCall => Some(PipelineStage::VariantCalling),
        FileCategory::QualityControl => Some(PipelineStage::QualityControl),
        FileCategory::Quantification => Some(PipelineStage::Quantification),
        FileCategory::Annotation => Some(PipelineStage::Annotation),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::classifier::extension_map::classify_extension;

    #[test]
    fn test_infer_from_directory() {
        let class = classify_extension(Some("fastq"));
        assert_eq!(
            infer_pipeline_stage(Path::new("raw/sample1.fastq"), Some("fastq"), &class),
            Some(PipelineStage::RawData)
        );

        let class = classify_extension(Some("bam"));
        assert_eq!(
            infer_pipeline_stage(Path::new("aligned/sample1.bam"), Some("bam"), &class),
            Some(PipelineStage::Alignment)
        );
    }

    #[test]
    fn test_infer_from_filename() {
        let class = classify_extension(Some("gz"));
        assert_eq!(
            infer_pipeline_stage(Path::new("data/sample1_trimmed.fq.gz"), Some("gz"), &class),
            Some(PipelineStage::Trimming)
        );
    }

    #[test]
    fn test_infer_from_category() {
        let class = classify_extension(Some("vcf"));
        assert_eq!(
            infer_pipeline_stage(Path::new("output/calls.vcf"), Some("vcf"), &class),
            Some(PipelineStage::VariantCalling)
        );
    }

    #[test]
    fn test_stage_ordering() {
        assert!(PipelineStage::RawData < PipelineStage::Alignment);
        assert!(PipelineStage::Alignment < PipelineStage::VariantCalling);
        assert!(PipelineStage::VariantCalling < PipelineStage::Results);
    }
}