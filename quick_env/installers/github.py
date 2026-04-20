"""GitHub Release 安装器"""
import re
import subprocess
from pathlib import Path
from typing import Optional

from ..installer import (
    InstallResult,
    Installer,
    detect_platform,
    download_file,
    extract_tarball,
    extract_zip,
    get_env_paths,
    installer,
    log_install,
    log_uninstall,
    make_executable,
    run_subprocess,
)
from ..tools import Tool
from ..github import GitHubAPI


@installer("github", priority=10)
class GitHubInstaller(Installer):
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
            level = "INFO" if result.success else "ERROR"
            log_install(
                tool.display_name,
                self.name,
                level,
                result.version or "",
                result.message,
            )
            return result
        if not tool.repo or not tool.github_asset_patterns:
            result = InstallResult(
                False, "Tool does not support GitHub installation", self.name
            )
            log_install(tool.display_name, self.name, "ERROR", "", result.message)
            return result
        result = self._install_binary(tool)
        level = "INFO" if result.success else "ERROR"
        log_install(
            tool.display_name, self.name, level, result.version or "", result.message
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

        bin_dir = Path(self.paths["quick_env_bin"])
        bin_dir.mkdir(parents=True, exist_ok=True)

        if tool.links:
            entries = tool.links
        elif tool.bin_entries:
            entries = tool.bin_entries
        else:
            entries = [tool.name]

        for entry in entries:
            if hasattr(entry, "glob"):
                glob = entry.glob
                bin_name = entry.to if entry.to else glob
            else:
                glob = entry
                bin_name = entry

            if "/" in glob or "\\" in glob:
                exe = extracted / glob
                if not exe.exists():
                    continue
            else:
                exe = self._find_specific_executable(extracted, glob)
                if not exe.exists():
                    continue

            make_executable(exe)
            bin_path = bin_dir / self.platform.bin_name(bin_name)
            self.platform.remove_bin_entry(bin_path)

            run_cmd = entry.run if hasattr(entry, "run") else ""

            if run_cmd:
                if exe and exe.exists():
                    run_parts = run_cmd.split()
                    run_parts[0] = str(exe.resolve())
                    run_cmd = " ".join(run_parts)
                self.platform.install_bin_entry(
                    bin_path, Path(run_cmd.split()[0]), run_cmd
                )
            else:
                if exe and exe.exists():
                    relative_target = os.path.relpath(exe, bin_dir)
                    self.platform.install_bin_entry(bin_path, Path(relative_target))
                else:
                    self.platform.install_bin_entry(bin_path, Path(glob))

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
        return self.platform.find_exe(data_dir, entry_name)

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