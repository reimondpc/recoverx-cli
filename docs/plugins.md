# Plugins

RecoverX supports a plugin system for extending functionality without modifying core code.

## Plugin Types

| Type                 | Description                              |
|----------------------|------------------------------------------|
| `ANALYZER`           | Behavioral analysis of forensic events   |
| `FILESYSTEM_PARSER`  | Custom filesystem implementations        |
| `REPORT_EXPORTER`    | Custom report output formats             |
| `QUERY_EXTENSION`    | Custom query operators and functions     |
| `ACQUISITION_PROVIDER` | Custom disk acquisition backends       |
| `DISTRIBUTED_WORKER` | Custom distributed task handlers         |
| `TRANSPORT`          | Custom data transport protocols          |

## Creating a Plugin

```python
from recoverx.plugins.base import Plugin, PluginType

class MyAnalyzer(Plugin):
    def __init__(self):
        super().__init__(
            name="my_analyzer",
            version="1.0.0",
            plugin_type=PluginType.ANALYZER,
        )

    def initialize(self):
        # Setup logic here
        pass

    def validate(self) -> list[str]:
        return []  # Return list of validation errors
```

## Loading Plugins

```bash
recoverx plugins list                     # List all registered plugins
recoverx plugins list --type ANALYZER     # Filter by type
recoverx plugins list --json              # JSON output
```
