#!/usr/bin/env bash
# OPTIONAL, PER-USER: install opencode inside the dev container.
#
# Deliberately NOT wired into the shared .devcontainer/devcontainer.json --
# teammates using other coding agents should not have it installed for them.
#
# Requires the personal container configuration, which mounts the persistent
# opencode-config / -data / -cache volumes:
#
#   cp .devcontainer/personal/devcontainer.example.json \
#      .devcontainer/personal/devcontainer.json
#
# See README "Dev container" and `design/0012`.
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

STATE_DIRS=(
  "$HOME/.config/opencode"
  "$HOME/.local/share/opencode"
  "$HOME/.cache/opencode"
)

if mountpoint -q "${STATE_DIRS[0]}"; then
  # Named volumes mount root-owned; give them back to the remote user.
  sudo chown -R "$(id -u):$(id -g)" "${STATE_DIRS[@]}"
else
  echo "warning: opencode state directories are not mounted volumes." >&2
  echo "         opencode will be installed, but its config, data and cache" >&2
  echo "         will NOT survive a rebuild." >&2
  echo "         Use .devcontainer/personal/devcontainer.json to persist them." >&2
fi

curl -fsSL https://opencode.ai/v2/install | bash

echo "setup-opencode: ok"
