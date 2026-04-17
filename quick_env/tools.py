"""Tool definitions and metadata."""

from dataclasses import dataclass, field
from typing import Optional


DEFAULT_COMMANDS: dict[str, str] = field(default_factory=lambda: {})


@dataclass
class Tool:
    name: str
    display_name: str
    installable_by: list[str] = field(default_factory=list)
    package_name: Optional[str] = None
    platform_commands: dict[str, str] = field(default_factory=dict)
    repo: Optional[str] = None
    asset_pattern: Optional[str] = None
    config_repo: Optional[str] = None
    config_link: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    description: str = ""

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases


TOOLS = {
    "lazygit": Tool(
        name="lazygit",
        display_name="Lazygit",
        installable_by=["github"],
        package_name="lazygit",
        repo="jesseduffield/lazygit",
        asset_pattern="lazygit_{version}_{platform}_{arch}.tar.gz",
        aliases=["lg"],
        description="Terminal UI for git commands",
    ),
    "fd": Tool(
        name="fd",
        display_name="FD",
        installable_by=["github"],
        package_name="fd-find",
        platform_commands={
            "apt": "fdfind",
            "brew": "fd",
            "dnf": "fd",
            "pacman": "fd",
            "default": "fd",
        },
        repo="sharkdp/fd",
        asset_pattern="fd-{version}-{platform}-{arch}.tar.gz",
        description="Simple, fast and user-friendly alternative to find",
    ),
    "rg": Tool(
        name="rg",
        display_name="RipGrep",
        installable_by=["github"],
        package_name="ripgrep",
        repo="BurntSushi/ripgrep",
        asset_pattern="ripgrep-{version}-{platform}-{arch}.tar.gz",
        aliases=["ripgrep"],
        description="Ultra fast grep alternative",
    ),
    "nvim": Tool(
        name="nvim",
        display_name="Neovim",
        installable_by=["github", "package_manager"],
        package_name="neovim",
        repo="neovim/neovim",
        asset_pattern="nvim-{platform}{arch}.tar.gz",
        description="Hyperextensible Vim-based text editor",
    ),
    "tmux": Tool(
        name="tmux",
        display_name="Tmux",
        installable_by=["package_manager"],
        package_name="tmux",
        repo="tmux/tmux",
        asset_pattern="tmux-{version}.tar.gz",
        description="Terminal multiplexer",
    ),
    "tmux-config": Tool(
        name="tmux-config",
        display_name="Tmux Config",
        installable_by=["git_clone"],
        config_repo="moecly/tmux-config",
        config_link="~/.tmux.conf",
        aliases=["tmuxconf"],
        description="My tmux configuration",
    ),
    "nvim-config": Tool(
        name="nvim-config",
        display_name="Neovim Config",
        installable_by=["git_clone"],
        config_repo="moecly/nvim-config",
        config_link="~/.config/nvim",
        aliases=["nvimconf"],
        description="My neovim configuration",
    ),
}


def get_tool(name: str) -> Tool | None:
    for tool in TOOLS.values():
        if tool.matches(name):
            return tool
    return None


def get_all_tools() -> dict[str, Tool]:
    return TOOLS.copy()


def get_tools_by_category(category: str) -> dict[str, Tool]:
    if category == "all":
        return TOOLS.copy()
    result = {}
    for name, tool in TOOLS.items():
        if category in tool.installable_by:
            result[name] = tool
    return result


BINARY_TOOLS = {"lazygit", "fd", "rg", "nvim"}
PACKAGE_MANAGER_TOOLS = {"tmux", "nvim"}
GIT_CLONE_TOOLS = {"tmux-config", "nvim-config"}
