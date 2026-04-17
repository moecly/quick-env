"""Tests for tools module."""

import unittest
from quick_env.tools import Tool
from quick_env.config import get_config


class TestToolDefinition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = get_config()
        cls.tools = cls.config.get_all_tools()

    def test_lazygit_definition(self):
        tool = self.tools["lazygit"]
        self.assertEqual(tool.name, "lazygit")
        self.assertEqual(tool.display_name, "Lazygit")
        self.assertIn("github", tool.installable_by)
        self.assertEqual(tool.repo, "jesseduffield/lazygit")
        self.assertIn("lg", tool.aliases)

    def test_fd_definition(self):
        tool = self.tools["fd"]
        self.assertEqual(tool.name, "fd")
        self.assertIn("github", tool.installable_by)
        self.assertEqual(tool.repo, "sharkdp/fd")

    def test_rg_definition(self):
        tool = self.tools["rg"]
        self.assertEqual(tool.name, "rg")
        self.assertEqual(tool.display_name, "RipGrep")
        self.assertIn("github", tool.installable_by)
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
        self.assertIn("git_clone", tool.installable_by)
        self.assertEqual(tool.config_repo, "moecly/tmux-config")
        self.assertEqual(tool.config_link, "~/.tmux.conf")

    def test_nvim_config_definition(self):
        tool = self.tools["nvim-config"]
        self.assertEqual(tool.name, "nvim-config")
        self.assertIn("git_clone", tool.installable_by)
        self.assertEqual(tool.config_repo, "moecly/nvim-config")
        self.assertEqual(tool.config_link, "~/.config/nvim")


class TestGetTool(unittest.TestCase):
    def setUp(self):
        self.config = get_config()

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
        self.config = get_config()

    def test_get_all_tools_returns_dict(self):
        tools = self.config.get_all_tools()
        self.assertIsInstance(tools, dict)
        self.assertGreater(len(tools), 0)

    def test_all_defined_tools_present(self):
        tools = self.config.get_all_tools()
        expected = {"lazygit", "fd", "rg", "nvim", "tmux", "tmux-config", "nvim-config"}
        self.assertEqual(set(tools.keys()), expected)


class TestToolCategories(unittest.TestCase):
    def setUp(self):
        self.config = get_config()
        self.tools = self.config.get_all_tools()

    @property
    def binary_tools(self):
        return {name for name, tool in self.tools.items() if "github" in tool.installable_by and not tool.config_repo}

    @property
    def package_manager_tools(self):
        return {name for name, tool in self.tools.items() if "package_manager" in tool.installable_by}

    @property
    def git_clone_tools(self):
        return {name for name, tool in self.tools.items() if "git_clone" in tool.installable_by}

    def test_binary_tools(self):
        self.assertIn("lazygit", self.binary_tools)
        self.assertIn("fd", self.binary_tools)
        self.assertIn("rg", self.binary_tools)
        self.assertIn("nvim", self.binary_tools)

    def test_package_manager_tools(self):
        self.assertIn("tmux", self.package_manager_tools)
        self.assertIn("nvim", self.package_manager_tools)

    def test_git_clone_tools(self):
        self.assertIn("tmux-config", self.git_clone_tools)
        self.assertIn("nvim-config", self.git_clone_tools)


class TestToolMatches(unittest.TestCase):
    def setUp(self):
        self.config = get_config()

    def test_matches_by_name(self):
        tool = self.config.get_tool("lazygit")
        self.assertTrue(tool.matches("lazygit"))

    def test_matches_by_alias(self):
        tool = self.config.get_tool("lazygit")
        self.assertTrue(tool.matches("lg"))

    def test_matches_false(self):
        tool = self.config.get_tool("lazygit")
        self.assertFalse(tool.matches("fd"))


if __name__ == "__main__":
    unittest.main()
