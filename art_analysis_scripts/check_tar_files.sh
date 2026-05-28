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
SMALLER_BROKEN_FILE=$(mktemp)       # local < remote, only local broken
SMALLER_OK_FILE=$(mktemp)           # local < remote, only remote broken (local intact)
LARGER_REMOTE_BROKEN_FILE=$(mktemp) # local > remote, only remote broken
LARGER_REMOTE_OK_FILE=$(mktemp)     # local > remote, only local broken (remote intact)
BOTH_INTACT_FILE=$(mktemp)          # size mismatch, both intact
BOTH_BROKEN_FILE=$(mktemp)          # size mismatch, both broken
BROKEN_SIZE_MATCH_FILE=$(mktemp)    # broken local, size matches remote
BROKEN_NO_REMOTE_FILE=$(mktemp)     # broken local, no remote counterpart
MISSING_ON_REMOTE_FILE=$(mktemp)    # only on local, no remote counterpart
trap 'rm -f "$SMALLER_BROKEN_FILE" "$SMALLER_OK_FILE" "$LARGER_REMOTE_BROKEN_FILE" "$LARGER_REMOTE_OK_FILE" "$BOTH_INTACT_FILE" "$BOTH_BROKEN_FILE" "$BROKEN_SIZE_MATCH_FILE" "$BROKEN_NO_REMOTE_FILE" "$MISSING_ON_REMOTE_FILE"' EXIT

# Run comparison pipeline
python3 "$COMPARE_SCRIPT" $VERBOSE \
    --local-path "$SCRATCH" \
    --remote-host "$ARCHIVER" \
    --remote-path "/scoutfs/projects/TG-AST200017/stampede3/" \
    --smaller-broken-file "$SMALLER_BROKEN_FILE" \
    --smaller-ok-file "$SMALLER_OK_FILE" \
    --larger-remote-broken-file "$LARGER_REMOTE_BROKEN_FILE" \
    --larger-remote-ok-file "$LARGER_REMOTE_OK_FILE" \
    --both-intact-file "$BOTH_INTACT_FILE" \
    --both-broken-file "$BOTH_BROKEN_FILE" \
    --broken-size-match-file "$BROKEN_SIZE_MATCH_FILE" \
    --broken-no-remote-file "$BROKEN_NO_REMOTE_FILE" \
    --missing-on-remote-file "$MISSING_ON_REMOTE_FILE"

COMPARE_EXIT=$?

# 1. size mismatch, both intact — SYNC BLOCKED
if [ -s "$BOTH_INTACT_FILE" ]; then
    echo ""
    echo "[UNEXPECTED] size mismatch but both intact — SYNC BLOCKED:"
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)"
    done < <(sort "$BOTH_INTACT_FILE")
fi

# 2. local > remote, only local broken (remote intact) — SYNC BLOCKED
if [ -s "$LARGER_REMOTE_OK_FILE" ]; then
    echo ""
    echo "[ERROR] local > remote, only remote intact (local broken) — SYNC BLOCKED:"
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)"
    done < <(sort "$LARGER_REMOTE_OK_FILE")
fi

# 3. local > remote, only remote broken — re-sync will fix
if [ -s "$LARGER_REMOTE_BROKEN_FILE" ]; then
    echo ""
    echo "[INFO] local > remote, only remote broken (re-sync will fix):"
    while IFS='|' read -r f local_size remote_size; do
        echo "  $f  (local: $local_size B, remote: $remote_size B)"
    done < <(sort "$LARGER_REMOTE_BROKEN_FILE")
fi

# 4. size mismatch, both broken — offer deletion of local
if [ -s "$BOTH_BROKEN_FILE" ]; then
    echo ""
    echo "[ERROR] size mismatch, both broken — SYNC BLOCKED:"
    while IFS='|' read -r f local_size remote_size err; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)  [local: $err]"
    done < <(sort "$BOTH_BROKEN_FILE")
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f local_size remote_size err; do
                rm -f "$f" && echo "Deleted: \$SCRATCH${f#$SCRATCH}"
            done < "$BOTH_BROKEN_FILE"
            echo "Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped."
            ;;
    esac
fi

# 5. local < remote, only remote broken (local intact) — re-sync will fix
if [ -s "$SMALLER_OK_FILE" ]; then
    echo ""
    echo "[INFO] local < remote, only remote broken (re-sync will fix):"
    while IFS='|' read -r f local_size remote_size; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)"
    done < <(sort "$SMALLER_OK_FILE")
fi

# 6. EXPECTED: local < remote, only local broken — offer deletion
if [ -s "$SMALLER_BROKEN_FILE" ]; then
    echo ""
    echo "[WARN] local < remote and local is broken:"
    while IFS='|' read -r f local_size remote_size err; do
        echo "  \$SCRATCH${f#$SCRATCH}  (local: $local_size B, remote: $remote_size B)  [$err]"
    done < <(sort "$SMALLER_BROKEN_FILE")
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

# 7. Broken local, size matches remote — offer deletion
if [ -s "$BROKEN_SIZE_MATCH_FILE" ]; then
    echo ""
    echo "[WARN] broken local files, size matches remote:"
    while IFS='|' read -r f err; do
        echo "  \$SCRATCH${f#$SCRATCH}  [$err]"
    done < <(sort "$BROKEN_SIZE_MATCH_FILE")
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f err; do
                rm -f "$f" && echo "Deleted: \$SCRATCH${f#$SCRATCH}"
            done < "$BROKEN_SIZE_MATCH_FILE"
            echo "Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped."
            ;;
    esac
fi

# 8. Broken local, no remote counterpart — offer deletion
if [ -s "$BROKEN_NO_REMOTE_FILE" ]; then
    echo ""
    echo "[WARN] broken local files, no remote counterpart:"
    while IFS='|' read -r f err; do
        echo "  \$SCRATCH${f#$SCRATCH}  [$err]"
    done < <(sort "$BROKEN_NO_REMOTE_FILE")
    echo ""
    read -r -p "Delete these broken local files? [y/N] " REPLY
    case "$REPLY" in
        [yY][eE][sS]|[yY])
            while IFS='|' read -r f err; do
                rm -f "$f" && echo "Deleted: \$SCRATCH${f#$SCRATCH}"
            done < "$BROKEN_NO_REMOTE_FILE"
            echo "Run: python pack_files.py --repair  to regenerate."
            ;;
        *)
            echo "Skipped."
            ;;
    esac
fi

# 9. Only on local — informational
if [ -s "$MISSING_ON_REMOTE_FILE" ]; then
    echo ""
    echo "[INFO] only on local (will be uploaded on next sync):"
    while IFS='|' read -r f local_size; do
        echo "  \$SCRATCH${f#$SCRATCH}  ($local_size B)"
    done < <(sort "$MISSING_ON_REMOTE_FILE")
fi

exit $COMPARE_EXIT
