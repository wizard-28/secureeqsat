#!/usr/bin/env bash
# Set up the independent security oracles OUTSIDE this repository.
#
# Why outside: VerifMSI is GPLv3. Our rule (AGENTS.md §6.4, design/0005) is that
# GPL oracles are invoked as external processes only — never linked, vendored,
# or copied into this tree. This script therefore clones into $ORACLE_DIR
# (default: ~/oracles) and creates a dedicated venv there.
#
# Usage:  bash experiments/oracle_crosscheck/setup_oracles.sh [oracle_dir]
set -euo pipefail

ORACLE_DIR="${1:-${SECUREEQSAT_ORACLE_DIR:-$HOME/oracles}}"
mkdir -p "$ORACLE_DIR"
cd "$ORACLE_DIR"

if [ ! -d verif_msi ]; then
  git clone -q --depth 1 https://github.com/quentin-meunier/VerifMSI.git verif_msi
fi

# VerifMSI is pure stdlib, so the venv needs no packages.
if [ ! -x venv/bin/python ]; then
  uv venv venv --python 3.14
fi

echo "oracle dir:  $ORACLE_DIR"
echo "oracle py:   $ORACLE_DIR/venv/bin/python"
echo -n "import check: "
PYTHONPATH="$ORACLE_DIR" "$ORACLE_DIR/venv/bin/python" -c \
  "from verif_msi import *; print('verif_msi import OK')"
