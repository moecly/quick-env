"""Custom URL 安装器"""
import re
import subprocess
from pathlib import Path
from typing import Optional

from ..downloader import download_file, extract_tarball, extract_zip, make_executable
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


@installer("custom_url", priority=10)
class CustomURLInstaller(Installer):
    name = "custom_url"

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

    def _get_version_fallback(self, tool: Tool) -> Optional[str]:
        tools_dir = Path(self.paths["quick_env_tools"])
        prefix = f"{tool.name}_"
        for item in tools_dir.iterdir():
            if item.is_dir() and item.name.startswith(prefix):
                if "_" in item.name:
                    return item.name.split("_", 1)[1]
        return None

    def install(self, tool: Tool) -> InstallResult:
        url = tool.get_custom_url(
            self.platform.platform_name, self.platform.platform_arch
        )
        if not url:
            return InstallResult(
                False, "No custom_url defined for this platform", self.name
            )

        try:
            cache_dir = Path(self.paths["quick_env_cache"])
            cache_dir.mkdir(parents=True, exist_ok=True)

            filename = url.split("/")[-1].split("?")[0]
            cache_path = cache_dir / filename

            log_install(
                tool.display_name, self.name, "INFO", "", f"Downloading from {url}..."
            )
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
            log_install(
                tool.display_name, self.name, "INFO", version, "Installed successfully"
            )
            return InstallResult(
                True, f"Installed {tool.display_name}", self.name, version
            )

        except Exception as e:
            return InstallResult(False, str(e), self.name)

    def _find_executable(self, data_dir: Path, tool_name: str) -> Optional[Path]:
        return self.platform.find_exe(data_dir, tool_name)

    def _find_specific_executable(
        self, data_dir: Path, entry_name: str
    ) -> Optional[Path]:
        return self.platform.find_exe(data_dir, entry_name)

    def uninstall(self, tool: Tool) -> InstallResult:
        bin_path = self._get_bin_path(tool)
        self.platform.remove_bin_entry(bin_path)

        for data_dir in Path(self.paths["quick_env_tools"]).glob(f"{tool.name}_*"):
            if data_dir.is_dir():
                self.platform.rmtree(data_dir)

        return InstallResult(True, f"Uninstalled {tool.display_name}", self.name)