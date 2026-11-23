"""Tests for the Raspberry Pi installer's release-layout validation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from rmg_watcher.config import PROJECT_ROOT

INSTALLER = PROJECT_ROOT / "deploy" / "scripts" / "install-rpi5.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")


def _check(script: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Pass a path relative to cwd: it works for Git Bash and WSL alike.
    relative = Path(os.path.relpath(script, cwd)).as_posix()
    return subprocess.run(
        ["bash", relative, "--check"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installer_check_mode_finds_release_root() -> None:
    result = _check(INSTALLER, PROJECT_ROOT)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Release layout OK")


def test_installer_check_mode_is_independent_of_cwd(tmp_path: Path) -> None:
    result = _check(INSTALLER, tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Release layout OK")


def test_installer_check_mode_rejects_missing_release(tmp_path: Path) -> None:
    script_dir = tmp_path / "deploy" / "scripts"
    script_dir.mkdir(parents=True)
    script = script_dir / INSTALLER.name
    shutil.copy2(INSTALLER, script)

    result = _check(script, tmp_path)

    assert result.returncode == 1
    assert "No release found" in result.stderr
