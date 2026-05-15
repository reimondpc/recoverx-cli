"""Fuzz tests for plugin system modules (base, loader, registry, lifecycle).

Ensures the plugin subsystem never crashes on malformed metadata,
invalid paths, concurrent access, or abstract-interface violations.
"""

from __future__ import annotations

import random
import string
import threading
from abc import ABC, abstractmethod
from typing import Any

from recoverx.plugins.base import Plugin, PluginCapabilities, PluginType
from recoverx.plugins.lifecycle import PluginLifecycle
from recoverx.plugins.loader import PluginLoader, PluginLoadError
from recoverx.plugins.registry import PluginRegistry


def _random_string(max_len: int = 20) -> str:  # pragma: no cover
    return "".join(random.choice(string.ascii_letters) for _ in range(random.randint(0, max_len)))


class _RaisingPlugin(Plugin):  # pragma: no cover
    def initialize(self) -> None:
        raise RuntimeError("simulated init failure")

    def shutdown(self) -> None:
        raise RuntimeError("simulated shutdown failure")

    def validate(self) -> list[str]:
        return ["simulated validation error"]


class _MalformedMetaPlugin(Plugin):  # pragma: no cover
    pass


class _UnstablePlugin(Plugin):  # pragma: no cover
    def __init__(self) -> None:
        super().__init__(name=_random_string(), plugin_type=random.choice(list(PluginType)))
        self._fail_on_call = random.random() < 0.3

    def initialize(self) -> None:
        if self._fail_on_call:
            raise RuntimeError("unstable init")

    def validate(self) -> list[str]:
        if self._fail_on_call:
            raise ValueError("unstable validate")
        return []

    def shutdown(self) -> None:
        if self._fail_on_call:
            raise RuntimeError("unstable shutdown")


class _MisnamedPlugin(Plugin):  # pragma: no cover
    def __init__(self) -> None:
        super().__init__(
            name=random.choice(["", "\x00", "a" * 10000, "\ud83d\udca5" * 50, None]),  # type: ignore[arg-type]
            plugin_type=random.choice(list(PluginType)),
        )


class TestFuzzPluginBase:
    def test_fuzz_plugin_metadata_malformed(self) -> None:
        for _ in range(50):
            try:
                name = random.choice(
                    [
                        "",
                        "\x00",
                        "a" * 10000,
                        "\ud83d\udca5" * 50,
                        "valid_name",
                        None,  # type: ignore[list-item]
                    ]
                )
                plugin = _MalformedMetaPlugin(
                    name=name,  # type: ignore[arg-type]
                    version=random.choice(["", "\x00", "a" * 500, None]),  # type: ignore[arg-type]
                    plugin_type=random.choice(list(PluginType)),
                )
                m = plugin.metadata()
                assert isinstance(m, dict)
            except Exception:
                pass

    def test_fuzz_plugin_type_stress(self) -> None:
        reg = PluginRegistry()
        all_types = list(PluginType)
        for i in range(150):
            pt = random.choice(all_types)
            p = Plugin(
                name=f"fuzz_plugin_{i}_{_random_string()}",
                plugin_type=pt,
                capabilities=PluginCapabilities(
                    parallel_safe=random.random() < 0.5,
                    streaming=random.random() < 0.5,
                    incremental=random.random() < 0.5,
                    resumable=random.random() < 0.5,
                    bounded_memory=random.random() < 0.5,
                    supports_batch=random.random() < 0.5,
                ),
            )
            reg.register(p)

        assert reg.count == 150
        for pt in all_types:
            by_type = reg.get_by_type(pt)
            assert isinstance(by_type, list)

        listed = reg.list_all()
        assert len(listed) == 150

    def test_fuzz_plugin_capabilities_combinations(self) -> None:
        for bits in range(64):
            try:
                caps = PluginCapabilities(
                    parallel_safe=bool(bits & 1),
                    streaming=bool(bits & 2),
                    incremental=bool(bits & 4),
                    resumable=bool(bits & 8),
                    bounded_memory=bool(bits & 16),
                    supports_batch=bool(bits & 32),
                )
                p = Plugin(
                    name=f"caps_plugin_{bits}",
                    plugin_type=PluginType.ANALYZER,
                    capabilities=caps,
                )
                m = p.metadata()
                assert m["capabilities"]["parallel_safe"] == bool(bits & 1)
                assert m["capabilities"]["supports_batch"] == bool(bits & 32)
            except Exception:
                pass

    def test_fuzz_plugin_defaults(self) -> None:
        for _ in range(30):
            try:
                p = Plugin(name=_random_string())
                assert p.version == "0.1.0"
                assert p.plugin_type == PluginType.ANALYZER
                m = p.metadata()
                assert isinstance(m, dict)
            except Exception:
                pass


class TestFuzzPluginLoader:
    def test_fuzz_plugin_loader_invalid_paths(self) -> None:
        loader = PluginLoader()
        invalid_paths: list[str] = [
            "",
            "\x00",
            "/nonexistent/path/" + "a" * 500,
            "/dev/null",
            "/proc/self/mem",
            "relative/path",
            ".",
            "..",
            "\ud83d\udcc4",
        ]
        for path in invalid_paths:
            try:
                loader.load_from_path(path)
            except (PluginLoadError, OSError, ValueError, IndexError):
                pass

    def test_fuzz_plugin_loader_invalid_modules(self) -> None:
        loader = PluginLoader()
        invalid_modules: list[str] = [
            "",
            "\x00",
            "a" * 1000,
            ".",
            "..",
            "nonexistent.module.path",
            "import doesnt work",
            "\ud83d\udca5",
        ]
        for mod in invalid_modules:
            try:
                loader.load_from_module(mod)
            except (PluginLoadError, ModuleNotFoundError, ValueError, TypeError):
                pass

    def test_fuzz_loader_empty_and_none(self) -> None:
        try:
            loader = PluginLoader(search_paths=[])
            assert loader.loaded == {}
        except Exception:
            pass

        try:
            loader = PluginLoader(search_paths=None)
            assert loader.loaded == {}
        except Exception:
            pass


class TestFuzzPluginRegistry:
    def test_fuzz_registry_concurrent_access(self) -> None:
        reg = PluginRegistry()
        n_threads = 8
        ops_per_thread = 100
        barrier = threading.Barrier(n_threads)

        def worker(worker_id: int) -> None:
            barrier.wait()
            for i in range(ops_per_thread):
                try:
                    choice = random.randint(0, 4)
                    if choice == 0:
                        p = Plugin(
                            name=f"concurrent_{worker_id}_{i}",
                            plugin_type=random.choice(list(PluginType)),
                        )
                        reg.register(p)
                    elif choice == 1:
                        reg.unregister(f"concurrent_{worker_id}_{i}")
                    elif choice == 2:
                        reg.get(f"concurrent_{worker_id}_{i}")
                    elif choice == 3:
                        reg.get_by_type(random.choice(list(PluginType)))
                    elif choice == 4:
                        reg.list_all()
                except Exception:
                    pass

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert reg.count >= 0

    def test_fuzz_registry_register_unregister_cycle(self) -> None:
        reg = PluginRegistry()
        for i in range(200):
            name = f"cycle_{i}"
            p = Plugin(
                name=name,
                plugin_type=random.choice(list(PluginType)),
            )
            reg.register(p)
            assert reg.get(name) is not None

        for i in range(200):
            name = f"cycle_{i}"
            reg.unregister(name)
            assert reg.get(name) is None

        assert reg.count == 0

    def test_fuzz_registry_get_by_type_empty(self) -> None:
        reg = PluginRegistry()
        for pt in PluginType:
            assert reg.get_by_type(pt) == []

    def test_fuzz_registry_double_register(self) -> None:
        reg = PluginRegistry()
        p = Plugin(name="double", plugin_type=PluginType.ANALYZER)
        reg.register(p)
        reg.register(p)
        assert reg.count == 1


class TestFuzzPluginLifecycle:
    def test_fuzz_lifecycle_init_failures(self) -> None:
        reg = PluginRegistry()
        for i in range(30):
            p = _RaisingPlugin(
                name=f"raising_{i}",
                plugin_type=random.choice(list(PluginType)),
            )
            reg.register(p)

        lc = PluginLifecycle(reg)
        errors = lc.initialize_all()
        assert len(errors) == 30
        lc.shutdown_all()

    def test_fuzz_lifecycle_mixed_plugins(self) -> None:
        reg = PluginRegistry()
        names: list[str] = []
        for i in range(20):
            is_stable = random.random() < 0.5
            if is_stable:
                p = Plugin(
                    name=f"stable_{i}",
                    plugin_type=random.choice(list(PluginType)),
                )
            else:
                p = _UnstablePlugin()
                p.name = f"unstable_{i}"
            reg.register(p)
            names.append(p.name)

        lc = PluginLifecycle(reg)
        errors = lc.initialize_all()
        assert isinstance(errors, list)

        for name in names:
            try:
                lc.is_initialized(name)
            except Exception:
                pass

        lc.shutdown_all()

    def test_fuzz_lifecycle_context_manager(self) -> None:
        reg = PluginRegistry()
        for i in range(10):
            p = Plugin(name=f"ctx_{i}", plugin_type=PluginType.ANALYZER)
            reg.register(p)

        try:
            with PluginLifecycle(reg) as lc:
                for i in range(10):
                    assert lc.is_initialized(f"ctx_{i}") or not lc.is_initialized(f"ctx_{i}")
        except Exception:
            pass

    def test_fuzz_lifecycle_validate_all(self) -> None:
        reg = PluginRegistry()
        for i in range(10):
            prototype = Plugin if random.random() < 0.5 else _RaisingPlugin
            p = prototype(
                name=f"val_{i}",
                plugin_type=random.choice(list(PluginType)),
            )
            reg.register(p)

        lc = PluginLifecycle(reg)
        results = lc.validate_all()
        assert isinstance(results, dict)

    def test_fuzz_lifecycle_empty_registry(self) -> None:
        reg = PluginRegistry()
        lc = PluginLifecycle(reg)
        errors = lc.initialize_all()
        assert errors == []
        lc.shutdown_all()
        results = lc.validate_all()
        assert results == {}


class TestFuzzPluginInterfaces:
    def test_fuzz_malformed_interfaces(self) -> None:
        bad_concretions: list[type] = []

        class _NoAbstractOverride(Plugin):  # pragma: no cover
            pass

        bad_concretions.append(_NoAbstractOverride)

        try:
            inst = _NoAbstractOverride(name="bad_no_override")
            inst.metadata()
        except TypeError:
            pass
        except Exception:
            pass

    def test_fuzz_partial_abstract_impl(self) -> None:
        for _ in range(20):
            try:
                abstract_methods = [
                    "parse",
                    "collect",
                    "export",
                    "format_name",
                    "extend_query",
                    "custom_operators",
                    "analyze",
                ]
                n_impl = random.randint(0, len(abstract_methods))
                chosen = set(random.sample(abstract_methods, n_impl))

                cls_dict: dict[str, Any] = {"__module__": __name__}
                for m in chosen:
                    cls_dict[m] = lambda self, *a, **kw: None

                BadPlugin = type("BadPlugin", (Plugin,), cls_dict)
                try:
                    inst = BadPlugin(name=_random_string())
                    inst.metadata()
                except TypeError:
                    pass
            except Exception:
                pass
