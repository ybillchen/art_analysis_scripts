#!/bin/bash

# Check tar files on local and remote for conflicts before sync.
#
# This script compares tar files between local and remote, detecting any
# conflicts (files that exist on both sides with different checksums).
#
# Usage:
#   ./check_tar_files.sh [--verbose] [--check-integrity]
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
CHECK_INTEGRITY=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --check-integrity)
            CHECK_INTEGRITY="--check-integrity"
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

# Temp files for all mismatch and integrity categories
SMALLER_FILE=$(mktemp)        # local < remote (size)
LARGER_FILE=$(mktemp)         # local > remote (size)
BROKEN_LOCAL_FILE=$(mktemp)   # local tar failed tar -tf
BROKEN_REMOTE_FILE=$(mktemp)  # remote tar failed tar -tf
trap 'rm -f "$SMALLER_FILE" "$LARGER_FILE" "$BROKEN_LOCAL_FILE" "$BROKEN_REMOTE_FILE"' EXIT

# Run comparison check
python3 "$COMPARE_SCRIPT" $VERBOSE $CHECK_INTEGRITY \
    --local-path "$SCRATCH" \
    --remote-host "$ARCHIVER" \
    --remote-path "/scoutfs/projects/TG-AST200017/stampede3/" \
    --suspect-file "$SMALLER_FILE" \
    --local-larger-file "$LARGER_FILE" \
    --broken-local-file "$BROKEN_LOCAL_FILE" \
    --broken-remote-file "$BROKEN_REMOTE_FILE"

COMPARE_EXIT=$?

# Category 1: local < remote — local may be damaged, offer deletion
if [ -s "$SMALLER_FILE" ]; then
    echo ""
    echo "[WARN] The following local tar files are smaller than their remote counterparts."
    echo "       This likely means the local copy is incomplete or corrupt:"
    echo ""
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Local:  $local_size bytes  |  Remote: $remote_size bytes"
    done < "$SMALLER_FILE"
    echo ""
    read -r -p "Delete these local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f local_size remote_size; do
                echo "Deleting: \$SCRATCH${f#$SCRATCH}"
                rm -f "$f"
            done < "$SMALLER_FILE"
            echo "Done."
            ;;
        *)
            echo "Skipped deletion."
            ;;
    esac
fi

# Category 2: local > remote — remote may be wrong, list for manual inspection
if [ -s "$LARGER_FILE" ]; then
    echo ""
    echo "[INFO] The following local tar files are larger than their remote counterparts."
    echo "       Check these files on the remote server:"
    echo ""
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Local:  $local_size bytes  |  Remote: $remote_size bytes"
    done < "$LARGER_FILE"
fi

# Broken local tars — offer deletion (run pack_files.py --repair to regenerate)
if [ -s "$BROKEN_LOCAL_FILE" ]; then
    echo ""
    echo "[ERROR] The following local tar files failed integrity check (tar -tf):"
    echo ""
    while IFS='|' read -r f err; do
        echo "  \$SCRATCH${f#$SCRATCH}"
        echo "    Error: $err"
    done < "$BROKEN_LOCAL_FILE"
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f err; do
                echo "Deleting: \$SCRATCH${f#$SCRATCH}"
                rm -f "$f"
            done < "$BROKEN_LOCAL_FILE"
            echo "Done. Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped deletion."
            ;;
    esac
fi

# Broken remote tars — list for manual inspection (re-sync will overwrite them)
if [ -s "$BROKEN_REMOTE_FILE" ]; then
    echo ""
    echo "[WARN] The following remote tar files failed integrity check (tar -tf):"
    echo "       Re-syncing from local will overwrite these."
    echo ""
    while IFS= read -r f; do
        echo "  $f"
    done < "$BROKEN_REMOTE_FILE"
fi

exit $COMPARE_EXIT
