"""Installers for different installation methods."""

import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from .github import GitHubAPI, GitHubRelease
from .platform import Platform, detect_platform, detect_package_manager, PACKAGE_MANAGER_COMMANDS, get_env_paths
from .tools import Tool
from .downloader import download_file, extract_tarball, extract_zip, make_executable
from .logger import log_install, log_uninstall


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
        return tool.package_manager_commands.get(pm, tool.package_manager_commands.get("default", tool.name))
    return tool.name


def get_latest_from_package_manager(tool: Tool) -> Optional[str]:
    """从包管理器获取最新版本"""
    pm = detect_package_manager()
    if not pm or not tool.package_name:
        return None

    try:
        if pm == "apt":
            result = subprocess.run(
                ["apt-cache", "policy", tool.package_name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(r"Candidate:\s*(\S+)", result.stdout)
                if match:
                    version = match.group(1)
                    if version and version != "(none)":
                        return version

        elif pm == "brew":
            result = subprocess.run(
                ["brew", "info", tool.package_name, "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                if data:
                    return data[0].get("versions", {}).get("stable") or data[0].get("versions", {}).get("bottle")

        elif pm == "dnf":
            result = subprocess.run(
                ["dnf", "list", tool.package_name, "--available"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(rf"{re.escape(tool.package_name)}.*?\s+(\S+)", result.stdout)
                if match:
                    return match.group(1)

        elif pm == "yum":
            result = subprocess.run(
                ["yum", "list", tool.package_name, "--available"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(rf"{re.escape(tool.package_name)}.*?\s+(\S+)", result.stdout)
                if match:
                    return match.group(1)

        elif pm == "pacman":
            result = subprocess.run(
                ["pacman", "-Si", tool.package_name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(r"Version\s*:\s*(\S+)", result.stdout)
                if match:
                    return match.group(1)

        elif pm == "zypper":
            result = subprocess.run(
                ["zypper", "info", tool.package_name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(r"Version\s*:\s*(\S+)", result.stdout)
                if match:
                    return match.group(1)

        elif pm == "winget":
            result = subprocess.run(
                ["winget", "list", "--id", tool.package_name],
                capture_output=True, text=True, timeout=30
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
    which_path = shutil.which(cmd_name)

    if not which_path:
        quick_env_bin = Path(get_env_paths()["quick_env_bin"])
        executable = current_platform.get_bin_executable_path(quick_env_bin, cmd_name)
        if executable and executable.exists():
            which_path = str(executable)

    if which_path:
        try:
            result = subprocess.run([which_path, "--version"], capture_output=True, text=True, timeout=5)
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
        return shutil.which("curl") is not None or shutil.which("wget") is not None

    def _get_data_dir(self, tool: Tool, version: str) -> Path:
        clean_version = self._sanitize_dirname(version.lstrip("v"))
        return Path(self.paths["quick_env_data"]) / f"{tool.name}_{clean_version}"

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
        return self.platform.is_bin_installed(bin_dir, tool.name)

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
            result = subprocess.run([str(bin_path), "--version"], capture_output=True, text=True)
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
            result = subprocess.run(
                ["git", "-C", str(dest), "log", "-1", "--format=%ci"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()[:10]
        except Exception:
            pass
        return None

    def _cleanup_old_versions(self, tool: Tool, current_version: str) -> None:
        data_dir = Path(self.paths["quick_env_data"])
        if not data_dir.exists():
            return
        clean_current = self._sanitize_dirname(current_version.lstrip("v"))
        prefix = f"{tool.name}_"
        for item in data_dir.iterdir():
            if item.is_dir() and item.name.startswith(prefix):
                version = self._parse_version_from_data_dir(item)
                if version and version != clean_current:
                    shutil.rmtree(item)

    def install(self, tool: Tool) -> InstallResult:
        if tool.config_repo:
            result = self._install_config(tool)
            log_install(tool.display_name, result.version, self.name, result.success, result.message)
            return result
        if not tool.repo or not tool.github_asset_patterns:
            result = InstallResult(False, "Tool does not support GitHub installation", self.name)
            log_install(tool.display_name, None, self.name, False, result.message)
            return result
        result = self._install_binary(tool)
        log_install(tool.display_name, result.version, self.name, result.success, result.message)
        return result

    def _install_binary(self, tool: Tool) -> InstallResult:
        try:
            release = self.api.get_latest_release(tool.repo)
        except Exception as e:
            return InstallResult(False, f"Failed to fetch release: {e}", self.name)

        version = release.tag_name.lstrip("v")

        if tool.github_asset_patterns:
            asset = self.api.find_asset_by_platform(
                release, tool.github_asset_patterns, self.platform.platform_name, self.platform.arch_name
            )
        else:
            return InstallResult(False, "No github_asset_patterns defined", self.name)

        if not asset:
            return InstallResult(False, f"No asset found for {self.platform.platform_name}/{self.platform.arch_name}", self.name)

        cache_dir = Path(self.paths["quick_env_cache"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        archive_path = cache_dir / asset.name

        if not archive_path.exists():
            if not download_file(asset.browser_download_url, archive_path):
                return InstallResult(False, "Download failed", self.name)

        data_dir = self._get_data_dir(tool, version)
        if data_dir.exists():
            shutil.rmtree(data_dir)
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
        bin_path = self._get_bin_path(tool)

        self.platform.remove_bin_entry(bin_path)

        relative_target = os.path.relpath(executable, bin_dir)
        self.platform.install_bin_entry(bin_path, Path(relative_target))

        self._cleanup_old_versions(tool, version)

        return InstallResult(True, f"Installed {tool.display_name} {release.tag_name}", self.name, release.tag_name)

    def _install_config(self, tool: Tool) -> InstallResult:
        dest = self._get_config_dest(tool)
        if not dest:
            return InstallResult(False, "Invalid config path", self.name)

        if dest.exists():
            try:
                subprocess.run(["git", "-C", str(dest), "pull"], check=True, capture_output=True)
                return InstallResult(True, f"Updated {tool.display_name}", self.name)
            except subprocess.CalledProcessError:
                return InstallResult(False, f"Failed to update {tool.display_name}", self.name)

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", f"https://github.com/{tool.config_repo}", str(dest)],
                check=True, capture_output=True
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
                    shutil.move(str(user_link), str(backup))
            if dest.is_dir():
                os.symlink(dest, user_link)

        return InstallResult(True, f"Installed {tool.display_name}", self.name)

    def uninstall(self, tool: Tool) -> InstallResult:
        if tool.config_repo:
            return InstallResult(False, "Use git_clone uninstall for config repos", self.name)

        bin_path = self._get_bin_path(tool)
        self.platform.remove_bin_entry(bin_path)

        data_dir = Path(self.paths["quick_env_data"])
        if data_dir.exists():
            prefix = f"{tool.name}_"
            for item in data_dir.iterdir():
                if item.is_dir() and item.name.startswith(prefix):
                    shutil.rmtree(item)

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
        which_path = shutil.which(cmd_name)
        if not which_path:
            return False
        quick_env_bin = Path(self.paths["quick_env_bin"]).resolve()
        tool_path = Path(which_path).resolve()
        return tool_path.parent.resolve() != quick_env_bin

    def get_version(self, tool: Tool) -> Optional[str]:
        cmd_name = get_command_name(tool)
        which_path = shutil.which(cmd_name)
        if not which_path:
            return None
        try:
            result = subprocess.run([cmd_name, "--version"], capture_output=True, text=True)
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
            return InstallResult(False, "Tool does not support package manager installation", self.name)

        cmd = PACKAGE_MANAGER_COMMANDS.get(self.manager, {}).get("install", "")
        cmd = cmd.format(pkg=tool.package_name)
        if not cmd:
            return InstallResult(False, "Package manager not configured", self.name)

        try:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            version = self.get_version(tool)
            return InstallResult(True, f"Installed {tool.display_name} via {self.manager}", self.name, version)
        except subprocess.CalledProcessError as e:
            return InstallResult(False, f"Installation failed: {e.stderr}", self.name)

    def uninstall(self, tool: Tool) -> InstallResult:
        if not self.manager or not tool.package_name:
            result = InstallResult(False, "Tool does not support uninstall via package manager", self.name)
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
            result = InstallResult(False, f"Cannot uninstall {tool.package_name} via {self.manager}", self.name)
            log_uninstall(tool.display_name, False, result.message)
            return result

        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
            log_uninstall(tool.display_name, True, result.message)
            return result
        except subprocess.CalledProcessError as e:
            result = InstallResult(False, f"Uninstall failed: {e.stderr}", self.name)
            log_uninstall(tool.display_name, False, result.message)
            return result


class GitCloneInstaller(Installer):
    name = "git_clone"
    priority = 10

    def __init__(self):
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return shutil.which("git") is not None

    def is_installed(self, tool: Tool) -> bool:
        if not tool.config_repo:
            return False
        dest = self._get_config_dest(tool)
        return dest.exists() if dest else False

    def get_version(self, tool: Tool) -> Optional[str]:
        if not tool.config_repo:
            return None
        dest = self._get_config_dest(tool)
        if not dest or not dest.exists():
            return None
        try:
            result = subprocess.run(
                ["git", "-C", str(dest), "log", "-1", "--format=%ci"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()[:10]
        except Exception:
            pass
        return None

    def install(self, tool: Tool) -> InstallResult:
        if not tool.config_repo:
            return InstallResult(False, "Tool does not support git clone installation", self.name)

        dest = self._get_config_dest(tool)
        if not dest:
            return InstallResult(False, "Invalid config path", self.name)

        if dest.exists():
            try:
                subprocess.run(["git", "-C", str(dest), "pull"], check=True, capture_output=True)
                return InstallResult(True, f"Updated {tool.display_name}", self.name)
            except subprocess.CalledProcessError:
                return InstallResult(False, f"Failed to update {tool.display_name}", self.name)

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", f"https://github.com/{tool.config_repo}", str(dest)],
                check=True, capture_output=True
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
                    shutil.move(str(user_link), str(backup))
            if dest.is_dir():
                os.symlink(dest, user_link)

        return InstallResult(True, f"Installed {tool.display_name}", self.name)

    def uninstall(self, tool: Tool) -> InstallResult:
        if not tool.config_repo:
            result = InstallResult(False, "Tool does not support uninstall", self.name)
            log_uninstall(tool.display_name, False, result.message)
            return result

        dest = self._get_config_dest(tool)
        if dest and dest.exists():
            shutil.rmtree(dest)

        if tool.config_link:
            user_link = Path(os.path.expanduser(tool.config_link))
            if user_link.is_symlink():
                user_link.unlink()

        result = InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
        log_uninstall(tool.display_name, True, result.message)
        return result

    def _get_config_dest(self, tool: Tool) -> Optional[Path]:
        if not tool.config_repo:
            return None
        return Path(self.paths["quick_env_config"]) / tool.name


class InstallerFactory:
    _instances: dict = {}

    @classmethod
    def get_installer(cls, name: str) -> Optional[Installer]:
        if name in cls._instances:
            return cls._instances[name]

        installers = {
            "github": GitHubInstaller,
            "system": PackageManagerInstaller,
            "package_manager": PackageManagerInstaller,
            "git_clone": GitCloneInstaller,
        }

        if name in installers:
            cls._instances[name] = installers[name]()
            return cls._instances[name]
        return None

    @classmethod
    def is_tool_available_in_system(cls, tool: Tool) -> bool:
        """检查工具命令是否在系统 PATH 中可用（不考虑 quick-env/bin）"""
        cmd_name = get_command_name(tool)
        which_path = shutil.which(cmd_name)
        if not which_path:
            return False

        quick_env_bin = Path(get_env_paths()["quick_env_bin"]).resolve()
        tool_path = Path(which_path).resolve()
        return tool_path.parent.resolve() != quick_env_bin

    @classmethod
    def get_all_installers(cls) -> List[Installer]:
        return [
            cls.get_installer("github"),
            cls.get_installer("system"),
            cls.get_installer("git_clone"),
        ]

    @classmethod
    def get_best_installer(cls, tool: Tool) -> Optional[Installer]:
        available = []
        for name in tool.installable_by:
            installer = cls.get_installer(name)
            if installer and installer.is_available():
                priority = tool.get_priority(name, installer.priority)
                available.append((installer, priority))

        available.sort(key=lambda x: x[1])
        return available[0][0] if available else None

    @classmethod
    def detect_tool(cls, tool: Tool) -> ToolDetection:
        detection = ToolDetection(tool_name=tool.name)
        quick_env_bin = Path(get_env_paths()["quick_env_bin"]).resolve()

        for installer in cls.get_all_installers():
            if not installer.is_available():
                continue
            if installer.is_installed(tool):
                cmd_name = get_command_name(tool)
                which_path = shutil.which(cmd_name)
                is_current = False
                if which_path:
                    tool_path = Path(which_path).resolve()
                    if installer.name == "github":
                        is_current = tool_path.parent.resolve() == quick_env_bin
                    else:
                        is_current = True

                version = installer.get_version(tool)
                detection.sources.append(SourceInfo(
                    name=installer.name,
                    path=str(which_path) if which_path else "unknown",
                    version=version,
                    is_current=is_current,
                ))
                if is_current:
                    detection.current_source = installer.name
                detection.installed = True

        detection.sources.sort(key=lambda x: not x.is_current)
        return detection
