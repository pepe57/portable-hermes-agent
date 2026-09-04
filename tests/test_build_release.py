import subprocess
import sys
from pathlib import Path

import build_release


def test_release_zip_includes_user_launchers_and_docs():
    assert build_release.should_exclude("START.bat") is False
    assert build_release.should_exclude("hermes_gui.bat") is False
    assert build_release.should_exclude("UPDATE.bat") is False
    assert build_release.should_exclude("START_HERE.txt") is False
    assert build_release.should_exclude("README.md") is False


def test_tracked_release_inventory_contains_complete_portable_surface():
    release_files = set(build_release.iter_release_files())

    assert {
        "README.md",
        "START.bat",
        "START_HERE.txt",
        "UPDATE.bat",
        "hermes.bat",
        "hermes_gui.bat",
        "hermes_gui.vbs",
        "install.bat",
        "assets/SOUL.md",
        "gui/__init__.py",
        "gui/app.py",
        "gui/agent_bridge.py",
        "gui/api_setup_wizard.py",
        "gui/extensions.py",
        "gui/lm_studio.py",
        "gui/permissions.py",
        "gui/permissions_panel.py",
        "gui/theme.py",
        "skills/extensions/comfyui/SKILL.md",
        "skills/extensions/music-server/SKILL.md",
        "skills/extensions/tts-server/SKILL.md",
        "skills/getting-started/SKILL.md",
        "skills/lm-studio/SKILL.md",
        "tools/extension_tools.py",
        "tools/gpu_tool.py",
        "tools/guide_tool.py",
        "tools/lm_studio_tools.py",
        "tools/model_switcher_tool.py",
        "tools/run_python_tool.py",
        "tools/serper_search_tool.py",
        "tools/tool_maker.py",
        "tools/update_hermes_tool.py",
        "tools/workflow_tool.py",
    } <= release_files


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


def test_windows_launchers_keep_runtime_state_in_active_hermes_home():
    root = Path(build_release.PROJECT_ROOT)
    start = (root / "START.bat").read_text(encoding="utf-8")
    install = (root / "install.bat").read_text(encoding="utf-8")
    cli_launcher = (root / "hermes.bat").read_text(encoding="utf-8")
    gui_launcher = (root / "hermes_gui.bat").read_text(encoding="utf-8")
    updater = (root / "UPDATE.bat").read_text(encoding="utf-8")

    for launcher in (install, cli_launcher, gui_launcher):
        assert 'if not defined HERMES_HOME set "HERMES_HOME=%USERPROFILE%\\.hermes"' in launcher

    assert "%HERMES_HOME%\\.env" in install
    assert "%HERMES_HOME%\\config.yaml" in install
    assert "%HERMES_HOME%\\permissions.json" in install
    assert "%HERMES_HOME%\\skills\\" in install
    assert "%USERPROFILE%\\.hermes\\permissions.json" not in install
    assert 'call "%SCRIPT_DIR%hermes_gui.bat" %*' in start

    for launcher in (start, cli_launcher, gui_launcher, updater):
        assert 'set "PIP_PREFIX=' not in launcher


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
