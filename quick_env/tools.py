"""Tool definitions and metadata."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LinkConfig:
    glob: str
    to: str

    @classmethod
    def from_dict(cls, data: dict) -> "LinkConfig":
        return cls(
            glob=data.get("glob", ""),
            to=data.get("to", ""),
        )


@dataclass
class Tool:
    name: str
    type: str = "binary"
    display_name: str = ""
    installable_by: list[str] = field(default_factory=list)
    priority: dict[str, int] = field(default_factory=dict)
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

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases

    def get_github_asset_pattern(self, platform: str) -> str | None:
        if platform in self.github_asset_patterns:
            return self.github_asset_patterns[platform]
        if "default" in self.github_asset_patterns:
            return self.github_asset_patterns["default"]
        return None

    def get_priority(self, installer_name: str, default: int = 100) -> int:
        return self.priority.get(installer_name, default)

    def is_binary(self) -> bool:
        return self.type == "binary"

    def is_dotfile(self) -> bool:
        return self.type == "dotfile"
