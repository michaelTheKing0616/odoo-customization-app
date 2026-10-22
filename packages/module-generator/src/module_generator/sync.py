"""Versioned recompile and drift-blocking sync for ``ModuleSpec``.

Recompile calls the existing renderer and stores a new artifact. It never
opens an existing version path for write. Sync only reads. Drift blocks and
returns a report; it does not rewrite the artifact or the spec.

The provider argument is an opaque label. It is not a model id, and this
module does not call a model or a database.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Same operator phrase as the product confirm gate. This package does not
# import the API layer to read it.
CONFIRM_PHRASE = "I understand the risks"

SPEC_EDITED_OUTSIDE = "spec_edited_outside"
MODULE_EDITED_IN_ODOO = "module_edited_in_odoo"

_ARTIFACT_FORMAT = "ingenium_recompile_artifact"
_TECHNICAL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
_VERSION_PATH = re.compile(r"^[a-z][a-z0-9_]*/[a-z][a-z0-9_-]{0,40}/[0-9a-f]{64}$")
_LOG_NAME = "recompile.log"
_LOG_TMP_PREFIX = "recompile-log-"
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class RecompileRefused(Exception):
    """Recompile wrote nothing. An existing artifact is left unchanged."""


class SyncRefused(Exception):
    """Sync did not run. Drift is a ``SyncResult``, not this exception."""


@dataclass(frozen=True)
class ArtifactDiff:
    """File diff of the new render against the previous artifact."""

    previous_version_path: str | None
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]


@dataclass(frozen=True)
class RecompileResult:
    """A newly written version. ``version_path`` is relative to the store."""

    version_path: str
    provider: str
    ispec_sha256: str
    diff: ArtifactDiff


@dataclass(frozen=True)
class DriftItem:
    """One drift finding. ``detail`` never includes file or spec contents."""

    source: str
    path: str
    detail: str


@dataclass(frozen=True)
class SyncResult:
    """Drift report. ``blocked`` is true when ``report`` is non-empty.

    Sync does not modify the store or the spec on either result.
    """

    blocked: bool
    version_path: str
    report: tuple[DriftItem, ...]

    def text(self) -> str:
        head = "Sync blocked." if self.blocked else "Sync is clear."
        lines = [f"{item.source} {item.path}: {item.detail}" for item in self.report]
        return head if not lines else head + "\n" + "\n".join(lines)


def recompile_module(
    spec: object,
    *,
    store: Path,
    provider: str,
    confirm_advanced: bool,
    confirm_phrase: str | None,
) -> RecompileResult:
    """Write a new versioned artifact for ``spec``.

    Inputs: a ``module_generator.ModuleSpec``, a store directory, a provider
    label, and the confirm flag plus phrase. Output: the relative version
    path and a diff against the previous artifact for that module. Side
    effect: one new directory under the store, plus one appended log line.
    An existing version path is refused and left untouched.
    """

    spec = _require_spec(spec)
    _check_confirm_types(confirm_advanced, confirm_phrase)
    if not _phrase_ok(confirm_advanced, confirm_phrase):
        raise RecompileRefused("recompile requires confirm")
    provider = _require_provider(provider)
    technical_name = _require_technical_name(spec.technical_name)
    ispec = _ispec_text(spec)
    digest = _sha256_text(ispec)
    version_path = f"{technical_name}/{provider}/{digest}"
    root = _store_root(store, create=False)
    dest = _join(root, version_path)
    if _occupied(dest):
        raise RecompileRefused(
            f"recompile refuses to overwrite existing version path {version_path}"
        )
    logged, on_disk = _version_sets(root, technical_name)
    if set(logged) != on_disk:
        raise RecompileRefused("recompile log does not match stored artifacts")
    previous = logged[-1] if logged else None
    previous_files = (
        artifact_module_files(root, previous) if previous is not None else None
    )
    rendered = _render_copy(ispec)
    diff = _file_diff(previous, previous_files, rendered)
    _commit(
        root,
        dest,
        version_path=version_path,
        provider=provider,
        technical_name=technical_name,
        digest=digest,
        ispec=ispec,
        module_files=rendered,
    )
    return RecompileResult(
        version_path=version_path,
        provider=provider,
        ispec_sha256=digest,
        diff=diff,
    )


def sync_module(
    *,
    store: Path,
    version_path: str,
    outside_ispec: str,
    odoo_module_files: Mapping[str, str],
    confirm_advanced: bool,
    confirm_phrase: str | None,
) -> SyncResult:
    """Compare one artifact with an outside spec and an observed module.

    Inputs are the stored version, the outside ISPEC text, and the module
    files observed for that version. Those observations may be fixtures.
    This function does not open a database and does not call a model.

    Drift returns ``blocked`` and a report, including when the confirm
    phrase is present. A clear result still requires confirm. Neither
    result writes.
    """

    _check_confirm_types(confirm_advanced, confirm_phrase)
    if type(outside_ispec) is not str:
        raise TypeError("outside_ispec must be a string")
    observed = _require_text_map(odoo_module_files, "odoo_module_files")
    root = _store_root(store, create=False)
    path = _require_version_path(version_path)
    stored_ispec = artifact_ispec(root, path)
    stored_files = artifact_module_files(root, path)
    report = tuple(
        _spec_drift(stored_ispec, outside_ispec) + _module_drift(stored_files, observed)
    )
    if report:
        return SyncResult(blocked=True, version_path=path, report=report)
    if not _phrase_ok(confirm_advanced, confirm_phrase):
        raise SyncRefused("sync requires confirm")
    return SyncResult(blocked=False, version_path=path, report=())


def artifact_ispec(store: Path, version_path: str) -> str:
    """Return the ISPEC document stored for ``version_path``."""

    root = _store_root(store, create=False)
    path = _require_version_path(version_path)
    record, directory = _load_record(root, path)
    text = _read_text(directory / "ispec.md")
    if _sha256_text(text) != record["ispec_sha256"]:
        raise SyncRefused("artifact ISPEC does not match its digest")
    return text


def artifact_module_files(store: Path, version_path: str) -> dict[str, str]:
    """Return a copy of the rendered module files for ``version_path``."""

    root = _store_root(store, create=False)
    path = _require_version_path(version_path)
    record, directory = _load_record(root, path)
    files = _read_module_dir(directory / "module")
    if _files_digest(files) != record["module_sha256"]:
        raise SyncRefused("artifact module files do not match the recorded digest")
    return files


def _require_spec(spec: object) -> Any:
    from module_generator import ModuleSpec

    if type(spec) is not ModuleSpec:
        raise TypeError(
            "recompile accepts module_generator.ModuleSpec only; "
            f"got {type(spec).__module__}.{type(spec).__name__}"
        )
    return spec


def _ispec_text(spec: object) -> str:
    from module_generator.ispec import module_spec_to_ispec

    return module_spec_to_ispec(spec)  # type: ignore[arg-type]


def _render_copy(ispec: str) -> dict[str, str]:
    """Render a copy so the caller's ModuleSpec is not mutated."""

    from module_generator import render_module_files
    from module_generator.ispec import ispec_to_module_spec

    files = render_module_files(ispec_to_module_spec(ispec))
    if type(files) is not dict:
        raise RecompileRefused("compiler did not return module files")
    rendered: dict[str, str] = {}
    for path, content in files.items():
        if type(path) is not str:
            raise RecompileRefused("compiler returned a non-text module path")
        try:
            relative = _safe_relative(path)
        except ValueError as exc:
            raise RecompileRefused("compiler returned an unsafe module path") from exc
        if type(content) is not str:
            raise RecompileRefused("compiler returned a non-text module file")
        if relative in rendered:
            raise RecompileRefused("compiler returned a duplicate module path")
        rendered[relative] = content
    return rendered


def _check_confirm_types(confirm_advanced: object, confirm_phrase: object) -> None:
    if type(confirm_advanced) is not bool:
        raise TypeError("confirm_advanced must be a bool")
    if confirm_phrase is not None and type(confirm_phrase) is not str:
        raise TypeError("confirm_phrase must be a string or None")


def _phrase_ok(confirm_advanced: bool, confirm_phrase: str | None) -> bool:
    phrase = confirm_phrase.strip() if confirm_phrase else ""
    return confirm_advanced and phrase == CONFIRM_PHRASE


def _require_provider(provider: object) -> str:
    if type(provider) is not str or _PROVIDER.fullmatch(provider) is None:
        raise RecompileRefused("provider is not a version-path label")
    return provider


def _require_technical_name(name: object) -> str:
    if type(name) is not str or _TECHNICAL_NAME.fullmatch(name) is None:
        raise RecompileRefused("technical_name is not a module name")
    return name


def _require_version_path(version_path: object) -> str:
    if type(version_path) is not str or _VERSION_PATH.fullmatch(version_path) is None:
        raise SyncRefused("version path is not a recompile artifact path")
    return version_path


def _require_text_map(value: object, label: str) -> dict[str, str]:
    if type(value) is not dict:
        raise TypeError(f"{label} must be a dict of strings")
    cleaned: dict[str, str] = {}
    for path, content in value.items():
        if type(path) is not str or type(content) is not str:
            raise TypeError(f"{label} must be a dict of strings")
        try:
            relative = _safe_relative(path)
        except ValueError as exc:
            raise SyncRefused("observed module path is not a relative path") from exc
        cleaned[relative] = content
    return cleaned


def _safe_relative(path: str) -> str:
    if not path or path.startswith(("/", "\\")) or "\\" in path:
        raise ValueError("module path is not a relative path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("module path is not a relative path")
    return path


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _files_digest(files: Mapping[str, str]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(files):
        hasher.update(path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(files[path].encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def _store_root(store: Path, *, create: bool) -> Path:
    if not isinstance(store, Path):
        raise TypeError("store must be a pathlib.Path")
    if store.is_symlink():
        raise RecompileRefused("store path must not be a symlink")
    if store.exists():
        if not store.is_dir():
            raise RecompileRefused("store path is not a directory")
        return store.resolve()
    if not create:
        return store
    store.mkdir(parents=True)
    return store.resolve()


def _join(root: Path, relative: str) -> Path:
    candidate = root.joinpath(*relative.split("/"))
    if candidate.is_symlink():
        raise RecompileRefused(
            f"recompile refuses to overwrite existing version path {relative}"
        )
    resolved_root = root.resolve() if root.exists() else root.absolute()
    resolved = candidate.resolve() if candidate.exists() else candidate.absolute()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise RecompileRefused("version path escapes the store")
    return candidate


def _occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _version_sets(root: Path, technical_name: str) -> tuple[list[str], set[str]]:
    if not root.exists():
        return [], set()
    logged = _log_versions(root, technical_name)
    on_disk = _versions_on_disk(root, technical_name)
    if len(logged) != len(set(logged)):
        raise RecompileRefused("recompile log does not match stored artifacts")
    return logged, on_disk


def _log_versions(root: Path, technical_name: str) -> list[str]:
    log = root / _LOG_NAME
    if not log.exists():
        return []
    if log.is_symlink() or not log.is_file():
        raise RecompileRefused("recompile log must be a regular file")
    prefix = technical_name + "/"
    found: list[str] = []
    for line in _read_text(log).splitlines():
        if not line:
            continue
        if _VERSION_PATH.fullmatch(line) is None:
            raise RecompileRefused("recompile log has an invalid line")
        if line.startswith(prefix):
            found.append(line)
    return found


def _versions_on_disk(root: Path, technical_name: str) -> set[str]:
    base = root / technical_name
    if not base.exists():
        return set()
    if base.is_symlink() or not base.is_dir():
        raise RecompileRefused("module directory is not a real directory")
    found: set[str] = set()
    for provider_dir in base.iterdir():
        if provider_dir.name.startswith("."):
            continue
        if provider_dir.is_symlink() or not provider_dir.is_dir():
            raise RecompileRefused("store contains an unexpected version entry")
        for digest_dir in provider_dir.iterdir():
            if digest_dir.name.startswith("."):
                continue
            relative = f"{technical_name}/{provider_dir.name}/{digest_dir.name}"
            if (
                _VERSION_PATH.fullmatch(relative) is None
                or digest_dir.is_symlink()
                or not digest_dir.is_dir()
            ):
                raise RecompileRefused("store contains an unexpected version entry")
            found.add(relative)
    return found


def _file_diff(
    previous: str | None,
    previous_files: Mapping[str, str] | None,
    rendered: Mapping[str, str],
) -> ArtifactDiff:
    if previous is None or previous_files is None:
        return ArtifactDiff(
            previous_version_path=None,
            added=tuple(sorted(rendered)),
            removed=(),
            changed=(),
        )
    added = tuple(sorted(set(rendered) - set(previous_files)))
    removed = tuple(sorted(set(previous_files) - set(rendered)))
    changed = tuple(
        sorted(
            path
            for path in set(rendered) & set(previous_files)
            if rendered[path] != previous_files[path]
        )
    )
    return ArtifactDiff(
        previous_version_path=previous,
        added=added,
        removed=removed,
        changed=changed,
    )


def _commit(
    root: Path,
    dest: Path,
    *,
    version_path: str,
    provider: str,
    technical_name: str,
    digest: str,
    ispec: str,
    module_files: dict[str, str],
) -> None:
    if not root.exists():
        root.mkdir(parents=True)
    root = root.resolve()
    dest = _join(root, version_path)
    if _occupied(dest):
        raise RecompileRefused(
            f"recompile refuses to overwrite existing version path {version_path}"
        )
    incoming = root / ".incoming"
    incoming.mkdir(exist_ok=True)
    tmp = incoming / uuid.uuid4().hex
    renamed = False
    try:
        tmp.mkdir()
        record = {
            "format": _ARTIFACT_FORMAT,
            "format_version": 1,
            "ispec_sha256": digest,
            "module_sha256": _files_digest(module_files),
            "provider": provider,
            "technical_name": technical_name,
        }
        _write_text(
            tmp / "artifact.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )
        _write_text(tmp / "ispec.md", ispec)
        for relative, content in module_files.items():
            _write_text(tmp / "module" / relative, content)
        if _occupied(dest):
            raise RecompileRefused(
                f"recompile refuses to overwrite existing version path {version_path}"
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.rename(tmp, dest)
        renamed = True
        try:
            _append_log(root, version_path)
        except BaseException:
            # The live log gains a complete line or stays unchanged. Remove
            # only this new directory, and only when its line is absent.
            # The previous version is a different directory and stays.
            # A failed removal propagates so the caller does not treat the
            # new directory as gone.
            if not _log_has_version_line(root, version_path):
                _discard_unlogged_version(dest)
            raise
    finally:
        if not renamed and tmp.exists():
            shutil.rmtree(tmp)


def _log_has_version_line(root: Path, version_path: str) -> bool:
    """True when the live log already contains ``version_path`` as a line.

    A regular file that cannot be read returns True so the caller keeps the
    new directory instead of deleting a version that may already be logged.
    """

    log = root / _LOG_NAME
    if log.is_symlink() or not log.is_file():
        return False
    try:
        text = _read_bytes(log).decode("utf-8")
    except (OSError, SyncRefused, UnicodeError):
        return True
    return any(line == version_path for line in text.splitlines())


def _discard_unlogged_version(dest: Path) -> None:
    """Remove a version directory that was renamed before its log line.

    ``OSError`` from the removal propagates. This path is the new version
    only; an earlier version directory is not removed.
    """

    if dest.is_symlink() or not dest.is_dir():
        return
    shutil.rmtree(dest)


def _append_log(root: Path, version_path: str) -> None:
    """Publish one complete log line, or leave the live log unchanged.

    The new line is written to a temp file and replaces ``recompile.log``
    only after every byte is in that file. A failed ``os.write`` cannot
    leave a partial line in the live log. Replacement is the last step, so
    a line that reaches the live log is not paired with deletion of its
    version directory. The version directory itself is never opened for
    write.
    """

    log = root / _LOG_NAME
    if log.is_symlink() or (log.exists() and not log.is_file()):
        raise RecompileRefused("recompile log must be a regular file")
    previous = _read_bytes(log) if log.exists() else b""
    if previous and not previous.endswith(b"\n"):
        previous += b"\n"
    payload = previous + (version_path + "\n").encode("utf-8")
    tmp = root / ".incoming" / f"{_LOG_TMP_PREFIX}{uuid.uuid4().hex}"
    tmp.parent.mkdir(exist_ok=True)
    _write_complete_file(tmp, payload)
    try:
        os.replace(tmp, log)
    except BaseException:
        _unlink_log_temp(tmp)
        raise


def _write_complete_file(path: Path, payload: bytes) -> None:
    """Write ``payload`` to a new file.

    On failure the new file is removed and the error propagates. ``os.close``
    failing after every byte has been written does not raise: the bytes are
    already in the file, and the caller can publish it.
    """

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RecompileRefused("recompile log could not be appended")
            view = view[written:]
        os.fsync(fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        _unlink_log_temp(path)
        raise
    try:
        os.close(fd)
    except OSError:
        return


def _unlink_log_temp(path: Path) -> None:
    """Remove a log temp file. This path is not the live log.

    A failed unlink must not replace the publish error. The temp file is
    not ``recompile.log``, so a leftover file is not a log line.
    """

    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
    except OSError:
        return


def _load_record(root: Path, version_path: str) -> tuple[dict[str, Any], Path]:
    if not root.exists():
        raise SyncRefused(f"unknown version path {version_path}")
    directory = _join(root.resolve(), version_path)
    if directory.is_symlink() or not directory.is_dir():
        raise SyncRefused(f"unknown version path {version_path}")
    record_path = directory / "artifact.json"
    if record_path.is_symlink() or not record_path.is_file():
        raise SyncRefused(f"unknown version path {version_path}")
    try:
        record = json.loads(_read_text(record_path))
    except json.JSONDecodeError as exc:
        raise SyncRefused("artifact record is not readable") from exc
    if type(record) is not dict:
        raise SyncRefused("artifact record is not readable")
    technical_name, provider, _digest = version_path.split("/")
    expected = {
        "format": _ARTIFACT_FORMAT,
        "format_version": 1,
        "provider": provider,
        "technical_name": technical_name,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise SyncRefused("artifact record is not readable")
    for key in ("ispec_sha256", "module_sha256"):
        digest = record.get(key)
        if type(digest) is not str or len(digest) != 64:
            raise SyncRefused("artifact record is not readable")
    if record["ispec_sha256"] != _digest:
        raise SyncRefused("artifact record is not readable")
    return record, directory


def _read_module_dir(module_dir: Path) -> dict[str, str]:
    if module_dir.is_symlink() or not module_dir.is_dir():
        raise SyncRefused("artifact module files are missing")
    files: dict[str, str] = {}
    root = module_dir.resolve()
    for path in sorted(module_dir.rglob("*")):
        if path.is_symlink():
            raise SyncRefused("artifact module files are missing")
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            raise SyncRefused("artifact module path escapes the store")
        relative = path.relative_to(module_dir).as_posix()
        files[relative] = _read_text(path)
    return files


def _spec_drift(stored: str, outside: str) -> list[DriftItem]:
    if stored == outside:
        return []
    from module_generator.ispec import IspecError, ispec_to_module_spec

    try:
        stored_spec = ispec_to_module_spec(stored)
    except IspecError as exc:
        raise SyncRefused("artifact ISPEC does not parse") from exc
    try:
        outside_spec = ispec_to_module_spec(outside)
    except IspecError:
        return [
            DriftItem(
                source=SPEC_EDITED_OUTSIDE,
                path="ispec",
                detail="outside document does not parse as the artifact ISPEC",
            )
        ]
    paths: list[str] = []
    _diff_values(stored_spec, outside_spec, "module", paths)
    if not paths:
        return [
            DriftItem(
                source=SPEC_EDITED_OUTSIDE,
                path="ispec",
                detail="outside document text differs from the artifact ISPEC",
            )
        ]
    return [
        DriftItem(source=SPEC_EDITED_OUTSIDE, path=path, detail="value differs")
        for path in paths
    ]


def _module_drift(
    stored: Mapping[str, str], observed: Mapping[str, str]
) -> list[DriftItem]:
    items: list[DriftItem] = []
    for path in sorted(set(stored) | set(observed)):
        if path not in observed:
            detail = "missing from the observed module"
        elif path not in stored:
            detail = "present only in the observed module"
        elif stored[path] != observed[path]:
            detail = "content differs"
        else:
            continue
        items.append(DriftItem(source=MODULE_EDITED_IN_ODOO, path=path, detail=detail))
    return items


def _diff_values(left: Any, right: Any, prefix: str, out: list[str]) -> None:
    if dataclasses.is_dataclass(left) and dataclasses.is_dataclass(right):
        if type(left) is not type(right):
            out.append(prefix)
            return
        for field in dataclasses.fields(left):
            child = f"{prefix}.{field.name}"
            _diff_values(
                getattr(left, field.name), getattr(right, field.name), child, out
            )
        return
    if type(left) is list and type(right) is list:
        if len(left) != len(right):
            out.append(prefix)
            return
        for index, (item_left, item_right) in enumerate(zip(left, right)):
            _diff_values(item_left, item_right, f"{prefix}[{index}]", out)
        return
    if type(left) is dict and type(right) is dict:
        for key in sorted(set(left) | set(right), key=str):
            child = f"{prefix}.{key}"
            if key not in left or key not in right:
                out.append(child)
                continue
            _diff_values(left[key], right[key], child, out)
        return
    if left != right or type(left) is not type(right):
        out.append(prefix)


def _read_text(path: Path) -> str:
    try:
        return _read_bytes(path).decode("utf-8")
    except UnicodeError as exc:
        raise SyncRefused("artifact file is not text") from exc


def _read_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SyncRefused("artifact file is not a regular file")
    fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    try:
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _occupied(path):
        raise RecompileRefused("recompile refuses to overwrite an artifact file")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o644)
    try:
        payload = text.encode("utf-8")
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RecompileRefused("artifact file could not be written")
            view = view[written:]
    finally:
        os.close(fd)


__all__ = [
    "CONFIRM_PHRASE",
    "MODULE_EDITED_IN_ODOO",
    "SPEC_EDITED_OUTSIDE",
    "ArtifactDiff",
    "DriftItem",
    "RecompileRefused",
    "RecompileResult",
    "SyncRefused",
    "SyncResult",
    "artifact_ispec",
    "artifact_module_files",
    "recompile_module",
    "sync_module",
]
