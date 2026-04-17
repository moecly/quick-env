"""Tests for platform detection."""

import unittest
from unittest.mock import patch
from quick_env.platform import (
    detect_platform,
    detect_package_manager,
    get_env_paths,
    command_exists,
    Platform,
)


class TestPlatformDetection(unittest.TestCase):
    def test_detect_platform_returns_platform_object(self):
        platform = detect_platform()
        self.assertIsInstance(platform, Platform)
        self.assertIsNotNone(platform.system)
        self.assertIsNotNone(platform.arch)
        self.assertIsNotNone(platform.platform_name)
        self.assertIsNotNone(platform.arch_name)

    def test_platform_properties_linux(self):
        with patch("platform.system", return_value="Linux"):
            with patch("platform.machine", return_value="x86_64"):
                platform = detect_platform()
                self.assertTrue(platform.is_linux)
                self.assertFalse(platform.is_macos)
                self.assertFalse(platform.is_windows)

    def test_platform_properties_macos(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.machine", return_value="arm64"):
                platform = detect_platform()
                self.assertTrue(platform.is_macos)
                self.assertFalse(platform.is_linux)
                self.assertFalse(platform.is_windows)

    def test_platform_properties_windows(self):
        with patch("platform.system", return_value="Windows"):
            with patch("platform.machine", return_value="AMD64"):
                platform = detect_platform()
                self.assertTrue(platform.is_windows)
                self.assertFalse(platform.is_linux)
                self.assertFalse(platform.is_macos)

    def test_platform_properties_git_bash(self):
        with patch("platform.system", return_value="MINGW64_NT"):
            with patch("platform.machine", return_value="x86_64"):
                platform = detect_platform()
                self.assertTrue(platform.is_git_bash)
                self.assertTrue(platform.platform_name, "windows")


class TestPackageManagerDetection(unittest.TestCase):
    @patch("quick_env.platform.shutil.which")
    def test_detect_brew(self, mock_which):
        mock_which.side_effect = lambda x: x == "brew"
        self.assertEqual(detect_package_manager(), "brew")

    @patch("quick_env.platform.shutil.which")
    def test_detect_apt(self, mock_which):
        def which(cmd):
            if cmd == "brew":
                return None
            if cmd in ("apt", "apt-get"):
                return f"/usr/bin/{cmd}"
            return None
        mock_which.side_effect = which
        self.assertEqual(detect_package_manager(), "apt")

    @patch("quick_env.platform.shutil.which")
    def test_detect_none(self, mock_which):
        mock_which.return_value = None
        self.assertIsNone(detect_package_manager())


class TestCommandExists(unittest.TestCase):
    @patch("quick_env.platform.shutil.which")
    def test_command_exists_true(self, mock_which):
        mock_which.return_value = "/usr/bin/python"
        self.assertTrue(command_exists("python"))

    @patch("quick_env.platform.shutil.which")
    def test_command_exists_false(self, mock_which):
        mock_which.return_value = None
        self.assertFalse(command_exists("nonexistent"))


class TestGetEnvPaths(unittest.TestCase):
    def test_get_env_paths_returns_dict(self):
        paths = get_env_paths()
        self.assertIsInstance(paths, dict)
        self.assertIn("home", paths)
        self.assertIn("bin_home", paths)
        self.assertIn("quick_env_home", paths)
        self.assertIn("quick_env_bin", paths)
        self.assertIn("quick_env_config", paths)

    def test_quick_env_paths_contain_quick_env(self):
        paths = get_env_paths()
        quick_env_keys = ["quick_env_home", "quick_env_bin", "quick_env_config"]
        for key in quick_env_keys:
            self.assertIn("quick-env", paths[key])


if __name__ == "__main__":
    unittest.main()
