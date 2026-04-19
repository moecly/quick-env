"""Configuration loading module."""

import sys
from pathlib import Path
from typing import Optional

from .platform import detect_platform, Platform
from .tools import Tool, LinkConfig, GithubConfig, PackageManagerConfig, CustomUrlConfig


class ToolConfig(Tool):
    pass


class Config:
    def __init__(self):
        self.tools: dict[str, ToolConfig] = {}

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """加载用户配置（~/.quick-env/configs/tools.toml）"""
        config = cls()

        user_config = config_path or cls._get_user_config_path()
        if user_config.exists():
            config._load_file(user_config)

        return config

    @classmethod
    def load_from(cls, path: Path) -> "Config":
        """从指定路径加载配置（用于测试）"""
        config = cls()
        if path.exists():
            config._load_file(path)
        return config

    @staticmethod
    def _get_user_config_path() -> Path:
        home = Path.home()
        return home / ".quick-env" / "configs" / "tools.toml"

    @staticmethod
    def _get_user_home_path() -> Path:
        return Path.home() / ".quick-env"

    @staticmethod
    def is_initialized() -> bool:
        """检查配置是否已初始化"""
        return Config._get_user_config_path().exists()

    @staticmethod
    def get_project_config_path() -> Path:
        """获取项目内置配置路径"""
        return Path(__file__).parent.parent / "tools.toml"

    @staticmethod
    def init_config() -> Path:
        """初始化用户配置目录、文件及所有必要目录"""
        from .platform import get_env_paths, detect_platform

        platform = detect_platform()
        user_home = Config._get_user_home_path()
        platform.mkdir(Path(user_home), parents=True, exist_ok=True)

        paths = get_env_paths()
        for key, path in paths.items():
            if key.startswith("quick_env_"):
                platform.mkdir(Path(path), parents=True, exist_ok=True)

        tools_dir = Path(paths["quick_env_tools"])
        if not platform.is_dir(tools_dir):
            platform.mkdir(tools_dir, parents=True, exist_ok=True)

        dotfiles_dir = Path(paths["quick_env_dotfiles"])
        if not platform.is_dir(dotfiles_dir):
            platform.mkdir(dotfiles_dir, parents=True, exist_ok=True)

        user_config = Config._get_user_config_path()
        if not user_config.exists():
            built_in = Config.get_project_config_path()
            if built_in.exists():
                platform.copy2(built_in, user_config)

        return user_config

    def _load_file(self, path: Path):
        import tomllib

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            print(f"\n[red]Config error: {e}[/red]")
            print(f"[red]File: {path}[/red]")
            sys.exit(1)

        for name, tool_data_list in data.get("tools", {}).items():
            # TOML [[tools.xxx]] 语法会创建一个数组
            # 我们只取第一个元素
            tool_data = (
                tool_data_list[0]
                if isinstance(tool_data_list, list)
                else tool_data_list
            )

            # 解析 links
            links_raw = tool_data.get("links", [])
            if links_raw and isinstance(links_raw[0], dict):
                links = [LinkConfig.from_dict(link) for link in links_raw]
            else:
                links = []

            # 解析 github 配置
            github_data = tool_data.get("github")
            github_config = None
            if github_data:
                github_config = GithubConfig(
                    repo=github_data.get("repo", ""),
                    asset_patterns=github_data.get("asset_patterns", {}),
                    supported=github_data.get("supported", {}),
                    priority=github_data.get("priority", 10),
                )

            # 解析 package_manager 配置
            pm_data = tool_data.get("package_manager")
            pm_config = None
            if pm_data:
                pm_config = PackageManagerConfig(
                    name=pm_data.get("name", ""),
                    commands=pm_data.get("commands", {}),
                    priority=pm_data.get("priority", 30),
                )

            # 解析 custom_url 配置
            custom_url_data = tool_data.get("custom_url")
            custom_url_config = None
            if custom_url_data:
                custom_url_config = CustomUrlConfig.from_dict(custom_url_data)

            # 解析 custom_script 配置
            custom_script_data = tool_data.get("custom_script")
            custom_script_config = None
            if custom_script_data:
                from .tools import CustomScriptConfig  # 延迟导入避免循环依赖

                custom_script_config = CustomScriptConfig.from_dict(custom_script_data)

            self.tools[name] = ToolConfig(
                name=tool_data.get("name", name),
                type=tool_data.get("type", "binary"),
                display_name=tool_data.get("display_name", name),
                description=tool_data.get("description", ""),
                installable_by=tool_data.get("installable_by", []),
                aliases=tool_data.get("aliases", []),
                links=links,
                exclude=tool_data.get("exclude", []),
                github=github_config,
                package_manager=pm_config,
                custom_url=custom_url_config,
                custom_script=custom_script_config,
                _config_repo=tool_data.get("config_repo", ""),
                _config_branch=tool_data.get("config_branch", "main"),
                _custom_version_cmd=tool_data.get("custom_version_cmd", ""),
                bin_entries=tool_data.get("bin_entries", []),
            )

    def get_tool(self, name: str) -> Optional[ToolConfig]:
        for tool in self.tools.values():
            if tool.matches(name):
                return tool
        return None

    def get_all_tools(self) -> dict[str, ToolConfig]:
        return self.tools.copy()


# 全局配置实例（延迟加载）
_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config(config_path: Optional[Path] = None):
    global _config
    _config = Config.load(config_path)
