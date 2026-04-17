"""Tests for platform detection."""

import os
import unittest
import tempfile
from pathlib import Path
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


class TestPlatformBinMethods(unittest.TestCase):
    def setUp(self):
        self.platform = detect_platform()

    def test_exe_name_linux(self):
        if not self.platform.is_linux:
            self.skipTest("Not running on Linux")
        self.assertEqual(self.platform.exe_name("lazygit"), "lazygit")

    def test_exe_name_windows(self):
        with patch("platform.system", return_value="Windows"):
            with patch("platform.machine", return_value="AMD64"):
                platform = detect_platform()
                self.assertEqual(platform.exe_name("lazygit"), "lazygit.exe")

    def test_exe_name_msys(self):
        with patch("platform.system", return_value="MINGW64_NT"):
            with patch("platform.machine", return_value="x86_64"):
                with patch.dict(os.environ, {"MSYSTEM": "MINGW64"}):
                    platform = detect_platform()
                    self.assertEqual(platform.exe_name("lazygit"), "lazygit.exe")

    def test_bin_name_linux(self):
        if not self.platform.is_linux:
            self.skipTest("Not running on Linux")
        self.assertEqual(self.platform.bin_name("lazygit"), "lazygit")

    def test_bin_name_msys(self):
        with patch("platform.system", return_value="MINGW64_NT"):
            with patch("platform.machine", return_value="x86_64"):
                with patch.dict(os.environ, {"MSYSTEM": "MINGW64"}):
                    platform = detect_platform()
                    self.assertEqual(platform.bin_name("lazygit"), "lazygit.cmd")

    def test_find_exe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            exe = tmp / "test_app"
            exe.touch()
            result = self.platform.find_exe(tmp, "test_app")
            self.assertEqual(result, exe)

    def test_find_exe_with_suffix(self):
        if self.platform.is_linux:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                exe = tmp / "test_app"
                exe.touch()
                result = self.platform.find_exe(tmp, "test_app")
                self.assertEqual(result, exe)
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                exe = tmp / "test_app.exe"
                exe.touch()
                result = self.platform.find_exe(tmp, "test_app")
                self.assertEqual(result, exe)

    def test_is_bin_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            if self.platform.is_linux:
                (tmp / "tool").touch()
                self.assertTrue(self.platform.is_bin_installed(tmp, "tool"))
            else:
                (tmp / "tool.cmd").touch()
                self.assertTrue(self.platform.is_bin_installed(tmp, "tool"))

    def test_install_bin_entry_symlink(self):
        if self.platform.is_msys:
            self.skipTest("Not testing symlink on MSYS")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            target = tmp / "target_app"
            target.touch()
            bin_path = tmp / "link"
            self.platform.install_bin_entry(bin_path, target)
            if self.platform.is_linux:
                self.assertTrue(bin_path.is_symlink())
                self.assertEqual(bin_path.resolve(), target.resolve())

    def test_remove_bin_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bin_path = tmp / "tool"
            bin_path.touch()
            self.platform.remove_bin_entry(bin_path)
            self.assertFalse(bin_path.exists())


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
        self.assertIn("quick_env_home", paths)
        self.assertIn("quick_env_bin", paths)
        self.assertIn("quick_env_config", paths)
        self.assertIn("quick_env_data", paths)
        self.assertIn("quick_env_cache", paths)

    def test_quick_env_paths_contain_quick_env(self):
        paths = get_env_paths()
        quick_env_keys = ["quick_env_home", "quick_env_bin", "quick_env_config", "quick_env_data"]
        for key in quick_env_keys:
            self.assertIn("quick-env", paths[key])


if __name__ == "__main__":
    unittest.main()
