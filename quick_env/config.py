"""Configuration loading module."""

import os
import shutil
from pathlib import Path
from typing import Optional

from .tools import Tool


class ToolConfig(Tool):
    pass


class Config:
    def __init__(self):
        self.tools: dict[str, ToolConfig] = {}

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        config = cls()

        # 加载内置配置
        built_in = cls._get_built_in_config()
        if built_in.exists():
            config._load_file(built_in)

        # 加载用户配置（覆盖内置）
        user_config = config_path or cls._get_user_config_path()
        if user_config.exists():
            config._load_file(user_config)

        return config

    @staticmethod
    def _get_built_in_config() -> Path:
        return Path(__file__).parent.parent / "tools.toml"

    @staticmethod
    def _get_user_config_path() -> Path:
        home = Path.home()
        return home / ".quick-env" / "configs" / "tools.toml"

    @staticmethod
    def _get_user_home_path() -> Path:
        return Path.home() / ".quick-env"

    @staticmethod
    def init_config() -> Path:
        """初始化用户配置目录和文件"""
        user_config = Config._get_user_config_path()
        user_home = Config._get_user_home_path()

        if not user_config.exists():
            user_home.mkdir(parents=True, exist_ok=True)
            user_config.parent.mkdir(parents=True, exist_ok=True)

            built_in = Config._get_built_in_config()
            if built_in.exists():
                shutil.copy2(built_in, user_config)

        return user_config

    def _load_file(self, path: Path):
        import tomllib

        with open(path, "rb") as f:
            data = tomllib.load(f)

        for name, tool_data in data.get("tools", {}).items():
            self.tools[name] = ToolConfig(
                name=tool_data.get("name", name),
                display_name=tool_data.get("display_name", name),
                description=tool_data.get("description", ""),
                installable_by=tool_data.get("installable_by", []),
                priority=tool_data.get("priority", {}),
                package_name=tool_data.get("package_name"),
                package_manager_commands=tool_data.get("package_manager_commands", {}),
                repo=tool_data.get("repo"),
                github_asset_patterns=tool_data.get("github_asset_patterns", {}),
                config_repo=tool_data.get("config_repo"),
                config_link=tool_data.get("config_link"),
                aliases=tool_data.get("aliases", []),
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
