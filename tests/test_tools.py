"""Tests for tools module."""

import unittest
from quick_env.tools import (
    TOOLS,
    get_tool,
    get_all_tools,
    Tool,
    BINARY_TOOLS,
    PACKAGE_MANAGER_TOOLS,
    GIT_CLONE_TOOLS,
)


class TestToolDefinition(unittest.TestCase):
    def test_lazygit_definition(self):
        tool = TOOLS["lazygit"]
        self.assertEqual(tool.name, "lazygit")
        self.assertEqual(tool.display_name, "Lazygit")
        self.assertIn("github", tool.installable_by)
        self.assertEqual(tool.repo, "jesseduffield/lazygit")
        self.assertIn("lg", tool.aliases)

    def test_fd_definition(self):
        tool = TOOLS["fd"]
        self.assertEqual(tool.name, "fd")
        self.assertIn("github", tool.installable_by)
        self.assertEqual(tool.repo, "sharkdp/fd")

    def test_rg_definition(self):
        tool = TOOLS["rg"]
        self.assertEqual(tool.name, "rg")
        self.assertEqual(tool.display_name, "RipGrep")
        self.assertIn("github", tool.installable_by)
        self.assertEqual(tool.repo, "BurntSushi/ripgrep")

    def test_nvim_definition(self):
        tool = TOOLS["nvim"]
        self.assertEqual(tool.name, "nvim")
        self.assertIn("github", tool.installable_by)
        self.assertIn("package_manager", tool.installable_by)
        self.assertEqual(tool.repo, "neovim/neovim")

    def test_tmux_definition(self):
        tool = TOOLS["tmux"]
        self.assertEqual(tool.name, "tmux")
        self.assertIn("package_manager", tool.installable_by)

    def test_tmux_config_definition(self):
        tool = TOOLS["tmux-config"]
        self.assertEqual(tool.name, "tmux-config")
        self.assertIn("git_clone", tool.installable_by)
        self.assertEqual(tool.config_repo, "moecly/tmux-config")
        self.assertEqual(tool.config_link, "~/.tmux.conf")

    def test_nvim_config_definition(self):
        tool = TOOLS["nvim-config"]
        self.assertEqual(tool.name, "nvim-config")
        self.assertIn("git_clone", tool.installable_by)
        self.assertEqual(tool.config_repo, "moecly/nvim-config")
        self.assertEqual(tool.config_link, "~/.config/nvim")


class TestGetTool(unittest.TestCase):
    def test_get_tool_by_name(self):
        tool = get_tool("lazygit")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "lazygit")

    def test_get_tool_by_alias(self):
        tool = get_tool("lg")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "lazygit")

    def test_get_tool_not_found(self):
        tool = get_tool("nonexistent")
        self.assertIsNone(tool)


class TestGetAllTools(unittest.TestCase):
    def test_get_all_tools_returns_dict(self):
        tools = get_all_tools()
        self.assertIsInstance(tools, dict)
        self.assertGreater(len(tools), 0)

    def test_all_defined_tools_present(self):
        tools = get_all_tools()
        expected = {"lazygit", "fd", "rg", "nvim", "tmux", "tmux-config", "nvim-config"}
        self.assertEqual(set(tools.keys()), expected)


class TestToolCategories(unittest.TestCase):
    def test_binary_tools(self):
        self.assertIn("lazygit", BINARY_TOOLS)
        self.assertIn("fd", BINARY_TOOLS)
        self.assertIn("rg", BINARY_TOOLS)
        self.assertIn("nvim", BINARY_TOOLS)

    def test_package_manager_tools(self):
        self.assertIn("tmux", PACKAGE_MANAGER_TOOLS)
        self.assertIn("nvim", PACKAGE_MANAGER_TOOLS)

    def test_git_clone_tools(self):
        self.assertIn("tmux-config", GIT_CLONE_TOOLS)
        self.assertIn("nvim-config", GIT_CLONE_TOOLS)


class TestToolMatches(unittest.TestCase):
    def test_matches_by_name(self):
        tool = TOOLS["lazygit"]
        self.assertTrue(tool.matches("lazygit"))

    def test_matches_by_alias(self):
        tool = TOOLS["lazygit"]
        self.assertTrue(tool.matches("lg"))

    def test_matches_false(self):
        tool = TOOLS["lazygit"]
        self.assertFalse(tool.matches("fd"))


if __name__ == "__main__":
    unittest.main()
