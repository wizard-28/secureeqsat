#!/usr/bin/env bash
# Team-wide dev container provisioning.
#
# Invoked by postCreateCommand in .devcontainer/devcontainer.json; safe to
# re-run by hand. Agent-neutral by design -- see README "Dev container" and
# `design/0012`.
#
# AGENTS.md section 3 forbids ad-hoc `curl | sh` against a running sandbox.
# This script is the sanctioned carve-out: it runs only during container
# provisioning, and the rule it implements is "edit the devcontainer and
# rebuild", not "mutate the sandbox".
set -euo pipefail

# Run from the repo root regardless of the caller's cwd.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# uv installs into ~/.local/bin. Its installer appends that to ~/.bashrc, but
# postCreateCommand runs this script in a single non-login shell, so the export
# is what makes `uv` resolvable for the rest of this script.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv tool install --python 3.14 pyright
uv tool install --python 3.14 ruff
uv sync

echo "setup-tools: ok (uv $(uv --version | cut -d' ' -f2))"
