"""Read-only ModuleSpec validation against a live Odoo connection (TIER-2)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Literal

from odoo_client import OdooClient

ValidateStatus = Literal["pass", "warn", "fail"]


@dataclass
class ValidateLiveItem:
    item_id: str
    category: str
    status: ValidateStatus
    message: str


@dataclass
class ValidateLiveResult:
    ok: bool
    items: list[ValidateLiveItem] = field(default_factory=list)
    fail_count: int = 0
    warn_count: int = 0
    message: str = ""

    def add(self, item: ValidateLiveItem) -> None:
        self.items.append(item)
        if item.status == "fail":
            self.fail_count += 1
        elif item.status == "warn":
            self.warn_count += 1


def _selection_keys(selection: Any) -> list[str]:
    if not isinstance(selection, str):
        return []
    return re.findall(r"\('([^']+)'\s*,", selection)


def _models_in_spec(spec: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for m in spec.get("models") or []:
        if isinstance(m, dict) and m.get("model"):
            out.add(str(m["model"]))
    return out


def _model_exists_or_planned(client: OdooClient, model: str, planned: set[str]) -> bool:
    if model in planned:
        return True
    try:
        return client.model_exists(model)
    except Exception:  # noqa: BLE001
        return False


def _xpath_matches(parent_arch: str, expr: str) -> bool | None:
    expr = (expr or "").strip()
    if not expr or not parent_arch.strip():
        return None
    try:
        root = ET.fromstring(parent_arch)
    except ET.ParseError:
        return None

    name_match = re.search(r"@name=['\"]([^'\"]+)['\"]", expr)
    if expr.startswith("//field") and name_match:
        fname = name_match.group(1)
        return any(el.tag == "field" and el.get("name") == fname for el in root.iter())

    if expr.startswith("//"):
        tag = re.match(r"//([a-zA-Z0-9_-]+)", expr)
        if tag:
            t = tag.group(1)
            return any(el.tag == t for el in root.iter())
    return None


def validate_module_spec_live(client: OdooClient, spec: dict[str, Any]) -> ValidateLiveResult:
    result = ValidateLiveResult(ok=True, message="Validation complete")
    planned = _models_in_spec(spec)

    models = spec.get("models") or []
    if not isinstance(models, list) or not models:
        result.add(
            ValidateLiveItem(
                item_id="spec.models",
                category="spec",
                status="fail",
                message="spec.models must be a non-empty list",
            )
        )
    else:
        result.add(
            ValidateLiveItem(
                item_id="spec.models",
                category="spec",
                status="pass",
                message=f"{len(models)} model(s) in draft",
            )
        )

    for idx, model_def in enumerate(models if isinstance(models, list) else []):
        if not isinstance(model_def, dict):
            continue
        model_name = str(model_def.get("model") or "")
        if not model_name:
            result.add(
                ValidateLiveItem(
                    item_id=f"models[{idx}]",
                    category="model",
                    status="fail",
                    message="Model entry missing model name",
                )
            )
            continue
        fields = model_def.get("fields") or []
        if not isinstance(fields, list):
            continue
        for fidx, fdef in enumerate(fields):
            if not isinstance(fdef, dict):
                continue
            fname = str(fdef.get("name") or "")
            ftype = str(fdef.get("ttype") or "")
            if ftype == "selection" and fdef.get("selection"):
                keys = _selection_keys(fdef.get("selection"))
                if not keys:
                    result.add(
                        ValidateLiveItem(
                            item_id=f"{model_name}.{fname}",
                            category="field",
                            status="warn",
                            message="Selection field has no parseable keys",
                        )
                    )
                else:
                    result.add(
                        ValidateLiveItem(
                            item_id=f"{model_name}.{fname}",
                            category="field",
                            status="pass",
                            message=f"Selection keys: {', '.join(keys[:8])}",
                        )
                    )

    for idx, view in enumerate(spec.get("views") or []):
        if not isinstance(view, dict):
            continue
        model = str(view.get("model") or "")
        vtype = str(view.get("type") or "form")
        arch = view.get("arch")
        item_id = f"views[{idx}]"
        if not model:
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="view",
                    status="fail",
                    message="View missing model",
                )
            )
            continue
        if not _model_exists_or_planned(client, model, planned):
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="view",
                    status="fail",
                    message=f"Model {model} does not exist on this connection",
                )
            )
            continue
        if model in planned and not client.model_exists(model):
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="view",
                    status="pass",
                    message=f"Model {model} will be created during apply",
                )
            )
        if not isinstance(arch, str) or not arch.strip():
            continue
        try:
            root = ET.fromstring(arch if arch.strip().startswith("<") else f"<wrap>{arch}</wrap>")
            xpath_exprs = [
                el.get("expr", "")
                for el in root.iter("xpath")
                if el.get("expr")
            ]
        except ET.ParseError:
            xpath_exprs = re.findall(r'expr=(["\'])(.*?)\1', arch)
        if not xpath_exprs:
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="view",
                    status="pass",
                    message=f"View arch for {model} ({vtype}) — no xpath anchors to verify",
                )
            )
            continue
        parent_arch = ""
        try:
            primary = client.find_view(model, vtype, primary_only=True)
            if primary is None:
                primary = client.find_view(model, vtype)
            if primary and primary.arch:
                parent_arch = primary.arch
        except Exception:  # noqa: BLE001
            parent_arch = ""
        if not parent_arch:
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="view",
                    status="warn",
                    message=f"Could not load parent {vtype} arch for {model} — xpath not verified",
                )
            )
            continue
        for expr in xpath_exprs:
            matched = _xpath_matches(parent_arch, expr)
            if matched is True:
                result.add(
                    ValidateLiveItem(
                        item_id=f"{item_id}:{expr}",
                        category="xpath",
                        status="pass",
                        message=f"XPath anchor resolves: {expr}",
                    )
                )
            elif matched is False:
                result.add(
                    ValidateLiveItem(
                        item_id=f"{item_id}:{expr}",
                        category="xpath",
                        status="fail",
                        message=f"XPath anchor not found in parent view: {expr}",
                    )
                )
            else:
                result.add(
                    ValidateLiveItem(
                        item_id=f"{item_id}:{expr}",
                        category="xpath",
                        status="warn",
                        message=f"Could not automatically verify xpath: {expr}",
                    )
                )

    for idx, auto in enumerate(spec.get("automations") or []):
        if not isinstance(auto, dict):
            continue
        model = str(auto.get("model") or "")
        item_id = f"automations[{idx}]"
        if not model:
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="automation",
                    status="fail",
                    message="Automation missing model",
                )
            )
            continue
        if not _model_exists_or_planned(client, model, planned):
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="automation",
                    status="fail",
                    message=f"Automation model {model} does not exist",
                )
            )
        else:
            result.add(
                ValidateLiveItem(
                    item_id=item_id,
                    category="automation",
                    status="pass",
                    message=f"Automation target model {model} OK",
                )
            )

    for idx, btn in enumerate(spec.get("smart_buttons") or []):
        if not isinstance(btn, dict):
            continue
        on_model = str(btn.get("on_model") or btn.get("source_model") or "")
        related = str(btn.get("related_model") or btn.get("target_model") or "")
        item_id = f"smart_buttons[{idx}]"
        for label, m in (("on_model", on_model), ("related_model", related)):
            if not m:
                continue
            if not _model_exists_or_planned(client, m, planned):
                result.add(
                    ValidateLiveItem(
                        item_id=f"{item_id}.{label}",
                        category="smart_button",
                        status="fail",
                        message=f"Smart button {label} {m} does not exist",
                    )
                )
            else:
                result.add(
                    ValidateLiveItem(
                        item_id=f"{item_id}.{label}",
                        category="smart_button",
                        status="pass",
                        message=f"Smart button {label} {m} OK",
                    )
                )

    result.ok = result.fail_count == 0
    if result.fail_count:
        result.message = f"{result.fail_count} check(s) failed — fix before apply"
    elif result.warn_count:
        result.message = f"Passed with {result.warn_count} warning(s)"
    else:
        result.message = "All live checks passed"
    return result
