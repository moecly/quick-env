"""Tool definitions and metadata."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Tool:
    name: str
    display_name: str
    installable_by: list[str] = field(default_factory=list)
    package_name: Optional[str] = None
    platform_commands: dict[str, str] = field(default_factory=dict)
    repo: Optional[str] = None
    asset_patterns: dict[str, str] = field(default_factory=dict)
    config_repo: Optional[str] = None
    config_link: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    description: str = ""

    def matches(self, name: str) -> bool:
        return name == self.name or name in self.aliases

    def get_asset_pattern(self, platform: str) -> str | None:
        if platform in self.asset_patterns:
            return self.asset_patterns[platform]
        if "default" in self.asset_patterns:
            return self.asset_patterns["default"]
        return None


TOOLS = {
    "lazygit": Tool(
        name="lazygit",
        display_name="Lazygit",
        installable_by=["github"],
        package_name="lazygit",
        repo="jesseduffield/lazygit",
        asset_patterns={
            "linux_x86_64": "lazygit_{version}_linux_x86_64.tar.gz",
            "linux_arm64": "lazygit_{version}_linux_arm64.tar.gz",
            "linux_armv7": "lazygit_{version}_linux_armv6.tar.gz",
            "linux_i686": "lazygit_{version}_linux_32-bit.tar.gz",
            "darwin_x86_64": "lazygit_{version}_darwin_x86_64.tar.gz",
            "darwin_arm64": "lazygit_{version}_darwin_arm64.tar.gz",
            "windows_x86_64": "lazygit_{version}_windows_x86_64.zip",
            "windows_arm64": "lazygit_{version}_windows_arm64.zip",
            "windows_i686": "lazygit_{version}_windows_32-bit.zip",
        },
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
        asset_patterns={
            "linux_x86_64": "fd-v{version}-x86_64-unknown-linux-gnu.tar.gz",
            "linux_arm64": "fd-v{version}-aarch64-unknown-linux-gnu.tar.gz",
            "linux_armv7": "fd-v{version}-arm-unknown-linux-gnueabihf.tar.gz",
            "linux_i686": "fd-v{version}-i686-unknown-linux-gnu.tar.gz",
            "darwin_arm64": "fd-v{version}-aarch64-apple-darwin.tar.gz",
            "windows_x86_64": "fd-v{version}-x86_64-pc-windows-gnu.zip",
            "windows_arm64": "fd-v{version}-aarch64-pc-windows-msvc.zip",
        },
        description="Simple, fast and user-friendly alternative to find",
    ),
    "rg": Tool(
        name="rg",
        display_name="RipGrep",
        installable_by=["github"],
        package_name="ripgrep",
        repo="BurntSushi/ripgrep",
        asset_patterns={
            "linux_x86_64": "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz",
            "linux_arm64": "ripgrep-{version}-aarch64-unknown-linux-gnu.tar.gz",
            "linux_armv7": "ripgrep-{version}-armv7-unknown-linux-gnueabihf.tar.gz",
            "linux_i686": "ripgrep-{version}-i686-unknown-linux-gnu.tar.gz",
            "darwin_x86_64": "ripgrep-{version}-x86_64-apple-darwin.tar.gz",
            "darwin_arm64": "ripgrep-{version}-aarch64-apple-darwin.tar.gz",
            "windows_x86_64": "ripgrep-{version}-x86_64-pc-windows-gnu.zip",
            "windows_arm64": "ripgrep-{version}-aarch64-pc-windows-msvc.zip",
        },
        aliases=["ripgrep"],
        description="Ultra fast grep alternative",
    ),
    "nvim": Tool(
        name="nvim",
        display_name="Neovim",
        installable_by=["github", "package_manager"],
        package_name="neovim",
        repo="neovim/neovim",
        asset_patterns={
            "linux_x86_64": "nvim-linux-x86_64.tar.gz",
            "linux_arm64": "nvim-linux-arm64.tar.gz",
            "darwin_x86_64": "nvim-macos-x86_64.tar.gz",
            "darwin_arm64": "nvim-macos-arm64.tar.gz",
        },
        description="Hyperextensible Vim-based text editor",
    ),
    "tmux": Tool(
        name="tmux",
        display_name="Tmux",
        installable_by=["package_manager"],
        package_name="tmux",
        repo="tmux/tmux",
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
