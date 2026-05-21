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

# Temp files for the 5 output categories
SMALLER_BROKEN_FILE=$(mktemp)       # local < remote AND local broken
SMALLER_OK_FILE=$(mktemp)           # local < remote AND local intact (unexpected)
LARGER_REMOTE_BROKEN_FILE=$(mktemp) # local > remote AND remote broken
LARGER_REMOTE_OK_FILE=$(mktemp)     # local > remote AND remote intact (unexpected)
BROKEN_REMAINING_FILE=$(mktemp)     # broken local, sizes match or no remote
trap 'rm -f "$SMALLER_BROKEN_FILE" "$SMALLER_OK_FILE" "$LARGER_REMOTE_BROKEN_FILE" "$LARGER_REMOTE_OK_FILE" "$BROKEN_REMAINING_FILE"' EXIT

# Run comparison pipeline
python3 "$COMPARE_SCRIPT" $VERBOSE \
    --local-path "$SCRATCH" \
    --remote-host "$ARCHIVER" \
    --remote-path "/scoutfs/projects/TG-AST200017/stampede3/" \
    --smaller-broken-file "$SMALLER_BROKEN_FILE" \
    --smaller-ok-file "$SMALLER_OK_FILE" \
    --larger-remote-broken-file "$LARGER_REMOTE_BROKEN_FILE" \
    --larger-remote-ok-file "$LARGER_REMOTE_OK_FILE" \
    --broken-remaining-file "$BROKEN_REMAINING_FILE"

COMPARE_EXIT=$?

# 1. UNEXPECTED: local > remote, remote intact — warn only, does not block sync
if [ -s "$LARGER_REMOTE_OK_FILE" ]; then
    echo ""
    echo "[UNEXPECTED] The following files have local > remote but the remote is intact."
    echo "             This may mean local was recently updated. Rsync will overwrite remote."
    echo ""
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Local:  $local_size bytes  |  Remote: $remote_size bytes"
    done < "$LARGER_REMOTE_OK_FILE"
fi

# 2. INFO: local > remote, remote broken — re-sync will fix
if [ -s "$LARGER_REMOTE_BROKEN_FILE" ]; then
    echo ""
    echo "[INFO] The following remote files are broken and smaller than local."
    echo "       Re-syncing will overwrite them with the intact local copies."
    echo ""
    while IFS='|' read -r f local_size remote_size; do
        echo "  $f"
        echo "    Local:  $local_size bytes  |  Remote: $remote_size bytes"
    done < "$LARGER_REMOTE_BROKEN_FILE"
fi

# 3. UNEXPECTED: local < remote, local intact — SYNC BLOCKED
if [ -s "$SMALLER_OK_FILE" ]; then
    echo ""
    echo "[UNEXPECTED] The following files have local < remote but the local is intact."
    echo "             Manual investigation required. SYNC BLOCKED."
    echo ""
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Local:  $local_size bytes  |  Remote: $remote_size bytes"
    done < "$SMALLER_OK_FILE"
fi

# 4. EXPECTED: local < remote, local broken — offer deletion
if [ -s "$SMALLER_BROKEN_FILE" ]; then
    echo ""
    echo "[WARN] The following local files are broken and smaller than their remote counterparts:"
    echo ""
    while IFS='|' read -r f local_size remote_size err; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Local:  $local_size bytes  |  Remote: $remote_size bytes"
        echo "    Error:  $err"
    done < "$SMALLER_BROKEN_FILE"
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f local_size remote_size err; do
                echo "Deleting: \$SCRATCH${f#$SCRATCH}"
                rm -f "$f"
            done < "$SMALLER_BROKEN_FILE"
            echo "Done. Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped deletion."
            ;;
    esac
fi

# 5. Remaining broken locals — offer deletion
if [ -s "$BROKEN_REMAINING_FILE" ]; then
    echo ""
    echo "[WARN] The following local files are broken (size matches remote or no remote counterpart):"
    echo ""
    while IFS='|' read -r f err; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Error: $err"
    done < "$BROKEN_REMAINING_FILE"
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f err; do
                echo "Deleting: \$SCRATCH${f#$SCRATCH}"
                rm -f "$f"
            done < "$BROKEN_REMAINING_FILE"
            echo "Done. Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped deletion."
            ;;
    esac
fi

exit $COMPARE_EXIT
