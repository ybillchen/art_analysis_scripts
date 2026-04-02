#!/bin/bash

# Check tar files on local and remote for conflicts before sync.
#
# This script compares tar files between local and remote, detecting any
# conflicts (files that exist on both sides with different checksums).
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

# Run comparison check
python3 "$COMPARE_SCRIPT" $VERBOSE \
    --local-path "$SCRATCH" \
    --remote-host "$ARCHIVER" \
    --remote-path "/scoutfs/projects/TG-AST200017/stampede3/"
