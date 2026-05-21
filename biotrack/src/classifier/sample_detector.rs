use once_cell::sync::Lazy;
use regex::Regex;
use std::path::Path;


static SAMPLE_PATTERNS: Lazy<Vec<SamplePattern>> = Lazy::new(|| {
    vec![

        SamplePattern::new(r"((?:SRR|ERR|DRR|SRX|ERX|DRX)\d+)", "SRA/ENA accession"),

        SamplePattern::new(r"((?:sample|Sample|SAMPLE)[_-]?\d+[A-Za-z]*)", "Sample ID"),

        SamplePattern::new(r"^([A-Z]{2,6}\d{3,8}[A-Za-z]?)", "Alphanumeric ID"),

        SamplePattern::new(r"((?:patient|subject|donor)[_-]?[A-Za-z0-9]+)", "Patient ID"),

        SamplePattern::new(
            r"^([A-Za-z0-9][A-Za-z0-9_-]{2,20}?)(?:_R[12]|_[12]|_trimmed|_sorted|_aligned|_dedup|\.|_)",
            "Generic prefix",
        ),
    ]
});

struct SamplePattern {
    regex: Regex,
    #[allow(dead_code)]
    description: &'static str,
}

impl SamplePattern {
    fn new(pattern: &str, description: &'static str) -> Self {
        Self {
            regex: Regex::new(pattern).expect("Invalid sample detection regex"),
            description,
        }
    }
}


pub fn detect_sample_name(path: &Path) -> Option<String> {
    let filename = path.file_name()?.to_str()?;

    let stem = strip_compound_extensions(filename);

    for pattern in SAMPLE_PATTERNS.iter() {
        if let Some(captures) = pattern.regex.captures(&stem) {
            if let Some(m) = captures.get(1) {
                let sample = m.as_str().to_string();

                if sample.len() >= 3 && sample.len() <= 50 {
                    return Some(sample);
                }
            }
        }
    }

    None
}

fn strip_compound_extensions(filename: &str) -> String {
    let suffixes_to_strip = [
        ".fastq.gz",
        ".fq.gz",
        ".vcf.gz",
        ".fa.gz",
        ".fasta.gz",
        ".gff.gz",
        ".bed.gz",
        ".tar.gz",
        ".sam.gz",
    ];

    let lower = filename.to_lowercase();
    for suffix in &suffixes_to_strip {
        if lower.ends_with(suffix) {
            let stem = &filename[..filename.len() - suffix.len()];
            return stem.to_string();
        }
    }


    match filename.rfind('.') {
        Some(pos) if pos > 0 => filename[..pos].to_string(),
        _ => filename.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_detect_sra_accession() {
        assert_eq!(
            detect_sample_name(&PathBuf::from("data/SRR1234567_1.fastq.gz")),
            Some("SRR1234567".to_string())
        );
        assert_eq!(
            detect_sample_name(&PathBuf::from("ERX467883.bam")),
            Some("ERX467883".to_string())
        );
    }

    #[test]
    fn test_detect_alphanumeric_id() {
        assert_eq!(
            detect_sample_name(&PathBuf::from("data/NA12878_sorted.bam")),
            Some("NA12878".to_string())
        );
        assert_eq!(
            detect_sample_name(&PathBuf::from("TBNmA041_R1.fastq.gz")),
            Some("TBNmA041".to_string())
        );
    }

    #[test]
    fn test_detect_generic_prefix() {
        assert_eq!(
            detect_sample_name(&PathBuf::from("tumor_sample_R1.fastq.gz")),
            Some("tumor_sample".to_string())
        );
    }

    #[test]
    fn test_no_detection_for_generic_files() {

        assert_eq!(detect_sample_name(&PathBuf::from("a.txt")), None);
    }

    #[test]
    fn test_strip_compound_extensions() {
        assert_eq!(
            strip_compound_extensions("sample1_R1.fastq.gz"),
            "sample1_R1"
        );
        assert_eq!(strip_compound_extensions("output.vcf.gz"), "output");
        assert_eq!(strip_compound_extensions("readme.md"), "readme");
    }
}