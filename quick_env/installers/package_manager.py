"""Package Manager 安装器"""
import re
import subprocess
from pathlib import Path
from typing import Optional

from ..installer import (
    InstallResult,
    Installer,
    detect_package_manager,
    detect_platform,
    get_command_name,
    get_env_paths,
    installer,
    log_uninstall,
    run_subprocess,
)
from ..platform import PACKAGE_MANAGER_COMMANDS
from ..tools import Tool


@installer("package_manager", priority=30)
@installer("system", priority=30)
class PackageManagerInstaller(Installer):
    name = "system"

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
            self._create_bin_entry(tool)
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