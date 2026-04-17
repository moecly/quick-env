"""Command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .platform import detect_platform, detect_package_manager, get_env_paths, command_exists
from .config import get_config
from .installer import InstallerFactory, InstallResult, get_version_info

app = typer.Typer(
    name="quick-env",
    help="Cross-platform development environment setup tool",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        from . import __version__
        console.print(f"quick-env {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
):
    pass


@app.command()
def install(
    tools: List[str] = typer.Argument(..., help="Tool(s) to install. Use 'all' to install everything."),
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Installation method (github, system, git_clone)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall"),
):
    """Install tools."""
    config = get_config()
    if "all" in tools:
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
                console.print(f"[yellow]{tool.display_name} does not support '{method}' installation[/yellow]")
                continue
        else:
            installer = InstallerFactory.get_best_installer(tool)
            if not installer:
                console.print(f"[red]No installer available for {tool.display_name}[/red]")
                continue

        if installer.is_installed(tool) and not force:
            console.print(f"[yellow]{tool.display_name} is already installed[/yellow]")
            continue

        console.print(f"[cyan]Installing {tool.display_name} via {installer.name}...[/cyan]")
        result = installer.install(tool)
        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
        else:
            console.print(f"[red]✗ {result.message}[/red]")


@app.command()
def uninstall(
    tools: List[str] = typer.Argument(..., help="Tool(s) to uninstall."),
):
    """Uninstall tools."""
    config = get_config()
    for tool_name in tools:
        tool = config.get_tool(tool_name)
        if not tool:
            console.print(f"[red]Unknown tool: {tool_name}[/red]")
            continue

        for method_name in tool.installable_by:
            installer = InstallerFactory.get_installer(method_name)
            if installer and installer.is_installed(tool):
                result = installer.uninstall(tool)
                if result.success:
                    console.print(f"[green]✓ {result.message}[/green]")
                else:
                    console.print(f"[red]✗ {result.message}[/red]")
                break
        else:
            console.print(f"[yellow]{tool.display_name} is not installed[/yellow]")


@app.command()
def upgrade(
    tools: List[str] = typer.Argument(..., help="Tool(s) to upgrade. Use 'all' to upgrade everything."),
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
            console.print(f"[yellow]{tool.display_name} is not installed, installing...[/yellow]")
            result = installer.install(tool)
        else:
            result = installer.install(tool)

        if result.success:
            console.print(f"[green]✓ {result.message}[/green]")
        else:
            console.print(f"[red]✗ {result.message}[/red]")


@app.command("list")
def list_tools(
    tools: List[str] = typer.Argument(None, help="Show tools. Use 'all' to show all tools."),
    show_updates: bool = typer.Option(False, "--updates", "-u", help="Only show tools with updates"),
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
    tools_to_show = all_tools if show_all else {k: all_tools[k] for k in tools if k in all_tools}

    for tool_name, tool in tools_to_show.items():
        detection = InstallerFactory.detect_tool(tool)
        version_info = get_version_info(tool)

        if not detection.installed and not show_all:
            continue

        if show_updates and not version_info.has_update:
            continue

        status = "[green]✓[/green]" if detection.installed else "[red]✗[/red]"
        source = detection.current_source or detection.sources[0].name if detection.sources else "-"
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
    tools: List[str] = typer.Argument(None, help="Tool name(s). Use 'all' to show all tools."),
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
        status_text = "[green]Installed[/green]" if detection.installed else "[yellow]Not installed[/yellow]"
        console.print(f"Status: {status_icon} {status_text}")

        if detection.installed:
            console.print(f"Source: {detection.current_source or detection.sources[0].name if detection.sources else '-'}")

        if version_info.current:
            console.print(f"Current version: {version_info.current}")
        if version_info.latest:
            if version_info.has_update:
                console.print(f"Latest version: {version_info.latest} (via {version_info.source})")
                console.print(f"[yellow]Update available![/yellow]")
            else:
                console.print(f"Latest version: {version_info.latest} (via {version_info.source})")
                console.print(f"[green]Up to date[/green]")
        elif not detection.installed:
            console.print(f"Latest version: -")

        console.print()


@app.command()
def doctor():
    """Check system requirements."""
    console.print("[bold]System Check[/bold]\n")

    from .platform import command_exists

    checks = [
        ("Python", sys.version_info >= (3, 10)),
        ("Git", command_exists("git")),
        ("curl/wget", command_exists("curl") or command_exists("wget")),
        ("Package Manager", detect_package_manager() is not None),
    ]

    all_passed = True
    for name, passed in checks:
        check_status = "[green]✓[/green]" if passed else "[red]✗[/red]"
        console.print(f"{check_status} {name}")
        if not passed:
            all_passed = False

    pm = detect_package_manager()
    if pm:
        console.print(f"[green]✓[/green] Package manager: {pm}")
    else:
        console.print("[red]✗[/red] Package manager: None")

    paths = get_env_paths()
    console.print(f"\n[bold]Directories[/bold]")
    for key, value in paths.items():
        p = Path(value)
        exists = "[green]✓[/green]" if p.exists() else "[red]✗[/red]"
        console.print(f"{exists} {key}: {value}")

    quick_env_bin = paths["quick_env_bin"]
    console.print(f"\n[bold yellow]PATH Configuration[/bold yellow]")
    console.print(f"Add the following to your ~/.bashrc or ~/.zshrc:\n")
    console.print(f"  [cyan]export PATH=\"{quick_env_bin}:$PATH\"[/cyan]\n")
    console.print(f"Or run this command:")
    console.print(f"  echo 'export PATH=\"{quick_env_bin}:$PATH\"' >> ~/.bashrc")
    console.print(f"  echo 'export PATH=\"{quick_env_bin}:$PATH\"' >> ~/.zshrc\n")
    console.print(f"Then restart your shell or run:")
    console.print(f"  source ~/.bashrc  # or ~/.zshrc")


def main():
    app()
