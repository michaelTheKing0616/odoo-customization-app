"""Touch 133: Ingenium's own emails at receipt quality.

One button, mono reference, readable with images off (there are none), dark-mode safe
(no forced backgrounds on text; colour-scheme declared), and a plain-text twin.
"""

from __future__ import annotations

from html import escape


def receipt_html(*, title: str, lead: str, button_label: str, button_url: str, reference: str | None = None, footnote: str | None = None) -> str:
    ref = f'<p style="margin:24px 0 0;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace;color:#6b6b6b">{escape(reference)}</p>' if reference else ""
    foot = f'<p style="margin:24px 0 0;font-size:13px;line-height:1.5;color:#6b6b6b">{escape(footnote)}</p>' if footnote else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">'
        f"<title>{escape(title)}</title></head>"
        '<body style="margin:0;padding:32px 16px;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
        '<table role="presentation" width="100%" style="max-width:480px" cellpadding="0" cellspacing="0"><tr><td>'
        '<p style="margin:0 0 24px;font-size:13px;letter-spacing:.08em;text-transform:uppercase">Ingenium</p>'
        f'<h1 style="margin:0 0 12px;font-size:20px;line-height:1.3;font-weight:600">{escape(title)}</h1>'
        f'<p style="margin:0 0 24px;font-size:15px;line-height:1.55">{escape(lead)}</p>'
        f'<a href="{escape(button_url, quote=True)}" style="display:inline-block;padding:10px 18px;border-radius:6px;'
        f'background:#0f766e;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600">{escape(button_label)}</a>'
        f'<p style="margin:16px 0 0;font-size:13px;line-height:1.5;color:#6b6b6b">Or paste this link: {escape(button_url)}</p>'
        f"{ref}{foot}"
        "</td></tr></table></td></tr></table></body></html>"
    )
