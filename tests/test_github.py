"""Tests for GitHub API."""

import unittest
from unittest.mock import patch, MagicMock
from quick_env.github import GitHubAPI, GitHubRelease, GitHubAsset


class TestGitHubAPI(unittest.TestCase):
    def setUp(self):
        self.api = GitHubAPI()

    def test_init_without_token(self):
        api = GitHubAPI()
        self.assertIsNone(api.token)
        self.assertIsNotNone(api.session)

    def test_init_with_token(self):
        api = GitHubAPI(token="test_token")
        self.assertEqual(api.token, "test_token")
        self.assertIn("Authorization", api.session.headers)

    @patch("quick_env.github.requests.Session.get")
    def test_get_latest_release_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tag_name": "v1.0.0",
            "name": "v1.0.0",
            "body": "Test release",
            "html_url": "https://github.com/test/repo/releases/tag/v1.0.0",
            "created_at": "2024-01-01T00:00:00Z",
            "published_at": "2024-01-01T00:00:00Z",
            "assets": [
                {
                    "name": "test-linux-amd64.tar.gz",
                    "browser_download_url": "https://example.com/test.tar.gz",
                    "size": 1024,
                }
            ],
        }
        mock_get.return_value = mock_response

        release = self.api.get_latest_release("test/repo")

        self.assertEqual(release.tag_name, "v1.0.0")
        self.assertEqual(release.name, "v1.0.0")
        self.assertEqual(len(release.assets), 1)
        self.assertEqual(release.assets[0].name, "test-linux-amd64.tar.gz")

    @patch("quick_env.github.requests.Session.get")
    def test_get_latest_release_handles_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException("Network error")

        with self.assertRaises(requests.RequestException):
            self.api.get_latest_release("test/repo")


class TestGitHubRelease(unittest.TestCase):
    def test_release_creation(self):
        asset = GitHubAsset(
            name="test.tar.gz",
            download_url="https://example.com/test.tar.gz",
            size=1024,
            browser_download_url="https://example.com/test.tar.gz",
        )
        release = GitHubRelease(
            tag_name="v1.0.0",
            name="v1.0.0",
            body="Test",
            html_url="https://github.com/test/repo/releases/tag/v1.0.0",
            assets=[asset],
            created_at="2024-01-01",
            published_at="2024-01-01",
        )
        self.assertEqual(release.tag_name, "v1.0.0")
        self.assertEqual(len(release.assets), 1)
        self.assertEqual(release.assets[0].name, "test.tar.gz")


class TestGitHubAsset(unittest.TestCase):
    def test_asset_creation(self):
        asset = GitHubAsset(
            name="test.tar.gz",
            download_url="https://example.com/test.tar.gz",
            size=1024,
            browser_download_url="https://example.com/test.tar.gz",
        )
        self.assertEqual(asset.name, "test.tar.gz")
        self.assertEqual(asset.size, 1024)


if __name__ == "__main__":
    unittest.main()
