#!/usr/bin/env bash
# Team-wide dev container provisioning.
#
# Invoked by postCreateCommand in .devcontainer/devcontainer.json; safe to
# re-run by hand. Agent-neutral by design -- see README "Dev container" and
# `design/0012`.
#
# AGENTS.md section 3 forbids ad-hoc `curl | sh` against a running sandbox.
# This script is the sanctioned carve-out: it runs only during container
# provisioning, and the rule it implements is "edit the devcontainer and rebuild".
# -e: stop at the first failing command; -u: an unset variable is an error;
# -o pipefail: a pipeline fails if ANY command in it fails (not just the last).
set -euo pipefail

# Run from the repo root regardless of the caller's cwd.
# ${BASH_SOURCE[0]} is this script's own path; dirname gives its folder; `..` goes up
# one level to the repo root; `pwd` prints the absolute path.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# uv installs into ~/.local/bin.
# postCreateCommand runs in a non-login shell, so explicitly add it to PATH.
export PATH="$HOME/.local/bin:$PATH"

# --- 1. Directories uv needs -------------------------------------------------
# Docker creates missing mount-point PARENTS as root. With volumes mounted
# under $HOME, that left ~/.local/share root-owned and `uv sync` failed on the
# first real rebuild. Create if absent, then take ownership.
RUNTIME_DIRS=(
  "$HOME/.config"       # uv writes ~/.config/uv
  "$HOME/.local"
  "$HOME/.local/bin"
  "$HOME/.local/share"
  "$HOME/.cache"
)
# For each directory: create it if missing (`[ -d d ] || mkdir`), then, if its owner
# (`stat -c %u` = numeric user id) is not the current user (`id -u`), hand it over
# with `chown uid:gid`.
for d in "${RUNTIME_DIRS[@]}"; do
  [ -d "$d" ] || sudo mkdir -p "$d"
  [ "$(stat -c %u "$d")" = "$(id -u)" ] || sudo chown "$(id -u):$(id -g)" "$d"
done

# --- 2. Named-volume mount points --------------------------------------------
# Mounted root-owned by Docker. Only ownership is fixed, and absent entries are
# SKIPPED -- so the shared configuration never grows agent-specific directories
# it did not ask for.
#
# KEEP IN SYNC with `mounts` in .devcontainer/devcontainer.json and
# .devcontainer/personal/devcontainer.example.json.
VOLUME_MOUNTS=(
  "$HOME/oracles"                 # shared: VerifMSI oracle (design/0012)
  "$HOME/.config/opencode"        # personal: opencode
  "$HOME/.local/share/opencode"   # personal: opencode
  "$HOME/.cache/opencode"         # personal: opencode
)
# `[ -e d ] || continue` skips a path that does not exist (no agent-specific folders
# are created by this script).
for d in "${VOLUME_MOUNTS[@]}"; do
  [ -e "$d" ] || continue
  [ "$(stat -c %u "$d")" = "$(id -u)" ] || sudo chown "$(id -u):$(id -g)" "$d"
done

# --- 3. Toolchain ------------------------------------------------------------
# `command -v uv` succeeds if `uv` is on the PATH; the output is discarded
# (`>/dev/null 2>&1`). The installer runs only when uv is missing.
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv tool install --python 3.14 pyright
uv tool install --python 3.14 ruff
uv sync

# --- 4. VerifMSI oracle ------------------------------------------------------
# REQUIRED by the trust boundary (AGENTS.md 6.3): without it the three
# cross-check tests SKIP, and a skip is not a pass. It is GPLv3, so it must stay
# outside this repository -- it lives in the ~/oracles volume (design/0005).
#
# Non-fatal on purpose: a network failure here must not leave a broken
# container. The setup script is idempotent, so a manual re-run is enough.
if ! bash experiments/oracle_crosscheck/setup_oracles.sh; then
  echo "warning: VerifMSI oracle setup FAILED." >&2
  echo "         Cross-check tests will SKIP, not pass." >&2
  echo "         Retry: bash experiments/oracle_crosscheck/setup_oracles.sh" >&2
fi

# `uv --version` prints "uv 0.x.y"; `cut -d' ' -f2` keeps the second space-separated
# field, the version number.
echo "setup-tools: ok (uv $(uv --version | cut -d' ' -f2))"
