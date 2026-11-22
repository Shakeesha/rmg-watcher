# AGENTS.md — canonical process rules for rmg-watcher

This file is the permanent operating manual for this repository. Every agent and
contributor must follow it. It supersedes ad-hoc instructions given in chat;
changes to this file require explicit user approval.

## 1. Identity and naming

- Display name: **RMG-Watcher**. **RMG** stands for **Rhein-Main-Gebiet** (the
  Rhine-Main region). The package, CLI command, and deployment name are
  `rmg-watcher`.
- The Python package lives in `src/rmg_watcher`. There is **no** `transit_pipeline`
  module and **no** backwards-compatibility shims for that old name. Do not
  reintroduce it.
- CLI entry point: `rmg-watcher`; `python -m rmg_watcher` also works when the
  package is installed.

## 2. Hardware and runtime constraints

- Target device: **Raspberry Pi 5, 4 GB RAM**, NVMe SSD, Waveshare UPS HAT (E),
  5" 720×1280 portrait DSI capacitive touch display.
- The display draws power from the GPIO header and the UPS HAT uses pogo pins, so
  **there are no GPIO pins available for navigation buttons**. Navigation is
  touch-only (keyboard handling is for development/debugging only).
- Stock **Raspberry Pi OS Bookworm (64-bit)** compatibility is required:
  **Python 3.11+** (CI checks 3.11 and 3.12), distro `chromium` browser.
- **Node 22** is a build-time dependency only (Vite build, stop-catalog
  generation). **No Node.js runtime is installed or required on the device.**
- OSM tiles are fetched **only** through the cached local proxy
  (`/api/tiles/{z}/{x}/{y}.png`, 7-day on-disk cache). No mapping library may be
  added to the Pi footprint.

## 3. Transitous usage policy

Transitous is a live community service. Respect its
[usage policy](https://transitous.org/api/):

- Keep request volume low: cached stop catalog (at most once per 24 h), cached
  departures (10-minute minimum refresh), bucketed connection cache, and a
  configurable daily `/v6/plan` cap.
- Always send a contact (`TRANSIT_CONTACT`) in the `User-Agent`.
- Attribute Transitous and OpenStreetMap in the UI and README.
- **No ticket/account/profile features** may be added.

## 4. Absolute rule: never read `.env`

**NEVER read `.env` files.** Standing read permission has been explicitly
revoked. This applies to every agent, every tool call, and every script. If a
task appears to require reading `.env`, stop and ask the user instead.
`.env.example` is documentation and may be read only when strictly necessary.
CI may generate a `.env` from `.env.example` for Compose validation, but agents
must not read real `.env` content.

## 5. Commit process

- **One commit per task.** A task is a feature, a fix, or a chore. Group closely
  related changes into one coherent commit; do not make a commit for every tiny
  edit.
- Use conventional commit messages, e.g.
  `fix(ingestion): invalidate cached stop catalog on file change`, with
  `-` prefixed bullet lines in the body.
- Never push to a remote without explicit user instruction.

## 6. Semantic versioning (complete rule)

- **MAJOR (`X.0.0`)** — bump when a change breaks existing users or deployments
  and requires them to change something to keep working. Examples: removing a
  public CLI command or flag; removing/renaming env vars without backwards
  compatibility; incompatible changes to the `/api/*` JSON contract; dropping
  support for Python 3.11 or Raspberry Pi OS Bookworm; a schema/data-path change
  that makes an existing installation fail on upgrade; removing a feature users
  rely on. Create a **new** tag `vX.0.0` on the release commit.
- **MINOR (`0.Y.0`)** — backwards-compatible new features/capabilities (e.g.
  the street map, Pi packaging, CI gates). Create a **new** tag `v0.Y.0`.
- **PATCH (`0.Y.Z`)** — compatible fixes, refactors, chores, and docs/tooling
  changes. **Never create a patch tag.** Force-move the current major/minor tag
  to the latest commit of that series:
  `git tag -f -a v0.21.0 -m "..." HEAD`.
- Rule of thumb: if an existing user/deployment must change configuration, code,
  or hardware assumptions to keep working → MAJOR. If it only adds compatible
  capability → MINOR. Otherwise → PATCH.
- Tags exist only for major and minor releases and always point to the **last**
  commit of their release series.

### Files that must change on every version bump

All six must be updated together:

1. `src/rmg_watcher/__init__.py`
2. `frontend/package.json`
3. `frontend/package-lock.json` (regenerate with
   `npm install --package-lock-only --silent` in `frontend/`)
4. `deploy/docker-compose.rpi5.yml`
5. `README.md` (the `- **Version:**` line)
6. `CHANGELOG.md` (new `## [X.Y.Z] - YYYY-MM-DD` section under
   `## [Unreleased]`)

## 7. Verification gate (run ALL before every commit)

From the repository root:

```
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe
npm run check --prefix frontend
npm run build --prefix frontend
bash -n deploy/scripts/*.sh
.\.venv\Scripts\python.exe -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8')); print('ok')"
git diff --check
```

All commands must pass. If formatting is required, run
`.\.venv\Scripts\ruff.exe format .` first. After committing, force-move the
current minor/major tag and verify that `git status --short` is empty and that
`git rev-list -n 1 vX.Y.0` equals `git rev-parse HEAD`.

## 8. Agent role

This repository has a designated **bugfix and CI-maintenance agent** (tracked by
session ID). That agent must be kept in the loop for all future code changes and
process decisions and is reused for follow-up bugfixes. Changes to CI, release
engineering, or high-severity bugs should be routed to it.
