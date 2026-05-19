---
title: "Dashboard"
date: 2026-05-19 00:34
---

# Project Intelligence Dashboard

**Last Updated:** 2026-05-19 00:34

---

## Watched Projects

| Project | Path | Tracked Files | New | Modified | Status |
|---------|------|---------------|-----|----------|--------|

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tracked Files | 0 |
| New Files (this scan) | 0 |
| Modified Files (this scan) | 0 |
| Deleted Files (this scan) | 0 |
| Projects | 0 |

---

## Quick Navigation

| Section | Description |
|---------|-------------|
| [File Registry](registry/) | All tracked files with metadata and annotations |
| [Pipeline Runs](runs/) | Nextflow runs, SLURM jobs, log files |
| [Notes](notes/) | Manual notes, debugging entries, observations |
| [Annotations](annotations.md) | File tags and context annotations |

---

## How to Add Context

To annotate files detected by the scanner, use:

biolab annotate <relative-file-path> --tags "tag1,tag2" --context "description"

Or edit `docs/annotations.md` directly on GitHub to add tags and context
to any tracked file.

