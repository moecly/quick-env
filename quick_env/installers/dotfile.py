"""Dotfile 安装器"""
import fnmatch
import os
import subprocess
from pathlib import Path
from typing import List, Optional

from ..installer import (
    InstallResult,
    Installer,
    detect_platform,
    get_env_paths,
    installer,
    log_uninstall,
    run_subprocess,
)
from ..tools import Tool


@installer("dotfile", priority=10)
@installer("git_clone", priority=10)
class DotfileInstaller(Installer):
    name = "dotfile"

    def __init__(self):
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def _create_bin_entry(self, tool: Tool) -> None:
        pass

    def is_available(self) -> bool:
        return self.platform.which("git") is not None

    def _get_dotfiles_dir(self, tool: Tool) -> Path:
        return Path(self.paths["quick_env_dotfiles"]) / tool.name

    def is_installed(self, tool: Tool) -> bool:
        if not tool.config_repo:
            return False
        dest = self._get_dotfiles_dir(tool)
        return dest.exists() and self._is_git_repo(dest)

    def _is_git_repo(self, path: Path) -> bool:
        try:
            result = run_subprocess(
                ["git", "-C", str(path), "rev-parse", "--git-dir"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_version(self, tool: Tool) -> Optional[str]:
        dest = self._get_dotfiles_dir(tool)
        if not dest.exists():
            return None
        try:
            result = run_subprocess(
                ["git", "-C", str(dest), "log", "-1", "--format=%ci"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()[:10]
        except Exception:
            pass
        return None

    def _get_current_branch(self, repo_path: Path) -> Optional[str]:
        try:
            result = run_subprocess(
                ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_git_dirty(self, repo_path: Path) -> bool:
        try:
            result = run_subprocess(
                ["git", "-C", str(repo_path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _should_exclude(self, path: str, exclude_patterns: list[str]) -> bool:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        return False

    def _find_matching_files(
        self, repo_path: Path, glob_pattern: str, exclude_patterns: list[str]
    ) -> List[Path]:
        matches = []
        base_pattern = glob_pattern.replace("*", "").rstrip("/")

        for item in repo_path.rglob("*"):
            rel_path = item.relative_to(repo_path)
            rel_str = str(rel_path)

            if self._should_exclude(rel_str, exclude_patterns):
                continue

            if fnmatch.fnmatch(rel_str, glob_pattern) or fnmatch.fnmatch(
                item.name, glob_pattern
            ):
                matches.append(item)

            if (
                base_pattern
                and str(rel_path).startswith(base_pattern)
                and "*" in glob_pattern
            ):
                if self._should_exclude(rel_str, exclude_patterns):
                    continue
                if fnmatch.fnmatch(rel_str, glob_pattern):
                    matches.append(item)

        return matches

    def _create_link(self, src: Path, dest_path: Path) -> bool:
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if dest_path.is_symlink():
                dest_path.unlink()
            elif dest_path.exists():
                backup = dest_path.with_suffix(".bak")
                self.platform.move(dest_path, Path(str(backup)))

            return self.platform.create_symlink(
                src, dest_path, target_is_directory=src.is_dir()
            )

            return True
        except OSError:
            return False

    def _remove_link(self, link_path: Path) -> bool:
        try:
            if link_path.is_symlink():
                link_path.unlink()
                return True
            return False
        except OSError:
            return False

    def install(self, tool: Tool) -> InstallResult:
        if not tool.config_repo:
            return InstallResult(
                False, "Tool does not support dotfile installation", self.name
            )

        dest = self._get_dotfiles_dir(tool)

        if dest.exists():
            if self._is_git_repo(dest):
                try:
                    run_subprocess(
                        ["git", "-C", str(dest), "pull"],
                        check=True,
                        capture_output=True,
                        timeout=30,
                    )
                    self._create_links(tool, dest)
                    return InstallResult(
                        True, f"Updated {tool.display_name}", self.name
                    )
                except subprocess.CalledProcessError:
                    return InstallResult(
                        False, f"Failed to update {tool.display_name}", self.name
                    )
            else:
                self.platform.rmtree(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            branch_args = (
                ["--branch", tool.config_branch] if tool.config_branch != "main" else []
            )
            run_subprocess(
                ["git", "clone"]
                + branch_args
                + [f"https://github.com/{tool.config_repo}", str(dest)],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except subprocess.CalledProcessError as e:
            return InstallResult(False, f"Clone failed: {e.stderr}", self.name)
        except subprocess.TimeoutExpired:
            return InstallResult(False, "Clone timed out", self.name)

        self._create_links(tool, dest)

        return InstallResult(True, f"Installed {tool.display_name}", self.name)

    def _create_links(self, tool: Tool, repo_path: Path):
        for link_config in tool.links:
            dest_path_str = link_config.get_target()
            if not dest_path_str:
                continue

            src_path = repo_path / link_config.glob
            dest_path = Path(os.path.expanduser(dest_path_str))

            if src_path.exists():
                if self._should_exclude(
                    str(src_path.relative_to(repo_path)), tool.exclude
                ):
                    continue
                self._create_link(src_path, dest_path)
            else:
                matching = self._find_matching_files(
                    repo_path, link_config.glob, tool.exclude
                )
                if matching:
                    if dest_path.is_dir() or (
                        not dest_path.suffix
                        and dest_path.name != link_config.glob.split("/")[0]
                    ):
                        dest_path.mkdir(parents=True, exist_ok=True)
                        for match in matching:
                            rel_path = match.relative_to(repo_path)
                            target = dest_path / rel_path.name
                            if self._should_exclude(str(rel_path), tool.exclude):
                                continue
                            self._create_link(match, target)
                    else:
                        if self._should_exclude(
                            str(matching[0].relative_to(repo_path)), tool.exclude
                        ):
                            continue
                        self._create_link(matching[0], dest_path)

    def uninstall(self, tool: Tool) -> InstallResult:
        if not tool.is_dotfile():
            return InstallResult(
                False, "Use dotfile uninstall for config repos", self.name
            )

        for link_config in tool.links:
            dest_path = Path(os.path.expanduser(link_config.to))
            self._remove_link(dest_path)

        dest = self._get_dotfiles_dir(tool)
        if dest.exists():
            self.platform.rmtree(dest)

        result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
        log_uninstall(tool.display_name, True, result.message)
        return result