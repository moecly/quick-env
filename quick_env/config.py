"""Configuration loading module."""

import shutil
import sys
from pathlib import Path
from typing import Optional

from .tools import Tool, LinkConfig


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
        from .platform import get_env_paths

        user_home = Config._get_user_home_path()
        user_home.mkdir(parents=True, exist_ok=True)

        paths = get_env_paths()
        for key, path in paths.items():
            if key.startswith("quick_env_"):
                Path(path).mkdir(parents=True, exist_ok=True)

        tools_dir = Path(paths["quick_env_tools"])
        if not tools_dir.exists():
            tools_dir.mkdir(parents=True, exist_ok=True)

        dotfiles_dir = Path(paths["quick_env_dotfiles"])
        if not dotfiles_dir.exists():
            dotfiles_dir.mkdir(parents=True, exist_ok=True)

        user_config = Config._get_user_config_path()
        if not user_config.exists():
            built_in = Config.get_project_config_path()
            if built_in.exists():
                shutil.copy2(built_in, user_config)

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

        for name, tool_data in data.get("tools", {}).items():
            links = [LinkConfig.from_dict(link) for link in tool_data.get("links", [])]

            self.tools[name] = ToolConfig(
                name=tool_data.get("name", name),
                type=tool_data.get("type", "binary"),
                display_name=tool_data.get("display_name", name),
                description=tool_data.get("description", ""),
                installable_by=tool_data.get("installable_by", []),
                priority=tool_data.get("priority", {}),
                package_name=tool_data.get("package_name"),
                package_manager_commands=tool_data.get("package_manager_commands", {}),
                repo=tool_data.get("repo"),
                github_asset_patterns=tool_data.get("github_asset_patterns", {}),
                config_repo=tool_data.get("config_repo"),
                config_branch=tool_data.get("config_branch", "main"),
                links=links,
                exclude=tool_data.get("exclude", []),
                aliases=tool_data.get("aliases", []),
                custom_script=tool_data.get("custom_script"),
                custom_url=tool_data.get("custom_url"),
                custom_url_extract=tool_data.get("custom_url_extract", True),
                custom_version_cmd=tool_data.get("custom_version_cmd"),
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
