"""Tiny text-only PDF writer (A4, Helvetica) for printable guides.

No extra dependency. Returns None when the text has letters the built-in PDF
fonts can't show (the caller then offers a printable page instead).
"""

from __future__ import annotations

import textwrap

W, H, MARGIN = 595, 842, 56


def _esc(t: str) -> bytes:
    return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("cp1252")


def text_pdf(title: str, sections: list[tuple[str, str]], note: str = "") -> bytes | None:
    try:
        (title + note + "".join(a + b for a, b in sections)).encode("cp1252")
    except UnicodeEncodeError:
        return None
    lines: list[tuple[str, int, bool]] = [(title, 18, True), (note, 9, False), ("", 10, False)]
    for i, (head, body) in enumerate(sections, start=1):
        lines.append((f"{i}. {head}", 12, True))
        lines += [(ln, 10, False) for ln in textwrap.wrap(body, 95) or [""]]
        lines.append(("", 6, False))
    pages: list[list[tuple[str, int, bool, int]]] = [[]]
    y = H - MARGIN
    for text, size, bold in lines:
        step = int(size * 1.45)
        if y - step < MARGIN:
            pages.append([])
            y = H - MARGIN
        y -= step
        pages[-1].append((text, size, bold, y))
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
                         b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
                         b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for n, page in enumerate(pages, start=1):
        stream = b"".join(b"BT /%s %d Tf %d %d Td (%s) Tj ET\n" % (b"F2" if bold else b"F1", size, MARGIN, yy, _esc(text))
                          for text, size, bold, yy in page if text)
        stream += b"BT /F1 8 Tf %d %d Td (%s) Tj ET\n" % (W - MARGIN - 40, MARGIN - 24, _esc(f"Page {n} of {len(pages)}"))
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content_id = len(objs)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>" % (W, H, content_id))
        kids.append(len(objs))
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
