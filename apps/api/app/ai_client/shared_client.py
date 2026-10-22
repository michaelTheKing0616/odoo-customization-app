"""The one shared AI client. Every provider handed out by app.llm_provider is wrapped here.

Order per call: topic guard (client surfaces) -> injection guard on untrusted text ->
PII/secret redaction (cloud) -> cache (exact, then safe near-duplicate) -> provider ->
output checks -> cache store (redacted only) -> restore placeholders -> client-facing checks.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.ai_client import ai_cache, guards
from app.ai_client.ai_scope import current_scope

LOCAL_PROVIDERS = frozenset({"ollama"})


class GuardBlocked(Exception):
    """Raised when policy forbids the call (e.g. no cloud-AI consent)."""


def _base():
    from app.llm_provider import LLMProvider
    return LLMProvider


def _make_class():
    LLMProvider = _base()

    class SharedAIClient(LLMProvider):
        shared_ai_client = True

        def __init__(self, inner: Any, *, guard_provider: Any = None) -> None:
            object.__setattr__(self, "inner", inner)
            object.__setattr__(self, "_guard_provider", guard_provider)

        # -- passthrough
        @property
        def name(self) -> str:
            return self.inner.name

        def reachable(self, *, timeout_s: float = 2.0) -> tuple[bool, str]:
            return self.inner.reachable(timeout_s=timeout_s)

        def __getattr__(self, item: str) -> Any:
            return getattr(object.__getattribute__(self, "inner"), item)

        # -- guarded, cached generation
        def generate_json(self, prompt: str, **kw: Any) -> str:
            return self._call("generate_json", prompt, kw)

        def generate_text(self, prompt: str, **kw: Any) -> str:
            return self._call("generate_text", prompt, kw)

        def _generate(self, method: str, prompt: str, kw: dict[str, Any]) -> str:
            """Primary model with a short timeout; on timeout or 5xx fall back once (Gemini)."""
            import os
            import re as _re
            from app.llm_provider import LLMError, _is_timeout_error

            fn = getattr(self.inner, method)
            if (self.inner.name or "").lower() != "gemini":
                return fn(prompt, **kw)
            fallback = os.environ.get("INGENIUM_GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
            primary = kw.get("model") or getattr(self.inner, "model", None)
            if not fallback or primary == fallback:
                return fn(prompt, **kw)
            # The primary model gets the caller's own timeout. A fixed 25 s cap made long contract/design
            # prompts time out on the primary and silently switch model mid-pipeline (452 fallbacks in one
            # eval run), which mixes models and invalidates comparisons. An explicit env cap still applies.
            want = float(kw.get("timeout_s") or 120.0)
            cap = os.environ.get("INGENIUM_PRIMARY_TIMEOUT_S")
            first = dict(kw, timeout_s=min(want, float(cap)) if cap else want)
            try:
                return fn(prompt, **first)
            except (LLMError, TimeoutError, OSError) as exc:
                if isinstance(exc, LLMError) and not (_is_timeout_error(exc) or _is_5xx(exc, _re)):
                    raise
                ai_cache.bump("model_fallbacks")
                guards.log_flag("model_fallback", {"from": str(primary), "to": fallback, "why": type(exc).__name__,
                                                    "detail": str(exc)[:160], "timeout_s": first.get("timeout_s"),
                                                    "prompt_chars": len(prompt) + len(str(kw.get("system") or ""))})
                return fn(prompt, **dict(kw, model=fallback))

        def _guard_llm(self) -> Any:
            gp = object.__getattribute__(self, "_guard_provider")
            return gp if gp is not None else self.inner

        def _call(self, method: str, prompt: str, kw: dict[str, Any]) -> str:
            sc = current_scope()
            fresh = bool(kw.pop("fresh", False)) or sc.fresh
            json_mode = method == "generate_json"
            system = kw.get("system") or ""
            cloud = (self.inner.name or "").lower() not in LOCAL_PROVIDERS
            if cloud and not sc.consent_cloud:
                guards.log_flag("cloud_consent_block", {})
                raise GuardBlocked("Cloud AI is switched off for this database until the client agrees to it.")

            def _reply(text: str) -> str:
                return json.dumps({"refused": True, "message": text}) if json_mode else text

            client_facing = sc.surface in guards.CLIENT_SURFACES
            # 4. topic guard
            topic_text = prompt if not guards.has_fences(prompt) else guards.client_chat_text(prompt)
            if client_facing and topic_text:
                tv = guards.topic_guard(topic_text, self._guard_llm())
                if not tv.allowed:
                    guards.log_flag(f"topic_{tv.kind}", {"sha": hashlib.sha256(prompt.encode()).hexdigest()[:16]})
                    return _reply(tv.reply)
            # 1. injection guard
            original_inputs = f"{system}\n{prompt}"
            if guards.has_fences(prompt):
                prompt, flags = guards.sanitize_untrusted(prompt, self._guard_llm())
                for f in flags:
                    guards.log_flag("injection", f)
                kw["system"] = system = (system + "\n\n" + guards.DATA_RULE).strip()
            elif client_facing:
                v = guards.classify_injection(prompt, self._guard_llm())
                if v.flagged:
                    guards.log_flag("injection", {"source": sc.surface, "score": v.score, "reasons": v.reasons})
                    return _reply(guards.REFUSAL_INJECTION)
            else:
                # Internal call with no fences: untrusted text may still be pasted in (uploads, BRDs,
                # record text). Scan every paragraph cheaply; withhold only strong hits, log the rest.
                prompt, flags = guards.sweep_unfenced(prompt)
                if flags:
                    for f in flags:
                        guards.log_flag("injection_unfenced", f)
                    kw["system"] = system = (system + "\n\n" + guards.DATA_RULE).strip()
            # 2. redaction before cloud AI
            red = guards.Redactor(sc.pii_names) if cloud else None
            if red is not None:
                prompt = red.redact(prompt)
                if system:
                    kw["system"] = system = red.redact(system)
                if red.kinds:
                    guards.log_flag("redacted", {"counts": dict(red.kinds)})
                    if red.mapping:
                        kw["system"] = system = (system + "\n\nValues like ⟦EMAIL_1⟧ are placeholders; "
                                                 "keep them exactly as written.").strip()
            # cache
            model = kw.get("model") or getattr(self.inner, "model", None) or self.inner.name
            opts = {k: v for k, v in kw.items() if k not in {"system", "timeout_s", "image_bytes"}}
            if kw.get("image_bytes"):
                opts["image_sha"] = hashlib.sha256(kw["image_bytes"]).hexdigest()
            key, scope_key = ai_cache.make_key(
                provider=self.inner.name, model=str(model), method=method, system=system, prompt=prompt,
                options=opts, db=sc.db, odoo_version=sc.odoo_version, snapshot_hash=sc.snapshot_hash)
            ai_cache.bump("calls")
            in_tok = ai_cache.est_tokens(system) + ai_cache.est_tokens(prompt)
            cached: str | None = None
            if fresh:
                ai_cache.bump("bypass_fresh")
            else:
                cached = ai_cache.get_exact(key)
                kind = "hits_exact"
                if cached is None and sc.semantic_ok and not kw.get("image_bytes"):
                    sem = ai_cache.get_semantic(scope_key, prompt)
                    if sem:
                        cached, kind = sem[0], "hits_semantic"
                if cached is not None:
                    ai_cache.note_hit(True)
                    ai_cache.bump(kind)
                    out_tok = ai_cache.est_tokens(cached)
                    ai_cache.bump("tokens_saved", in_tok + out_tok)
                    ai_cache.bump("usd_saved", ai_cache.usd_cost(str(model), in_tok, out_tok))
            if cached is None:
                ai_cache.note_hit(False)
                ai_cache.bump("misses")
                raw = self._generate(method, prompt, kw)
                out_tok = ai_cache.est_tokens(raw)
                ai_cache.bump("usd_spent", ai_cache.usd_cost(str(model), in_tok, out_tok))
                pre = guards.check_output(raw, system=system, inputs=prompt + system, surface="internal",
                                          json_mode=json_mode)
                for f in pre.flags:
                    guards.log_flag(f["kind"], f)
                raw = pre.text
                sensitive = bool(pre.flags) or (red is None and _looks_sensitive(prompt + raw))
                if sensitive:
                    ai_cache.bump("skip_sensitive")
                else:
                    ai_cache.put(key, scope_key, db=sc.db, model=str(model), prompt=prompt, value=raw,
                                 ttl_s=sc.cache_ttl_s, in_tok=in_tok, out_tok=out_tok,
                                 reads=sc.reads or None)
            else:
                raw = cached
            # restore + client-facing checks
            if red is not None:
                raw = red.restore_json(raw) if json_mode else red.restore(raw)
            if client_facing:
                chk = guards.check_output(raw, system=system, inputs=original_inputs, surface=sc.surface,
                                          json_mode=json_mode, claim_verifier=sc.claim_verifier)
                for f in chk.flags:
                    guards.log_flag(f["kind"], f)
                raw = chk.text
            return raw

    return SharedAIClient


def _is_5xx(exc: Exception, _re: Any) -> bool:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int) and code:
        return code >= 500
    msg = str(exc).lower()
    return bool(_re.search(r"\b5\d\d\b", msg)) or "unavailable" in msg or "high demand" in msg


def _looks_sensitive(text: str) -> bool:
    r = guards.Redactor()
    r.redact(text)
    return bool(r.kinds)


_CLS: Any = None


def shared_client_class() -> Any:
    global _CLS
    if _CLS is None:
        _CLS = _make_class()
    return _CLS


def wrap(provider: Any, *, guard_provider: Any = None) -> Any:
    """Route a provider through the shared AI client (idempotent)."""
    if provider is None or getattr(provider, "shared_ai_client", False):
        return provider
    base = shared_client_class()
    cls = _SUBCLASSES.get(type(provider))
    if cls is None:
        # Subclass the provider's own class too, so isinstance(p, GeminiProvider) keeps working.
        cls = type(f"Shared{type(provider).__name__}", (base, type(provider)), {})
        _SUBCLASSES[type(provider)] = cls
    return cls(provider, guard_provider=guard_provider)


_SUBCLASSES: dict[type, Any] = {}


def unwrap(provider: Any) -> Any:
    return getattr(provider, "inner", provider) if getattr(provider, "shared_ai_client", False) else provider


def batch_generate(provider: Any, items: list[dict[str, Any]], *, max_workers: int = 4) -> list[str | Exception]:
    """Run many calls at once. Identical requests are sent once; each item is
    {"method": "generate_json"|"generate_text", "prompt": str, **kwargs}. Order is preserved."""
    client = wrap(provider)
    sig = [json.dumps(it, sort_keys=True, default=str) for it in items]
    uniq = list(dict.fromkeys(sig))
    if len(uniq) < len(sig):
        ai_cache.bump("batch_deduped", len(sig) - len(uniq))

    def _one(s: str) -> str | Exception:
        it = dict(json.loads(s))
        m = it.pop("method", "generate_json")
        p = it.pop("prompt")
        try:
            return getattr(client, m)(p, **it)
        except Exception as exc:  # noqa: BLE001
            return exc

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 8))) as ex:
        futs = {s: ex.submit(contextvars.copy_context().run, _one, s) for s in uniq}
        res = {s: f.result() for s, f in futs.items()}
    return [res[s] for s in sig]
