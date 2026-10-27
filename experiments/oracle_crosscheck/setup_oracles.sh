#!/usr/bin/env bash
# Set up the independent security oracles OUTSIDE this repository.
#
# Why outside: VerifMSI is GPLv3. Our rule (AGENTS.md §6.4, design/0005) is that
# GPL oracles are invoked as external processes only — never linked, vendored,
# or copied into this tree. This script therefore clones into $ORACLE_DIR
# (default: ~/oracles) and creates a dedicated venv there.
#
# Usage:  bash experiments/oracle_crosscheck/setup_oracles.sh [oracle_dir]
# -e: stop at the first failing command; -u: unset variables are errors; -o pipefail:
# a failure anywhere in a pipeline fails the whole pipeline.
set -euo pipefail

# `${1:-X}` means "the first argument, or X if it is missing". So the directory is the
# first argument, else $SECUREEQSAT_ORACLE_DIR, else ~/oracles.
ORACLE_DIR="${1:-${SECUREEQSAT_ORACLE_DIR:-$HOME/oracles}}"
mkdir -p "$ORACLE_DIR"
cd "$ORACLE_DIR"

# Clone only if the folder is not there yet (--depth 1: latest commit only; -q: quiet),
# so re-running the script is safe.
if [ ! -d verif_msi ]; then
  git clone -q --depth 1 https://github.com/quentin-meunier/VerifMSI.git verif_msi
fi

# VerifMSI is pure stdlib, so the venv needs no packages.
# `-x` tests that the file exists and is executable: create the venv only if missing.
if [ ! -x venv/bin/python ]; then
  uv venv venv --python 3.14
fi

echo "oracle dir:  $ORACLE_DIR"
echo "oracle py:   $ORACLE_DIR/venv/bin/python"
# `echo -n` prints without a newline, so the import result appears on the same line.
echo -n "import check: "
PYTHONPATH="$ORACLE_DIR" "$ORACLE_DIR/venv/bin/python" -c \
  "from verif_msi import *; print('verif_msi import OK')"
