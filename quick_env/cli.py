"""Command-line interface."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .platform import detect_platform, detect_package_manager, get_env_paths
from .tools import get_tool, get_all_tools, Tool
from .installer import InstallerFactory, InstallResult

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
    method: Optional[str] = typer.Option(None, "--method", "-m", help="Installation method (github, package_manager, git_clone)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall"),
):
    """Install tools."""
    if "all" in tools:
        tools = list(get_all_tools().keys())

    for tool_name in tools:
        tool = get_tool(tool_name)
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
    for tool_name in tools:
        tool = get_tool(tool_name)
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
    if "all" in tools:
        tools = list(get_all_tools().keys())

    for tool_name in tools:
        tool = get_tool(tool_name)
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


@app.command()
def list(
    all_tools: bool = typer.Option(False, "--all", "-a", help="Show all tools, not just installed"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category (github, package_manager, git_clone)"),
):
    """List installed tools."""
    table = Table(title="Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Method", style="yellow")
    table.add_column("Version", style="blue")

    tools = get_all_tools()
    for tool_name, tool in tools.items():
        installer = InstallerFactory.get_best_installer(tool)
        if not installer:
            continue

        is_installed = installer.is_installed(tool)
        if not is_installed and not all_tools:
            continue

        version = installer.get_version(tool) if is_installed else "-"
        method = installer.name if is_installed else "-"
        status = "[green]✓[/green]" if is_installed else "[red]✗[/red]"

        table.add_row(tool.display_name, status, method, version or "-")

    if table.row_count == 0:
        console.print("[yellow]No tools found[/yellow]")
    else:
        console.print(table)


@app.command()
def status(
    tools: List[str] = typer.Argument(..., help="Tool(s) to check. Use 'all' to check everything."),
):
    """Check for updates."""
    if "all" in tools:
        tools = list(get_all_tools().keys())

    for tool_name in tools:
        tool = get_tool(tool_name)
        if not tool:
            console.print(f"[red]Unknown tool: {tool_name}[/red]")
            continue

        installer = InstallerFactory.get_best_installer(tool)
        if not installer:
            console.print(f"[red]No installer available for {tool.display_name}[/red]")
            continue

        installed = installer.is_installed(tool)
        current = installer.get_version(tool) if installed else None
        latest = installer.get_version(tool)

        if not installed:
            console.print(f"[yellow]{tool.display_name}: Not installed[/yellow]")
        elif current == latest:
            console.print(f"[green]{tool.display_name}: Up to date ({current})[/green]")
        else:
            console.print(f"[cyan]{tool.display_name}: {current} → {latest}[/cyan]")


@app.command()
def info(
    tool_name: str = typer.Argument(..., help="Tool name"),
):
    """Show information about a tool."""
    tool = get_tool(tool_name)
    if not tool:
        console.print(f"[red]Unknown tool: {tool_name}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]{tool.display_name}[/bold cyan]")
    console.print(f"Description: {tool.description}")
    console.print(f"Supported methods: {', '.join(tool.installable_by)}")

    if tool.package_name:
        console.print(f"Package name: {tool.package_name}")
    if tool.repo:
        console.print(f"GitHub repo: {tool.repo}")

    installer = InstallerFactory.get_best_installer(tool)
    if installer:
        installed = installer.is_installed(tool)
        version = installer.get_version(tool) if installed else None
        console.print(f"Status: {'[green]Installed[/green]' if installed else '[red]Not installed[/red]'}")
        if version:
            console.print(f"Version: {version}")
    else:
        console.print("[yellow]No installer available[/yellow]")


@app.command()
def doctor():
    """Check system requirements."""
    console.print("[bold]System Check[/bold]\n")

    from .platform import command_exists
    from .downloader import download_file

    checks = [
        ("Python", sys.version_info >= (3, 10)),
        ("Git", command_exists("git")),
        ("curl/wget", command_exists("curl") or command_exists("wget")),
        ("Package Manager", detect_package_manager() is not None),
    ]

    for name, passed in checks:
        status = "[green]✓[/green]" if passed else "[red]✗[/red]"
        console.print(f"{status} {name}")

    paths = get_env_paths()
    console.print(f"\n[bold]Paths[/bold]")
    for key, value in paths.items():
        p = Path(value)
        exists = "[green]✓[/green]" if p.exists() else "[red]✗[/red]"
        console.print(f"{exists} {key}: {value}")


def main():
    app()
