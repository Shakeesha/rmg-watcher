#!/usr/bin/env bash
# Install a packaged rmg-watcher release on Raspberry Pi OS Bookworm.
set -euo pipefail

APP_DIR="${1:-/opt/rmg-watcher}"
SERVICE_USER="${SERVICE_USER:-transit}"
ENABLE_KIOSK="${ENABLE_KIOSK:-false}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root (sudo)." >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${SOURCE_DIR}/pyproject.toml" ]]; then
  echo "No release found in ${SOURCE_DIR}." >&2
  exit 1
fi

echo "Installing rmg-watcher into ${APP_DIR}"

apt-get update
apt-get install -y ca-certificates chromium python3-venv

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi
usermod -aG video,render,audio "${SERVICE_USER}"

mkdir -p "${APP_DIR}"
tar -C "${SOURCE_DIR}" \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='frontend/dist/.vite' \
  -cf - . | tar -C "${APP_DIR}" -xf -

sudo -u "${SERVICE_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  sudo -u "${SERVICE_USER}" cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
fi

sudo -u "${SERVICE_USER}" mkdir -p \
  "${APP_DIR}/data/raw" \
  "${APP_DIR}/data/quarantine" \
  "${APP_DIR}/data/transitous"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

install -m 0644 "${APP_DIR}/deploy/systemd/"*.service \
  "${APP_DIR}/deploy/systemd/"*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rmg-watcher-api.service rmg-watcher-pipeline.timer

if [[ "${ENABLE_KIOSK}" == "true" ]]; then
  systemctl enable --now rmg-watcher-kiosk.service
fi

echo "rmg-watcher installed. Edit ${APP_DIR}/.env for live data."
