"""GitHub API utilities."""

import re
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class GitHubRelease:
    tag_name: str
    name: str
    body: str
    html_url: str
    assets: list["GitHubAsset"]
    created_at: str
    published_at: str


@dataclass
class GitHubAsset:
    name: str
    download_url: str
    size: int
    browser_download_url: str


@dataclass
class GitHubRepo:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @classmethod
    def parse(cls, repo_str: str) -> "GitHubRepo":
        parts = repo_str.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo_str}")
        return cls(owner=parts[0], name=parts[1])


class GitHubAPI:
    BASE_URL = "https://api.github.com"
    TIMEOUT = 30
    MAX_RETRIES = 3

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.session.headers["Accept"] = "application/vnd.github+json"
        self.session.headers["X-GitHub-Api-Version"] = "2022-11-28"

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, params=params, timeout=self.TIMEOUT)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
        raise last_error or requests.RequestException(f"Failed after {self.MAX_RETRIES} retries")

    def get_latest_release(self, repo: str) -> GitHubRelease:
        url = f"{self.BASE_URL}/repos/{repo}/releases/latest"
        data = self._get(url).json()
        return self._parse_release(data)

    def get_release(self, repo: str, tag: str) -> GitHubRelease:
        url = f"{self.BASE_URL}/repos/{repo}/releases/tags/{tag}"
        data = self._get(url).json()
        return self._parse_release(data)

    def get_releases(self, repo: str, per_page: int = 30) -> list[GitHubRelease]:
        url = f"{self.BASE_URL}/repos/{repo}/releases"
        releases = []
        page = 1
        while True:
            data = self._get(url, params={"per_page": per_page, "page": page}).json()
            if not data:
                break
            releases.extend([self._parse_release(r) for r in data])
            if len(data) < per_page:
                break
            page += 1
        return releases

    def _parse_release(self, data: dict) -> GitHubRelease:
        assets = []
        for asset in data.get("assets", []):
            assets.append(GitHubAsset(
                name=asset["name"],
                download_url=asset["browser_download_url"],
                size=asset["size"],
                browser_download_url=asset["browser_download_url"],
            ))
        return GitHubRelease(
            tag_name=data["tag_name"],
            name=data["name"] or data["tag_name"],
            body=data.get("body", ""),
            html_url=data["html_url"],
            assets=assets,
            created_at=data["created_at"],
            published_at=data["published_at"],
        )

    def find_asset(self, release: GitHubRelease, pattern: str, platform_name: str, arch_name: str) -> Optional[GitHubAsset]:
        version = release.tag_name.lstrip("v")
        pattern = pattern.replace("{version}", version)
        pattern = pattern.replace("{platform}", platform_name)
        pattern = pattern.replace("{arch}", arch_name)

        for asset in release.assets:
            if self._match_pattern(asset.name, pattern):
                return asset
        return None

    def find_asset_by_platform(self, release: GitHubRelease, patterns: dict[str, str], platform_name: str, arch_name: str) -> Optional[GitHubAsset]:
        version = release.tag_name.lstrip("v")
        platform_key = f"{platform_name}_{arch_name}"

        if platform_key in patterns:
            pattern = patterns[platform_key].replace("{version}", version)
            for asset in release.assets:
                if self._match_pattern(asset.name, pattern):
                    return asset

        fallback_patterns = [
            f"{platform_name}_x86_64",
            f"{platform_name}_amd64",
            f"{platform_name}_arm64",
        ]
        for key in fallback_patterns:
            if key in patterns:
                pattern = patterns[key].replace("{version}", version)
                for asset in release.assets:
                    if self._match_pattern(asset.name, pattern):
                        return asset

        return None

    def _match_pattern(self, name: str, pattern: str) -> bool:
        pattern = re.escape(pattern)
        pattern = pattern.replace(r"\{version\}", r"[^/]+")
        pattern = pattern.replace(r"\{platform\}", r"[^/]+")
        pattern = pattern.replace(r"\{arch\}", r"[^/]+")
        pattern = f"^{pattern}$"
        return bool(re.match(pattern, name))


def compare_versions(v1: str, v2: str) -> int:
    def parse(v: str) -> tuple:
        v = v.lstrip("v")
        parts = re.split(r"[.\-_]", v)
        result = []
        for p in parts:
            if p.isdigit():
                result.append(int(p))
            else:
                break
        return tuple(result)

    v1_parts = parse(v1)
    v2_parts = parse(v2)
    return (v1_parts > v2_parts) - (v1_parts < v2_parts)


if __name__ == "__main__":
    api = GitHubAPI()
    release = api.get_latest_release("jesseduffield/lazygit")
    print(f"Latest: {release.tag_name}")
