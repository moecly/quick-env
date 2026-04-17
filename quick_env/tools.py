"""Tool definitions and metadata."""

from dataclasses import dataclass, field
from typing import Optional


def get_current_platform_key() -> str:
    """获取当前平台的标识键"""
    from .platform import detect_platform

    p = detect_platform()
    if p.is_windows:
        return "windows"
    elif p.is_macos:
        return "macos"
    elif p.is_linux:
        return "linux"
    return "default"


@dataclass
class LinkConfig:
    glob: str
    to: str = ""
    to_linux: str = ""
    to_macos: str = ""
    to_windows: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "LinkConfig":
        return cls(
            glob=data.get("glob", ""),
            to=data.get("to", ""),
            to_linux=data.get("to_linux", ""),
            to_macos=data.get("to_macos", ""),
            to_windows=data.get("to_windows", ""),
        )

    def get_target(self, platform: Optional[str] = None) -> str:
        """根据平台获取目标路径"""
        if platform is None:
            platform = get_current_platform_key()

        if platform == "windows" and self.to_windows:
            return self.to_windows
        if platform == "macos" and self.to_macos:
            return self.to_macos
        if platform == "linux" and self.to_linux:
            return self.to_linux
        return self.to


@dataclass
class Tool:
    name: str
    type: str = "binary"
    display_name: str = ""
    installable_by: list[str] = field(default_factory=list)
    priority: dict[str, int] = field(default_factory=dict)
    supported_on: dict[str, bool] = field(default_factory=dict)
    package_name: Optional[str] = None
    package_manager_commands: dict[str, str] = field(default_factory=dict)
    repo: Optional[str] = None
    github_asset_patterns: dict[str, str] = field(default_factory=dict)
    config_repo: Optional[str] = None
    config_branch: str = "main"
    links: list[LinkConfig] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    custom_script: Optional[str] = None
    custom_url: Optional[str] = None
    custom_url_extract: bool = True
    custom_version_cmd: Optional[str] = None
    bin_entries: list[str] = field(default_factory=list)

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases

    def get_github_asset_pattern(self, platform: str) -> str | None:
        if platform in self.github_asset_patterns:
            return self.github_asset_patterns[platform]
        if "default" in self.github_asset_patterns:
            return self.github_asset_patterns["default"]
        return None

    def get_custom_url(self, platform: str) -> str | None:
        """根据平台获取 custom_url"""
        if self.custom_url is None:
            return None
        if isinstance(self.custom_url, dict):
            if platform in self.custom_url:
                return self.custom_url[platform]
            if "default" in self.custom_url:
                return self.custom_url["default"]
            return None
        return self.custom_url

    def get_priority(
        self, platform: str, installer_name: str, default: int = 100
    ) -> int:
        """根据平台和安装方式获取优先级"""
        key = f"{platform}.{installer_name}"
        if key in self.priority:
            return self.priority[key]
        return self.priority.get(installer_name, default)

    def is_platform_supported(self, platform: str, platform_arch: str = "") -> bool:
        """检查工具在平台上是否支持（默认 True）"""
        if not self.supported_on:
            return True
        # 1. 最具体：platform_arch (如 windows_x86_64)
        if platform_arch and platform_arch in self.supported_on:
            return self.supported_on[platform_arch]
        # 2. platform (如 windows)
        return self.supported_on.get(platform, True)

    def is_installer_supported(
        self, platform: str, installer_name: str, platform_arch: str = ""
    ) -> bool:
        """检查安装方式在平台上是否支持"""
        if not self.supported_on:
            return True
        # 1. 最具体：installer.platform_arch (如 custom_url.windows_x86_64)
        if platform_arch:
            key = f"{installer_name}.{platform_arch}"
            if key in self.supported_on:
                return self.supported_on[key]
        # 2. installer.platform (如 custom_url.windows)
        key = f"{installer_name}.{platform}"
        if key in self.supported_on:
            return self.supported_on[key]
        # 3. platform_arch (如 windows_x86_64)
        if platform_arch and platform_arch in self.supported_on:
            return self.supported_on[platform_arch]
        # 4. platform (默认，如 windows)
        return self.supported_on.get(platform, True)

    def is_binary(self) -> bool:
        return self.type == "binary"

    def is_dotfile(self) -> bool:
        return self.type == "dotfile"
