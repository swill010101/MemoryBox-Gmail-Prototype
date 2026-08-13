"""P2-I2 shell injection — light shared chrome over existing HTML surfaces."""
from __future__ import annotations

from pathlib import Path

SHELL_DIR = Path(__file__).resolve().parent / "static"

# Google Fonts matching mockup validation language (Figtree + Newsreader).
_FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />'
    '<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700'
    '&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400'
    '&display=swap" rel="stylesheet" />'
)

_SHELL_CSS = '<link rel="stylesheet" href="/static/shell/shell.css" />'
_SHELL_JS = '<script src="/static/shell/shell.js" defer></script>'


def inject_shell(html: str, *, surface: str) -> str:
    """Inject MBUX shell assets and data-mb-surface into an HTML document."""
    if not html:
        return html
    if 'data-mb-surface=' in html and "/static/shell/shell.css" in html:
        return html

    head_bits = f"{_FONT_LINK}{_SHELL_CSS}{_SHELL_JS}"
    out = html
    if "</head>" in out:
        out = out.replace("</head>", head_bits + "</head>", 1)
    else:
        out = head_bits + out

    # Prefer <html ...> attribute
    lower = out.lower()
    idx = lower.find("<html")
    if idx >= 0:
        end = out.find(">", idx)
        if end > idx and "data-mb-surface=" not in out[idx:end]:
            out = out[:end] + f' data-mb-surface="{surface}"' + out[end:]
    elif "<body" in lower:
        b = lower.find("<body")
        end = out.find(">", b)
        if end > b and "data-mb-surface=" not in out[b:end]:
            out = out[:end] + f' data-mb-surface="{surface}" class="mb-shell"' + out[end:]

    return out


def read_and_inject(path: Path, *, surface: str) -> str:
    return inject_shell(path.read_text(encoding="utf-8"), surface=surface)
