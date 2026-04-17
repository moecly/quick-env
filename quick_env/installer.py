"""Installers for different installation methods."""

import fnmatch
import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from .github import GitHubAPI, GitHubRelease
from .platform import (
    Platform,
    detect_platform,
    detect_package_manager,
    PACKAGE_MANAGER_COMMANDS,
    get_env_paths,
)
from .tools import Tool
from .downloader import download_file, extract_tarball, extract_zip, make_executable
from .logger import log_install, log_uninstall


def run_subprocess(*args, **kwargs) -> subprocess.CompletedProcess:
    """标准化 subprocess.run 调用，处理编码问题"""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.run(*args, **kwargs)


@dataclass
class InstallResult:
    success: bool
    message: str
    method: str
    version: Optional[str] = None


@dataclass
class SourceInfo:
    name: str
    path: str
    version: Optional[str] = None
    is_current: bool = False


@dataclass
class ToolDetection:
    tool_name: str
    installed: bool = False
    sources: List[SourceInfo] = field(default_factory=list)
    current_source: Optional[str] = None

    @property
    def current_path(self) -> Optional[str]:
        for source in self.sources:
            if source.is_current:
                return source.path
        return None

    @property
    def current_version(self) -> Optional[str]:
        for source in self.sources:
            if source.is_current:
                return source.version
        return None

    @property
    def sources_display(self) -> str:
        if not self.sources:
            return "-"
        names = [s.name for s in self.sources]
        return ", ".join(names)


@dataclass
class VersionInfo:
    current: Optional[str] = None
    latest: Optional[str] = None
    source: str = ""
    has_update: bool = False


def get_command_name(tool: Tool) -> str:
    """根据当前平台获取实际命令名"""
    pm = detect_package_manager()
    if pm and tool.package_manager_commands:
        return tool.package_manager_commands.get(
            pm, tool.package_manager_commands.get("default", tool.name)
        )
    return tool.name


def get_latest_from_package_manager(tool: Tool) -> Optional[str]:
    """从包管理器获取最新版本"""
    pm = detect_package_manager()
    if not pm or not tool.package_name:
        return None

    try:
        if pm == "apt":
            result = run_subprocess(
                ["apt-cache", "policy", tool.package_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                match = re.search(r"Candidate:\s*(\S+)", result.stdout)
                if match:
                    version = match.group(1)
                    if version and version != "(none)":
                        return version

        elif pm == "brew":
            result = run_subprocess(
                ["brew", "info", tool.package_name, "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                if data:
                    return data[0].get("versions", {}).get("stable") or data[0].get(
                        "versions", {}
                    ).get("bottle")

        elif pm == "dnf":
            result = run_subprocess(
                ["dnf", "list", tool.package_name, "--available"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                match = re.search(
                    rf"{re.escape(tool.package_name)}.*?\s+(\S+)", result.stdout
                )
                if match:
                    return match.group(1)

        elif pm == "yum":
            result = run_subprocess(
                ["yum", "list", tool.package_name, "--available"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                match = re.search(
                    rf"{re.escape(tool.package_name)}.*?\s+(\S+)", result.stdout
                )
                if match:
                    return match.group(1)

        elif pm == "pacman":
            result = run_subprocess(
                ["pacman", "-Si", tool.package_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                match = re.search(r"Version\s*:\s*(\S+)", result.stdout)
                if match:
                    return match.group(1)

        elif pm == "zypper":
            result = run_subprocess(
                ["zypper", "info", tool.package_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                match = re.search(r"Version\s*:\s*(\S+)", result.stdout)
                if match:
                    return match.group(1)

        elif pm == "winget":
            result = run_subprocess(
                ["winget", "list", "--id", tool.package_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if tool.package_name in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            return parts[-2]

    except Exception:
        pass

    return None


def get_version_info(tool: Tool) -> VersionInfo:
    """获取工具的版本信息，按 installable_by + priority 优先级检测"""
    info = VersionInfo()
    current_platform = detect_platform()

    cmd_name = get_command_name(tool)
    which_path = current_platform.which(cmd_name)

    if not which_path:
        quick_env_bin = Path(get_env_paths()["quick_env_bin"])
        executable = current_platform.get_bin_executable_path(quick_env_bin, cmd_name)
        if executable and executable.exists():
            which_path = str(executable)

    if which_path:
        try:
            result = run_subprocess(
                [which_path, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                output = result.stdout + result.stderr
                match = re.search(r"(\d+\.\d+\.?\d*)", output)
                if match:
                    info.current = match.group(1)
        except Exception:
            pass

    sources = []
    for name in tool.installable_by:
        priority = tool.get_priority(name, 100)
        sources.append((name, priority))
    sources.sort(key=lambda x: x[1])

    for source_name, _ in sources:
        if source_name == "github" and tool.repo:
            try:
                api = GitHubAPI()
                release = api.get_latest_release(tool.repo)
                info.latest = release.tag_name.lstrip("v")
                info.source = "github"
                break
            except Exception:
                pass
        elif source_name == "package_manager":
            latest = get_latest_from_package_manager(tool)
            if latest:
                info.latest = latest
                info.source = "package_manager"
                break

    if info.current and info.latest:
        info.has_update = compare_versions(info.latest, info.current) > 0

    return info


def compare_versions(v1: str, v2: str) -> int:
    """比较两个版本号，返回 1 if v1 > v2, -1 if v1 < v2, 0 if equal"""

    def parse(v: str) -> tuple:
        v = v.lstrip("v")
        parts = re.split(r"[.\-_]", v)
        result = []
        for p in parts:
            if p.isdigit():
                result.append(int(p))
            else:
                break
        return tuple(result) if result else (0,)

    v1_parts = parse(v1)
    v2_parts = parse(v2)
    return (v1_parts > v2_parts) - (v1_parts < v2_parts)


class Installer(ABC):
    name: str = "base"
    priority: int = 100

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def is_installed(self, tool: Tool) -> bool:
        pass

    @abstractmethod
    def get_version(self, tool: Tool) -> Optional[str]:
        pass

    @abstractmethod
    def install(self, tool: Tool) -> InstallResult:
        pass

    @abstractmethod
    def uninstall(self, tool: Tool) -> InstallResult:
        pass


class GitHubInstaller(Installer):
    name = "github"
    priority = 10

    def __init__(self):
        self.api = GitHubAPI()
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return (
            self.platform.which("curl") is not None
            or self.platform.which("wget") is not None
        )

    def _get_data_dir(self, tool: Tool, version: str) -> Path:
        clean_version = self._sanitize_dirname(version.lstrip("v"))
        return Path(self.paths["quick_env_tools"]) / f"{tool.name}_{clean_version}"

    def _get_bin_path(self, tool: Tool) -> Path:
        return Path(self.paths["quick_env_bin"]) / self.platform.bin_name(tool.name)

    def _sanitize_dirname(self, name: str) -> str:
        illegal_chars = "/\\.."
        for char in illegal_chars:
            name = name.replace(char, "-")
        return name.strip("-")

    def _parse_version_from_data_dir(self, data_dir: Path) -> Optional[str]:
        if not data_dir.exists():
            return None
        name = data_dir.name
        if "_" in name:
            parts = name.split("_", 1)
            if len(parts) == 2:
                return parts[1]
        return None

    def is_installed(self, tool: Tool) -> bool:
        if tool.config_repo:
            config_path = self._get_config_dest(tool)
            return config_path.exists() if config_path else False
        bin_dir = Path(self.paths["quick_env_bin"])
        return self.platform.is_bin_valid(bin_dir, tool.name)

    def get_version(self, tool: Tool) -> Optional[str]:
        if tool.config_repo:
            return self._get_git_version(tool)
        bin_dir = Path(self.paths["quick_env_bin"])
        executable = self.platform.get_bin_executable_path(bin_dir, tool.name)
        if executable:
            if executable.parent.exists():
                version = self._parse_version_from_data_dir(executable.parent)
                if version:
                    return version
            return self._get_binary_version(executable)
        return None

    def _get_binary_version(self, bin_path: Path) -> Optional[str]:
        try:
            result = run_subprocess(
                [str(bin_path), "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                output = result.stdout + result.stderr
                match = re.search(r"(\d+\.\d+\.?\d*)", output)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def _get_git_version(self, tool: Tool) -> Optional[str]:
        dest = self._get_config_dest(tool)
        if not dest or not dest.exists():
            return None
        try:
            result = run_subprocess(
                ["git", "-C", str(dest), "log", "-1", "--format=%ci"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()[:10]
        except Exception:
            pass
        return None

    def _cleanup_old_versions(self, tool: Tool, current_version: str) -> None:
        data_dir = Path(self.paths["quick_env_tools"])
        if not data_dir.exists():
            return
        clean_current = self._sanitize_dirname(current_version.lstrip("v"))
        prefix = f"{tool.name}_"
        for item in data_dir.iterdir():
            if item.is_dir() and item.name.startswith(prefix):
                version = self._parse_version_from_data_dir(item)
                if version and version != clean_current:
                    self.platform.rmtree(item)

    def install(self, tool: Tool) -> InstallResult:
        if tool.config_repo:
            result = self._install_config(tool)
            log_install(
                tool.display_name,
                result.version,
                self.name,
                result.success,
                result.message,
            )
            return result
        if not tool.repo or not tool.github_asset_patterns:
            result = InstallResult(
                False, "Tool does not support GitHub installation", self.name
            )
            log_install(tool.display_name, None, self.name, False, result.message)
            return result
        result = self._install_binary(tool)
        log_install(
            tool.display_name, result.version, self.name, result.success, result.message
        )
        return result

    def _install_binary(self, tool: Tool) -> InstallResult:
        try:
            release = self.api.get_latest_release(tool.repo)
        except Exception as e:
            return InstallResult(False, f"Failed to fetch release: {e}", self.name)

        version = release.tag_name.lstrip("v")

        if tool.github_asset_patterns:
            asset = self.api.find_asset_by_platform(
                release,
                tool.github_asset_patterns,
                self.platform.platform_name,
                self.platform.arch_name,
            )
        else:
            return InstallResult(False, "No github_asset_patterns defined", self.name)

        if not asset:
            return InstallResult(
                False,
                f"No asset found for {self.platform.platform_name}/{self.platform.arch_name}",
                self.name,
            )

        cache_dir = Path(self.paths["quick_env_cache"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        archive_path = cache_dir / asset.name

        if not archive_path.exists():
            if not download_file(asset.browser_download_url, archive_path):
                return InstallResult(False, "Download failed", self.name)

        data_dir = self._get_data_dir(tool, version)
        if data_dir.exists():
            self.platform.rmtree(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        if asset.name.endswith(".tar.gz") or asset.name.endswith(".tgz"):
            extracted = extract_tarball(archive_path, data_dir)
        elif asset.name.endswith(".zip"):
            extracted = extract_zip(archive_path, data_dir)
        else:
            return InstallResult(False, "Unsupported archive format", self.name)

        if not extracted:
            if archive_path.exists():
                archive_path.unlink()
            return InstallResult(False, "Extraction failed, cache cleared", self.name)

        executable = self.platform.find_exe(extracted, tool.name)
        if not executable:
            return InstallResult(False, "Executable not found in archive", self.name)

        make_executable(executable)

        bin_dir = Path(self.paths["quick_env_bin"])
        bin_dir.mkdir(parents=True, exist_ok=True)

        if tool.bin_entries:
            entries = tool.bin_entries
        else:
            entries = [tool.name]

        for entry_name in entries:
            exe = self._find_specific_executable(extracted, entry_name)
            if exe:
                make_executable(exe)
                bin_path = bin_dir / self.platform.bin_name(entry_name)
                self.platform.remove_bin_entry(bin_path)
                relative_target = os.path.relpath(exe, bin_dir)
                self.platform.install_bin_entry(bin_path, Path(relative_target))

        self._cleanup_old_versions(tool, version)

        return InstallResult(
            True,
            f"Installed {tool.display_name} {release.tag_name}",
            self.name,
            release.tag_name,
        )

    def _find_specific_executable(
        self, data_dir: Path, entry_name: str
    ) -> Optional[Path]:
        """查找指定名称的可执行文件"""
        exe_name = self.platform.exe_name(entry_name)
        exe_path = data_dir / exe_name
        if exe_path.exists():
            return exe_path

        for pattern in ["*", "bin/*", f"{entry_name}*"]:
            for path in data_dir.rglob(pattern):
                if path.is_file() and self.platform.find_exe(path.parent, entry_name):
                    return path
        return None

    def _install_config(self, tool: Tool) -> InstallResult:
        dest = self._get_config_dest(tool)
        if not dest:
            return InstallResult(False, "Invalid config path", self.name)

        if dest.exists():
            try:
                run_subprocess(
                    ["git", "-C", str(dest), "pull"], check=True, capture_output=True
                )
                return InstallResult(True, f"Updated {tool.display_name}", self.name)
            except subprocess.CalledProcessError:
                return InstallResult(
                    False, f"Failed to update {tool.display_name}", self.name
                )

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            run_subprocess(
                ["git", "clone", f"https://github.com/{tool.config_repo}", str(dest)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            return InstallResult(False, f"Clone failed: {e.stderr}", self.name)

        if tool.config_link:
            user_link = Path(os.path.expanduser(tool.config_link))
            user_link.parent.mkdir(parents=True, exist_ok=True)
            if user_link.exists() or user_link.is_symlink():
                if user_link.is_symlink():
                    user_link.unlink()
                else:
                    backup = user_link.with_suffix(".bak")
                    self.platform.move(Path(str(user_link)), Path(str(backup)))
            if dest.is_dir():
                self.platform.create_symlink(dest, user_link)

        return InstallResult(True, f"Installed {tool.display_name}", self.name)

    def uninstall(self, tool: Tool) -> InstallResult:
        if tool.config_repo:
            return InstallResult(
                False, "Use git_clone uninstall for config repos", self.name
            )

        bin_path = self._get_bin_path(tool)
        self.platform.remove_bin_entry(bin_path)

        data_dir = Path(self.paths["quick_env_tools"])
        if data_dir.exists():
            prefix = f"{tool.name}_"
            for item in data_dir.iterdir():
                if item.is_dir() and item.name.startswith(prefix):
                    self.platform.rmtree(item)

        result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
        log_uninstall(tool.display_name, True, result.message)
        return result

    def _get_config_dest(self, tool: Tool) -> Optional[Path]:
        if not tool.config_repo:
            return None
        return Path(self.paths["quick_env_config"]) / tool.name


class PackageManagerInstaller(Installer):
    name = "system"
    priority = 30

    def __init__(self):
        self.manager = detect_package_manager()
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return True

    def is_installed(self, tool: Tool) -> bool:
        cmd_name = get_command_name(tool)
        which_path = self.platform.which(cmd_name)
        if not which_path:
            return False
        quick_env_bin = Path(self.paths["quick_env_bin"]).resolve()
        tool_path = Path(which_path).resolve()
        return tool_path.parent.resolve() != quick_env_bin

    def get_version(self, tool: Tool) -> Optional[str]:
        cmd_name = get_command_name(tool)
        which_path = self.platform.which(cmd_name)
        if not which_path:
            return None
        try:
            result = run_subprocess(
                [cmd_name, "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                output = result.stdout + result.stderr
                match = re.search(r"(\d+\.\d+\.?\d*)", output)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def install(self, tool: Tool) -> InstallResult:
        if not self.manager or not tool.package_name:
            return InstallResult(
                False, "Tool does not support package manager installation", self.name
            )

        cmd = PACKAGE_MANAGER_COMMANDS.get(self.manager, {}).get("install", "")
        cmd = cmd.format(pkg=tool.package_name)
        if not cmd:
            return InstallResult(False, "Package manager not configured", self.name)

        try:
            result = run_subprocess(
                cmd, shell=True, check=True, capture_output=True, text=True
            )
            version = self.get_version(tool)
            return InstallResult(
                True,
                f"Installed {tool.display_name} via {self.manager}",
                self.name,
                version,
            )
        except subprocess.CalledProcessError as e:
            return InstallResult(False, f"Installation failed: {e.stderr}", self.name)

    def uninstall(self, tool: Tool) -> InstallResult:
        if not self.manager or not tool.package_name:
            result = InstallResult(
                False, "Tool does not support uninstall via package manager", self.name
            )
            log_uninstall(tool.display_name, False, result.message)
            return result

        uninstall_cmds = {
            "brew": f"brew uninstall {tool.package_name}",
            "apt": f"sudo apt remove -y {tool.package_name}",
            "dnf": f"sudo dnf remove -y {tool.package_name}",
            "yum": f"sudo yum remove -y {tool.package_name}",
            "pacman": f"sudo pacman -R --noconfirm {tool.package_name}",
            "zypper": f"sudo zypper remove -y {tool.package_name}",
            "winget": f"winget uninstall --id {tool.package_name}",
        }

        cmd = uninstall_cmds.get(self.manager)
        if not cmd:
            result = InstallResult(
                False,
                f"Cannot uninstall {tool.package_name} via {self.manager}",
                self.name,
            )
            log_uninstall(tool.display_name, False, result.message)
            return result

        try:
            run_subprocess(cmd, shell=True, check=True, capture_output=True, text=True)
            result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
            log_uninstall(tool.display_name, True, result.message)
            return result
        except subprocess.CalledProcessError as e:
            result = InstallResult(False, f"Uninstall failed: {e.stderr}", self.name)
            log_uninstall(tool.display_name, False, result.message)
            return result


class DotfileInstaller(Installer):
    name = "dotfile"
    priority = 10

    def __init__(self):
        self.platform = detect_platform()
        self.paths = get_env_paths()

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
        if tool.is_dotfile():
            return InstallResult(
                False, "Use dotfile uninstall for config repos", self.name
            )

        bin_path = self._get_bin_path(tool)
        self.platform.remove_bin_entry(bin_path)

        data_dir = Path(self.paths["quick_env_tools"])
        if data_dir.exists():
            prefix = f"{tool.name}_"
            for item in data_dir.iterdir():
                if item.is_dir() and item.name.startswith(prefix):
                    self.platform.rmtree(item)

        result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
        log_uninstall(tool.display_name, True, result.message)
        return result

        for link_config in tool.links:
            dest_path = Path(os.path.expanduser(link_config.to))
            self._remove_link(dest_path)

        dest = self._get_dotfiles_dir(tool)
        if dest.exists():
            self.platform.rmtree(dest)

        result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
        log_uninstall(tool.display_name, True, result.message)
        return result


class InstallerRegistry:
    """安装器注册表，支持内置 + 插件扩展"""

    _builtin: dict[str, type] = {}
    _extensions: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, installer_class: type):
        """注册安装器（内置或插件扩展）"""
        if not issubclass(installer_class, Installer):
            raise TypeError(f"{installer_class} must inherit from Installer")
        cls._extensions[name] = installer_class

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """获取安装器类"""
        return cls._builtin.get(name) or cls._extensions.get(name)

    @classmethod
    def create(cls, name: str) -> Optional[Installer]:
        """创建安装器实例"""
        installer_class = cls.get(name)
        return installer_class() if installer_class else None

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有可用的安装器"""
        return list(set(cls._builtin.keys()) | set(cls._extensions.keys()))

    @classmethod
    def load_plugins(cls, plugin_dir: Optional[Path] = None):
        """从插件目录加载插件"""
        if plugin_dir is None:
            plugin_dir = Path.home() / ".quick-env" / "plugins"

        if not plugin_dir.exists():
            return

        import sys

        if str(plugin_dir) not in sys.path:
            sys.path.insert(0, str(plugin_dir))

        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            try:
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    plugin_file.stem, plugin_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
            except Exception:
                pass


class CustomScriptInstaller(Installer):
    name = "custom_script"
    priority = 5

    def __init__(self):
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return True

    def is_installed(self, tool: Tool) -> bool:
        if not tool.custom_script:
            return False
        cmd_name = tool.name
        which_path = self.platform.which(cmd_name)
        if which_path:
            quick_env_bin = Path(self.paths["quick_env_bin"]).resolve()
            tool_path = Path(which_path).resolve()
            return tool_path.parent.resolve() == quick_env_bin
        return False

    def get_version(self, tool: Tool) -> Optional[str]:
        if tool.custom_version_cmd:
            try:
                result = run_subprocess(
                    tool.custom_version_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    version_match = re.search(r"(\d+\.\d+\.\d+[\d.a-z-]*)", output)
                    if version_match:
                        return version_match.group(1)
                    return output.split()[0] if output else None
            except Exception:
                pass
        return None

    def install(self, tool: Tool) -> InstallResult:
        script = tool.custom_script
        if isinstance(script, dict):
            script = script.get(self.platform.platform_name) or script.get("default")
        if not script:
            return InstallResult(
                False, "No custom_script defined for this platform", self.name
            )

        try:
            log_install(
                tool.display_name, self.name, "Installing with custom script..."
            )
            result = run_subprocess(
                script,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                version = self.get_version(tool)
                log_install(tool.display_name, self.name, f"Installed successfully")
                return InstallResult(
                    True, f"Installed {tool.display_name}", self.name, version
                )
            else:
                error_msg = (
                    result.stderr.strip() or result.stdout.strip() or "Unknown error"
                )
                return InstallResult(False, error_msg, self.name)
        except subprocess.TimeoutExpired:
            return InstallResult(False, "Installation timed out", self.name)
        except Exception as e:
            return InstallResult(False, str(e), self.name)

    def uninstall(self, tool: Tool) -> InstallResult:
        return InstallResult(False, "Use custom script to uninstall", self.name)


class CustomURLInstaller(Installer):
    name = "custom_url"
    priority = 10

    def __init__(self):
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return (
            self.platform.which("curl") is not None
            or self.platform.which("wget") is not None
        )

    def _get_data_dir(self, tool: Tool, version: str = "latest") -> Path:
        clean_version = version.lstrip("v").replace("/", "-")
        return Path(self.paths["quick_env_tools"]) / f"{tool.name}_{clean_version}"

    def _get_bin_path(self, tool: Tool) -> Path:
        return Path(self.paths["quick_env_bin"]) / self.platform.bin_name(tool.name)

    def is_installed(self, tool: Tool) -> bool:
        if not tool.custom_url:
            return False
        bin_dir = Path(self.paths["quick_env_bin"])
        return self.platform.is_bin_valid(bin_dir, tool.name)

    def get_version(self, tool: Tool) -> Optional[str]:
        if tool.custom_version_cmd:
            try:
                result = run_subprocess(
                    tool.custom_version_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    version_match = re.search(r"(\d+\.\d+\.\d+[\d.a-z-]*)", output)
                    if version_match:
                        return version_match.group(1)
                    return output.split()[0] if output else None
            except Exception:
                pass

        bin_path = self._get_bin_path(tool)
        if bin_path.exists() or bin_path.is_symlink():
            executable = self.platform.get_bin_executable_path(
                Path(self.paths["quick_env_bin"]), tool.name
            )
            if executable and executable.parent.exists():
                data_dir = executable.parent
                if "_" in data_dir.name:
                    return data_dir.name.split("_", 1)[1]
        return None

    def install(self, tool: Tool) -> InstallResult:
        url = tool.get_custom_url(self.platform.platform_name)
        if not url:
            return InstallResult(
                False, "No custom_url defined for this platform", self.name
            )

        try:
            cache_dir = Path(self.paths["quick_env_cache"])
            cache_dir.mkdir(parents=True, exist_ok=True)

            filename = url.split("/")[-1].split("?")[0]
            cache_path = cache_dir / filename

            log_install(tool.display_name, self.name, f"Downloading from {url}...")
            success = download_file(url, cache_path)
            if not success:
                return InstallResult(False, f"Failed to download {url}", self.name)

            data_dir = self._get_data_dir(tool)
            data_dir.mkdir(parents=True, exist_ok=True)

            if tool.custom_url_extract:
                if filename.endswith(".tar.gz") or filename.endswith(".tgz"):
                    extract_tarball(cache_path, data_dir)
                elif filename.endswith(".zip"):
                    extract_zip(cache_path, data_dir)
                else:
                    self.platform.copy2(cache_path, data_dir / tool.name)
            else:
                bin_path = data_dir / tool.name
                self.platform.copy2(cache_path, bin_path)
                make_executable(bin_path)

            bin_path = self._get_bin_path(tool)
            target_exe = self._find_executable(data_dir, tool.name)
            if target_exe:
                if tool.bin_entries:
                    for entry_name in tool.bin_entries:
                        exe = self._find_specific_executable(data_dir, entry_name)
                        if exe:
                            entry_bin_path = Path(
                                self.paths["quick_env_bin"]
                            ) / self.platform.bin_name(entry_name)
                            self.platform.remove_bin_entry(entry_bin_path)
                            self.platform.install_bin_entry(entry_bin_path, exe)
                else:
                    self.platform.install_bin_entry(bin_path, target_exe)

            version = self.get_version(tool)
            log_install(tool.display_name, self.name, f"Installed successfully")
            return InstallResult(
                True, f"Installed {tool.display_name}", self.name, version
            )

        except Exception as e:
            return InstallResult(False, str(e), self.name)

    def _find_executable(self, data_dir: Path, tool_name: str) -> Optional[Path]:
        exe_name = self.platform.exe_name(tool_name)
        exe_path = data_dir / exe_name
        if exe_path.exists():
            return exe_path

        for pattern in ["*", "bin/*", f"{tool_name}*"]:
            for path in data_dir.rglob(pattern):
                if path.is_file() and self.platform.find_exe(path.parent, tool_name):
                    return path
        return None

    def _find_specific_executable(
        self, data_dir: Path, entry_name: str
    ) -> Optional[Path]:
        """查找指定名称的可执行文件"""
        exe_name = self.platform.exe_name(entry_name)
        exe_path = data_dir / exe_name
        if exe_path.exists():
            return exe_path

        for pattern in ["*", "bin/*", f"{entry_name}*"]:
            for path in data_dir.rglob(pattern):
                if path.is_file() and self.platform.find_exe(path.parent, entry_name):
                    return path
        return None

    def uninstall(self, tool: Tool) -> InstallResult:
        bin_path = self._get_bin_path(tool)
        self.platform.remove_bin_entry(bin_path)

        for data_dir in Path(self.paths["quick_env_tools"]).glob(f"{tool.name}_*"):
            if data_dir.is_dir():
                self.platform.rmtree(data_dir)

        return InstallResult(True, f"Uninstalled {tool.display_name}", self.name)


InstallerRegistry._builtin = {
    "github": GitHubInstaller,
    "package_manager": PackageManagerInstaller,
    "system": PackageManagerInstaller,
    "dotfile": DotfileInstaller,
    "git_clone": DotfileInstaller,
    "custom_script": CustomScriptInstaller,
    "custom_url": CustomURLInstaller,
}


class InstallerFactory:
    _instances: dict = {}

    @classmethod
    def get_installer(cls, name: str) -> Optional[Installer]:
        if name in cls._instances:
            return cls._instances[name]

        installer = InstallerRegistry.create(name)
        if installer:
            cls._instances[name] = installer
            return installer
        return None

    @classmethod
    def is_tool_available_in_system(cls, tool: Tool) -> bool:
        """检查工具命令是否在系统 PATH 中可用（不考虑 quick-env/bin）"""
        from .platform import detect_platform

        platform = detect_platform()
        cmd_name = get_command_name(tool)
        which_path = platform.which(cmd_name)
        if not which_path:
            return False

        quick_env_bin = Path(get_env_paths()["quick_env_bin"]).resolve()
        tool_path = Path(which_path).resolve()
        return tool_path.parent.resolve() != quick_env_bin

    @classmethod
    def get_all_installers(cls) -> List[Installer]:
        all_names = InstallerRegistry.list_all()
        installers = []
        for name in all_names:
            installer = cls.get_installer(name)
            if installer and installer.is_available():
                installers.append(installer)
        return installers

    @classmethod
    def get_best_installer(cls, tool: Tool) -> Optional[Installer]:
        from .platform import detect_platform

        platform = detect_platform()
        platform_key = platform.platform_name
        platform_arch = platform.platform_arch

        # 检查工具是否支持当前平台
        if not tool.is_platform_supported(platform_key, platform_arch):
            return None

        if tool.is_dotfile():
            return cls.get_installer("dotfile")

        if tool.custom_script:
            if tool.is_installer_supported(
                platform_key, "custom_script", platform_arch
            ):
                return cls.get_installer("custom_script")
            return None

        available = []
        for name in tool.installable_by:
            # 检查安装方式是否在当前平台上支持
            if not tool.is_installer_supported(platform_key, name, platform_arch):
                continue

            installer = cls.get_installer(name)
            if installer and installer.is_available():
                priority = tool.get_priority(platform_key, name, installer.priority)
                available.append((installer, priority))

        available.sort(key=lambda x: x[1])
        return available[0][0] if available else None

    @classmethod
    def detect_tool(cls, tool: Tool) -> ToolDetection:
        from .platform import detect_platform

        detection = ToolDetection(tool_name=tool.name)
        quick_env_bin = Path(get_env_paths()["quick_env_bin"]).resolve()
        platform = detect_platform()

        for installer in cls.get_all_installers():
            if not installer.is_available():
                continue
            if installer.is_installed(tool):
                cmd_name = get_command_name(tool)
                which_path = platform.which(cmd_name)
                is_current = False
                if which_path:
                    tool_path = Path(which_path).resolve()
                    if installer.name in ("github", "custom_url"):
                        is_current = tool_path.parent.resolve() == quick_env_bin
                    else:
                        is_current = True

                version = installer.get_version(tool)
                detection.sources.append(
                    SourceInfo(
                        name=installer.name,
                        path=str(which_path) if which_path else "unknown",
                        version=version,
                        is_current=is_current,
                    )
                )
                if is_current:
                    detection.current_source = installer.name
                detection.installed = True

        detection.sources.sort(key=lambda x: not x.is_current)
        return detection


def install_parallel(
    tools: List[Tool], force: bool = False, max_workers: int = 4
) -> List[InstallResult]:
    """并行安装多个工具"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from .logger import log_install

    results = []

    def install_single(tool: Tool) -> InstallResult:
        installer = InstallerFactory.get_best_installer(tool)
        if not installer:
            return InstallResult(
                False, f"No installer available for {tool.display_name}", "none"
            )

        if not force and installer.is_installed(tool):
            return InstallResult(
                True, f"{tool.display_name} is already installed", installer.name
            )

        return installer.install(tool)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tool = {executor.submit(install_single, tool): tool for tool in tools}
        for future in as_completed(future_to_tool):
            tool = future_to_tool[future]
            try:
                result = future.result()
                results.append(result)
                log_install(
                    tool.display_name,
                    result.version,
                    result.method,
                    result.success,
                    result.message,
                )
            except Exception as e:
                result = InstallResult(False, f"Installation failed: {e}", "none")
                results.append(result)
                log_install(tool.display_name, None, "none", False, result.message)

    return results
