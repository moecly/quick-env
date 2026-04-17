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
from .downloader import download_file, extract_tarball, extract_zip, find_executable_in_dir, make_executable


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

    def detect(self, tool: Tool) -> ToolDetection:
        detection = ToolDetection(tool_name=tool.name)
        if self.is_installed(tool):
            detection.installed = True
            path = self._get_install_path(tool)
            version = self.get_version(tool)
            is_current = self._is_current_path(path)
            detection.sources.append(SourceInfo(
                name=self.name,
                path=str(path) if path else "unknown",
                version=version,
                is_current=is_current,
            ))
            if is_current:
                detection.current_source = self.name
        return detection

    def _get_install_path(self, tool: Tool) -> Optional[Path]:
        return None

    def _is_current_path(self, path: Optional[Path]) -> bool:
        if not path:
            return False
        which_path = shutil.which(tool.name if 'tool' in dir() else "")
        if not which_path:
            return False
        return Path(which_path).resolve() == path.resolve()


class GitHubInstaller(Installer):
    name = "github"
    priority = 10

    def __init__(self):
        self.api = GitHubAPI()
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return shutil.which("curl") is not None or shutil.which("wget") is not None

    def is_installed(self, tool: Tool) -> bool:
        if tool.config_repo:
            config_path = self._get_config_dest(tool)
            return config_path.exists() if config_path else False
        bin_path = Path(self.paths["quick_env_bin"]) / tool.name
        return bin_path.exists()

    def get_version(self, tool: Tool) -> Optional[str]:
        if tool.config_repo:
            return self._get_git_version(tool)
        if tool.repo:
            try:
                release = self.api.get_latest_release(tool.repo)
                return release.tag_name
            except Exception:
                return self._get_binary_version(tool)
        return None

    def _get_binary_version(self, tool: Tool) -> Optional[str]:
        bin_path = Path(self.paths["quick_env_bin"]) / tool.name
        if bin_path.exists():
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

    def install(self, tool: Tool) -> InstallResult:
        if tool.config_repo:
            return self._install_config(tool)
        if not tool.repo or not tool.asset_pattern:
            return InstallResult(False, "Tool does not support GitHub installation", self.name)
        return self._install_binary(tool)

    def _install_binary(self, tool: Tool) -> InstallResult:
        try:
            release = self.api.get_latest_release(tool.repo)
        except Exception as e:
            return InstallResult(False, f"Failed to fetch release: {e}", self.name)

        asset = self.api.find_asset(release, tool.asset_pattern, self.platform.platform_name, self.platform.arch_name)
        if not asset:
            return InstallResult(False, f"No asset found for {self.platform.platform_name}/{self.platform.arch_name}", self.name)

        cache_dir = Path(self.paths["quick_env_cache"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        archive_path = cache_dir / asset.name

        if not archive_path.exists():
            if not download_file(asset.browser_download_url, archive_path):
                return InstallResult(False, "Download failed", self.name)

        bin_dir = Path(self.paths["quick_env_bin"])
        bin_dir.mkdir(parents=True, exist_ok=True)

        if asset.name.endswith(".tar.gz") or asset.name.endswith(".tgz"):
            extracted = extract_tarball(archive_path, bin_dir)
        elif asset.name.endswith(".zip"):
            extracted = extract_zip(archive_path, bin_dir)
        else:
            return InstallResult(False, "Unsupported archive format", self.name)

        if not extracted:
            return InstallResult(False, "Extraction failed", self.name)

        executable = find_executable_in_dir(extracted, tool.name)
        if not executable:
            return InstallResult(False, "Executable not found in archive", self.name)

        make_executable(executable)
        dest = bin_dir / tool.name
        if dest.exists():
            dest.unlink()
        shutil.copy2(executable, dest)

        user_bin = Path(self.paths["bin_home"])
        user_bin.mkdir(parents=True, exist_ok=True)
        user_link = user_bin / tool.name
        if user_link.exists() or user_link.is_symlink():
            user_link.unlink()
        os.symlink(dest, user_link)

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
                check=True, capture_output=True, text=True
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
        bin_dir = Path(self.paths["quick_env_bin"])
        user_bin = Path(self.paths["bin_home"])

        dest = bin_dir / tool.name
        user_link = user_bin / tool.name

        if dest.exists():
            dest.unlink()
        if user_link.exists() or user_link.is_symlink():
            user_link.unlink()

        return InstallResult(True, f"Uninstalled {tool.display_name}", self.name)

    def _get_install_path(self, tool: Tool) -> Optional[Path]:
        if tool.config_repo:
            return self._get_config_dest(tool)
        return Path(self.paths["quick_env_bin"]) / tool.name

    def _get_config_dest(self, tool: Tool) -> Optional[Path]:
        if not tool.config_repo:
            return None
        return Path(self.paths["quick_env_config"]) / tool.name

    def detect(self, tool: Tool) -> ToolDetection:
        detection = ToolDetection(tool_name=tool.name)
        if self.is_installed(tool):
            detection.installed = True
            path = self._get_install_path(tool)
            version = self.get_version(tool)
            is_current = self._check_is_current(tool, path)
            detection.sources.append(SourceInfo(
                name=self.name,
                path=str(path) if path else "unknown",
                version=version,
                is_current=is_current,
            ))
            if is_current:
                detection.current_source = self.name
        return detection

    def _check_is_current(self, tool: Tool, path: Optional[Path]) -> bool:
        if not path:
            return False
        which_path = shutil.which(tool.name)
        if not which_path:
            return False
        return Path(which_path).resolve() == path.resolve()


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
        which_path = shutil.which(tool.name)
        if not which_path:
            return False
        quick_env_bin = Path(self.paths["quick_env_bin"]).resolve()
        tool_path = Path(which_path).resolve()
        if tool_path.parent.resolve() == quick_env_bin:
            return False
        if tool.package_name:
            cmd = PACKAGE_MANAGER_COMMANDS.get(self.manager, {}).get("check", "")
            cmd = cmd.format(pkg=tool.package_name)
            if cmd:
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    return result.returncode == 0
                except Exception:
                    pass
        return True

    def get_version(self, tool: Tool) -> Optional[str]:
        which_path = shutil.which(tool.name)
        if not which_path:
            return None
        try:
            result = subprocess.run([tool.name, "--version"], capture_output=True, text=True)
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
            return InstallResult(False, "Tool does not support uninstall via package manager", self.name)

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
            return InstallResult(False, f"Cannot uninstall {tool.package_name} via {self.manager}", self.name)

        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            return InstallResult(True, f"Uninstalled {tool.display_name}", self.name)
        except subprocess.CalledProcessError as e:
            return InstallResult(False, f"Uninstall failed: {e.stderr}", self.name)

    def _get_install_path(self, tool: Tool) -> Optional[Path]:
        which_path = shutil.which(tool.name)
        if which_path:
            return Path(which_path)
        return None

    def detect(self, tool: Tool) -> ToolDetection:
        detection = ToolDetection(tool_name=tool.name)
        if self.is_installed(tool):
            detection.installed = True
            path = self._get_install_path(tool)
            version = self.get_version(tool)
            is_current = not self._is_quick_env_path(tool)
            detection.sources.append(SourceInfo(
                name=self.name,
                path=str(path) if path else "system",
                version=version,
                is_current=is_current,
            ))
            if is_current:
                detection.current_source = self.name
        return detection

    def _is_quick_env_path(self, tool: Tool) -> bool:
        which_path = shutil.which(tool.name)
        if not which_path:
            return False
        quick_env_bin = Path(self.paths["quick_env_bin"]).resolve()
        tool_path = Path(which_path).resolve()
        return tool_path.parent.resolve() == quick_env_bin


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
                check=True, capture_output=True, text=True
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
            return InstallResult(False, "Tool does not support uninstall", self.name)

        dest = self._get_config_dest(tool)
        if dest and dest.exists():
            shutil.rmtree(dest)

        if tool.config_link:
            user_link = Path(os.path.expanduser(tool.config_link))
            if user_link.is_symlink():
                user_link.unlink()

        return InstallResult(True, f"Uninstalled {tool.display_name}", self.name)

    def _get_config_dest(self, tool: Tool) -> Optional[Path]:
        if not tool.config_repo:
            return None
        return Path(self.paths["quick_env_config"]) / tool.name

    def _get_install_path(self, tool: Tool) -> Optional[Path]:
        return self._get_config_dest(tool)


class InstallerFactory:
    _instances: dict = {}
    _detectors: dict = {}

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
                available.append(installer)

        available.sort(key=lambda x: x.priority)
        return available[0] if available else None

    @classmethod
    def detect_tool(cls, tool: Tool) -> ToolDetection:
        detection = ToolDetection(tool_name=tool.name)
        quick_env_bin = Path(get_env_paths()["quick_env_bin"]).resolve()

        for installer in cls.get_all_installers():
            if not installer.is_available():
                continue
            source_detection = installer.detect(tool)
            if source_detection.installed:
                for source in source_detection.sources:
                    is_current = False
                    if source.path and source.path != "unknown":
                        source_path = Path(source.path).resolve()
                        if source_path.parent.resolve() == quick_env_bin:
                            which_path = shutil.which(tool.name)
                            if which_path and Path(which_path).resolve() == source_path:
                                is_current = True
                        elif installer.name == "system":
                            which_path = shutil.which(tool.name)
                            if which_path and Path(which_path).resolve() == source_path:
                                is_current = True
                    detection.sources.append(source)
                    if is_current:
                        detection.current_source = installer.name
                detection.installed = True

        detection.sources.sort(key=lambda x: not x.is_current)
        return detection
