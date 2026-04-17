"""Tests for installer classes."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tomllib
from quick_env.installer import (
    GitHubInstaller,
    PackageManagerInstaller,
    DotfileInstaller,
    CustomScriptInstaller,
    CustomURLInstaller,
    InstallerFactory,
    InstallerRegistry,
    InstallResult,
    SourceInfo,
    ToolDetection,
)
from quick_env.config import Config


PROJECT_CONFIG = Path(__file__).parent.parent / "tools.toml"


def load_project_config():
    return Config.load_from(PROJECT_CONFIG)


class TestInstallResult(unittest.TestCase):
    def test_install_result_creation(self):
        result = InstallResult(
            success=True,
            message="Installed successfully",
            method="github",
            version="v1.0.0",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Installed successfully")
        self.assertEqual(result.method, "github")
        self.assertEqual(result.version, "v1.0.0")

    def test_install_result_without_version(self):
        result = InstallResult(
            success=False,
            message="Failed",
            method="github",
        )
        self.assertFalse(result.success)
        self.assertIsNone(result.version)


class TestSourceInfo(unittest.TestCase):
    def test_source_info_creation(self):
        source = SourceInfo(
            name="github",
            path="/home/user/.quick-env/bin/lazygit",
            version="v1.0.0",
            is_current=True,
        )
        self.assertEqual(source.name, "github")
        self.assertEqual(source.path, "/home/user/.quick-env/bin/lazygit")
        self.assertEqual(source.version, "v1.0.0")
        self.assertTrue(source.is_current)


class TestToolDetection(unittest.TestCase):
    def test_tool_detection_creation(self):
        detection = ToolDetection(tool_name="lazygit")
        self.assertEqual(detection.tool_name, "lazygit")
        self.assertFalse(detection.installed)
        self.assertEqual(detection.sources, [])
        self.assertIsNone(detection.current_source)

    def test_tool_detection_with_sources(self):
        detection = ToolDetection(tool_name="tmux")
        detection.installed = True
        detection.sources = [
            SourceInfo(name="system", path="/usr/bin/tmux", version="3.3a"),
            SourceInfo(
                name="github", path="/home/user/.quick-env/bin/tmux", version="3.5"
            ),
        ]
        detection.current_source = "system"

        self.assertTrue(detection.installed)
        self.assertEqual(len(detection.sources), 2)
        self.assertEqual(detection.current_source, "system")

    def test_sources_display_single(self):
        detection = ToolDetection(tool_name="lazygit")
        detection.sources = [SourceInfo(name="github", path="/path")]
        self.assertEqual(detection.sources_display, "github")

    def test_sources_display_multiple(self):
        detection = ToolDetection(tool_name="tmux")
        detection.sources = [
            SourceInfo(name="system", path="/usr/bin/tmux"),
            SourceInfo(name="github", path="/path/to/tmux"),
        ]
        self.assertEqual(detection.sources_display, "system, github")

    def test_sources_display_empty(self):
        detection = ToolDetection(tool_name="fd")
        self.assertEqual(detection.sources_display, "-")

    def test_current_path(self):
        detection = ToolDetection(tool_name="tmux")
        detection.sources = [
            SourceInfo(name="system", path="/usr/bin/tmux", is_current=True),
        ]
        self.assertEqual(detection.current_path, "/usr/bin/tmux")

    def test_current_version(self):
        detection = ToolDetection(tool_name="tmux")
        detection.sources = [
            SourceInfo(
                name="system", path="/usr/bin/tmux", version="3.3a", is_current=True
            ),
        ]
        self.assertEqual(detection.current_version, "3.3a")


class TestGitHubInstaller(unittest.TestCase):
    def setUp(self):
        self.installer = GitHubInstaller()

    def test_is_available_with_curl(self):
        with patch("quick_env.installer.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/curl"
            self.assertTrue(self.installer.is_available())

    def test_is_available_without_curl_or_wget(self):
        with patch("quick_env.installer.shutil.which") as mock_which:
            mock_which.return_value = None
            self.assertFalse(self.installer.is_available())


class TestPackageManagerInstaller(unittest.TestCase):
    def setUp(self):
        with patch("quick_env.installer.detect_package_manager") as mock_pm:
            mock_pm.return_value = "apt"
            self.installer = PackageManagerInstaller()

    def test_is_available_always_true(self):
        self.assertTrue(self.installer.is_available())


class TestDotfileInstaller(unittest.TestCase):
    def setUp(self):
        self.installer = DotfileInstaller()

    def test_is_available_with_git(self):
        with patch("quick_env.installer.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/git"
            self.assertTrue(self.installer.is_available())

    def test_is_available_without_git(self):
        with patch("quick_env.installer.shutil.which") as mock_which:
            mock_which.return_value = None
            self.assertFalse(self.installer.is_available())


class TestInstallerFactory(unittest.TestCase):
    def test_get_installer_github(self):
        installer = InstallerFactory.get_installer("github")
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "github")

    def test_get_installer_system(self):
        installer = InstallerFactory.get_installer("system")
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "system")

    def test_get_installer_git_clone(self):
        installer = InstallerFactory.get_installer("git_clone")
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "dotfile")

    def test_get_installer_dotfile(self):
        installer = InstallerFactory.get_installer("dotfile")
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "dotfile")

    def test_get_installer_invalid(self):
        installer = InstallerFactory.get_installer("invalid")
        self.assertIsNone(installer)

    def test_get_best_installer_for_lazygit(self):
        config = load_project_config()
        tool = config.get_tool("lazygit")
        self.assertIsNotNone(tool)
        installer = InstallerFactory.get_best_installer(tool)
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "github")

    def test_get_best_installer_for_tmux_config(self):
        config = load_project_config()
        tool = config.get_tool("tmux-config")
        self.assertIsNotNone(tool)
        self.assertTrue(tool.is_dotfile())
        installer = InstallerFactory.get_best_installer(tool)
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "dotfile")

    def test_detect_tool_returns_detection(self):
        config = load_project_config()
        tool = config.get_tool("lazygit")
        self.assertIsNotNone(tool)
        detection = InstallerFactory.detect_tool(tool)
        self.assertIsInstance(detection, ToolDetection)
        self.assertEqual(detection.tool_name, "lazygit")

    def test_get_best_installer_uses_type_for_dotfiles(self):
        config = load_project_config()
        tool = config.get_tool("nvim-config")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.type, "dotfile")
        installer = InstallerFactory.get_best_installer(tool)
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "dotfile")


class TestInstallerRegistry(unittest.TestCase):
    def test_registry_has_builtin_installers(self):
        self.assertIn("github", InstallerRegistry.list_all())
        self.assertIn("package_manager", InstallerRegistry.list_all())
        self.assertIn("dotfile", InstallerRegistry.list_all())
        self.assertIn("custom_script", InstallerRegistry.list_all())
        self.assertIn("custom_url", InstallerRegistry.list_all())

    def test_registry_get_builtin_installers(self):
        github_cls = InstallerRegistry.get("github")
        self.assertEqual(github_cls, GitHubInstaller)

        pm_cls = InstallerRegistry.get("package_manager")
        self.assertEqual(pm_cls, PackageManagerInstaller)

        dotfile_cls = InstallerRegistry.get("dotfile")
        self.assertEqual(dotfile_cls, DotfileInstaller)

    def test_registry_create_installers(self):
        github = InstallerRegistry.create("github")
        self.assertIsInstance(github, GitHubInstaller)

        dotfile = InstallerRegistry.create("dotfile")
        self.assertIsInstance(dotfile, DotfileInstaller)

    def test_registry_returns_none_for_invalid(self):
        result = InstallerRegistry.get("nonexistent")
        self.assertIsNone(result)

        result = InstallerRegistry.create("nonexistent")
        self.assertIsNone(result)


class TestCustomScriptInstaller(unittest.TestCase):
    def test_custom_script_installer_properties(self):
        installer = CustomScriptInstaller()
        self.assertEqual(installer.name, "custom_script")
        self.assertEqual(installer.priority, 5)

    def test_custom_script_is_available(self):
        installer = CustomScriptInstaller()
        self.assertTrue(installer.is_available())


class TestCustomURLInstaller(unittest.TestCase):
    def test_custom_url_installer_properties(self):
        installer = CustomURLInstaller()
        self.assertEqual(installer.name, "custom_url")
        self.assertEqual(installer.priority, 10)

    def test_custom_url_is_available_with_curl(self):
        installer = CustomURLInstaller()
        self.assertTrue(installer.is_available())


class TestGetBestInstallerWithCustom(unittest.TestCase):
    def test_get_best_installer_prefers_custom_script(self):
        from quick_env.tools import Tool

        tool = Tool(
            name="test-script-tool",
            custom_script="echo install",
            installable_by=["custom_script"],
        )
        installer = InstallerFactory.get_best_installer(tool)
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "custom_script")

    def test_get_best_installer_custom_url(self):
        from quick_env.tools import Tool

        tool = Tool(
            name="test-url-tool",
            custom_url="https://example.com/tool.tar.gz",
            installable_by=["custom_url"],
        )
        installer = InstallerFactory.get_best_installer(tool)
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "custom_url")


if __name__ == "__main__":
    unittest.main()
