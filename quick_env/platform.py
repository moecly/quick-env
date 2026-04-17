"""Platform detection utilities."""

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class Platform:
    system: str
    arch: str
    platform_name: str
    arch_name: str

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

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
        return self.is_linux and os.path.exists("/proc/version") and "microsoft" in open("/proc/version").read().lower()


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
    )


def detect_package_manager() -> Optional[str]:
    if shutil.which("brew"):
        return "brew"
    elif shutil.which("apt"):
        return "apt"
    elif shutil.which("apt-get"):
        return "apt"
    elif shutil.which("dnf"):
        return "dnf"
    elif shutil.which("yum"):
        return "yum"
    elif shutil.which("pacman"):
        return "pacman"
    elif shutil.which("zypper"):
        return "zypper"
    elif shutil.which("winget"):
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
        "data_home": os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local")),
        "bin_home": os.environ.get("XDG_BIN_HOME", os.path.join(home, ".local", "bin")),
        "quick_env_home": os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local")), "quick-env"),
        "quick_env_bin": os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local")), "quick-env", "bin"),
        "quick_env_cache": os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local")), "quick-env", "cache"),
        "quick_env_logs": os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local")), "quick-env", "logs"),
        "quick_env_config": os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local")), "quick-env", "config"),
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
