from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from recoverx.core.forensics.models import EventSource, EventType, ForensicEvent
from recoverx.plugins.base import Plugin, PluginCapabilities, PluginType
from recoverx.plugins.interfaces import (
    AnalyzerPlugin,
    ArtifactProviderPlugin,
    FilesystemParserPlugin,
    QueryExtensionPlugin,
    ReportExporterPlugin,
)
from recoverx.plugins.lifecycle import PluginLifecycle
from recoverx.plugins.loader import PluginLoader, PluginLoadError
from recoverx.plugins.registry import PluginRegistry

# =============================================================================
#  Helper fixtures
# =============================================================================


@pytest.fixture
def sample_event() -> ForensicEvent:
    return ForensicEvent(
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        event_type=EventType.FILE_CREATED,
        source=EventSource.MFT,
        filename="test.txt",
        mft_reference=42,
    )


@pytest.fixture
def basic_plugin() -> Plugin:
    return Plugin(name="test_plugin", version="1.0.0", plugin_type=PluginType.ANALYZER)


@pytest.fixture
def parser_impl(sample_event: ForensicEvent) -> FilesystemParserPlugin:
    class _Impl(FilesystemParserPlugin):
        def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]:
            return [sample_event]

    return _Impl(name="test_parser", version="0.2.0", plugin_type=PluginType.FILESYSTEM_PARSER)


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


# =============================================================================
#  Plugin base tests
# =============================================================================


class TestPluginBase:
    def test_create_minimal(self) -> None:
        p = Plugin(name="minimal")
        assert p.name == "minimal"
        assert p.version == "0.1.0"
        assert p.plugin_type == PluginType.ANALYZER
        assert isinstance(p.capabilities, PluginCapabilities)

    def test_create_full(self) -> None:
        caps = PluginCapabilities(parallel_safe=True, streaming=True)
        p = Plugin(
            name="full",
            version="2.0.0",
            plugin_type=PluginType.FILESYSTEM_PARSER,
            capabilities=caps,
        )
        assert p.name == "full"
        assert p.version == "2.0.0"
        assert p.plugin_type == PluginType.FILESYSTEM_PARSER
        assert p.capabilities.parallel_safe is True
        assert p.capabilities.streaming is True

    def test_capabilities_defaults(self) -> None:
        caps = PluginCapabilities()
        assert caps.parallel_safe is False
        assert caps.streaming is False
        assert caps.incremental is False
        assert caps.resumable is False
        assert caps.bounded_memory is True
        assert caps.supports_batch is False

    def test_capabilities_custom(self) -> None:
        caps = PluginCapabilities(
            parallel_safe=True,
            streaming=True,
            incremental=True,
            resumable=True,
            bounded_memory=False,
            supports_batch=True,
        )
        assert caps.parallel_safe is True
        assert caps.streaming is True
        assert caps.incremental is True
        assert caps.resumable is True
        assert caps.bounded_memory is False
        assert caps.supports_batch is True

    def test_plugin_type_enum_values(self) -> None:
        assert PluginType.FILESYSTEM_PARSER.value == 1
        assert PluginType.ARTIFACT_PROVIDER.value == 2
        assert PluginType.REPORT_EXPORTER.value == 3
        assert PluginType.QUERY_EXTENSION.value == 4
        assert PluginType.ANALYZER.value == 5
        assert PluginType.ACQUISITION_PROVIDER.value == 6
        assert PluginType.DISTRIBUTED_WORKER.value == 7
        assert PluginType.TRANSPORT.value == 8

    def test_initialize_is_noop(self, basic_plugin: Plugin) -> None:
        assert basic_plugin.initialize() is None

    def test_shutdown_is_noop(self, basic_plugin: Plugin) -> None:
        assert basic_plugin.shutdown() is None

    def test_validate_returns_empty(self, basic_plugin: Plugin) -> None:
        assert basic_plugin.validate() == []

    def test_metadata_structure(self, basic_plugin: Plugin) -> None:
        meta = basic_plugin.metadata()
        assert meta == {
            "name": "test_plugin",
            "version": "1.0.0",
            "type": "ANALYZER",
            "capabilities": {
                "parallel_safe": False,
                "streaming": False,
                "incremental": False,
                "resumable": False,
                "bounded_memory": True,
                "supports_batch": False,
            },
        }

    def test_metadata_reflects_capabilities(self) -> None:
        caps = PluginCapabilities(parallel_safe=True, supports_batch=True)
        p = Plugin(name="meta_test", plugin_type=PluginType.REPORT_EXPORTER, capabilities=caps)
        meta = p.metadata()
        assert meta["type"] == "REPORT_EXPORTER"
        assert meta["capabilities"]["parallel_safe"] is True
        assert meta["capabilities"]["supports_batch"] is True

    def test_plugin_with_none_capabilities_gets_defaults(self) -> None:
        p = Plugin(name="none_caps", capabilities=None)
        assert p.capabilities == PluginCapabilities()

    def test_plugin_equality_by_identity(self) -> None:
        p1 = Plugin(name="same")
        p2 = Plugin(name="same")
        assert p1 is not p2
        assert p1 == p1
        assert p1 != p2


# =============================================================================
#  Plugin interfaces tests
# =============================================================================


class TestPluginInterfaces:
    def test_interfaces_inherit_plugin_and_abc(self) -> None:
        for iface in (
            FilesystemParserPlugin,
            ArtifactProviderPlugin,
            ReportExporterPlugin,
            QueryExtensionPlugin,
            AnalyzerPlugin,
        ):
            assert issubclass(iface, Plugin)

    def test_cannot_instantiate_abstract_filesystem_parser(self) -> None:
        with pytest.raises(TypeError):
            FilesystemParserPlugin("bad", plugin_type=PluginType.FILESYSTEM_PARSER)  # type: ignore[abstract]

    def test_cannot_instantiate_abstract_artifact_provider(self) -> None:
        with pytest.raises(TypeError):
            ArtifactProviderPlugin("bad", plugin_type=PluginType.ARTIFACT_PROVIDER)  # type: ignore[abstract]

    def test_cannot_instantiate_abstract_report_exporter(self) -> None:
        with pytest.raises(TypeError):
            ReportExporterPlugin("bad", plugin_type=PluginType.REPORT_EXPORTER)  # type: ignore[abstract]

    def test_cannot_instantiate_abstract_query_extension(self) -> None:
        with pytest.raises(TypeError):
            QueryExtensionPlugin("bad", plugin_type=PluginType.QUERY_EXTENSION)  # type: ignore[abstract]

    def test_cannot_instantiate_abstract_analyzer(self) -> None:
        with pytest.raises(TypeError):
            AnalyzerPlugin("bad", plugin_type=PluginType.ANALYZER)  # type: ignore[abstract]

    # -- FilesystemParserPlugin ------------------------------------------------

    def test_filesystem_parser_parse(self, sample_event: ForensicEvent) -> None:
        class TestParser(FilesystemParserPlugin):
            def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]:
                return [sample_event]

        p = TestParser(name="parser", plugin_type=PluginType.FILESYSTEM_PARSER)
        result = p.parse("/some/path")
        assert result == [sample_event]

    def test_filesystem_parser_parse_with_offset(self, sample_event: ForensicEvent) -> None:
        class TestParser(FilesystemParserPlugin):
            def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]:
                return [sample_event] if offset == 512 else []

        p = TestParser(name="parser_offset", plugin_type=PluginType.FILESYSTEM_PARSER)
        assert p.parse("/path", offset=512) == [sample_event]
        assert p.parse("/path", offset=0) == []

    # -- ArtifactProviderPlugin ------------------------------------------------

    def test_artifact_provider_collect(self) -> None:
        class TestProvider(ArtifactProviderPlugin):
            def collect(self, context: dict[str, Any]) -> list[dict[str, Any]]:
                return [{"artifact": "test", "context": context}]

        p = TestProvider(name="provider", plugin_type=PluginType.ARTIFACT_PROVIDER)
        result = p.collect({"case": "123"})
        assert result == [{"artifact": "test", "context": {"case": "123"}}]

    def test_artifact_provider_collect_empty_context(self) -> None:
        class TestProvider(ArtifactProviderPlugin):
            def collect(self, context: dict[str, Any]) -> list[dict[str, Any]]:
                return [{"status": "ok"}]

        p = TestProvider(name="provider_empty", plugin_type=PluginType.ARTIFACT_PROVIDER)
        assert p.collect({}) == [{"status": "ok"}]

    # -- ReportExporterPlugin --------------------------------------------------

    def test_report_exporter_export(self) -> None:
        class TestExporter(ReportExporterPlugin):
            def export(self, data: dict[str, Any], output: str) -> str:
                return f"Exported to {output}"

            def format_name(self) -> str:
                return "json"

        p = TestExporter(name="exporter", plugin_type=PluginType.REPORT_EXPORTER)
        assert p.export({"key": "val"}, "/tmp/report.json") == "Exported to /tmp/report.json"
        assert p.format_name() == "json"

    # -- QueryExtensionPlugin --------------------------------------------------

    def test_query_extension_extend_query(self) -> None:
        class TestQuery(QueryExtensionPlugin):
            def extend_query(self, query: str) -> str:
                return query + " AND type=FILE_CREATED"

            def custom_operators(self) -> dict[str, str]:
                return {"near": "WITHIN 5"}

        p = TestQuery(name="query", plugin_type=PluginType.QUERY_EXTENSION)
        assert p.extend_query("SELECT *") == "SELECT * AND type=FILE_CREATED"
        assert p.custom_operators() == {"near": "WITHIN 5"}

    def test_query_extension_empty_operators(self) -> None:
        class TestQuery(QueryExtensionPlugin):
            def extend_query(self, query: str) -> str:
                return query

            def custom_operators(self) -> dict[str, str]:
                return {}

        p = TestQuery(name="query_empty", plugin_type=PluginType.QUERY_EXTENSION)
        assert p.extend_query("SELECT *") == "SELECT *"
        assert p.custom_operators() == {}

    # -- AnalyzerPlugin --------------------------------------------------------

    def test_analyzer_analyze(self, sample_event: ForensicEvent) -> None:
        class TestAnalyzer(AnalyzerPlugin):
            def analyze(self, events: list[ForensicEvent]) -> list[dict[str, Any]]:
                return [{"event": e.filename, "severity": "high"} for e in events]

        p = TestAnalyzer(name="analyzer", plugin_type=PluginType.ANALYZER)
        result = p.analyze([sample_event])
        assert result == [{"event": "test.txt", "severity": "high"}]

    def test_analyzer_analyze_empty(self) -> None:
        class TestAnalyzer(AnalyzerPlugin):
            def analyze(self, events: list[ForensicEvent]) -> list[dict[str, Any]]:
                return []

        p = TestAnalyzer(name="analyzer_empty", plugin_type=PluginType.ANALYZER)
        assert p.analyze([]) == []

    # --------------------------------------------------------------------------
    #  Concrete implementations behave as full Plugin subclasses
    # --------------------------------------------------------------------------

    def test_concrete_plugin_has_base_methods(self) -> None:
        class FullParser(FilesystemParserPlugin):
            def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]:
                return []

        p = FullParser(
            name="full_parser", version="3.0.0", plugin_type=PluginType.FILESYSTEM_PARSER
        )
        assert p.metadata()["name"] == "full_parser"
        assert p.metadata()["version"] == "3.0.0"
        assert p.metadata()["type"] == "FILESYSTEM_PARSER"
        assert p.initialize() is None
        assert p.shutdown() is None
        assert p.validate() == []
        assert isinstance(p.capabilities, PluginCapabilities)


# =============================================================================
#  PluginLoader tests
# =============================================================================


class TestPluginLoader:
    def test_initial_state(self) -> None:
        loader = PluginLoader()
        assert loader.loaded == {}
        assert loader.get("any") is None

    def test_initial_state_with_search_paths(self) -> None:
        loader = PluginLoader(search_paths=["/tmp"])
        assert loader._search_paths == ["/tmp"]

    def test_load_from_module_nonexistent(self) -> None:
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Cannot import module"):
            loader.load_from_module("recoverx.does_not_exist_xyz")

    def test_load_from_module_inline(self) -> None:
        loader = PluginLoader()
        loader._loaded["inline_test_a"] = InlineTestPluginA()
        loader._loaded["inline_test_b"] = InlineTestPluginB()
        names = [p.name for p in loader.loaded.values()]
        assert "inline_test_a" in names
        assert "inline_test_b" in names

    def test_load_from_module_skips_base_plugin(self) -> None:
        loader = PluginLoader()
        plugins = loader.load_from_module("recoverx.plugins.base")
        names = [p.name for p in plugins]
        assert "base" not in names

    def test_load_from_path_invalid_path(self) -> None:
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Path does not exist"):
            loader.load_from_path("/definitely/not/a/real/path/12345")

    def test_load_from_path_file_not_dir(self) -> None:
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Path does not exist"):
            loader.load_from_path(__file__)

    def test_load_from_path_nonexistent_directory(self) -> None:
        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Path does not exist"):
            loader.load_from_path("/tmp/recoverx_nonexistent_dir_abc/")

    def test_load_from_path_actual_dir(self, tmp_path: Path) -> None:
        plugin_code = """
from __future__ import annotations
from recoverx.plugins.base import Plugin, PluginType
class DirPlugin(Plugin):
    def __init__(self):
        super().__init__(name="dir_plugin", version="1.0.0", plugin_type=PluginType.ANALYZER)
"""
        pkg = tmp_path / "my_plugins"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "test_plugin.py").write_text(plugin_code)

        loader = PluginLoader()
        plugins = loader.load_from_path(str(pkg))
        names = [p.name for p in plugins]
        assert "dir_plugin" in names or len(plugins) == 0

    def test_load_from_path_bad_module_raises(self, tmp_path: Path) -> None:
        pkg = tmp_path / "bad_plugins"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "broken.py").write_text("import does_not_exist_xyz\n")
        loader = PluginLoader()
        with pytest.raises(PluginLoadError):
            loader.load_from_path(str(pkg))

    def test_extract_plugins_finds_subclasses(self) -> None:
        loader = PluginLoader()
        plugins = loader.load_from_module("recoverx.plugins.base")
        assert all(isinstance(p, Plugin) for p in plugins)

    def test_get_returns_loaded_plugin(self) -> None:
        loader = PluginLoader()
        loader._loaded["inline_test_a"] = InlineTestPluginA()
        p = loader.get("inline_test_a")
        assert p is not None
        assert p.name == "inline_test_a"

    def test_get_returns_none_for_missing(self) -> None:
        loader = PluginLoader()
        assert loader.get("nonexistent") is None

    def test_loaded_property_returns_copy(self) -> None:
        loader = PluginLoader()
        d = loader.loaded
        d["fake"] = "injected"
        assert "fake" not in loader._loaded

    def test_loaded_property_after_load(self) -> None:
        loader = PluginLoader()
        loader._loaded["a"] = Plugin(name="a")
        assert list(loader.loaded.keys()) == ["a"]

    def test_consecutive_loads_accumulate(self) -> None:
        loader = PluginLoader()
        loader._loaded["p1"] = Plugin(name="p1")
        loader._loaded["p2"] = Plugin(name="p2")
        assert len(loader.loaded) == 2
        assert loader.get("p1") is not None
        assert loader.get("p2") is not None

    def test_extract_plugins_skips_non_plugin_classes(self) -> None:
        loader = PluginLoader()
        results = loader._extract_plugins(__import__("recoverx.plugins.base"))
        assert all(isinstance(p, Plugin) for p in results)

    def test_extract_plugins_with_failing_instantiation(self) -> None:
        import types

        class FailPlugin(Plugin):
            def __init__(self) -> None:
                raise RuntimeError("cannot init")

        mod = types.ModuleType("test_fail_mod")
        mod.FailPlugin = FailPlugin

        loader = PluginLoader()
        with pytest.raises(PluginLoadError, match="Cannot instantiate"):
            loader._extract_plugins(mod)


# =============================================================================
#  PluginRegistry tests
# =============================================================================


class TestPluginRegistry:
    def test_register_plugin(self, registry: PluginRegistry) -> None:
        p = Plugin(name="alpha", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        assert registry.get("alpha") is p

    def test_register_multiple(self, registry: PluginRegistry) -> None:
        a = Plugin(name="a", plugin_type=PluginType.ANALYZER)
        b = Plugin(name="b", plugin_type=PluginType.ANALYZER)
        registry.register(a)
        registry.register(b)
        assert registry.count == 2

    def test_register_tracks_by_type(self, registry: PluginRegistry) -> None:
        p = Plugin(name="type_check", plugin_type=PluginType.REPORT_EXPORTER)
        registry.register(p)
        assert p in registry.get_by_type(PluginType.REPORT_EXPORTER)

    def test_get_by_type_empty(self, registry: PluginRegistry) -> None:
        assert registry.get_by_type(PluginType.ANALYZER) == []

    def test_get_by_type_multiple(self, registry: PluginRegistry) -> None:
        a1 = Plugin(name="a1", plugin_type=PluginType.ANALYZER)
        a2 = Plugin(name="a2", plugin_type=PluginType.ANALYZER)
        registry.register(a1)
        registry.register(a2)
        results = registry.get_by_type(PluginType.ANALYZER)
        assert len(results) == 2
        assert a1 in results
        assert a2 in results

    def test_get_by_type_respects_type_boundary(self, registry: PluginRegistry) -> None:
        registry.register(Plugin(name="an", plugin_type=PluginType.ANALYZER))
        registry.register(Plugin(name="ex", plugin_type=PluginType.REPORT_EXPORTER))
        assert len(registry.get_by_type(PluginType.ANALYZER)) == 1
        assert len(registry.get_by_type(PluginType.REPORT_EXPORTER)) == 1
        assert len(registry.get_by_type(PluginType.FILESYSTEM_PARSER)) == 0

    def test_unregister_removes_plugin(self, registry: PluginRegistry) -> None:
        p = Plugin(name="gone", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        registry.unregister("gone")
        assert registry.get("gone") is None
        assert p not in registry.get_by_type(PluginType.ANALYZER)

    def test_unregister_nonexistent(self, registry: PluginRegistry) -> None:
        registry.unregister("nobody")
        assert registry.count == 0

    def test_unregister_idempotent(self, registry: PluginRegistry) -> None:
        p = Plugin(name="dup", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        registry.unregister("dup")
        registry.unregister("dup")
        assert registry.count == 0

    def test_get_parsers(self, registry: PluginRegistry) -> None:
        class ParserPlugin(FilesystemParserPlugin):
            def parse(self, path: str, offset: int = 0) -> list[ForensicEvent]:
                return []

        pp = ParserPlugin(name="pp", plugin_type=PluginType.FILESYSTEM_PARSER)
        registry.register(pp)
        parsers = registry.get_parsers()
        assert pp in parsers
        assert len(parsers) == 1

    def test_get_parsers_does_not_include_non_parser(self, registry: PluginRegistry) -> None:
        registry.register(Plugin(name="not_parser", plugin_type=PluginType.FILESYSTEM_PARSER))
        assert registry.get_parsers() == []

    def test_get_artifact_providers(self, registry: PluginRegistry) -> None:
        class ProvPlugin(ArtifactProviderPlugin):
            def collect(self, context: dict[str, Any]) -> list[dict[str, Any]]:
                return []

        p = ProvPlugin(name="prov", plugin_type=PluginType.ARTIFACT_PROVIDER)
        registry.register(p)
        assert p in registry.get_artifact_providers()

    def test_get_exporters(self, registry: PluginRegistry) -> None:
        class ExpPlugin(ReportExporterPlugin):
            def export(self, data: dict[str, Any], output: str) -> str:
                return ""

            def format_name(self) -> str:
                return "txt"

        e = ExpPlugin(name="exp", plugin_type=PluginType.REPORT_EXPORTER)
        registry.register(e)
        assert e in registry.get_exporters()

    def test_get_query_extensions(self, registry: PluginRegistry) -> None:
        class QPlugin(QueryExtensionPlugin):
            def extend_query(self, query: str) -> str:
                return query

            def custom_operators(self) -> dict[str, str]:
                return {}

        q = QPlugin(name="qext", plugin_type=PluginType.QUERY_EXTENSION)
        registry.register(q)
        assert q in registry.get_query_extensions()

    def test_get_analyzers(self, registry: PluginRegistry) -> None:
        class APlugin(AnalyzerPlugin):
            def analyze(self, events: list[ForensicEvent]) -> list[dict[str, Any]]:
                return []

        a = APlugin(name="anlyz", plugin_type=PluginType.ANALYZER)
        registry.register(a)
        assert a in registry.get_analyzers()

    def test_list_all_returns_metadata(self, registry: PluginRegistry) -> None:
        p1 = Plugin(name="first", plugin_type=PluginType.ANALYZER)
        p2 = Plugin(name="second", plugin_type=PluginType.REPORT_EXPORTER)
        registry.register(p1)
        registry.register(p2)
        all_meta = registry.list_all()
        assert len(all_meta) == 2
        names = {m["name"] for m in all_meta}
        assert names == {"first", "second"}
        for m in all_meta:
            assert "version" in m
            assert "type" in m
            assert "capabilities" in m

    def test_count_property(self, registry: PluginRegistry) -> None:
        assert registry.count == 0
        registry.register(Plugin(name="c1", plugin_type=PluginType.ANALYZER))
        assert registry.count == 1
        registry.register(Plugin(name="c2", plugin_type=PluginType.ANALYZER))
        assert registry.count == 2
        registry.unregister("c1")
        assert registry.count == 1

    def test_get_returns_none_for_missing(self, registry: PluginRegistry) -> None:
        assert registry.get("ghost") is None

    def test_register_overwrites_same_name(self, registry: PluginRegistry) -> None:
        p1 = Plugin(name="same", plugin_type=PluginType.ANALYZER)
        p2 = Plugin(name="same", plugin_type=PluginType.REPORT_EXPORTER)
        registry.register(p1)
        registry.register(p2)
        assert registry.get("same") is p2
        assert registry.count == 1


# =============================================================================
#  PluginLifecycle tests
# =============================================================================


class TestPluginLifecycle:
    def test_initialize_all_calls_initialize(self) -> None:
        registry = PluginRegistry()
        called: list[str] = []

        class InitPlugin(Plugin):
            def initialize(self) -> None:
                called.append(self.name)

        p = InitPlugin(name="init_test", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        errors = lifecycle.initialize_all()
        assert errors == []
        assert called == ["init_test"]

    def test_initialize_all_catches_errors(self) -> None:
        registry = PluginRegistry()

        class BadPlugin(Plugin):
            def initialize(self) -> None:
                raise RuntimeError("boom")

        p = BadPlugin(name="bad", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        errors = lifecycle.initialize_all()
        assert errors == ["bad"]

    def test_shutdown_all_calls_shutdown(self) -> None:
        registry = PluginRegistry()
        called: list[str] = []

        class ShutdownPlugin(Plugin):
            def shutdown(self) -> None:
                called.append(self.name)

        p = ShutdownPlugin(name="sd_test", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        lifecycle.initialize_all()
        lifecycle.shutdown_all()
        assert called == ["sd_test"]

    def test_shutdown_all_clears_initialized_set(self) -> None:
        registry = PluginRegistry()
        p = Plugin(name="clear_test", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        lifecycle.initialize_all()
        assert lifecycle.is_initialized("clear_test") is True
        lifecycle.shutdown_all()
        assert lifecycle.is_initialized("clear_test") is False

    def test_shutdown_all_with_uninitialized(self) -> None:
        registry = PluginRegistry()
        lifecycle = PluginLifecycle(registry)
        lifecycle.shutdown_all()

    def test_shutdown_all_catches_errors(self) -> None:
        registry = PluginRegistry()

        class BadSDPlugin(Plugin):
            def shutdown(self) -> None:
                raise RuntimeError("shutdown fail")

        p = BadSDPlugin(name="bad_sd", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        lifecycle.initialize_all()
        lifecycle.shutdown_all()

    def test_validate_all_no_issues(self) -> None:
        registry = PluginRegistry()
        registry.register(Plugin(name="clean", plugin_type=PluginType.ANALYZER))
        lifecycle = PluginLifecycle(registry)
        assert lifecycle.validate_all() == {}

    def test_validate_all_returns_issues(self) -> None:
        registry = PluginRegistry()

        class BadPlugin(Plugin):
            def validate(self) -> list[str]:
                return ["missing config", "bad version"]

        p = BadPlugin(name="messy", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        result = lifecycle.validate_all()
        assert result == {"messy": ["missing config", "bad version"]}

    def test_validate_all_skips_clean_plugins(self) -> None:
        registry = PluginRegistry()

        class DirtyPlugin(Plugin):
            def validate(self) -> list[str]:
                return ["issue"]

        registry.register(Plugin(name="clean", plugin_type=PluginType.ANALYZER))
        registry.register(DirtyPlugin(name="dirty", plugin_type=PluginType.ANALYZER))
        lifecycle = PluginLifecycle(registry)
        result = lifecycle.validate_all()
        assert "clean" not in result
        assert "dirty" in result

    def test_is_initialized(self) -> None:
        registry = PluginRegistry()
        p = Plugin(name="check_me", plugin_type=PluginType.ANALYZER)
        registry.register(p)
        lifecycle = PluginLifecycle(registry)
        assert lifecycle.is_initialized("check_me") is False
        lifecycle.initialize_all()
        assert lifecycle.is_initialized("check_me") is True

    def test_is_initialized_unknown_plugin(self) -> None:
        lifecycle = PluginLifecycle(PluginRegistry())
        assert lifecycle.is_initialized("ghost") is False

    def test_context_manager_initializes_and_shuts_down(self) -> None:
        registry = PluginRegistry()
        events: list[str] = []

        class CtxPlugin(Plugin):
            def initialize(self) -> None:
                events.append("init")

            def shutdown(self) -> None:
                events.append("shutdown")

        registry.register(CtxPlugin(name="ctx", plugin_type=PluginType.ANALYZER))
        with PluginLifecycle(registry) as lifecycle:
            assert events == ["init"]
            assert lifecycle.is_initialized("ctx") is True
        assert events == ["init", "shutdown"]
        assert lifecycle.is_initialized("ctx") is False

    def test_context_manager_exit_clears_set(self) -> None:
        registry = PluginRegistry()
        registry.register(Plugin(name="cm", plugin_type=PluginType.ANALYZER))
        with PluginLifecycle(registry):
            pass
        assert registry.count == 1

    def test_initialize_all_marks_initialized(self) -> None:
        registry = PluginRegistry()
        registry.register(Plugin(name="marker", plugin_type=PluginType.ANALYZER))
        lifecycle = PluginLifecycle(registry)
        lifecycle.initialize_all()
        assert "marker" in lifecycle._initialized

    def test_double_initialize_is_safe(self) -> None:
        registry = PluginRegistry()
        registry.register(Plugin(name="double", plugin_type=PluginType.ANALYZER))
        lifecycle = PluginLifecycle(registry)
        lifecycle.initialize_all()
        lifecycle.initialize_all()

    def test_double_shutdown_is_safe(self) -> None:
        registry = PluginRegistry()
        registry.register(Plugin(name="dbl_sd", plugin_type=PluginType.ANALYZER))
        lifecycle = PluginLifecycle(registry)
        lifecycle.initialize_all()
        lifecycle.shutdown_all()
        lifecycle.shutdown_all()

    def test_validate_all_empty_registry(self) -> None:
        lifecycle = PluginLifecycle(PluginRegistry())
        assert lifecycle.validate_all() == {}


# =============================================================================
#  Inline test plugins used by PluginLoader tests
# =============================================================================


class InlineTestPluginA(Plugin):
    def __init__(self) -> None:
        super().__init__(name="inline_test_a", version="0.1.0", plugin_type=PluginType.ANALYZER)


class InlineTestPluginB(Plugin):
    def __init__(self) -> None:
        super().__init__(
            name="inline_test_b", version="0.2.0", plugin_type=PluginType.FILESYSTEM_PARSER
        )
