"""Tests for downloader utilities."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from quick_env.downloader import (
    download_file,
    download_with_progress,
    verify_checksum,
    extract_tarball,
    extract_zip,
    find_executable_in_dir,
    make_executable,
)


class TestDownloadFile(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dest = Path(self.temp_dir) / "test_file"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("quick_env.downloader.requests.get")
    def test_download_file_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"test content"]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = download_file("https://example.com/file", self.dest)

        self.assertTrue(result)
        self.assertTrue(self.dest.exists())

    @patch("quick_env.downloader.requests.get")
    def test_download_file_failure(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Network error")

        result = download_file("https://example.com/file", self.dest)

        self.assertFalse(result)
        self.assertFalse(self.dest.exists())


class TestVerifyChecksum(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test"
        self.test_file.write_bytes(b"test content")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verify_checksum_correct(self):
        import hashlib
        expected = hashlib.sha256(b"test content").hexdigest()
        self.assertTrue(verify_checksum(self.test_file, expected))

    def test_verify_checksum_incorrect(self):
        self.assertFalse(verify_checksum(self.test_file, "wrong_checksum"))

    def test_verify_checksum_missing_file(self):
        self.assertFalse(verify_checksum(Path("/nonexistent"), "checksum"))


class TestFindExecutable(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "test_app"
        self.test_dir.mkdir()
        (self.test_dir / "test_app").touch()
        (self.test_dir / "test_app.exe").touch()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_executable_by_name(self):
        result = find_executable_in_dir(self.test_dir, "test_app")
        self.assertIsNotNone(result)

    def test_find_executable_not_found(self):
        result = find_executable_in_dir(self.test_dir, "nonexistent")
        self.assertIsNone(result)


class TestMakeExecutable(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test"
        self.test_file.write_bytes(b"test")
        self.test_file.chmod(0o644)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_make_executable(self):
        make_executable(self.test_file)
        mode = self.test_file.stat().st_mode
        self.assertTrue(mode & 0o111)


if __name__ == "__main__":
    unittest.main()
