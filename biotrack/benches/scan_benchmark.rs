use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId};
use std::fs;
use std::io::Write;
use tempfile::TempDir;

fn create_test_tree(dir: &std::path::Path, num_files: usize, depth: usize) {
    for d in 0..depth {
        let subdir = dir.join(format!("level_{}", d));
        fs::create_dir_all(&subdir).unwrap();

        let files_per_dir = num_files / depth;
        for f in 0..files_per_dir {
            let file_path = subdir.join(format!("file_{}.txt", f));
            let mut file = fs::File::create(&file_path).unwrap();
            let content = vec![b'A' + (f % 26) as u8; (f + 1) * 100];
            file.write_all(&content).unwrap();
        }
    }
}

fn bench_scan(c: &mut Criterion) {
    let mut group = c.benchmark_group("filesystem_scan");

    for num_files in [100, 1000, 10000].iter() {
        let dir = TempDir::new().unwrap();
        create_test_tree(dir.path(), *num_files, 10);

        group.bench_with_input(
            BenchmarkId::new("parallel_scan", num_files),
            num_files,
            |b, _| {
                b.iter(|| {
                    let settings = biotrack::config::settings::Settings::default();
                    let scanner =
                        biotrack::scanner::parallel_walker::ParallelScanner::new(&settings);
                    let progress = indicatif::ProgressBar::hidden();
                    scanner.scan(dir.path(), &progress).unwrap()
                });
            },
        );
    }

    group.finish();
}

fn bench_hash(c: &mut Criterion) {
    let mut group = c.benchmark_group("blake3_hashing");

    let dir = TempDir::new().unwrap();
    create_test_tree(dir.path(), 1000, 10);

    let settings = biotrack::config::settings::Settings::default();
    let scanner = biotrack::scanner::parallel_walker::ParallelScanner::new(&settings);
    let progress = indicatif::ProgressBar::hidden();
    let entries = scanner.scan(dir.path(), &progress).unwrap();

    group.bench_function("hash_1000_files", |b| {
        b.iter(|| {
            let progress = indicatif::ProgressBar::hidden();
            biotrack::hasher::blake3::hash_entries_parallel(&entries, &progress, &settings)
                .unwrap()
        });
    });

    group.finish();
}

criterion_group!(benches, bench_scan, bench_hash);
criterion_main!(benches);