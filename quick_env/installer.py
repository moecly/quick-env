"""Installers for different installation methods."""

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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

    def is_installed(self, tool: Tool) -> bool:
        if tool.config_repo:
            config_path = self._get_config_dest(tool)
            return config_path.exists() if config_path else False
        bin_path = Path(self.paths["quick_env_bin"]) / tool.name
        return bin_path.exists()

    def get_version(self, tool: Tool) -> Optional[str]:
        if not tool.repo:
            return None
        try:
            release = self.api.get_latest_release(tool.repo)
            return release.tag_name
        except Exception:
            return None

    def install(self, tool: Tool) -> InstallResult:
        if not tool.repo or not tool.asset_pattern:
            return InstallResult(False, "Tool does not support GitHub installation", self.name)

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

    def _get_config_dest(self, tool: Tool) -> Optional[Path]:
        if not tool.config_repo:
            return None
        return Path(self.paths["quick_env_config"]) / tool.name


class PackageManagerInstaller(Installer):
    name = "package_manager"
    priority = 20

    def __init__(self):
        self.manager = detect_package_manager()
        self.platform = detect_platform()
        self.paths = get_env_paths()

    def is_available(self) -> bool:
        return self.manager is not None

    def is_installed(self, tool: Tool) -> bool:
        if not tool.package_name:
            return False
        if not self.manager:
            return False

        cmd = PACKAGE_MANAGER_COMMANDS.get(self.manager, {}).get("check", "")
        cmd = cmd.format(pkg=tool.package_name)
        if not cmd:
            return False

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            return False

    def get_version(self, tool: Tool) -> Optional[str]:
        if tool.package_name and shutil.which(tool.name):
            try:
                result = subprocess.run([tool.name, "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    output = result.stdout + result.stderr
                    import re
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
            result = subprocess.run(
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


class InstallerFactory:
    _instances: dict[str, Installer] = {}

    @classmethod
    def get_installer(cls, name: str) -> Optional[Installer]:
        if name in cls._instances:
            return cls._instances[name]

        installers = {
            "github": GitHubInstaller,
            "package_manager": PackageManagerInstaller,
            "git_clone": GitCloneInstaller,
        }

        if name in installers:
            cls._instances[name] = installers[name]()
            return cls._instances[name]
        return None

    @classmethod
    def get_all_installers(cls) -> list[Installer]:
        return [
            cls.get_installer("github"),
            cls.get_installer("package_manager"),
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
