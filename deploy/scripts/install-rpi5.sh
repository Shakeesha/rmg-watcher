#!/usr/bin/env bash
# Install a packaged rmg-watcher release on Raspberry Pi OS Bookworm (64-bit).
set -euo pipefail

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
  shift
fi

APP_DIR="${1:-/opt/rmg-watcher}"
SERVICE_USER="${SERVICE_USER:-transit}"
ENABLE_KIOSK="${ENABLE_KIOSK:-false}"

if [[ "${CHECK_ONLY}" != "true" && "${EUID}" -ne 0 ]]; then
  echo "Run this script as root (sudo)." >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ ! -f "${SOURCE_DIR}/pyproject.toml" ]]; then
  echo "No release found in ${SOURCE_DIR}." >&2
  exit 1
fi

# --check validates the release layout without changing the system. CI and the
# test suite use it to catch path regressions before a release is published.
if [[ "${CHECK_ONLY}" == "true" ]]; then
  echo "Release layout OK: ${SOURCE_DIR}"
  exit 0
fi

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "Warning: this package is intended for 64-bit Raspberry Pi OS (aarch64)." >&2
fi

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${VERSION_CODENAME:-}" != "bookworm" ]]; then
    echo "Warning: expected Raspberry Pi OS Bookworm, found ${PRETTY_NAME:-unknown}." >&2
  fi
fi

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
case "${PYTHON_VERSION}" in
  3.11|3.12|3.13) ;;
  *)
    echo "Warning: Python ${PYTHON_VERSION} found; 3.11-3.13 are supported." >&2
    ;;
esac

echo "Installing rmg-watcher into ${APP_DIR}"

apt-get update
apt-get install -y \
  ca-certificates \
  chromium \
  curl \
  python3-pip \
  python3-venv

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi
usermod -aG video,render,audio "${SERVICE_USER}"

# Keep /run/user/<uid> available to the unprivileged services.
loginctl enable-linger "${SERVICE_USER}" 2>/dev/null || true

# When the archive is extracted straight into APP_DIR, SOURCE_DIR and APP_DIR
# are the same tree. Copying it onto itself through a tar pipe can truncate
# files that are still being read, so only copy when the paths really differ.
if [[ "${SOURCE_DIR}" != "${APP_DIR}" ]]; then
  mkdir -p "${APP_DIR}"
  tar -C "${SOURCE_DIR}" \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='frontend/dist/.vite' \
    -cf - . | tar -C "${APP_DIR}" -xf -
fi

# The archive may have been extracted as root, so hand the tree to the service
# user before any step that writes there (venv creation, pip, .env, data dirs).
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

if [[ ! -f "${APP_DIR}/.venv/bin/python" ]]; then
  sudo -u "${SERVICE_USER}" python3 -m venv "${APP_DIR}/.venv"
fi
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  sudo -u "${SERVICE_USER}" cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
fi

sudo -u "${SERVICE_USER}" mkdir -p \
  "${APP_DIR}/data/raw" \
  "${APP_DIR}/data/quarantine" \
  "${APP_DIR}/data/transitous/tiles"

install -m 0644 "${APP_DIR}/deploy/systemd/"*.service \
  "${APP_DIR}/deploy/systemd/"*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rmg-watcher-api.service rmg-watcher-pipeline.timer

if [[ "${ENABLE_KIOSK}" == "true" ]]; then
  systemctl enable --now rmg-watcher-kiosk.service
fi

echo "rmg-watcher installed. Edit ${APP_DIR}/.env for live data."
