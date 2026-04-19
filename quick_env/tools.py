"""Tool definitions and metadata."""

from dataclasses import dataclass, field
from typing import Optional, Any


def get_current_platform_key() -> str:
    """获取当前平台的标识键"""
    from .platform import detect_platform

    p = detect_platform()
    if p.is_termux:
        return "android"
    elif p.is_windows:
        return "windows"
    elif p.is_macos:
        return "macos"
    elif p.is_linux:
        return "linux"
    return "default"


@dataclass
class LinkConfig:
    glob: str = ""
    to: str = ""
    to_linux: str = ""
    to_macos: str = ""
    to_windows: str = ""
    run: str = ""  # 自定义运行命令

    @classmethod
    def from_dict(cls, data: dict) -> "LinkConfig":
        if isinstance(data, str):
            return cls(glob=data, to=data)
        return cls(
            glob=data.get("glob", ""),
            to=data.get("to", ""),
            to_linux=data.get("to_linux", ""),
            to_macos=data.get("to_macos", ""),
            to_windows=data.get("to_windows", ""),
            run=data.get("run", ""),
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
        return self.to if self.to else self.glob


@dataclass
class GithubConfig:
    repo: str = ""
    asset_patterns: dict[str, str] = field(default_factory=dict)
    supported: dict[str, bool] = field(default_factory=dict)
    priority: int = 10

    def is_supported(self, platform: str) -> bool:
        """检查平台是否支持"""
        return self.supported.get(platform, True)

    def get_asset_pattern(
        self, platform_arch: str, platform: str = ""
    ) -> Optional[str]:
        """获取 asset pattern"""
        # 先找 platform_arch
        if platform_arch and platform_arch in self.asset_patterns:
            return self.asset_patterns[platform_arch]
        # 再找 platform
        if platform and platform in self.asset_patterns:
            return self.asset_patterns[platform]
        # 找 default
        if "default" in self.asset_patterns:
            return self.asset_patterns["default"]
        return None


@dataclass
class PackageManagerConfig:
    name: str = ""
    commands: dict[str, str] = field(default_factory=dict)
    priority: int = 30

    def get_command(self, pm: str) -> Optional[str]:
        """获取指定包管理器的命令"""
        if pm in self.commands:
            return self.commands[pm]
        if "default" in self.commands:
            return self.commands["default"]
        return self.name


@dataclass
class CustomUrlConfig:
    urls: dict[str, str] = field(default_factory=dict)
    extract: bool = True

    @classmethod
    def from_dict(cls, data: Any) -> "CustomUrlConfig":
        if isinstance(data, str):
            return cls(urls={"default": data})
        if isinstance(data, dict):
            extract = data.get("extract", True)
            urls = {k: v for k, v in data.items() if k != "extract"}
            return cls(urls=urls, extract=extract)
        return cls()

    def get_url(self, platform_arch: str, platform: str = "") -> Optional[str]:
        """获取 URL"""
        if platform_arch and platform_arch in self.urls:
            return self.urls[platform_arch]
        if platform and platform in self.urls:
            return self.urls[platform]
        if "default" in self.urls:
            return self.urls["default"]
        return None


@dataclass
class CustomScriptConfig:
    scripts: dict[str, str] = field(default_factory=dict)
    priority: int = 5
    supported: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "CustomScriptConfig":
        if isinstance(data, str):
            return cls(scripts={"default": data})
        if isinstance(data, dict):
            supported = data.get("supported", {})
            scripts = {
                k: v for k, v in data.items() if k != "supported" and k != "priority"
            }
            priority = data.get("priority", 5)
            return cls(scripts=scripts, priority=priority, supported=supported)
        return cls()

    def get_script(self, platform_arch: str, platform: str = "") -> Optional[str]:
        """获取安装脚本"""
        if platform_arch and platform_arch in self.scripts:
            return self.scripts[platform_arch]
        if platform and platform in self.scripts:
            return self.scripts[platform]
        if "default" in self.scripts:
            return self.scripts["default"]
        return None

    def is_supported(self, platform: str) -> bool:
        """检查平台是否支持"""
        return self.supported.get(platform, True)


def get_current_platform_key() -> str:
    """获取当前平台的标识键"""
    from .platform import detect_platform

    p = detect_platform()
    if p.is_termux:
        return "android"
    elif p.is_windows:
        return "windows"
    elif p.is_macos:
        return "macos"
    elif p.is_linux:
        return "linux"
    return "default"


@dataclass
class LinkConfig:
    glob: str = ""
    to: str = ""
    to_linux: str = ""
    to_macos: str = ""
    to_windows: str = ""
    run: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "LinkConfig":
        if isinstance(data, str):
            return cls(glob=data, to=data)
        return cls(
            glob=data.get("glob", ""),
            to=data.get("to", ""),
            to_linux=data.get("to_linux", ""),
            to_macos=data.get("to_macos", ""),
            to_windows=data.get("to_windows", ""),
            run=data.get("run", ""),
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
    description: str = ""
    installable_by: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    links: list[LinkConfig] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    # 新嵌套配置
    github: GithubConfig = None
    package_manager: PackageManagerConfig = None
    custom_url: CustomUrlConfig = None
    custom_script: CustomScriptConfig = None

    # Dotfile 配置
    _config_repo: str = ""
    _config_branch: str = "main"

    # 自定义版本检测命令
    _custom_version_cmd: str = ""

    # 二进制入口
    bin_entries: list[str] = field(default_factory=list)

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases

    # ===== 兼容方法 =====
    @property
    def repo(self) -> str:
        return self.github.repo if self.github else ""

    @property
    def github_asset_patterns(self) -> dict:
        return self.github.asset_patterns if self.github else {}

    @property
    def package_name(self) -> str:
        return self.package_manager.name if self.package_manager else ""

    @property
    def package_manager_commands(self) -> dict:
        return self.package_manager.commands if self.package_manager else {}

    @property
    def custom_url_extract(self) -> bool:
        return self.custom_url.extract if self.custom_url else True

    @property
    def priority(self) -> dict:
        """兼容旧的 priority 属性"""
        result = {}
        if self.github:
            result["github"] = self.github.priority
        if self.package_manager:
            result["package_manager"] = self.package_manager.priority
        return result

    @property
    def supported_on(self) -> dict:
        """兼容旧的 supported_on 属性"""
        result = {}
        if self.github and self.github.supported:
            result["github"] = self.github.supported
        return result

    @property
    def repo(self) -> str:
        return self.github.repo if self.github else ""

    @property
    def custom_version_cmd(self) -> str:
        return self._custom_version_cmd if self._custom_version_cmd else ""

    @property
    def config_repo(self) -> str:
        return self._config_repo if self._config_repo else ""

    @property
    def config_branch(self) -> str:
        return self._config_branch if self._config_branch else "main"

    def get_priority(
        self, platform: str, installer_name: str, default: int = 100
    ) -> int:
        """获取优先级"""
        if installer_name == "github" and self.github:
            return self.github.priority
        if installer_name == "package_manager" and self.package_manager:
            return self.package_manager.priority
        if installer_name == "custom_script" and self.custom_script:
            return self.custom_script.priority
        return default

    def is_installer_supported(
        self, platform: str, installer_name: str, platform_arch: str = ""
    ) -> bool:
        """检查安装方式是否支持"""
        if installer_name == "github" and self.github:
            return self.github.is_supported(platform)
        if installer_name == "package_manager" and self.package_manager:
            return True
        if installer_name == "custom_script" and self.custom_script:
            return self.custom_script.is_supported(platform)
        return True

    def get_github_asset_pattern(
        self, platform: str, platform_arch: str = ""
    ) -> str | None:
        # 优先使用新嵌套配置
        if self.github:
            return self.github.get_asset_pattern(platform_arch, platform)
        # 兼容旧格式
        if isinstance(self.github_asset_patterns, dict):
            if platform_arch and platform_arch in self.github_asset_patterns:
                return self.github_asset_patterns[platform_arch]
            if platform in self.github_asset_patterns:
                return self.github_asset_patterns[platform]
            if "default" in self.github_asset_patterns:
                return self.github_asset_patterns["default"]
        return None

    def get_custom_url(self, platform: str, platform_arch: str = "") -> str | None:
        """根据平台和架构获取 custom_url"""
        # 优先使用新嵌套配置
        if self.custom_url:
            return self.custom_url.get_url(platform_arch, platform)
        return None

    def get_priority(
        self, platform: str, installer_name: str, default: int = 100
    ) -> int:
        """根据平台和安装方式获取优先级"""
        if installer_name == "github" and self.github:
            return self.github.priority
        if installer_name == "package_manager" and self.package_manager:
            return self.package_manager.priority
        if installer_name == "custom_script" and self.custom_script:
            return self.custom_script.priority
        return default

    def is_platform_supported(self, platform: str, platform_arch: str = "") -> bool:
        """检查工具在平台上是否支持（默认 True）"""
        if not self.supported_on:
            return True
        # 1. 字符串格式：platform_arch (如 windows_x86_64)
        if platform_arch and platform_arch in self.supported_on:
            return self.supported_on[platform_arch]
        # 2. 嵌套格式：supported_on = {"windows": {"x86_64": True}}
        if platform in self.supported_on:
            inner = self.supported_on[platform]
            if isinstance(inner, dict):
                if platform_arch and platform_arch in inner:
                    return inner[platform_arch]
                default = inner.get("default", True)
                return default
        # 3. 字符串格式：platform (如 windows)
        return self.supported_on.get(platform, True)

    def is_installer_supported(
        self, platform: str, installer_name: str, platform_arch: str = ""
    ) -> bool:
        """检查安装方式在平台上是否支持"""
        if not self.supported_on:
            return True
        # 1. 字符串格式最具体：installer.platform_arch (如 custom_url.windows_x86_64)
        if platform_arch:
            key = f"{installer_name}.{platform_arch}"
            if key in self.supported_on:
                return self.supported_on[key]
        # 2. 字符串格式：installer.platform (如 custom_url.windows)
        key = f"{installer_name}.{platform}"
        if key in self.supported_on:
            return self.supported_on[key]
        # 3. 嵌套格式：supported_on = {"package_manager": {"windows": False}}
        if installer_name in self.supported_on:
            inner = self.supported_on[installer_name]
            if isinstance(inner, dict):
                if platform_arch and platform_arch in inner:
                    return inner[platform_arch]
                if platform in inner:
                    return inner[platform]
        # 4. platform_arch (如 windows_x86_64)
        if platform_arch and platform_arch in self.supported_on:
            return self.supported_on[platform_arch]
        # 5. platform (默认，如 windows)
        return self.supported_on.get(platform, True)

    def is_binary(self) -> bool:
        return self.type == "binary"

    def is_dotfile(self) -> bool:
        return self.type == "dotfile"
