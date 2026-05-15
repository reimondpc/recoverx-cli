from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from recoverx.core.forensics import list_analyzers, list_exporters, list_plugins
from recoverx.plugins import PluginRegistry, PluginType

plugins_app = typer.Typer(
    name="plugins",
    help="Manage RecoverX plugins and extensions.",
    rich_markup_mode="rich",
)


@plugins_app.command()
def list(
    plugin_type: str = typer.Option("", "--type", "-t", help="Filter by plugin type."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """List all registered plugins and their capabilities."""
    console = Console()
    registry = PluginRegistry()
    all_plugins = registry.list_all()

    if plugin_type:
        type_map = {
            "filesystem": PluginType.FILESYSTEM_PARSER,
            "artifact": PluginType.ARTIFACT_PROVIDER,
            "export": PluginType.REPORT_EXPORTER,
            "query": PluginType.QUERY_EXTENSION,
            "analyzer": PluginType.ANALYZER,
            "acquisition": PluginType.ACQUISITION_PROVIDER,
            "distributed": PluginType.DISTRIBUTED_WORKER,
        }
        pt = type_map.get(plugin_type.lower())
        if pt:
            typed = registry.get_by_type(pt)
            all_plugins = [p.metadata() for p in typed]

    registered_analyzers = list_analyzers()
    registered_exporters = list_exporters()
    registered_plugins = list_plugins()

    if json_output:
        console.print(
            json.dumps(
                {
                    "plugins": all_plugins,
                    "registered_analyzers": registered_analyzers,
                    "registered_exporters": registered_exporters,
                    "registered_plugins": registered_plugins,
                },
                indent=2,
                default=str,
            )
        )
    else:
        if all_plugins:
            table = Table(title=f"Plugin Registry ({len(all_plugins)} plugins)")
            table.add_column("Name", style="cyan")
            table.add_column("Version")
            table.add_column("Type")
            table.add_column("Parallel")
            table.add_column("Streaming")
            table.add_column("Resumable")
            for p in all_plugins:
                caps = p.get("capabilities", {})
                table.add_row(
                    p.get("name", ""),
                    p.get("version", ""),
                    p.get("type", ""),
                    "✓" if caps.get("parallel_safe") else "",
                    "✓" if caps.get("streaming") else "",
                    "✓" if caps.get("resumable") else "",
                )
            console.print(table)

        if registered_analyzers:
            console.print(f"\n[dim]Analyzers in registry:[/dim] {', '.join(registered_analyzers)}")
        if registered_exporters:
            console.print(f"[dim]Exporters in registry:[/dim] {', '.join(registered_exporters)}")
        if registered_plugins:
            console.print(f"[dim]Plugins in registry:[/dim] {', '.join(registered_plugins)}")

        if not all_plugins and not registered_analyzers:
            console.print("[yellow]No plugins registered.[/yellow]")
