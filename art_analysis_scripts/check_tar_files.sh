#!/bin/bash

# Check tar files on local and remote for conflicts before sync.
#
# Pipeline:
#   1. Check integrity of all local tar files
#   2. Fetch remote tar sizes and compare with local
#   3. Check integrity of remote files that mismatch local
#   4. Cross-reference to produce 5 output categories
#
# Usage:
#   ./check_tar_files.sh [--verbose]
#
# Environment Variables:
#   SCRATCH      - Local source directory (required)
#   ARCHIVER     - Remote hostname (required)
#
# Exit Codes:
#   0 = Safe to proceed (no conflicts)
#   1 = Conflicts found (SYNC BLOCKED)
#   2 = Configuration error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPARE_SCRIPT="$SCRIPT_DIR/compare_tar_files.py"

# Parse arguments
VERBOSE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        *)
            echo "ERROR: Unknown option: $1" >&2
            exit 2
            ;;
    esac
done

# Verify compare script exists
if [ ! -f "$COMPARE_SCRIPT" ]; then
    echo "ERROR: compare_tar_files.py not found at $COMPARE_SCRIPT" >&2
    exit 2
fi

# Verify required environment variables
if [ -z "$SCRATCH" ]; then
    echo "ERROR: \$SCRATCH environment variable not set" >&2
    exit 2
fi

if [ -z "$ARCHIVER" ]; then
    echo "ERROR: \$ARCHIVER environment variable not set" >&2
    exit 2
fi

# Temp files for output categories
SMALLER_BROKEN_FILE=$(mktemp)       # local < remote AND only local broken
SMALLER_OK_FILE=$(mktemp)           # local < remote AND local intact (unexpected)
LARGER_REMOTE_BROKEN_FILE=$(mktemp) # local > remote AND only remote broken
LARGER_REMOTE_OK_FILE=$(mktemp)     # local > remote AND remote intact (unexpected)
BOTH_BROKEN_FILE=$(mktemp)          # size mismatch AND both broken
BROKEN_REMAINING_FILE=$(mktemp)     # broken local, sizes match or no remote
trap 'rm -f "$SMALLER_BROKEN_FILE" "$SMALLER_OK_FILE" "$LARGER_REMOTE_BROKEN_FILE" "$LARGER_REMOTE_OK_FILE" "$BOTH_BROKEN_FILE" "$BROKEN_REMAINING_FILE"' EXIT

# Run comparison pipeline
python3 "$COMPARE_SCRIPT" $VERBOSE \
    --local-path "$SCRATCH" \
    --remote-host "$ARCHIVER" \
    --remote-path "/scoutfs/projects/TG-AST200017/stampede3/" \
    --smaller-broken-file "$SMALLER_BROKEN_FILE" \
    --smaller-ok-file "$SMALLER_OK_FILE" \
    --larger-remote-broken-file "$LARGER_REMOTE_BROKEN_FILE" \
    --larger-remote-ok-file "$LARGER_REMOTE_OK_FILE" \
    --both-broken-file "$BOTH_BROKEN_FILE" \
    --broken-remaining-file "$BROKEN_REMAINING_FILE"

COMPARE_EXIT=$?

# 1. UNEXPECTED: local > remote, remote intact — warn only, does not block sync
if [ -s "$LARGER_REMOTE_OK_FILE" ]; then
    echo ""
    echo "[UNEXPECTED] local > remote but remote is intact (rsync will overwrite remote):"
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)"
    done < "$LARGER_REMOTE_OK_FILE"
fi

# 2. INFO: local > remote, remote broken — re-sync will fix
if [ -s "$LARGER_REMOTE_BROKEN_FILE" ]; then
    echo ""
    echo "[INFO] local > remote and remote is broken (re-sync will fix):"
    while IFS='|' read -r f local_size remote_size; do
        echo "  $f  (local: $local_size B, remote: $remote_size B)"
    done < "$LARGER_REMOTE_BROKEN_FILE"
fi

# 3. BOTH BROKEN: size mismatch, both local and remote broken — SYNC BLOCKED
if [ -s "$BOTH_BROKEN_FILE" ]; then
    echo ""
    echo "[ERROR] both local and remote are broken — SYNC BLOCKED:"
    while IFS='|' read -r f local_size remote_size err; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)  [local: $err]"
    done < "$BOTH_BROKEN_FILE"
fi

# 5. UNEXPECTED: local < remote, local intact — SYNC BLOCKED
if [ -s "$SMALLER_OK_FILE" ]; then
    echo ""
    echo "[UNEXPECTED] local < remote but local is intact — SYNC BLOCKED:"
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)"
    done < "$SMALLER_OK_FILE"
fi

# 6. EXPECTED: local < remote, only local broken — offer deletion
if [ -s "$SMALLER_BROKEN_FILE" ]; then
    echo ""
    echo "[WARN] local < remote and local is broken:"
    while IFS='|' read -r f local_size remote_size err; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)  [$err]"
    done < "$SMALLER_BROKEN_FILE"
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f local_size remote_size err; do
                rm -f "$f" && echo "Deleted: \$SCRATCH${f#$SCRATCH}"
            done < "$SMALLER_BROKEN_FILE"
            echo "Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped."
            ;;
    esac
fi

# 7. Remaining broken locals — offer deletion
if [ -s "$BROKEN_REMAINING_FILE" ]; then
    echo ""
    echo "[WARN] broken local files (size matches remote or no remote counterpart):"
    while IFS='|' read -r f err; do
        echo "  \$SCRATCH${f#$SCRATCH}  [$err]"
    done < "$BROKEN_REMAINING_FILE"
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f err; do
                rm -f "$f" && echo "Deleted: \$SCRATCH${f#$SCRATCH}"
            done < "$BROKEN_REMAINING_FILE"
            echo "Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped."
            ;;
    esac
fi

exit $COMPARE_EXIT
