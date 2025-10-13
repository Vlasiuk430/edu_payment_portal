#!/bin/bash
# Apply snapshots to create a git repository with 50 commits.
set -e
ROOT="$(pwd)"
SNAP_DIR="$ROOT/snapshots"
REPO_DIR="$ROOT/edu_payment_portal_repo"

rm -rf "$REPO_DIR"
mkdir -p "$REPO_DIR"
cd "$REPO_DIR"
git init -b main

i=1
for snap in $(ls -1 "$SNAP_DIR" | sort); do
  echo "Applying $snap"
  rsync -a --delete "$SNAP_DIR/$snap/" "$REPO_DIR/"
  # determine commit message and date (from snapshots_note.txt inside snapshot)
  CM=$(sed -n '1p' "$SNAP_DIR/$snap/snapshots_note.txt")
  # get planned date from second line
  DATE=$(sed -n '2p' "$SNAP_DIR/$snap/snapshots_note.txt" | sed 's/.*: //')
  export GIT_AUTHOR_DATE="$DATE"
  export GIT_COMMITTER_DATE="$DATE"
  git add -A
  git commit -m "$CM"
  i=$((i+1))
done

echo "Repository created at $REPO_DIR with $(git rev-list --count HEAD) commits."
echo "Add remote and push when ready."
