#!/usr/bin/env bash
# Per-boot startup for the Saboteur 92 environment.
# Provides a headless X server (:99) with software Vulkan so the Godot game can
# render and be screen-captured for GUI testing. Idempotent: it will not start a
# second Xvfb if one is already listening on :99.
set -euo pipefail

DISPLAY_NUM=":99"

if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
  echo "Xvfb already running on ${DISPLAY_NUM}."
else
  echo "Starting Xvfb on ${DISPLAY_NUM} (1280x720x24)..."
  Xvfb "${DISPLAY_NUM}" -screen 0 1280x720x24 -ac +extension GLX +render -noreset \
    > /tmp/xvfb.log 2>&1 &
  # Wait briefly for the server to accept connections.
  for _ in $(seq 1 20); do
    xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi

if xdpyinfo -display "${DISPLAY_NUM}" >/dev/null 2>&1; then
  echo "Xvfb ready on ${DISPLAY_NUM}."
else
  echo "WARNING: Xvfb failed to become ready on ${DISPLAY_NUM}; GUI capture may be unavailable." >&2
fi
