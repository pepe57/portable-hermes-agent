"""End-to-end: built portable artifacts must ship working i18n catalogs."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import tarfile
import venv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_installed_wheel_renders_i18n_strings(tmp_path):
    wheel_dir = tmp_path / "wheel"
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir), "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert build.returncode == 0, f"uv build failed:\n{build.stderr}"
    wheels = glob.glob(str(wheel_dir / "*.whl"))
    assert wheels, "no wheel produced"
    wheel = wheels[0]

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    vpy = venv_dir / scripts_dir / ("python.exe" if sys.platform == "win32" else "python")
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "-q", "pyyaml"],
        check=True,
        timeout=300,
    )
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", wheel],
        check=True,
        timeout=300,
    )

    probe = (
        "from agent import i18n;"
        "import sys;"
        "r = i18n.t('gateway.reset.header_default', lang='en');"
        "s = i18n.t('gateway.status.header', lang='en');"
        "print(repr(r)); print(repr(s));"
        "sys.exit(0 if (r != 'gateway.reset.header_default' "
        "and s != 'gateway.status.header') else 1)"
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "HERMES_BUNDLED_LOCALES")
    }
    env["PATH"] = f"{venv_dir / scripts_dir}{os.pathsep}{env['PATH']}"
    env["VIRTUAL_ENV"] = str(venv_dir)
    run = subprocess.run(
        [str(vpy), "-c", probe],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert run.returncode == 0, (
        "installed wheel returned raw i18n keys instead of human strings:\n"
        f"stdout: {run.stdout}\nstderr: {run.stderr}"
    )


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_built_sdist_ships_locale_catalogs(tmp_path):
    sdist_dir = tmp_path / "sdist"
    build = subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(sdist_dir), "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert build.returncode == 0, f"uv build --sdist failed:\n{build.stderr}"
    tarballs = glob.glob(str(sdist_dir / "*.tar.gz"))
    assert tarballs, "no sdist produced"

    with tarfile.open(tarballs[0]) as archive:
        catalogs = [
            member
            for member in archive.getnames()
            if "/locales/" in member and member.endswith(".yaml")
        ]

    from agent.i18n import SUPPORTED_LANGUAGES

    expected = len(SUPPORTED_LANGUAGES)
    assert len(catalogs) == expected, (
        f"sdist shipped {len(catalogs)} locale catalogs, expected {expected}"
    )
    assert any(member.endswith("/locales/en.yaml") for member in catalogs)
