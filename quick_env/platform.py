"""Platform detection utilities."""

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Platform:
    system: str
    arch: str
    platform_name: str
    arch_name: str
    platform_arch: str = ""  # 如 windows_x86_64, linux_arm64

    def __post_init__(self):
        if not self.platform_arch:
            self.platform_arch = f"{self.platform_name}_{self.arch_name}"

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows" or self.is_git_bash

    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"

    @property
    def is_git_bash(self) -> bool:
        return "MINGW" in self.system or "MSYS" in self.system

    @property
    def is_wsl(self) -> bool:
        return (
            self.is_linux
            and os.path.exists("/proc/version")
            and "microsoft" in open("/proc/version").read().lower()
        )

    @property
    def is_msys(self) -> bool:
        return self.is_windows and ("MSYSTEM" in os.environ or "MSYS" in os.environ)

    def exe_name(self, name: str) -> str:
        if self.is_windows or self.is_msys:
            return f"{name}.exe"
        return name

    def bin_name(self, name: str) -> str:
        if self.is_msys:
            return f"{name}.cmd"
        return name

    def find_exe(self, directory: Path, name: str) -> Optional[Path]:
        exe = self.exe_name(name)
        path = directory / exe
        if path.exists():
            return path
        for p in directory.rglob(exe):
            if p.is_file():
                return p
        return None

    def get_all_bin_entries(self, bin_dir: Path, name: str) -> List[Path]:
        """获取所有可能的 bin 入口路径"""
        entries = []
        primary = bin_dir / self.bin_name(name)
        entries.append(primary)
        if self.is_msys:
            entries.append(primary.with_suffix(".sh"))
        return entries

    def get_bin_entry(self, bin_dir: Path, name: str) -> Optional[Path]:
        """获取主要的 bin 入口路径（优先标准入口）"""
        primary = bin_dir / self.bin_name(name)
        if primary.exists():
            return primary
        if self.is_msys:
            sh_path = primary.with_suffix(".sh")
            if sh_path.exists():
                return sh_path
        return None

    def is_bin_installed(self, bin_dir: Path, name: str) -> bool:
        """检测 bin 入口是否存在"""
        return self.get_bin_entry(bin_dir, name) is not None

    def is_bin_valid(self, bin_dir: Path, name: str) -> bool:
        """检测 bin 入口是否有效（存在且非损坏）"""
        entry = self.get_bin_entry(bin_dir, name)
        if not entry:
            return False
        if self.is_msys:
            return entry.is_file()
        if entry.is_symlink():
            return self.is_symlink_valid(entry)
        return entry.exists()

    def which(self, cmd: str) -> Optional[str]:
        """检测命令是否存在，返回路径或 None"""
        result = shutil.which(cmd)
        if result:
            return result
        if self.is_msys:
            result = shutil.which(f"{cmd}.cmd")
            if result:
                return result
            result = shutil.which(f"{cmd}.sh")
            if result:
                return result
        return None

    def command_exists(self, cmd: str) -> bool:
        """检测命令是否存在"""
        return self.which(cmd) is not None

    def is_symlink(self, path: Path) -> bool:
        """检查路径是否是符号链接"""
        return path.is_symlink()

    def symlink_exists(self, path: Path) -> bool:
        """检查符号链接是否存在（包括目标是否有效）"""
        return path.exists()

    def is_symlink_valid(self, path: Path) -> bool:
        """检查符号链接是否有效（指向的目标存在）"""
        if not path.is_symlink():
            return False
        try:
            return path.resolve().exists()
        except Exception:
            return False

    def create_symlink(
        self, src: Path, dest: Path, target_is_directory: bool = False
    ) -> bool:
        """创建符号链接"""
        try:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            os.symlink(src, dest, target_is_directory)
            return True
        except OSError:
            return False

    def remove_path(self, path: Path) -> bool:
        """删除文件或符号链接"""
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
            return True
        except OSError:
            return False

    def rmtree(self, path: Path) -> bool:
        """递归删除目录"""
        try:
            if path.exists():
                shutil.rmtree(path)
            return True
        except OSError:
            return False

    def move(self, src: Path, dest: Path) -> bool:
        """移动文件或目录"""
        try:
            shutil.move(str(src), str(dest))
            return True
        except OSError:
            return False

    def copy2(self, src: Path, dest: Path) -> bool:
        """复制文件（保留元数据）"""
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return True
        except OSError:
            return False

    def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> bool:
        """创建目录"""
        try:
            path.mkdir(parents=parents, exist_ok=exist_ok)
            return True
        except OSError:
            return False

    def is_dir(self, path: Path) -> bool:
        """检查是否是目录"""
        return path.is_dir()

    def is_file(self, path: Path) -> bool:
        """检查是否是文件"""
        return path.is_file()

    def install_bin_entry(self, bin_path: Path, target: Path) -> None:
        if self.is_msys:
            target_str = str(target).replace("\\", "/")
            cmd_path = bin_path.with_suffix(".cmd")
            sh_path = bin_path.with_suffix(".sh")
            content = f'@echo off\n"{target_str}" %*\n'
            cmd_path.write_text(content)
            content = f'#!/bin/bash\n"{target_str}" "$@"\n'
            sh_path.write_text(content)
            os.chmod(sh_path, 0o755)
        else:
            os.symlink(target, bin_path)

    def remove_bin_entry(self, bin_path: Path) -> None:
        if bin_path.exists():
            bin_path.unlink()
        if self.is_msys:
            cmd_path = bin_path.with_suffix(".cmd")
            sh_path = bin_path.with_suffix(".sh")
            if cmd_path.exists():
                cmd_path.unlink()
            if sh_path.exists():
                sh_path.unlink()

    def get_bin_executable_path(self, bin_dir: Path, name: str) -> Optional[Path]:
        """获取 bin 入口指向的可执行文件路径"""
        entry = self.get_bin_entry(bin_dir, name)
        if not entry:
            return None
        if self.is_msys:
            return entry
        if entry.is_symlink():
            return entry.resolve()
        return entry


PLATFORM_MAP = {
    # Linux
    ("Linux", "x86_64"): ("linux", "x86_64"),
    ("Linux", "aarch64"): ("linux", "arm64"),
    ("Linux", "armv7l"): ("linux", "armv7"),
    ("Linux", "arm64"): ("linux", "arm64"),
    ("Linux", "i686"): ("linux", "i686"),
    # macOS
    ("Darwin", "x86_64"): ("darwin", "x86_64"),
    ("Darwin", "arm64"): ("darwin", "arm64"),
    # Git Bash / MinGW on Windows
    ("MINGW64_NT", "x86_64"): ("windows", "x86_64"),
    ("MSYS_NT", "x86_64"): ("windows", "x86_64"),
    ("MINGW64_NT", "arm64"): ("windows", "arm64"),
    # Native Windows (via CI)
    ("Windows", "AMD64"): ("windows", "x86_64"),
    ("Windows", "x86_64"): ("windows", "x86_64"),
    ("Windows", "arm64"): ("windows", "arm64"),
}


def detect_platform() -> Platform:
    system = platform.system()
    arch = platform.machine()

    if system == "Windows":
        arch = arch.lower()
        if arch == "amd64":
            arch = "x86_64"
        elif arch == "arm64":
            arch = "arm64"

    key = (system, arch)
    platform_name, arch_name = PLATFORM_MAP.get(key, (system.lower(), arch))

    return Platform(
        system=system,
        arch=arch,
        platform_name=platform_name,
        arch_name=arch_name,
        platform_arch=f"{platform_name}_{arch_name}",
    )


def detect_package_manager() -> Optional[str]:
    p = detect_platform()
    if p.which("brew"):
        return "brew"
    elif p.which("apt"):
        return "apt"
    elif p.which("apt-get"):
        return "apt"
    elif p.which("dnf"):
        return "dnf"
    elif p.which("yum"):
        return "yum"
    elif p.which("pacman"):
        return "pacman"
    elif p.which("zypper"):
        return "zypper"
    elif p.which("winget"):
        return "winget"
    return None


PACKAGE_MANAGER_COMMANDS = {
    "brew": {
        "install": "brew install {pkg}",
        "check": "brew list {pkg}",
    },
    "apt": {
        "install": "sudo apt install -y {pkg}",
        "check": "dpkg -l {pkg}",
    },
    "yum": {
        "install": "sudo yum install -y {pkg}",
        "check": "rpm -q {pkg}",
    },
    "dnf": {
        "install": "sudo dnf install -y {pkg}",
        "check": "rpm -q {pkg}",
    },
    "pacman": {
        "install": "sudo pacman -S --noconfirm {pkg}",
        "check": "pacman -Q {pkg}",
    },
    "zypper": {
        "install": "sudo zypper install -y {pkg}",
        "check": "rpm -q {pkg}",
    },
    "winget": {
        "install": "winget install --id {pkg} --silent",
        "check": "winget list --id {pkg}",
    },
}


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def get_env_paths() -> dict[str, str]:
    home = os.path.expanduser("~")
    return {
        "home": home,
        "quick_env_home": os.path.join(home, ".quick-env"),
        "quick_env_bin": os.path.join(home, ".quick-env", "bin"),
        "quick_env_cache": os.path.join(home, ".quick-env", "cache"),
        "quick_env_tools": os.path.join(home, ".quick-env", "tools"),
        "quick_env_dotfiles": os.path.join(home, ".quick-env", "dotfiles"),
        "quick_env_logs": os.path.join(home, ".quick-env", "logs"),
        "quick_env_config": os.path.join(home, ".quick-env", "configs"),
    }


if __name__ == "__main__":
    p = detect_platform()
    print(f"System: {p.system}")
    print(f"Arch: {p.arch}")
    print(f"Platform: {p.platform_name}")
    print(f"Arch Name: {p.arch_name}")
    print(f"Is WSL: {p.is_wsl}")
    print(f"Is Git Bash: {p.is_git_bash}")
    print(f"Package Manager: {detect_package_manager()}")
