#!/usr/bin/env bash
# Auto-sync script for Project Aid: Healthcare Multimodal Triage
# Commits and pushes any new or modified files to GitHub origin main

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -n "$(git status --porcelain)" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Changes detected. Syncing to GitHub..."
    git add .
    git commit -m "chore(sync): auto-sync dataset and tooling $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Push complete."
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Workspace clean. Nothing to commit."
fi
