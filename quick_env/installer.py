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

    # 使用自定义版本检测命令（优先）
    if tool.custom_version_cmd:
        try:
            result = run_subprocess(
                tool.custom_version_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout + result.stderr
            match = re.search(r"(\d+\.\d+\.?\d*)", output)
            if match:
                info.current = match.group(1)
        except Exception:
            pass
    elif which_path:
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
        priority = tool.get_priority("default", name, 100)
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


def _parse_version_output(output: str) -> Optional[str]:
    """从命令输出中解析版本号"""
    match = re.search(r"(\d+\.\d+\.?\d*)", output)
    return match.group(1) if match else None


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
    def install(self, tool: Tool) -> InstallResult:
        pass

    @abstractmethod
    def uninstall(self, tool: Tool) -> InstallResult:
        pass

    def get_version(self, tool: Tool) -> Optional[str]:
        """统一版本检测流程"""
        if tool.custom_version_cmd:
            return self._run_version_cmd(tool.custom_version_cmd)

        bin_path = self._find_bin_entry(tool.name)
        if bin_path:
            return self._run_binary_version(bin_path)

        return self._get_version_fallback(tool)

    def _find_bin_entry(self, name: str) -> Optional[Path]:
        paths = get_env_paths()
        bin_dir = Path(paths["quick_env_bin"])
        platform = detect_platform()
        return platform.get_bin_executable_path(bin_dir, name)

    def _run_version_cmd(self, cmd: str) -> Optional[str]:
        try:
            result = run_subprocess(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return _parse_version_output(result.stdout + result.stderr)
        except Exception:
            pass
        return None

    def _run_binary_version(self, bin_path: Path) -> Optional[str]:
        return self._run_version_cmd(str(bin_path) + " --version")

    def _get_version_fallback(self, tool: Tool) -> Optional[str]:
        """子类可覆盖的回退逻辑"""
        return None

    def _create_bin_entry(self, tool: Tool) -> None:
        """默认创建 bin 入口 - 子类可覆盖"""
        # Dotfiles 不需要
        if tool.type == "dotfile":
            return

        if not tool.links:
            return

        from .platform import detect_platform, get_env_paths

        platform = detect_platform()
        paths = get_env_paths()
        bin_dir = Path(paths["quick_env_bin"])

        for link in tool.links:
            cmd_name = link.to if link.to else link.glob
            run_cmd = link.run if link.run else ""

            # 使用 which 获取系统命令路径
            system_path = platform.which(cmd_name)

            bin_path = bin_dir / platform.bin_name(cmd_name)
            platform.remove_bin_entry(bin_path)

            if run_cmd:
                # 自定义运行命令
                if system_path:
                    # 替换命令名为实际系统路径
                    run_parts = run_cmd.split()
                    run_parts[0] = system_path
                    run_cmd = " ".join(run_parts)
                    platform.install_bin_entry(bin_path, Path(system_path), run_cmd)
                else:
                    # 系统路径不存在，使用命令名
                    platform.install_bin_entry(bin_path, Path(cmd_name), run_cmd)
            else:
                # 无自定义命令
                if system_path:
                    platform.install_bin_entry(bin_path, Path(system_path))
                else:
                    # 使用命令名（假设在 PATH 中）
                    platform.install_bin_entry(bin_path, Path(cmd_name))


class InstallerRegistry:
    """安装器注册表"""

    _installers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, installer_class: type):
        """注册安装器"""
        if not issubclass(installer_class, Installer):
            raise TypeError(f"{installer_class} must inherit from Installer")
        cls._installers[name] = installer_class

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """获取安装器类"""
        return cls._installers.get(name)

    @classmethod
    def create(cls, name: str) -> Optional[Installer]:
        """创建安装器实例"""
        installer_class = cls.get(name)
        return installer_class() if installer_class else None

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有可用的安装器"""
        return list(cls._installers.keys())


def installer(name: str, priority: int = 10):
    """安装器装饰器 - 自动注册"""

    def decorator(cls):
        InstallerRegistry.register(name, cls)
        cls.name = name
        cls.priority = priority
        return cls

    return decorator


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
                level = "INFO" if result.success else "ERROR"
                log_install(
                    tool.display_name,
                    result.method,
                    level,
                    result.version or "",
                    result.message,
                )
            except Exception as e:
                result = InstallResult(False, f"Installation failed: {e}", "none")
                results.append(result)
                log_install(tool.display_name, "none", "ERROR", "", result.message)

    return results
