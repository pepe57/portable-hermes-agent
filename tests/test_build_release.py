import subprocess
import sys
from pathlib import Path

import build_release


def test_release_zip_includes_user_launchers_and_docs():
    assert build_release.should_exclude("START.bat") is False
    assert build_release.should_exclude("UPDATE.bat") is False
    assert build_release.should_exclude("START_HERE.txt") is False
    assert build_release.should_exclude("README.md") is False


def test_release_tag_produces_the_expected_asset_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_release.py", "--version", "v9.8.7", "--output-dir", str(tmp_path)],
    )
    monkeypatch.setattr(build_release, "iter_release_files", lambda: iter(()))

    build_release.main()

    assert (tmp_path / "portable-hermes-agent-v9.8.7.zip").is_file()


def test_readme_download_links_target_the_portable_release_page():
    content = (Path(build_release.PROJECT_ROOT) / "README.md").read_text(
        encoding="utf-8"
    )

    assert "https://github.com/aivrar/portable-hermes-agent/releases/latest" in content
    assert "NousResearch/hermes-agent/releases" not in content


def test_release_zip_excludes_development_only_dirs():
    assert build_release.should_exclude(".github/workflows/tests.yml") is True
    assert build_release.should_exclude("tests/test_toolsets.py") is True
    assert build_release.should_exclude(".pytest_cache/v/cache/nodeids") is True
    assert build_release.should_exclude("test.pdf") is True


def test_release_zip_excludes_generated_docs_but_keeps_runtime_assets():
    flagged_doc = (
        "website/docs/user-guide/skills/optional/autonomous-ai-agents/"
        "autonomous-ai-agents-blackbox.md"
    )
    assert build_release.should_exclude(flagged_doc) is True
    assert build_release.should_exclude(flagged_doc.replace("/", "\\")) is True

    localized_doc = (
        "website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/"
        "user-guide/skills/optional/autonomous-ai-agents/"
        "autonomous-ai-agents-blackbox.md"
    )
    assert build_release.should_exclude(localized_doc) is True
    assert build_release.should_exclude(localized_doc.replace("/", "\\")) is True
    assert (
        build_release.should_exclude(
            "website/i18n/es/docusaurus-plugin-content-docs-version-v2/intro.md"
        )
        is True
    )
    assert (
        build_release.should_exclude(
            "website/i18n/zh-Hans/docusaurus-theme-classic/navbar.json"
        )
        is False
    )
    assert (
        build_release.should_exclude("website/static/api/model-catalog.json") is False
    )
    assert (
        build_release.should_exclude(
            "optional-skills/autonomous-ai-agents/blackbox/SKILL.md"
        )
        is False
    )


def test_release_zip_excludes_portable_runtime_dirs():
    assert build_release.should_exclude(".hermes/config.yaml") is True
    assert build_release.should_exclude("python_embedded/python.exe") is True
    assert build_release.should_exclude("extensions/comfyui/README.md") is True
    assert build_release.should_exclude("extensions\\music-server\\README.md") is True


def test_release_files_prefer_git_tracked_list(monkeypatch):
    def fake_run(cmd, **kwargs):
        assert cmd == ["git", "ls-files", "-z"]
        return subprocess.CompletedProcess(cmd, 0, stdout=b"README.md\0START.bat\0")

    def fail_worktree_walk():
        raise AssertionError("ignored worktree files should not be walked")

    monkeypatch.setattr(build_release.subprocess, "run", fake_run)
    monkeypatch.setattr(build_release, "iter_worktree_files", fail_worktree_walk)

    assert list(build_release.iter_release_files()) == ["README.md", "START.bat"]


def test_release_files_fall_back_without_git(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(128, cmd)

    monkeypatch.setattr(build_release.subprocess, "run", fake_run)
    monkeypatch.setattr(
        build_release,
        "iter_worktree_files",
        lambda: iter(["README.md", "START.bat"]),
    )

    assert list(build_release.iter_release_files()) == ["README.md", "START.bat"]
