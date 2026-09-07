#!/usr/bin/env bash
# Idempotent Cloud Agent setup for the Saboteur 92 Godot project.
# Safe to re-run: every step is guarded so it is a fast no-op once satisfied
# (e.g. when booting from a prebuilt snapshot that already contains the tools).
set -euo pipefail

GODOT_VERSION="4.6-stable"
GODOT_DOTTED="4.6.stable"
GODOT_BIN="/usr/local/bin/godot"
TEMPLATES_DIR="${HOME}/.local/share/godot/export_templates/${GODOT_DOTTED}"
BASE_URL="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}"

log() { printf '\n=== %s ===\n' "$1"; }

log "System packages (Xvfb + software Vulkan + capture tooling)"
NEEDED_PKGS=(xvfb x11-utils x11-apps mesa-vulkan-drivers libvulkan1 vulkan-tools ffmpeg imagemagick xdotool unzip curl)
MISSING=()
for pkg in "${NEEDED_PKGS[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${MISSING[@]}"
else
  echo "All required system packages already installed."
fi

log "Godot ${GODOT_VERSION} editor/runtime binary"
if ! command -v godot >/dev/null 2>&1; then
  tmp="$(mktemp -d)"
  curl -sSL -o "${tmp}/godot.zip" "${BASE_URL}/Godot_v${GODOT_VERSION}_linux.x86_64.zip"
  unzip -o "${tmp}/godot.zip" -d "${tmp}" >/dev/null
  sudo mv "${tmp}/Godot_v${GODOT_VERSION}_linux.x86_64" "${GODOT_BIN}"
  sudo chmod +x "${GODOT_BIN}"
  rm -rf "${tmp}"
fi
godot --version

log "Godot export templates"
if [ ! -f "${TEMPLATES_DIR}/version.txt" ]; then
  tmp="$(mktemp -d)"
  curl -sSL -o "${tmp}/templates.tpz" "${BASE_URL}/Godot_v${GODOT_VERSION}_export_templates.tpz"
  unzip -o "${tmp}/templates.tpz" -d "${tmp}" >/dev/null
  mkdir -p "${TEMPLATES_DIR}"
  mv "${tmp}"/templates/* "${TEMPLATES_DIR}/"
  rm -rf "${tmp}"
fi
echo "Templates: $(ls "${TEMPLATES_DIR}" | wc -l) files"

log "Python dependencies for pixel-art asset tools"
python3 -c "import PIL, numpy" >/dev/null 2>&1 || \
  pip3 install --break-system-packages --quiet Pillow numpy

log "Import project resources (headless)"
godot --headless --import --path . >/dev/null 2>&1 || \
  godot --headless --import --path .

log "Install complete"
