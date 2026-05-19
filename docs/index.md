---
title: "Home"
---

# JT Lab Notebook

**Author:** Jash Trivedi
**System:** Automated Project Intelligence Tracker

---

## Overview

This system automatically monitors registered project directories and tracks:

- All new, modified, and deleted files
- Nextflow pipeline runs (parsed from `.nextflow.log` and trace files)
- SLURM job outputs (parsed from `slurm-*.out` and `sacct`)
- Log files (`.log`, `.out`, `.err`)
- Configuration files and scripts
- File content hashes for change detection

## Navigation

| Page | Purpose |
|------|---------|
| [Dashboard](dashboard.md) | Statistics and project overview |
| [File Registry](registry/) | Complete file inventory per project |
| [Pipeline Runs](runs/) | Detected runs with resource usage |
| [Annotations](annotations.md) | File tags and context |
| [Notes](notes/) | Manual notes and observations |

## Usage
biolab scan -- Scan all projects, detect changes
biolab annotate -- Add tags and context to files
biolab sync -- Scan + commit + push
biolab note -- Add a manual note

