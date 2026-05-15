from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

from .base import Plugin


class PluginLoadError(Exception):
    pass


class PluginLoader:
    def __init__(self, search_paths: list[str] | None = None) -> None:
        self._search_paths = search_paths or []
        self._loaded: dict[str, Plugin] = {}

    def load_from_module(self, module_name: str) -> list[Plugin]:
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise PluginLoadError(f"Cannot import module {module_name}: {e}") from e
        return self._extract_plugins(module)

    def load_from_path(self, path: str) -> list[Plugin]:
        path_obj = Path(path)
        if not path_obj.exists() or not path_obj.is_dir():
            raise PluginLoadError(f"Path does not exist: {path}")
        plugins: list[Plugin] = []
        sys.path.insert(0, str(path_obj))
        try:
            for pyfile in sorted(path_obj.iterdir()):
                if pyfile.suffix != ".py" or pyfile.name == "__init__.py":
                    continue
                modname = pyfile.stem
                spec = importlib.util.spec_from_file_location(modname, str(pyfile))
                if spec and spec.loader:
                    try:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        plugins.extend(self._extract_plugins(module))
                    except Exception as e:
                        raise PluginLoadError(f"Failed to load {modname}: {e}") from e
        finally:
            sys.path.remove(str(path_obj))
        return plugins

    def _extract_plugins(self, module: object) -> list[Plugin]:
        found: list[Plugin] = []
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                try:
                    instance = obj()  # type: ignore[call-arg]
                    if instance.name:
                        found.append(instance)
                        self._loaded[instance.name] = instance
                except Exception as e:
                    raise PluginLoadError(f"Cannot instantiate {name}: {e}") from e
        return found

    def get(self, name: str) -> Plugin | None:
        return self._loaded.get(name)

    @property
    def loaded(self) -> dict[str, Plugin]:
        return dict(self._loaded)
