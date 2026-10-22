"""Lossless ISPEC serialization of ``module_generator.ModuleSpec``.

ISPEC is a markdown document. It is not a second module IR: both
directions use the ``ModuleSpec`` dataclass the compiler already owns.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import math
import re
import types
import typing
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from module_generator import ModuleSpec

ISPEC_HEADER = "# ISPEC module_spec 1"

_HEADING = re.compile(r"^(#{2,6}) ([a-z_]+)(?: (\d+))?$")
_KEY = re.compile(r"^([a-z_][a-z0-9_]*): (.*)$")
_TEXT = re.compile(r"^text ([0-9]+)$")
_INLINE_LIMIT = 100


class IspecError(ValueError):
    """The document is not a lossless serialization of ModuleSpec."""


class _Block(NamedTuple):
    name: str
    index: int | None
    values: dict[str, Any]
    children: dict[str, list[_Block]]


def _root_type() -> type[ModuleSpec]:
    from module_generator import ModuleSpec as root

    return root


@functools.lru_cache(maxsize=None)
def _hints(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _dataclass_list_item(tp: Any) -> type | None:
    if typing.get_origin(tp) is not list:
        return None
    args = typing.get_args(tp)
    if len(args) != 1:
        return None
    item = args[0]
    if isinstance(item, type) and dataclasses.is_dataclass(item):
        return item
    return None


def _is_dict_type(tp: Any) -> bool:
    return typing.get_origin(tp) is dict


def _kind(tp: Any) -> str:
    """Classify a ModuleSpec field annotation. Unknown shapes fail closed."""
    if tp is str:
        return "str"
    if tp is bool:
        return "bool"
    if tp is int:
        return "int"
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if origin is typing.Union or origin is types.UnionType:
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1 and type(None) in args:
            inner = non_none[0]
            if inner is str:
                return "opt_str"
            if inner is int:
                return "opt_int"
            if _is_dict_type(inner):
                return "opt_dict"
        raise IspecError(f"unsupported union annotation {tp!r}")
    if origin is list:
        if len(args) != 1:
            raise IspecError(f"unsupported list annotation {tp!r}")
        arg = args[0]
        if arg is str:
            return "list_str"
        if _is_dict_type(arg):
            return "list_dict"
        if _dataclass_list_item(tp) is not None:
            return "list_dc"
        raise IspecError(f"unsupported list annotation {tp!r}")
    raise IspecError(f"unsupported annotation {tp!r}")


def _json_tree(value: Any, path: str) -> None:
    if value is None or type(value) is str or type(value) is bool:
        return
    if type(value) is int:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise IspecError(f"{path} is not a finite number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _json_tree(item, f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise IspecError(f"{path} key is not a string")
            _json_tree(item, f"{path}.{key}")
        return
    raise IspecError(f"{path} has unsupported value {type(value).__name__}")


def _check_scalar(kind: str, value: Any, path: str) -> None:
    if kind == "str":
        if type(value) is not str:
            raise IspecError(f"{path} must be a string")
        return
    if kind == "opt_str":
        if value is None or type(value) is str:
            return
        raise IspecError(f"{path} must be a string or null")
    if kind == "bool":
        if type(value) is not bool:
            raise IspecError(f"{path} must be a boolean")
        return
    if kind == "int":
        if type(value) is not int:
            raise IspecError(f"{path} must be an integer")
        return
    if kind == "opt_int":
        if value is None or type(value) is int:
            return
        raise IspecError(f"{path} must be an integer or null")
    if kind == "opt_dict":
        if value is None:
            return
        if type(value) is not dict:
            raise IspecError(f"{path} must be an object or null")
        _json_tree(value, path)
        return
    if kind == "list_str":
        if type(value) is not list or any(type(item) is not str for item in value):
            raise IspecError(f"{path} must be a list of strings")
        return
    if kind == "list_dict":
        if type(value) is not list or any(type(item) is not dict for item in value):
            raise IspecError(f"{path} must be a list of objects")
        for index, item in enumerate(value):
            _json_tree(item, f"{path}[{index}]")
        return
    raise IspecError(f"{path} has unsupported kind {kind}")


def _emit_scalar(key: str, value: Any, kind: str) -> str:
    _check_scalar(kind, value, key)
    if kind in {"str", "opt_str"} and type(value) is str and "\n" in value:
        return f"{key}: text {len(value)}\n```\n{value}\n```\n"
    wide = kind in {"opt_dict", "list_dict", "list_str"} and (
        len(json.dumps(value, ensure_ascii=False)) > _INLINE_LIMIT
    )
    if wide:
        payload = json.dumps(value, ensure_ascii=False, indent=2)
        return f"{key}: json\n```\n{payload}\n```\n"
    try:
        payload = json.dumps(value, ensure_ascii=False)
    except TypeError as exc:
        raise IspecError(f"{key} is not JSON-serializable") from exc
    if "\n" in payload:
        return f"{key}: json\n```\n{payload}\n```\n"
    return f"{key}: {payload}\n"


def _emit(obj: Any, level: int, name: str, index: int | None) -> str:
    if name == "module":
        if level != 2 or index is not None:
            raise IspecError("module heading must be '## module'")
        heading = "## module"
    else:
        if index is None:
            raise IspecError(f"heading {name!r} requires an index")
        heading = f"{'#' * level} {name} {index}"
    cls = type(obj)
    hints = _hints(cls)
    chunks: list[str] = [f"{heading}\n"]
    lists: list[tuple[str, type, list[Any]]] = []
    for field in dataclasses.fields(cls):
        hint = hints[field.name]
        value = getattr(obj, field.name)
        item_cls = _dataclass_list_item(hint)
        path = f"{cls.__name__}.{field.name}"
        if item_cls is not None:
            if type(value) is not list:
                raise IspecError(f"{path} must be a list")
            for item in value:
                if type(item) is not item_cls:
                    raise IspecError(f"{path} must contain {item_cls.__name__}")
            lists.append((field.name, item_cls, value))
            continue
        chunks.append(_emit_scalar(field.name, value, _kind(hint)))
    for field_name, _item_cls, items in lists:
        for item_index, item in enumerate(items):
            chunks.append("\n")
            chunks.append(_emit(item, level + 1, field_name, item_index))
    return "".join(chunks)


def module_spec_to_ispec(spec: ModuleSpec) -> str:
    """Serialize ``spec`` to an ISPEC markdown document."""
    root = _root_type()
    if type(spec) is not root:
        raise TypeError(
            "ISPEC serializes module_generator.ModuleSpec only; "
            f"got {type(spec).__module__}.{type(spec).__name__}"
        )
    return f"{ISPEC_HEADER}\n\n{_emit(spec, 2, 'module', None)}"


def _line_at(doc: str, pos: int) -> tuple[str, int]:
    if pos > len(doc):
        raise IspecError("read past end of ISPEC document")
    if pos == len(doc):
        return "", pos
    end = doc.find("\n", pos)
    if end < 0:
        return doc[pos:], len(doc)
    return doc[pos:end], end + 1


def _skip_blank(doc: str, pos: int) -> int:
    while pos < len(doc):
        line, nxt = _line_at(doc, pos)
        if line != "":
            return pos
        pos = nxt
    return pos


def _parse_json(payload: str, what: str) -> Any:
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise IspecError(f"invalid {what}: {exc.msg}") from exc


def _parse_value(doc: str, pos: int, rest: str) -> tuple[Any, int]:
    text_match = _TEXT.match(rest)
    if text_match:
        length = int(text_match.group(1))
        line, pos = _line_at(doc, pos)
        if line != "```":
            raise IspecError("text value must open with a fence")
        if pos + length > len(doc):
            raise IspecError("text value overruns the document")
        value = doc[pos : pos + length]
        pos += length
        if pos >= len(doc) or doc[pos] != "\n":
            raise IspecError("text value must be followed by a newline")
        pos += 1
        line, pos = _line_at(doc, pos)
        if line != "```":
            raise IspecError("text value must close with a fence")
        return value, pos
    if rest == "json":
        line, pos = _line_at(doc, pos)
        if line != "```":
            raise IspecError("json value must open with a fence")
        start = pos
        close = doc.find("\n```", start)
        if close < 0:
            raise IspecError("json value is missing its closing fence")
        payload = doc[start:close]
        pos = close + 1
        line, pos = _line_at(doc, pos)
        if line != "```":
            raise IspecError("json value must close with a fence")
        return _parse_json(payload, "json value"), pos
    return _parse_json(rest, "json value"), pos


def _parse_block(doc: str, pos: int, level: int) -> tuple[_Block, int]:
    pos = _skip_blank(doc, pos)
    if pos >= len(doc):
        raise IspecError("expected a heading, found the end of the document")
    line, pos = _line_at(doc, pos)
    match = _HEADING.match(line)
    if not match or len(match.group(1)) != level:
        raise IspecError(f"expected a level-{level} heading, found {line!r}")
    name = match.group(2)
    index = int(match.group(3)) if match.group(3) is not None else None
    if name == "module":
        if index is not None or level != 2:
            raise IspecError("module heading must be '## module'")
    elif index is None:
        raise IspecError(f"heading {name!r} requires an index")
    values: dict[str, Any] = {}
    children: dict[str, list[_Block]] = {}
    while True:
        pos = _skip_blank(doc, pos)
        if pos >= len(doc):
            break
        line, nxt = _line_at(doc, pos)
        heading = _HEADING.match(line)
        if heading:
            child_level = len(heading.group(1))
            if child_level <= level:
                break
            if child_level != level + 1:
                raise IspecError(f"heading skipped a level: {line}")
            child, pos = _parse_block(doc, pos, child_level)
            bucket = children.setdefault(child.name, [])
            if child.index != len(bucket):
                raise IspecError(f"{child.name} index {child.index} is out of order")
            bucket.append(child)
            continue
        key_match = _KEY.match(line)
        if not key_match:
            raise IspecError(f"expected a field, found {line!r}")
        key, rest = key_match.group(1), key_match.group(2)
        if key in values:
            raise IspecError(f"duplicate field {key}")
        value, pos = _parse_value(doc, nxt, rest)
        values[key] = value
    return _Block(name, index, values, children), pos


def _build(cls: type, block: _Block, path: str) -> Any:
    hints = _hints(cls)
    kwargs: dict[str, Any] = {}
    consumed: set[str] = set()
    for field in dataclasses.fields(cls):
        hint = hints[field.name]
        field_path = f"{path}.{field.name}"
        item_cls = _dataclass_list_item(hint)
        if item_cls is not None:
            kids = block.children.get(field.name, [])
            kwargs[field.name] = [
                _build(item_cls, kid, f"{field_path}[{item_index}]")
                for item_index, kid in enumerate(kids)
            ]
            consumed.add(field.name)
            continue
        if field.name not in block.values:
            raise IspecError(f"missing {field_path}")
        kwargs[field.name] = block.values[field.name]
        _check_scalar(_kind(hint), kwargs[field.name], field_path)
        consumed.add(field.name)
    unknown = (set(block.values) | set(block.children)) - consumed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise IspecError(f"unknown field on {path}: {names}")
    try:
        return cls(**kwargs)
    except (TypeError, ValueError) as exc:
        raise IspecError(f"could not build {cls.__name__}: {exc}") from exc


def ispec_to_module_spec(text: str) -> ModuleSpec:
    """Parse an ISPEC document back into the same ``ModuleSpec`` type."""
    if type(text) is not str:
        raise TypeError("ISPEC document must be a string")
    pos = _skip_blank(text, 0)
    if pos >= len(text):
        raise IspecError("empty ISPEC document")
    line, pos = _line_at(text, pos)
    if line != ISPEC_HEADER:
        raise IspecError(f"expected {ISPEC_HEADER!r}")
    block, pos = _parse_block(text, pos, 2)
    if block.name != "module":
        raise IspecError("root heading must be module")
    pos = _skip_blank(text, pos)
    if pos < len(text):
        trailing, _ = _line_at(text, pos)
        raise IspecError(f"unexpected trailing content: {trailing!r}")
    root = _root_type()
    built = _build(root, block, "module")
    if type(built) is not root:
        raise IspecError("parse did not produce ModuleSpec")
    return built


__all__ = [
    "ISPEC_HEADER",
    "IspecError",
    "ispec_to_module_spec",
    "module_spec_to_ispec",
]
