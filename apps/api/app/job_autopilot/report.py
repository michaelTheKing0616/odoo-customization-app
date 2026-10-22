"""UAT delivery report — markdown plus a stdlib PDF (no reportlab)."""

from __future__ import annotations

from app.job_autopilot.packet import AutopilotResult


def render_markdown(result: AutopilotResult) -> str:
    packet = result.packet
    score = result.job_scorecard
    lines = [
        "# Job Autopilot UAT report",
        "",
        result.scorecard_note,
        "",
        f"Status: {'smoke passed' if result.ok else 'not ready'}",
        f"Connection: {result.connection_kind}"
        + (" (sandbox)" if result.sandbox else ""),
        f"Promote ready: {'yes (human step)' if result.promote_ready else 'no'}",
        f"Retries: {result.retry_count}",
        f"Walkthrough seeded: {'yes' if result.walkthrough_seeded else 'no (client files — skipped)'}",
        "",
        "## Implementation-job scorecard",
    ]
    if score:
        lines.extend(
            [
                f"- stack_fit: {score.stack_fit:.1f}/10",
                f"- stock_coverage: {score.stock_coverage:.1f}/10",
                f"- data_load: {score.data_load:.1f}/10",
                f"- process_smoke: {score.process_smoke:.1f}/10",
                f"- overall (min): {score.overall:.1f}/10",
                "",
                "Findings:",
                *[f"- {f}" for f in score.findings],
            ]
        )
    else:
        lines.append("(not scored)")
    lines.extend(
        [
            "",
            "## Brief",
            packet.prompt,
            "",
            "## Stock apps",
            ", ".join(packet.stock_apps) or "(none)",
            "",
            "## Custom code",
        ]
    )
    if packet.custom_residuals:
        lines.extend(f"- {r.model}: {r.reason}" for r in packet.custom_residuals)
    else:
        lines.append("none — stock + data only")
    if packet.grounding:
        lines.extend(["", "## Matched from your documents", *[f"- {g[:300]}" for g in packet.grounding[:8]]])
    lines.extend(
        [
            "",
            "## Stages",
            " → ".join(result.stages) or "(none)",
            "",
            "## Bootstrap",
            (result.bootstrap.message if result.bootstrap else "skipped"),
            f"Recipe version: {getattr(result.bootstrap, 'recipe_version', 'n/a') if result.bootstrap else 'n/a'}",
            "",
            "## Connectors (domain-agnostic)",
        ]
    )
    conn = result.connectors
    if conn is None or conn.skipped:
        lines.append(conn.message if conn else "not run")
    else:
        lines.append(conn.message)
        for step in conn.steps[:16]:
            extra = f" ({step.detail})" if step.detail else ""
            lines.append(f"- {step.name}: {'ok' if step.ok else 'gap'}{extra}")
    lines.extend(
        [
            "",
            "## Custom apply",
        ]
    )
    custom = result.custom
    if custom is None:
        lines.append("n/a")
    elif custom.skipped:
        lines.append(custom.reason or "skipped")
    else:
        lines.append(custom.apply_message or "applied")
        if custom.expert_score_before is not None:
            lines.append(
                f"Expert-fix score {custom.expert_score_before} → {custom.expert_score_after}"
            )
        if custom.zip_base64:
            lines.append("Module zip attached (you publish-to may use it).")
    ingest = result.ingest
    lines.extend(["", "## Ingest"])
    if ingest is None or ingest.skipped:
        lines.append(ingest.reason if ingest else "skipped")
    else:
        lines.append(ingest.message)
        lines.append(
            f"Source rows: {ingest.source_rows}; loaded: {ingest.loaded_rows}; "
            f"unmatched M2O: {len(ingest.unmatched_m2o)}"
        )
        lines.extend(f"- gap: {g}" for g in ingest.gaps[:12])
    smoke = result.smoke
    lines.extend(["", "## Process smoke", smoke.message if smoke else "not run"])
    if smoke:
        lines.append(f"Named process: {smoke.named_process or 'default'}")
        lines.extend(f"- {'ok' if s.ok else 'fail'} {s.name}: {s.detail}" for s in smoke.steps)
    packet = result.config_packet if isinstance(result.config_packet, dict) else None
    if packet:
        lines.extend(["", "## config summary (client replay)", f"sha256: {packet.get('sha256')}"])
        for item in (packet.get("checklist") or [])[:24]:
            if isinstance(item, dict):
                lines.append(
                    f"- [{item.get('status')}] {item.get('label')} ({item.get('surface')})"
                )
            else:
                lines.append(f"- {item}")
        lines.append("Apply on the client with confirm — Autopilot stays sandbox-only.")
    lines.extend(["", "## Message", result.message])
    return "\n".join(lines)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_lines(markdown: str, width: int = 92) -> list[str]:
    raw_lines: list[str] = []
    for line in (markdown or "").splitlines() or [""]:
        safe = line.encode("latin-1", "replace").decode("latin-1")
        if not safe:
            raw_lines.append("")
            continue
        while len(safe) > width:
            raw_lines.append(safe[:width])
            safe = safe[width:]
        raw_lines.append(safe)
    return raw_lines


# Touch 134: the keystone seal, drawn in PDF path operators (arch in ink, keystone in cinnabar). 256-grid mark scaled to 72 pt.
def _seal_ops(x: float, y: float, size: float = 72) -> list[str]:
    k = size / 256

    def P(px: float, py: float) -> str:
        return f"{x + px * k:.2f} {y + (256 - py) * k:.2f}"

    import math

    def arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 16) -> list[tuple[float, float]]:
        return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * t / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * t / n))) for t in range(n + 1)]

    def ang(cx: float, cy: float, px: float, py: float) -> float:
        return math.degrees(math.atan2(py - cy, px - cx))

    # Extrados R100 about (128,151); intrados r46 about (128,148), from directions/A ingenium-mark-color.svg.
    left = arc(128, 151, 100, ang(128, 151, 93.53, 57.13), -180) + [(28, 208), (82, 208)] + arc(128, 148, 46, -180, ang(128, 148, 106.92, 107.11))
    right = arc(128, 151, 100, ang(128, 151, 162.47, 57.13), 0) + [(228, 208), (174, 208)] + arc(128, 148, 46, 0, ang(128, 148, 149.08, 107.11))
    legs = [[("m" if i == 0 else "l", a, b) for i, (a, b) in enumerate(pts)] for pts in (left, right)]
    ops = ["q", "0.10 0.11 0.13 rg"]
    for leg in legs:
        ops += [f"{P(a, b)} {c}" for c, a, b in leg] + ["h f"]
    ops += ["0.81 0.27 0.15 rg", f"{P(102.12, 54.41)} m", f"{P(153.88, 54.41)} l", f"{P(140.65, 103.77)} l", f"{P(115.35, 103.77)} l", "h f"]
    ops += ["0.10 0.11 0.13 RG", "0.6 w", f"{x - 6:.2f} {y - 6:.2f} {size + 12:.2f} {size + 12:.2f} re S", "Q"]
    return ops


def _qr_ops(data: str, x: float, y: float, size: float = 96) -> list[str]:
    """Verification QR drawn as filled squares (segno, MIT). Encodes the document fingerprint."""
    import segno

    rows = [list(r) for r in segno.make(data, error="m", micro=False).matrix]
    n = len(rows) + 8  # 4-module quiet zone each side
    m = size / n
    ops = ["q", "1 1 1 rg", f"{x:.2f} {y:.2f} {size:.2f} {size:.2f} re f", "0 0 0 rg"]
    for r, row in enumerate(rows):
        for c, on in enumerate(row):
            if on:
                ops.append(f"{x + (c + 4) * m:.2f} {y + size - (r + 5) * m:.2f} {m:.3f} {m:.3f} re")
    ops += ["f", "Q"]
    return ops


def sealed_pages(markdown: str, *, title: str, prepared: str) -> tuple[list[list[str]], dict[int, list[str]], str]:
    """Cover, contents, body, and a last page with the keystone seal and the document fingerprint."""
    import hashlib

    fp = hashlib.sha256((markdown or "").encode("utf-8")).hexdigest()
    body = _wrap_lines(markdown)
    body_pages = [body[i : i + 58] for i in range(0, max(len(body), 1), 58)]
    heads: list[tuple[str, int]] = []
    for n, pg in enumerate(body_pages):
        for line in pg:
            if line.startswith("#"):
                heads.append((line.lstrip("#").strip(), n + 3))
    cover = ["", "", "", "", "", title, "", prepared, "", "Fingerprint (SHA-256 of the contents):", fp[:32], fp[32:]]
    contents = ["Contents", ""] + [f"{h[:70]:<74}{pg:>4}" for h, pg in heads[:52]]
    seal = ["Seal", "", "This document was prepared and sealed by Ingenium.", "Its fingerprint is the SHA-256 of its contents:", fp[:32], fp[32:],
            "", "To verify: hash the contents again and compare. Any change gives a different fingerprint."]
    pages = [cover, contents, *body_pages, seal]
    seal.append("The QR code holds the same fingerprint.")
    extra = {len(pages) - 1: _seal_ops(200, 420) + _qr_ops(f"ingenium:sha256:{fp}", 320, 408)}
    return pages, extra, fp


def render_sealed_pdf_bytes(markdown: str, *, title: str, prepared: str) -> bytes:
    pages, extra, _ = sealed_pages(markdown, title=title, prepared=prepared)
    return render_pdf_bytes(markdown, pages=pages, extra_ops=extra)


def render_pdf_bytes(markdown: str, *, pages: list[list[str]] | None = None, extra_ops: dict[int, list[str]] | None = None) -> bytes:
    """Minimal multi-page PDF using Helvetica. Non-ASCII becomes '?'."""
    if pages is None:
        wrapped = _wrap_lines(markdown)
        pages = [wrapped[i : i + 58] for i in range(0, max(len(wrapped), 1), 58)]
    extra_ops = extra_ops or {}
    page_ids = list(range(3, 3 + 2 * len(pages), 2))
    content_ids = [pid + 1 for pid in page_ids]
    font_id = page_ids[-1] + 2
    blobs: dict[int, bytes] = {}

    def put(n: int, body: bytes) -> None:
        blobs[n] = b"%d 0 obj\n" % n + body + b"\nendobj\n"

    kids = b" ".join(b"%d 0 R" % i for i in page_ids)
    put(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    put(2, b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(page_ids))
    for idx, (page_id, content_id, page_lines) in enumerate(zip(page_ids, content_ids, pages, strict=True)):
        cmds = [*extra_ops.get(idx, []), "BT", "/F1 9 Tf", "36 760 Td", "11 TL"]
        for i, line in enumerate(page_lines):
            esc = _pdf_escape(line.encode("latin-1", "replace").decode("latin-1"))
            if i == 0:
                cmds.append(f"({esc}) Tj")
            else:
                cmds.append("T*")
                cmds.append(f"({esc}) Tj")
        cmds.append("ET")
        stream = "\n".join(cmds).encode("latin-1")
        put(
            page_id,
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>"
                % (content_id, font_id)
            ),
        )
        put(content_id, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    put(font_id, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    max_id = font_id
    out = bytearray(b"%PDF-1.4\n")
    offsets = {0: 0}
    for n in range(1, max_id + 1):
        offsets[n] = len(out)
        out.extend(blobs[n])
    xref_pos = len(out)
    out.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for n in range(1, max_id + 1):
        out.extend(f"{offsets[n]:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def attach_reports(result: AutopilotResult) -> AutopilotResult:
    result.report_markdown = render_markdown(result)
    return result


__all__ = ["attach_reports", "render_markdown", "render_pdf_bytes", "render_sealed_pdf_bytes", "sealed_pages"]
