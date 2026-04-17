"""Tests for installer classes."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tomllib
from quick_env.installer import (
    GitHubInstaller,
    PackageManagerInstaller,
    GitCloneInstaller,
    InstallerFactory,
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
            SourceInfo(name="github", path="/home/user/.quick-env/bin/tmux", version="3.5"),
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
            SourceInfo(name="system", path="/usr/bin/tmux", version="3.3a", is_current=True),
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


class TestGitCloneInstaller(unittest.TestCase):
    def setUp(self):
        self.installer = GitCloneInstaller()

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
        self.assertEqual(installer.name, "git_clone")

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
        installer = InstallerFactory.get_best_installer(tool)
        self.assertIsNotNone(installer)
        self.assertEqual(installer.name, "git_clone")

    def test_detect_tool_returns_detection(self):
        config = load_project_config()
        tool = config.get_tool("lazygit")
        self.assertIsNotNone(tool)
        detection = InstallerFactory.detect_tool(tool)
        self.assertIsInstance(detection, ToolDetection)
        self.assertEqual(detection.tool_name, "lazygit")


if __name__ == "__main__":
    unittest.main()
