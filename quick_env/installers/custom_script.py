"""Custom Script 安装器"""
import re
import subprocess
from pathlib import Path
from typing import Optional

from ..installer import (
    InstallResult,
    Installer,
    detect_platform,
    get_env_paths,
    installer,
    log_install,
    run_subprocess,
)
from ..tools import Tool


@installer("custom_script", priority=5)
class CustomScriptInstaller(Installer):
    name = "custom_script"

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

    def install(self, tool: Tool) -> InstallResult:
        script = (
            tool.custom_script.get_script(
                self.platform.platform_arch, self.platform.platform_name
            )
            if tool.custom_script
            else None
        )
        if not script:
            return InstallResult(
                False, "No custom_script defined for this platform", self.name
            )

        try:
            log_install(
                tool.display_name,
                self.name,
                "INFO",
                "",
                "Installing with custom script...",
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
                self._create_bin_entry(tool)
                log_install(
                    tool.display_name,
                    self.name,
                    "INFO",
                    version,
                    "Installed successfully",
                )
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