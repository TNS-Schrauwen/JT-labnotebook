#!/usr/bin/env bash
#
# auto_sync.sh
# Automated scan and push for JT-labnotebook.


set -euo pipefail

NOTEBOOK_DIR="/home/jtrivedi@BLUECAT.arizona.edu/JT-labnotebook"
CONDA_BASE="/home/jtrivedi@BLUECAT.arizona.edu/software/miniconda3"
CONDA_ENV="labnotebook"
LOG_FILE="${NOTEBOOK_DIR}/.biolab/cron.log"
MAX_LOG_SIZE=50242880

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

rotate_log() {
    if [ -f "$LOG_FILE" ] && [ "$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        log "Log rotated"
    fi
}

rotate_log
log "=== Starting automated sync ==="

if [ -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]; then
    source "${CONDA_BASE}/etc/profile.d/conda.sh"
    conda activate "${CONDA_ENV}"
else
    log "ERROR: Cannot find conda or micromamba"
    exit 1
fi

cd "${NOTEBOOK_DIR}" || { log "ERROR: Cannot cd to ${NOTEBOOK_DIR}"; exit 1; }

if ! command -v biolab &> /dev/null; then
    log "ERROR: biolab command not found in PATH"
    exit 1
fi

log "Running scan..."
SCAN_START=$(date +%s)
biolab scan 2>&1 | while IFS= read -r line; do log "  $line"; done
SCAN_END=$(date +%s)
SCAN_DURATION=$((SCAN_END - SCAN_START))
log "Scan completed in ${SCAN_DURATION} seconds"

if git status --porcelain | grep -q .; then
    log "Changes detected, committing..."
    
    git add -A
    
    NEW_FILES=$(git diff --cached --name-only --diff-filter=A | wc -l)
    MOD_FILES=$(git diff --cached --name-only --diff-filter=M | wc -l)
    DEL_FILES=$(git diff --cached --name-only --diff-filter=D | wc -l)
    
    COMMIT_MSG="auto-sync $(date '+%Y-%m-%d %H:%M') | +${NEW_FILES} ~${MOD_FILES} -${DEL_FILES}"
    git commit -m "${COMMIT_MSG}"
    
    log "Pushing to GitHub..."
    if git push origin main 2>&1; then
        log "Push successful"
    else
        log "ERROR: Push failed (network issue or auth problem)"
        exit 1
    fi
else
    log "No changes detected, nothing to commit"
fi

log "=== Sync complete ==="