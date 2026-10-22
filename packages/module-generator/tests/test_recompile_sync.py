"""Recompile writes a new version. Sync blocks on drift. Neither overwrites."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from module_generator import (
    CONFIRM_PHRASE,
    MODULE_EDITED_IN_ODOO,
    SPEC_EDITED_OUTSIDE,
    ModelSpec,
    ModuleSpec,
    RecompileRefused,
    SyncRefused,
    artifact_ispec,
    artifact_module_files,
    ispec_to_module_spec,
    module_spec_to_ispec,
    recompile_module,
    sync_module,
)

_SOURCE = Path(__file__).resolve().parents[1] / "src" / "module_generator" / "sync.py"


def _spec(display_name: str = "Alpha Name") -> ModuleSpec:
    return ModuleSpec(technical_name="demo_min", display_name=display_name)


def _confirm() -> dict[str, object]:
    return {"confirm_advanced": True, "confirm_phrase": CONFIRM_PHRASE}


def _fingerprint(root: Path) -> list[tuple[str, int, int, bytes]]:
    rows: list[tuple[str, int, int, bytes]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        rows.append(
            (
                path.relative_to(root).as_posix(),
                stat.st_ino,
                stat.st_mtime_ns,
                path.read_bytes(),
            )
        )
    return rows


def test_recompile_writes_a_new_version_and_keeps_the_previous(tmp_path: Path) -> None:
    store = tmp_path / "store"
    original = _spec("Alpha Name")
    before = module_spec_to_ispec(original)
    first = recompile_module(original, store=store, provider="provider_a", **_confirm())
    assert module_spec_to_ispec(original) == before
    previous = _fingerprint(store / first.version_path)
    second = recompile_module(
        _spec("Beta Name"), store=store, provider="provider_a", **_confirm()
    )

    assert first.version_path != second.version_path
    assert second.diff.previous_version_path == first.version_path
    assert second.diff.changed
    assert _fingerprint(store / first.version_path) == previous
    kept = (store / first.version_path / "ispec.md").read_text(encoding="utf-8")
    assert '"Alpha Name"' in kept
    assert '"Beta Name"' not in kept
    assert (store / second.version_path / "ispec.md").is_file()


def test_failed_log_append_does_not_block_a_changed_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A log failure after rename must not leave a version that blocks later work."""

    store = tmp_path / "store"
    first = recompile_module(
        _spec("Alpha Name"), store=store, provider="provider_a", **_confirm()
    )
    previous = _fingerprint(store / first.version_path)
    log_before = (store / "recompile.log").read_bytes()
    observed: dict[str, object] = {}

    def fail_after_version_dir(root: Path, version_path: str) -> None:
        dest = root.joinpath(*version_path.split("/"))
        observed["path"] = version_path
        observed["in_place"] = (
            dest.is_dir()
            and not dest.is_symlink()
            and (dest / "artifact.json").is_file()
            and (dest / "ispec.md").is_file()
        )
        raise RecompileRefused("recompile log could not be appended")

    with monkeypatch.context() as patch:
        patch.setattr("module_generator.sync._append_log", fail_after_version_dir)
        with pytest.raises(
            RecompileRefused, match="recompile log could not be appended"
        ):
            recompile_module(
                _spec("Beta Name"), store=store, provider="provider_a", **_confirm()
            )

    failed_path = observed["path"]
    assert isinstance(failed_path, str)
    assert observed["in_place"] is True
    assert failed_path != first.version_path
    assert not (store / failed_path).exists()
    assert _fingerprint(store / first.version_path) == previous
    assert (store / "recompile.log").read_bytes() == log_before

    with pytest.raises(RecompileRefused, match="existing version path"):
        recompile_module(
            _spec("Alpha Name"), store=store, provider="provider_a", **_confirm()
        )
    assert _fingerprint(store / first.version_path) == previous

    changed = recompile_module(
        _spec("Gamma Name"), store=store, provider="provider_a", **_confirm()
    )
    assert changed.version_path != first.version_path
    assert changed.version_path != failed_path
    assert (store / changed.version_path / "ispec.md").is_file()
    assert '"Gamma Name"' in (store / changed.version_path / "ispec.md").read_text(
        encoding="utf-8"
    )
    assert _fingerprint(store / first.version_path) == previous
    kept = (store / first.version_path / "ispec.md").read_text(encoding="utf-8")
    assert '"Alpha Name"' in kept
    assert '"Gamma Name"' not in kept


def _artifact_version_paths(store: Path) -> set[str]:
    found: set[str] = set()
    if not store.exists():
        return found
    for record in store.rglob("artifact.json"):
        if record.is_symlink() or not record.is_file():
            continue
        found.add(record.parent.relative_to(store).as_posix())
    return found


def _assert_log_matches_artifacts(store: Path) -> None:
    from module_generator.sync import _VERSION_PATH

    raw = (store / "recompile.log").read_bytes()
    assert raw.endswith(b"\n")
    lines = [line for line in raw.decode("utf-8").splitlines() if line]
    assert lines
    assert len(lines) == len(set(lines))
    assert all(_VERSION_PATH.fullmatch(line) for line in lines)
    assert set(lines) == _artifact_version_paths(store)


def test_failed_version_removal_is_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed removal of the new directory is the error the caller sees."""

    store = tmp_path / "store"
    first = recompile_module(
        _spec("Alpha Name"), store=store, provider="provider_a", **_confirm()
    )
    previous = _fingerprint(store / first.version_path)
    log_before = (store / "recompile.log").read_bytes()
    observed: dict[str, object] = {}

    def fail_before_log_write(root: Path, version_path: str) -> None:
        observed["path"] = version_path
        raise RecompileRefused("recompile log could not be appended")

    def fail_remove(path: object, *_args: object, **_kwargs: object) -> None:
        observed["removed"] = path
        raise OSError("version removal failed")

    with monkeypatch.context() as patch:
        patch.setattr("module_generator.sync._append_log", fail_before_log_write)
        patch.setattr("module_generator.sync.shutil.rmtree", fail_remove)
        with pytest.raises(OSError, match="version removal failed"):
            recompile_module(
                _spec("Beta Name"), store=store, provider="provider_a", **_confirm()
            )

    failed_path = observed["path"]
    assert isinstance(failed_path, str)
    removed = observed["removed"]
    assert isinstance(removed, Path)
    assert removed.resolve() == (store / failed_path).resolve()
    assert removed.resolve() != (store / first.version_path).resolve()
    assert failed_path != first.version_path
    assert (store / failed_path).is_dir()
    assert _fingerprint(store / first.version_path) == previous
    assert (store / "recompile.log").read_bytes() == log_before
    assert failed_path.encode() not in log_before
    kept = (store / first.version_path / "ispec.md").read_text(encoding="utf-8")
    assert '"Alpha Name"' in kept
    assert '"Beta Name"' not in kept


def test_log_write_that_persists_bytes_before_raising_does_not_block_a_changed_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A log write that lands bytes and then raises must not strand the store."""

    store = tmp_path / "store"
    first = recompile_module(
        _spec("Alpha Name"), store=store, provider="provider_a", **_confirm()
    )
    previous = _fingerprint(store / first.version_path)
    real_open = os.open
    real_write = os.write
    watched: set[int] = set()
    persisted = {"count": 0, "nbytes": 0}

    def _base_name(path: object) -> str:
        text = os.fspath(path)  # type: ignore[arg-type]
        if isinstance(text, bytes):
            text = os.fsdecode(text)
        return text.replace("\\", "/").rsplit("/", 1)[-1]

    def open_hook(path: object, flags: int, *args: object, **kwargs: object) -> int:
        fd = real_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]
        writable = (flags & os.O_ACCMODE) != os.O_RDONLY
        name = _base_name(path)
        if writable and (name == "recompile.log" or name.startswith("recompile-log-")):
            watched.add(fd)
        return fd

    def write_hook(fd: int, data: object) -> int:
        if fd not in watched:
            return real_write(fd, data)  # type: ignore[arg-type]
        blob = bytes(data)  # type: ignore[arg-type]
        if not blob:
            return real_write(fd, data)  # type: ignore[arg-type]
        real_write(fd, blob)
        persisted["count"] += 1
        persisted["nbytes"] = len(blob)
        raise OSError("log write persisted bytes then failed")

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", open_hook)
        patch.setattr(os, "write", write_hook)
        with pytest.raises(OSError, match="log write persisted bytes then failed"):
            recompile_module(
                _spec("Beta Name"), store=store, provider="provider_a", **_confirm()
            )

    assert persisted["count"] == 1
    assert persisted["nbytes"] > 0
    assert _fingerprint(store / first.version_path) == previous
    _assert_log_matches_artifacts(store)

    changed = recompile_module(
        _spec("Gamma Name"), store=store, provider="provider_a", **_confirm()
    )
    assert changed.version_path != first.version_path
    assert _fingerprint(store / first.version_path) == previous
    assert '"Gamma Name"' in (store / changed.version_path / "ispec.md").read_text(
        encoding="utf-8"
    )
    _assert_log_matches_artifacts(store)

    before_identical = _fingerprint(store)
    with pytest.raises(RecompileRefused, match="existing version path"):
        recompile_module(
            _spec("Gamma Name"), store=store, provider="provider_a", **_confirm()
        )
    with pytest.raises(RecompileRefused, match="existing version path"):
        recompile_module(
            _spec("Alpha Name"), store=store, provider="provider_a", **_confirm()
        )
    assert _fingerprint(store) == before_identical
    assert _fingerprint(store / first.version_path) == previous
    kept = (store / first.version_path / "ispec.md").read_text(encoding="utf-8")
    assert '"Alpha Name"' in kept
    assert '"Gamma Name"' not in kept


def test_identical_spec_into_existing_version_path_is_refused(tmp_path: Path) -> None:
    store = tmp_path / "store"
    first = recompile_module(_spec(), store=store, provider="provider_a", **_confirm())
    before = _fingerprint(store)

    with pytest.raises(RecompileRefused, match="existing version path"):
        recompile_module(_spec(), store=store, provider="provider_a", **_confirm())

    assert _fingerprint(store) == before
    assert (store / first.version_path).is_dir()


def test_other_provider_yields_a_distinct_versioned_artifact(tmp_path: Path) -> None:
    store = tmp_path / "store"
    spec = _spec()
    first = recompile_module(spec, store=store, provider="provider_a", **_confirm())
    previous = _fingerprint(store / first.version_path)
    second = recompile_module(spec, store=store, provider="provider_b", **_confirm())

    assert first.version_path != second.version_path
    assert first.provider == "provider_a"
    assert second.provider == "provider_b"
    assert _fingerprint(store / first.version_path) == previous
    first_record = (store / first.version_path / "artifact.json").read_bytes()
    second_record = (store / second.version_path / "artifact.json").read_bytes()
    assert first_record != second_record
    assert b"provider_a" in first_record
    assert b"provider_b" in second_record
    assert artifact_module_files(store, first.version_path) == artifact_module_files(
        store, second.version_path
    )
    assert second.diff.previous_version_path == first.version_path
    assert second.diff.changed == ()


def test_fixture_spec_edited_outside_blocks_sync(tmp_path: Path) -> None:
    """Fixture: an ISPEC edit standing in for a spec edited outside the compiler."""

    store = tmp_path / "store"
    written = recompile_module(
        _spec(), store=store, provider="provider_a", **_confirm()
    )
    outside = ispec_to_module_spec(artifact_ispec(store, written.version_path))
    outside.display_name = "Edited outside"
    fixture_outside_ispec = module_spec_to_ispec(outside)
    fixture_odoo_module_files = artifact_module_files(store, written.version_path)
    before = _fingerprint(store)

    result = sync_module(
        store=store,
        version_path=written.version_path,
        outside_ispec=fixture_outside_ispec,
        odoo_module_files=fixture_odoo_module_files,
        **_confirm(),
    )

    assert result.blocked is True
    assert result.report
    assert {item.source for item in result.report} == {SPEC_EDITED_OUTSIDE}
    assert any(item.path.endswith("display_name") for item in result.report)
    assert "Edited outside" not in result.text()
    assert _fingerprint(store) == before


def test_fixture_module_edited_in_odoo_blocks_sync(tmp_path: Path) -> None:
    """Fixture: a changed module file standing in for a module edited in Odoo.

    No database is opened.
    """

    store = tmp_path / "store"
    written = recompile_module(
        _spec(), store=store, provider="provider_a", **_confirm()
    )
    fixture_outside_ispec = artifact_ispec(store, written.version_path)
    fixture_odoo_module_files = artifact_module_files(store, written.version_path)
    manifest = next(
        path for path in fixture_odoo_module_files if path.endswith("__manifest__.py")
    )
    fixture_odoo_module_files[manifest] += "\n# fixture: module edited in Odoo\n"
    before = _fingerprint(store)

    result = sync_module(
        store=store,
        version_path=written.version_path,
        outside_ispec=fixture_outside_ispec,
        odoo_module_files=fixture_odoo_module_files,
        **_confirm(),
    )

    assert result.blocked is True
    assert {item.source for item in result.report} == {MODULE_EDITED_IN_ODOO}
    assert any(item.path == manifest for item in result.report)
    assert all(item.detail == "content differs" for item in result.report)
    assert "fixture:" not in result.text()
    assert _fingerprint(store) == before


def test_confirm_phrase_does_not_bypass_drift(tmp_path: Path) -> None:
    store = tmp_path / "store"
    written = recompile_module(
        _spec(), store=store, provider="provider_a", **_confirm()
    )
    before = _fingerprint(store)

    result = sync_module(
        store=store,
        version_path=written.version_path,
        outside_ispec="fixture: not an ISPEC document\n",
        odoo_module_files=artifact_module_files(store, written.version_path),
        confirm_advanced=True,
        confirm_phrase="not the phrase",
    )

    assert result.blocked is True
    assert result.report[0].source == SPEC_EDITED_OUTSIDE
    assert _fingerprint(store) == before


def test_clean_sync_requires_confirm_and_does_not_write(tmp_path: Path) -> None:
    store = tmp_path / "store"
    written = recompile_module(
        _spec(), store=store, provider="provider_a", **_confirm()
    )
    observed_ispec = artifact_ispec(store, written.version_path)
    observed_files = artifact_module_files(store, written.version_path)
    before = _fingerprint(store)

    with pytest.raises(SyncRefused, match="confirm"):
        sync_module(
            store=store,
            version_path=written.version_path,
            outside_ispec=observed_ispec,
            odoo_module_files=observed_files,
            confirm_advanced=False,
            confirm_phrase=CONFIRM_PHRASE,
        )
    assert _fingerprint(store) == before

    result = sync_module(
        store=store,
        version_path=written.version_path,
        outside_ispec=observed_ispec,
        odoo_module_files=observed_files,
        **_confirm(),
    )
    assert result.blocked is False
    assert result.report == ()
    assert result.text() == "Sync is clear."
    assert _fingerprint(store) == before


def test_recompile_without_confirm_writes_nothing(tmp_path: Path) -> None:
    store = tmp_path / "store"
    with pytest.raises(RecompileRefused, match="confirm"):
        recompile_module(
            _spec(),
            store=store,
            provider="provider_a",
            confirm_advanced=False,
            confirm_phrase=CONFIRM_PHRASE,
        )
    assert not store.exists()


def test_recompile_refuses_a_non_module_spec(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="ModuleSpec"):
        recompile_module(
            ModelSpec(model="x_a", description="A"),  # type: ignore[arg-type]
            store=tmp_path / "store",
            provider="provider_a",
            **_confirm(),
        )
    assert not (tmp_path / "store").exists()


def test_sync_source_does_not_define_a_second_ir_or_compiler() -> None:
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    class_names = [
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]
    forbidden = {
        "ModuleSpec",
        "ModelSpec",
        "FieldSpec",
        "ViewSpec",
        "ActionSpec",
        "MenuSpec",
        "GroupSpec",
        "PythonAutomationSpec",
        "AccessRuleSpec",
        "RecordRuleSpec",
        "MailTemplateSpec",
        "CronJobSpec",
        "ReportSpec",
    }
    assert forbidden.isdisjoint(class_names)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(
        {
            "openai",
            "litellm",
            "odoorpc",
            "xmlrpc",
            "psycopg",
            "psycopg2",
            "httpx",
            "requests",
            "urllib",
        }
    )
    source = _SOURCE.read_text(encoding="utf-8")
    assert "render_module_files" in source
    assert "module_spec_to_ispec" in source
    assert "FileSystemLoader" not in source
    assert "Environment(" not in source
