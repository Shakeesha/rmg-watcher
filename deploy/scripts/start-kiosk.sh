#!/usr/bin/env bash
# Fullscreen kiosk launcher with API/display readiness checks and crash recovery.
set -euo pipefail

URL="${KIOSK_URL:-http://127.0.0.1:8000/}"
API_URL="${KIOSK_API_URL:-http://127.0.0.1:8000/api/health}"
RESTART_DELAY="${KIOSK_RESTART_DELAY:-3}"
READY_ATTEMPTS="${KIOSK_READY_ATTEMPTS:-60}"
DISPLAY_MODE="${KIOSK_DISPLAY_SERVER:-auto}"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:0}"

RUNNING=1
BROWSER_PID=""

log() {
  printf '[kiosk] %s\n' "$*"
}

cleanup() {
  RUNNING=0
  if [[ -n "$BROWSER_PID" ]]; then
    kill "$BROWSER_PID" 2>/dev/null || true
    wait "$BROWSER_PID" 2>/dev/null || true
    BROWSER_PID=""
  fi
}

trap cleanup EXIT INT TERM

find_browser() {
  local candidate

  if [[ -n "${KIOSK_BROWSER:-}" ]]; then
    command -v "$KIOSK_BROWSER" 2>/dev/null || true
    return 0
  fi

  for candidate in chromium chromium-browser google-chrome; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done

  return 0
}

api_ready() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 2 "$API_URL" >/dev/null 2>&1
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 2 -O /dev/null "$API_URL" >/dev/null 2>&1
  else
    return 0
  fi
}

wait_for_api() {
  local attempt

  for attempt in $(seq 1 "$READY_ATTEMPTS"); do
    if api_ready; then
      return 0
    fi
    sleep 1
  done

  log "API did not become ready; starting the browser anyway"
}

wait_for_display() {
  local attempt
  local socket="${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}"

  if [[ "$DISPLAY_MODE" == "wayland" ]]; then
    for attempt in $(seq 1 "$READY_ATTEMPTS"); do
      if [[ -S "$socket" ]]; then
        return 0
      fi
      sleep 1
    done
    log "Wayland socket $socket not found; continuing"
    return 0
  fi

  if [[ "$DISPLAY_MODE" == "x11" ]]; then
    for attempt in $(seq 1 "$READY_ATTEMPTS"); do
      if command -v xdpyinfo >/dev/null 2>&1 && xdpyinfo >/dev/null 2>&1; then
        return 0
      fi
      sleep 1
    done
    log "X display $DISPLAY not ready; continuing"
    return 0
  fi

  for attempt in $(seq 1 "$READY_ATTEMPTS"); do
    if [[ -S "$socket" ]]; then
      DISPLAY_MODE="wayland"
      return 0
    fi
    if command -v xdpyinfo >/dev/null 2>&1 && xdpyinfo >/dev/null 2>&1; then
      DISPLAY_MODE="x11"
      return 0
    fi
    sleep 1
  done

  log "No graphical session detected; continuing with X11"
  DISPLAY_MODE="x11"
}

BROWSER="$(find_browser)"
if [[ -z "$BROWSER" ]]; then
  log "No Chromium browser found; install chromium or set KIOSK_BROWSER"
  exit 1
fi

BROWSER_ARGS=(
  --kiosk
  --app="$URL"
  --incognito
  --noerrdialogs
  --no-first-run
  --no-default-browser-check
  --disable-infobars
  --disable-session-crashed-bubble
  --disable-component-update
  --disable-dev-shm-usage
  --disable-features=Translate,MediaRouter
  --hide-scrollbars
  --password-store=basic
  --check-for-update-interval=31536000
  --overscroll-history-navigation=0
  --autoplay-policy=no-user-gesture-required
)

while [[ "$RUNNING" -eq 1 ]]; do
  wait_for_display
  wait_for_api

  launch_args=("${BROWSER_ARGS[@]}")
  if [[ "$DISPLAY_MODE" == "wayland" ]]; then
    launch_args+=(--ozone-platform=wayland)
  fi

  log "starting $BROWSER at $URL ($DISPLAY_MODE)"
  "$BROWSER" "${launch_args[@]}" &
  BROWSER_PID=$!

  wait "$BROWSER_PID" || true
  BROWSER_PID=""

  if [[ "$RUNNING" -eq 1 ]]; then
    log "browser exited; restarting in ${RESTART_DELAY}s"
    sleep "$RESTART_DELAY"
  fi
done
