"""Command-line interface."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .platform import (
    detect_platform,
    detect_package_manager,
    get_env_paths,
    command_exists,
)
from .config import get_config, Config
from .installer import InstallerFactory, InstallResult, get_version_info

app = typer.Typer(
    name="quick-env",
    help="Cross-platform development environment setup tool",
    add_completion=False,
)
console = Console()

config_app = typer.Typer(help="Configuration management")
app.add_typer(config_app, name="config")


def version_callback(value: bool):
    if value:
        from . import __version__

        console.print(f"quick-env {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    if not Config.is_initialized():
        console.print("[cyan]Initializing config...[/cyan]")
        Config.init_config()
        console.print(f"[green]✓ Config created[/green]\n")


@app.command()
def install(
    tools: List[str] = typer.Argument(
        ..., help="Tool(s) to install. Use 'all' to install everything."
    ),
    method: Optional[str] = typer.Option(
        None, "--method", "-m", help="Installation method (github, system, dotfile)"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall"),
    parallel: bool = typer.Option(
        False, "-P", "--parallel", help="Install in parallel (for 'all')"
    ),
):
    """Install tools."""
    from .installer import install_parallel

    config = get_config()
    is_install_all = "all" in tools

    if is_install_all:
        tools = list(config.get_all_tools().values())

        if parallel and len(tools) > 1:
            console.print(
                f"[cyan]Installing {len(tools)} tools in parallel...[/cyan]\n"
            )
            results = install_parallel(tools, force=force)

            success_count = sum(1 for r in results if r.success)
            fail_count = len(results) - success_count

            for result in results:
                if result.success:
                    console.print(f"[green]✓ {result.message}[/green]")
                else:
                    console.print(f"[red]✗ {result.message}[/red]")

            console.print(
                f"\n[cyan]Summary: {success_count} succeeded, {fail_count} failed[/cyan]"
            )
            return

        tools = list(config.get_all_tools().keys())

    for tool_name in tools:
        tool = config.get_tool(tool_name)
        if not tool:
            console.print(f"[red]Unknown tool: {tool_name}[/red]")
            continue

        if method:
            installer = InstallerFactory.get_installer(method)
            if not installer:
                console.print(f"[red]Installer '{method}' not available[/red]")
                continue
            if method not in tool.installable_by:
                console.print(
                    f"[yellow]{tool.display_name} does not support '{method}' installation[/yellow]"
                )
                continue
        else:
            installer = InstallerFactory.get_best_installer(tool)
            if not installer:
                console.print(
                    f"[red]No installer available for {tool.display_name}[/red]"
                )
                continue

        is_in_quick_env = installer.is_installed(tool)
        is_in_system = InstallerFactory.is_tool_available_in_system(tool)

        if is_in_quick_env and not force:
            console.print(
                f"[yellow]{tool.display_name} is already installed in quick-env[/yellow]"
            )
            continue
        elif is_in_system and not force:
            console.print(
                f"[yellow]{tool.display_name} is already installed in system[/yellow]"
            )
            continue

        console.print(
            f"[cyan]Installing {tool.display_name} via {installer.name}...[/cyan]"
        )
        result = installer.install(tool)
        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
        else:
            console.print(f"[red]✗ {result.message}[/red]")


@app.command()
def uninstall(
    tools: List[str] = typer.Argument(
        ..., help="Tool(s) to uninstall. Use 'all' to uninstall everything."
    ),
):
    """Uninstall tools from ~/.quick-env."""
    config = get_config()

    if "all" in tools:
        tools = list(config.get_all_tools().values())
    else:
        tools = [config.get_tool(t) for t in tools]
        tools = [t for t in tools if t is not None]

    for tool in tools:
        if tool.is_dotfile():
            installer = InstallerFactory.get_installer("dotfile")
        else:
            installer = InstallerFactory.get_installer("github")

        if installer and installer.is_installed(tool):
            result = installer.uninstall(tool)
            if result.success:
                console.print(f"[green]✓ {result.message}[/green]")
            else:
                console.print(f"[red]✗ {result.message}[/red]")
        else:
            console.print(
                f"[yellow]{tool.display_name} is not installed in quick-env[/yellow]"
            )


@app.command()
def upgrade(
    tools: List[str] = typer.Argument(
        ..., help="Tool(s) to upgrade. Use 'all' to upgrade everything."
    ),
):
    """Upgrade tools to latest version."""
    config = get_config()
    if "all" in tools:
        tools = list(config.get_all_tools().keys())

    for tool_name in tools:
        tool = config.get_tool(tool_name)
        if not tool:
            console.print(f"[red]Unknown tool: {tool_name}[/red]")
            continue

        installer = InstallerFactory.get_best_installer(tool)
        if not installer:
            console.print(f"[red]No installer available for {tool.display_name}[/red]")
            continue

        if not installer.is_installed(tool):
            console.print(
                f"[yellow]{tool.display_name} is not installed, installing...[/yellow]"
            )
            result = installer.install(tool)
        else:
            result = installer.install(tool)

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
        else:
            console.print(f"[red]✗ {result.message}[/red]")


@app.command("list")
def list_tools(
    tools: List[str] = typer.Argument(
        None, help="Show tools. Use 'all' to show all tools."
    ),
    show_updates: bool = typer.Option(
        False, "--updates", "-u", help="Only show tools with updates"
    ),
):
    """List installed tools with version and update information."""
    config = get_config()
    show_all = tools is None or "all" in tools

    table = Table(title="Tools")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Status", style="green", justify="center")
    table.add_column("Source", style="yellow", no_wrap=True)
    table.add_column("Version", style="blue")
    table.add_column("Update", style="magenta", justify="center")

    all_tools = config.get_all_tools()
    tools_to_show = (
        all_tools if show_all else {k: all_tools[k] for k in tools if k in all_tools}
    )

    for tool_name, tool in tools_to_show.items():
        detection = InstallerFactory.detect_tool(tool)
        version_info = get_version_info(tool)

        if not detection.installed and not show_all:
            continue

        if show_updates and not version_info.has_update:
            continue

        status = "[green]✓[/green]" if detection.installed else "[red]✗[/red]"
        source = (
            detection.current_source or detection.sources[0].name
            if detection.sources
            else "-"
        )
        version = version_info.current or "-"
        if version_info.has_update:
            update = f"[yellow]✓[/yellow]"
        elif version_info.latest:
            update = "[green]✗[/green]"
        else:
            update = "-"

        table.add_row(tool.display_name, status, source, version, update)

    if table.row_count == 0:
        console.print("[yellow]No tools found[/yellow]")
    else:
        console.print(table)


@app.command()
def info(
    tools: List[str] = typer.Argument(
        None, help="Tool name(s). Use 'all' to show all tools."
    ),
):
    """Show information about a tool."""
    config = get_config()
    show_all = tools is not None and "all" in tools
    tools_to_show = tools if tools and not show_all else None

    all_tools = config.get_all_tools()
    if tools_to_show:
        tools_dict = {k: all_tools[k] for k in tools_to_show if k in all_tools}
    else:
        tools_dict = all_tools

    for tool_name, tool in tools_dict.items():
        console.print(f"[bold cyan]{'=' * 40}[/bold cyan]")
        console.print(f"[bold]{tool.display_name}[/bold]")

        detection = InstallerFactory.detect_tool(tool)
        version_info = get_version_info(tool)

        console.print(f"Description: {tool.description}")
        console.print(f"Supported methods: {', '.join(tool.installable_by)}")

        if tool.package_name:
            console.print(f"Package name: {tool.package_name}")
        if tool.repo:
            console.print(f"GitHub repo: {tool.repo}")

        status_icon = "[green]✓[/green]" if detection.installed else "[red]✗[/red]"
        status_text = (
            "[green]Installed[/green]"
            if detection.installed
            else "[yellow]Not installed[/yellow]"
        )
        console.print(f"Status: {status_icon} {status_text}")

        if detection.installed:
            console.print(
                f"Source: {detection.current_source or detection.sources[0].name if detection.sources else '-'}"
            )

        if version_info.current:
            console.print(f"Current version: {version_info.current}")
        if version_info.latest:
            if version_info.has_update:
                console.print(
                    f"Latest version: {version_info.latest} (via {version_info.source})"
                )
                console.print(f"[yellow]Update available![/yellow]")
            else:
                console.print(
                    f"Latest version: {version_info.latest} (via {version_info.source})"
                )
                console.print(f"[green]Up to date[/green]")
        elif not detection.installed:
            console.print(f"Latest version: -")

        console.print()


@app.command()
def init():
    """Initialize configuration in ~/.quick-env."""
    if Config.is_initialized():
        console.print(f"[yellow]Config already exists[/yellow]")
        console.print(f"  Path: {Config._get_user_config_path()}")
    else:
        path = Config.init_config()
        console.print(f"[green]✓ Config created[/green]")
        console.print(f"  Path: {path}")
        console.print(f"\n[cyan]Run 'quick-env doctor' to check setup[/cyan]")


@app.command()
def doctor():
    """Check system requirements."""
    from .platform import command_exists, detect_platform
    from .installer import InstallerFactory
    from datetime import datetime

    platform = detect_platform()
    pm = detect_package_manager()
    paths = get_env_paths()

    console.print("=" * 50)
    console.print("quick-env Doctor Report")
    console.print("=" * 50)
    console.print(
        f"Platform: {platform.system} ({platform.platform_name}) {platform.arch}"
    )
    console.print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print()

    console.print("[bold]1. System Check[/bold]")
    system_passed = 0
    system_total = 0

    def check(name: str, passed: bool, info: str = ""):
        nonlocal system_passed, system_total
        system_total += 1
        if passed:
            system_passed += 1
            console.print(f"  [green]✓[/green] {name}")
        else:
            console.print(f"  [red]✗[/red] {name}")
        if info:
            console.print(f"      {info}")

    check(
        "Python",
        sys.version_info >= (3, 10),
        f"version {sys.version_info.major}.{sys.version_info.minor}",
    )
    check("Git", command_exists("git"))
    check("curl/wget", command_exists("curl") or command_exists("wget"))
    pm_status = pm is not None
    check("Package Manager", pm_status, pm if pm else "None")
    console.print()

    console.print("[bold]2. Directory Check[/bold]")
    dir_passed = 0
    dir_total = 0

    required_dirs = [
        ("quick_env_home", True),
        ("quick_env_bin", True),
        ("quick_env_cache", True),
        ("quick_env_tools", False),
        ("quick_env_dotfiles", False),
        ("quick_env_logs", True),
        ("quick_env_config", True),
    ]

    for key, required in required_dirs:
        dir_total += 1
        path = Path(paths[key])
        exists = path.exists()
        if exists:
            dir_passed += 1
            icon = "[green]✓[/green]"
        elif required:
            icon = "[red]✗[/red]"
        else:
            icon = "[yellow]![/yellow]"
        console.print(f"  {icon} {key}: {paths[key]}")
    console.print()

    console.print("[bold]3. Config Check[/bold]")
    config_path = Config._get_user_config_path()
    config_ok = True

    if not config_path.exists():
        console.print(f"  [yellow]![/yellow] Config not found: {config_path}")
        console.print(f"      Run 'quick-env init' to create config")
        config_ok = False
    else:
        console.print(f"  [green]✓[/green] Config exists: {config_path}")

        try:
            config = Config.load_from(config_path)
            tool_count = len(config.tools)
            binary_count = sum(1 for t in config.tools.values() if t.is_binary())
            dotfile_count = sum(1 for t in config.tools.values() if t.is_dotfile())
            console.print(
                f"      Tools: {tool_count} (binary: {binary_count}, dotfile: {dotfile_count})"
            )
        except Exception as e:
            console.print(f"  [red]✗[/red] Config parse error: {e}")
            config_ok = False
    console.print()

    console.print("[bold]4. Binary Tools Check[/bold]")
    binary_passed = 0
    binary_total = 0

    if config_ok:
        config = Config.load_from(config_path)
        binary_tools = [t for t in config.tools.values() if t.is_binary()]

        if not binary_tools:
            console.print(f"  [yellow]![/yellow] No binary tools defined")
        else:
            for tool in binary_tools:
                binary_total += 1
                installer = InstallerFactory.get_best_installer(tool)

                if installer and installer.is_installed(tool):
                    version = installer.get_version(tool)
                    bin_path = Path(paths["quick_env_bin"]) / tool.name
                    is_symlink = bin_path.is_symlink()
                    target_exists = (
                        bin_path.resolve().exists() if is_symlink else bin_path.exists()
                    )

                    if target_exists:
                        binary_passed += 1
                        icon = "[green]✓[/green]"
                    else:
                        icon = "[red]✗[/red]"
                        version = "-"

                    console.print(f"  {icon} {tool.name:<12} {version or '-':<10} OK")
                else:
                    console.print(
                        f"  [yellow]![/yellow] {tool.name:<12} -          Not installed"
                    )
    console.print()

    console.print("[bold]5. Dotfiles Check[/bold]")
    dotfile_passed = 0
    dotfile_total = 0

    if config_ok:
        config = Config.load_from(config_path)
        dotfile_tools = [t for t in config.tools.values() if t.is_dotfile()]

        if not dotfile_tools:
            console.print(f"  [yellow]![/yellow] No dotfiles defined")
        else:
            dotfiles_dir = Path(paths["quick_env_dotfiles"])

            for tool in dotfile_tools:
                dotfile_total += 1
                repo_path = dotfiles_dir / tool.name
                repo_exists = repo_path.exists()

                if not repo_exists:
                    console.print(f"  [red]✗[/red] {tool.name}")
                    console.print(f"      Repo: Not cloned")
                    continue

                is_git = (repo_path / ".git").exists()
                if not is_git:
                    console.print(f"  [yellow]![/yellow] {tool.name}")
                    console.print(f"      Repo: {repo_path} (not a git repo)")
                    continue

                current_branch = None
                try:
                    import subprocess

                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_path),
                            "rev-parse",
                            "--abbrev-ref",
                            "HEAD",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        current_branch = result.stdout.strip()
                except Exception:
                    pass

                is_dirty = False
                try:
                    result = subprocess.run(
                        ["git", "-C", str(repo_path), "status", "--porcelain"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    is_dirty = bool(result.stdout.strip())
                except Exception:
                    pass

                all_links_ok = True
                broken_links = []
                for link in tool.links:
                    dest = Path(os.path.expanduser(link.to))
                    if not dest.exists() and not dest.is_symlink():
                        all_links_ok = False
                        broken_links.append(link.to)
                    elif dest.is_symlink() and not dest.exists():
                        all_links_ok = False
                        broken_links.append(link.to)

                if broken_links:
                    console.print(f"  [red]✗[/red] {tool.name}")
                    for bl in broken_links:
                        console.print(f"      Broken link: {bl}")
                else:
                    dotfile_passed += 1
                    status = "Dirty" if is_dirty else "Clean"
                    status_icon = (
                        "[yellow]![/yellow]" if is_dirty else "[green]✓[/green]"
                    )
                    console.print(f"  [green]✓[/green] {tool.name} ({status})")
                    console.print(f"      Repo: {repo_path}")
                    console.print(f"      Branch: {current_branch or 'unknown'}")

    console.print()

    console.print("[bold]6. PATH Check[/bold]")
    bin_in_path = any(
        paths["quick_env_bin"] in p
        for p in os.environ.get("PATH", "").split(os.pathsep)
    )
    if bin_in_path:
        console.print(f"  [green]✓[/green] ~/.quick-env/bin is in PATH")
    else:
        console.print(f"  [yellow]![/yellow] ~/.quick-env/bin is NOT in PATH")
    console.print()

    console.print("=" * 50)
    console.print("[bold]Summary[/bold]")
    console.print(f"  System:     {system_passed}/{system_total} passed")
    console.print(f"  Directory:  {dir_passed}/{dir_total} passed")
    console.print(f"  Config:     {'OK' if config_ok else 'ERROR'}")
    console.print(f"  Binary:     {binary_passed}/{binary_total} passed")
    console.print(f"  Dotfiles:   {dotfile_passed}/{dotfile_total} passed")
    console.print()

    if not bin_in_path:
        console.print("[bold yellow]Action Required[/bold yellow]")
        console.print(f"  Add to PATH:")
        console.print(f'    export PATH="{paths["quick_env_bin"]}:$PATH"')
        console.print()

    console.print("=" * 50)


@config_app.command("edit")
def config_edit():
    """Open configuration file in default editor."""
    import os
    import subprocess

    config_path = Config._get_user_config_path()
    if not config_path.exists():
        console.print(f"[yellow]Config not found. Run 'quick-env init' first.[/yellow]")
        return

    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(config_path)])


@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = get_config()
    for name, tool in config.get_all_tools().items():
        console.print(f"[cyan]{name}[/cyan]")
        console.print(f"  display_name: {tool.display_name}")
        console.print(f"  installable_by: {', '.join(tool.installable_by)}")
        if tool.repo:
            console.print(f"  repo: {tool.repo}")
        if tool.priority:
            console.print(f"  priority: {tool.priority}")
        console.print()


def main():
    app()
