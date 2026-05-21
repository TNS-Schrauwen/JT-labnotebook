use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use std::path::{Path, PathBuf};
use tempfile::TempDir;

fn create_bioinformatics_project(dir: &Path, num_samples: usize) {

    for i in 0..num_samples {
        let sample = format!("sample_{:04}", i);
        let raw_dir = dir.join("raw");
        std::fs::create_dir_all(&raw_dir).unwrap();
        std::fs::write(
            raw_dir.join(format!("{}_R1.fastq.gz", sample)),
            vec![b'A'; 100],
        ).unwrap();
        std::fs::write(
            raw_dir.join(format!("{}_R2.fastq.gz", sample)),
            vec![b'T'; 100],
        ).unwrap();

        let aligned_dir = dir.join("aligned");
        std::fs::create_dir_all(&aligned_dir).unwrap();
        std::fs::write(
            aligned_dir.join(format!("{}_sorted.bam", sample)),
            vec![b'B'; 500],
        ).unwrap();
        std::fs::write(
            aligned_dir.join(format!("{}_sorted.bam.bai", sample)),
            vec![b'I'; 50],
        ).unwrap();

        let var_dir = dir.join("variants");
        std::fs::create_dir_all(&var_dir).unwrap();
        std::fs::write(
            var_dir.join(format!("{}.vcf", sample)),
            vec![b'V'; 200],
        ).unwrap();

        let qc_dir = dir.join("qc");
        std::fs::create_dir_all(&qc_dir).unwrap();
        std::fs::write(
            qc_dir.join(format!("{}_fastqc.html", sample)),
            vec![b'H'; 80],
        ).unwrap();
    }
}

fn bench_tree_build(c: &mut Criterion) {
    let mut group = c.benchmark_group("tree_build");

    for num_samples in [10, 100, 500].iter() {
        let dir = TempDir::new().unwrap();
        create_bioinformatics_project(dir.path(), *num_samples);


        let settings = biotrack::config::settings::Settings::default();
        let scanner = biotrack::scanner::parallel_walker::ParallelScanner::new(&settings);
        let progress = indicatif::ProgressBar::hidden();
        let entries = scanner.scan(dir.path(), &progress).unwrap();

        group.bench_with_input(
            BenchmarkId::new("build", num_samples),
            num_samples,
            |b, _| {
                b.iter(|| {
                    biotrack::tree::builder::TreeBuilder::build_from_entries(
                        dir.path(),
                        &entries,
                    )
                });
            },
        );
    }

    group.finish();
}

fn bench_relationship_inference(c: &mut Criterion) {
    let mut group = c.benchmark_group("relationship_inference");

    for num_samples in [10, 100].iter() {
        let dir = TempDir::new().unwrap();
        create_bioinformatics_project(dir.path(), *num_samples);

        let settings = biotrack::config::settings::Settings::default();
        let scanner = biotrack::scanner::parallel_walker::ParallelScanner::new(&settings);
        let progress = indicatif::ProgressBar::hidden();
        let entries = scanner.scan(dir.path(), &progress).unwrap();
        let tree = biotrack::tree::builder::TreeBuilder::build_from_entries(
            dir.path(),
            &entries,
        );

        group.bench_with_input(
            BenchmarkId::new("infer", num_samples),
            num_samples,
            |b, _| {
                b.iter(|| {
                    biotrack::relationship::inference::infer_relationships(&tree)
                });
            },
        );
    }

    group.finish();
}

criterion_group!(benches, bench_tree_build, bench_relationship_inference);
criterion_main!(benches);