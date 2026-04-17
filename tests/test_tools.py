"""Tests for tools module."""

import unittest
from pathlib import Path
from quick_env.config import Config


PROJECT_CONFIG = Path(__file__).parent.parent / "tools.toml"


class TestToolDefinition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = Config.load_from(PROJECT_CONFIG)
        cls.tools = cls.config.tools

    def test_lazygit_definition(self):
        tool = self.tools["lazygit"]
        self.assertEqual(tool.name, "lazygit")
        self.assertEqual(tool.display_name, "Lazygit")
        self.assertIn("github", tool.installable_by)
        self.assertIn("package_manager", tool.installable_by)
        self.assertEqual(tool.repo, "jesseduffield/lazygit")
        self.assertIn("lg", tool.aliases)

    def test_fd_definition(self):
        tool = self.tools["fd"]
        self.assertEqual(tool.name, "fd")
        self.assertIn("github", tool.installable_by)
        self.assertIn("package_manager", tool.installable_by)
        self.assertEqual(tool.repo, "sharkdp/fd")

    def test_rg_definition(self):
        tool = self.tools["rg"]
        self.assertEqual(tool.name, "rg")
        self.assertEqual(tool.display_name, "RipGrep")
        self.assertIn("github", tool.installable_by)
        self.assertIn("package_manager", tool.installable_by)
        self.assertEqual(tool.repo, "BurntSushi/ripgrep")

    def test_nvim_definition(self):
        tool = self.tools["nvim"]
        self.assertEqual(tool.name, "nvim")
        self.assertIn("github", tool.installable_by)
        self.assertIn("package_manager", tool.installable_by)
        self.assertEqual(tool.repo, "neovim/neovim")

    def test_tmux_definition(self):
        tool = self.tools["tmux"]
        self.assertEqual(tool.name, "tmux")
        self.assertIn("package_manager", tool.installable_by)

    def test_tmux_config_definition(self):
        tool = self.tools["tmux-config"]
        self.assertEqual(tool.name, "tmux-config")
        self.assertEqual(tool.type, "dotfile")
        self.assertIn("dotfile", tool.installable_by)
        self.assertEqual(tool.config_repo, "moecly/tmux_config")
        self.assertEqual(tool.config_branch, "main")
        self.assertEqual(len(tool.links), 2)
        self.assertEqual(tool.links[0].glob, ".tmux.conf")
        self.assertEqual(tool.links[0].to, "~/.tmux.conf")
        self.assertEqual(tool.links[1].glob, ".tmux.conf.local")
        self.assertEqual(tool.links[1].to, "~/.tmux.conf.local")

    def test_nvim_config_definition(self):
        tool = self.tools["nvim-config"]
        self.assertEqual(tool.name, "nvim-config")
        self.assertEqual(tool.type, "dotfile")
        self.assertIn("dotfile", tool.installable_by)
        self.assertEqual(tool.config_repo, "moecly/nvim-config")
        self.assertEqual(tool.config_branch, "main")
        self.assertEqual(len(tool.links), 1)
        self.assertEqual(tool.links[0].glob, "*")
        self.assertEqual(tool.links[0].to, "~/.config/nvim/")


class TestGetTool(unittest.TestCase):
    def setUp(self):
        self.config = Config.load_from(PROJECT_CONFIG)

    def test_get_tool_by_name(self):
        tool = self.config.get_tool("lazygit")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "lazygit")

    def test_get_tool_by_alias(self):
        tool = self.config.get_tool("lg")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "lazygit")

    def test_get_tool_not_found(self):
        tool = self.config.get_tool("nonexistent")
        self.assertIsNone(tool)


class TestGetAllTools(unittest.TestCase):
    def setUp(self):
        self.config = Config.load_from(PROJECT_CONFIG)

    def test_get_all_tools_returns_dict(self):
        tools = self.config.get_all_tools()
        self.assertIsInstance(tools, dict)
        self.assertGreater(len(tools), 0)

    def test_all_defined_tools_present(self):
        tools = self.config.get_all_tools()
        expected = {"lazygit", "fd", "rg", "nvim", "tmux", "tmux-config", "nvim-config"}
        self.assertEqual(set(tools.keys()), expected)


class TestToolCategories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = Config.load_from(PROJECT_CONFIG)
        cls.tools = cls.config.tools

    @property
    def binary_tools(self):
        return {name for name, tool in self.tools.items() if tool.is_binary()}

    @property
    def package_manager_tools(self):
        return {
            name
            for name, tool in self.tools.items()
            if "package_manager" in tool.installable_by
        }

    @property
    def dotfile_tools(self):
        return {name for name, tool in self.tools.items() if tool.is_dotfile()}

    def test_binary_tools(self):
        self.assertIn("lazygit", self.binary_tools)
        self.assertIn("fd", self.binary_tools)
        self.assertIn("rg", self.binary_tools)
        self.assertIn("nvim", self.binary_tools)
        self.assertIn("tmux", self.binary_tools)

    def test_package_manager_tools(self):
        self.assertIn("tmux", self.package_manager_tools)
        self.assertIn("lazygit", self.package_manager_tools)
        self.assertIn("fd", self.package_manager_tools)
        self.assertIn("rg", self.package_manager_tools)
        self.assertIn("nvim", self.package_manager_tools)

    def test_dotfile_tools(self):
        self.assertIn("tmux-config", self.dotfile_tools)
        self.assertIn("nvim-config", self.dotfile_tools)


class TestToolMatches(unittest.TestCase):
    def setUp(self):
        self.config = Config.load_from(PROJECT_CONFIG)

    def test_matches_by_name(self):
        tool = self.config.get_tool("lazygit")
        self.assertTrue(tool.matches("lazygit"))

    def test_matches_by_alias(self):
        tool = self.config.get_tool("lazygit")
        self.assertTrue(tool.matches("lg"))

    def test_matches_false(self):
        tool = self.config.get_tool("lazygit")
        self.assertFalse(tool.matches("fd"))


class TestToolPriority(unittest.TestCase):
    def setUp(self):
        self.config = Config.load_from(PROJECT_CONFIG)

    def test_nvim_has_priority(self):
        tool = self.config.get_tool("nvim")
        self.assertEqual(tool.priority.get("github"), 10)
        self.assertEqual(tool.priority.get("package_manager"), 30)

    def test_lazygit_has_priority(self):
        tool = self.config.get_tool("lazygit")
        self.assertEqual(tool.priority.get("github"), 10)
        self.assertEqual(tool.priority.get("package_manager"), 30)

    def test_get_priority_default(self):
        tool = self.config.get_tool("tmux")
        self.assertEqual(tool.get_priority("github"), 100)


class TestLinkConfigPlatform(unittest.TestCase):
    def test_link_config_get_target_default(self):
        from quick_env.tools import LinkConfig

        link = LinkConfig(glob="*", to="~/.config/nvim")
        self.assertEqual(link.get_target(), "~/.config/nvim")

    def test_link_config_get_target_linux(self):
        from quick_env.tools import LinkConfig

        link = LinkConfig(
            glob="*", to="~/.config/nvim", to_linux="~/.config/nvim-linux"
        )
        self.assertEqual(link.get_target("linux"), "~/.config/nvim-linux")

    def test_link_config_get_target_macos(self):
        from quick_env.tools import LinkConfig

        link = LinkConfig(
            glob="*", to="~/.config/nvim", to_macos="~/Library/Application Support/nvim"
        )
        self.assertEqual(link.get_target("macos"), "~/Library/Application Support/nvim")

    def test_link_config_get_target_windows(self):
        from quick_env.tools import LinkConfig

        link = LinkConfig(
            glob="*", to="~/.config/nvim", to_windows="~/AppData/Local/nvim"
        )
        self.assertEqual(link.get_target("windows"), "~/AppData/Local/nvim")

    def test_link_config_get_target_fallback(self):
        from quick_env.tools import LinkConfig

        link = LinkConfig(glob="*", to="~/.config/nvim")
        self.assertEqual(link.get_target("linux"), "~/.config/nvim")


class TestToolBinEntries(unittest.TestCase):
    def test_tool_bin_entries_default_empty(self):
        from quick_env.tools import Tool

        tool = Tool(name="test")
        self.assertEqual(tool.bin_entries, [])

    def test_tool_bin_entries_from_config(self):
        config = Config.load_from(PROJECT_CONFIG)
        tool = config.get_tool("lazygit")
        self.assertIsNotNone(tool)


if __name__ == "__main__":
    unittest.main()
