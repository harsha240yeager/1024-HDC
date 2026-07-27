#!/usr/bin/env python3
"""Render a Markdown document to a print-ready PDF.

Uses Python-Markdown for HTML and a headless Chromium (Edge or Chrome) for the
PDF, so no LaTeX or pandoc install is needed on Windows:

    python3 scripts/md_to_pdf.py docs/PAPER_DISCUSSION_GUIDE.md
    python3 scripts/md_to_pdf.py docs/GUIDE.md --out /tmp/guide.pdf --no-toc

Exit code is 0 when the PDF is written, 1 otherwise.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import markdown
except ImportError:  # pragma: no cover - dependency hint
    sys.exit("Python-Markdown is required: pip install markdown")

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.45; color: #16191d; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1, h2, h3 { line-height: 1.25; break-after: avoid; page-break-after: avoid; }
h1 { font-size: 21pt; margin: 0 0 4pt; letter-spacing: -0.2pt; }
h2 {
  font-size: 14pt; margin: 20pt 0 7pt; padding-top: 6pt;
  border-top: 1.5pt solid #16191d;
}
h3 { font-size: 11.5pt; margin: 13pt 0 4pt; color: #23303f; }
p, ul, ol { margin: 0 0 7pt; orphans: 2; widows: 2; }
li { margin-bottom: 2.5pt; }
strong { color: #0b1015; }
a { color: #16191d; text-decoration: none; }
hr { border: 0; border-top: 0.5pt solid #d5dae0; margin: 14pt 0; }
code {
  font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt;
  background: #f2f4f7; padding: 0.5pt 3pt; border-radius: 2.5pt;
}
pre {
  background: #f7f9fb; border: 0.5pt solid #dde3ea; border-left: 2.5pt solid #7b8ea3;
  border-radius: 3pt; padding: 7pt 9pt; margin: 0 0 9pt;
  font-size: 8.8pt; line-height: 1.4; white-space: pre-wrap;
  break-inside: avoid; page-break-inside: avoid;
}
pre code { background: none; padding: 0; font-size: inherit; }
blockquote {
  margin: 0 0 10pt; padding: 8pt 11pt; background: #f4f7fa;
  border-left: 2.5pt solid #4a6785; border-radius: 0 3pt 3pt 0;
  font-size: 10.5pt; break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }
table {
  width: 100%; border-collapse: collapse; margin: 0 0 10pt; font-size: 9pt;
  break-inside: avoid; page-break-inside: avoid;
}
th, td { border: 0.5pt solid #cdd4dc; padding: 3.5pt 5pt; text-align: left; vertical-align: top; }
th { background: #eef1f5; font-weight: 600; }
tbody tr:nth-child(even) td { background: #fafbfc; }
.toc { break-after: page; page-break-after: always; }
.toc a { color: #16191d; }
.toc .doc-title {
  font-size: 15pt; font-weight: 600; line-height: 1.3; margin: 0 0 2pt;
}
.toc .doc-sub { color: #5a6673; font-size: 9.5pt; margin: 0 0 4pt; }
.toc > h2 { margin-top: 14pt; }
.toc ul { list-style: none; padding-left: 0; margin-bottom: 3pt; }
.toc ul ul { padding-left: 13pt; font-size: 9.5pt; color: #46505c; }
.toc li { margin-bottom: 1.5pt; }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head><body>{toc}{body}</body></html>
"""


def find_browser() -> str:
    for candidate in BROWSERS:
        if Path(candidate).is_file():
            return candidate
    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("no Edge or Chrome found for headless PDF printing")


def render_html(md_path: Path, with_toc: bool) -> tuple[str, str]:
    text = md_path.read_text(encoding="utf-8")
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc", "attr_list"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
    )
    body = md.convert(text)

    first_h1 = next(
        (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
        md_path.stem.replace("_", " "),
    )
    toc = ""
    if with_toc and md.toc_tokens:
        toc = (
            f'<div class="toc"><div class="doc-title">{first_h1}</div>'
            f'<div class="doc-sub">{md_path.name}</div>'
            f"<h2>Contents</h2>{md.toc}</div>"
        )
    return TEMPLATE.format(title=first_h1, css=CSS, toc=toc, body=body), first_h1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Markdown file to render")
    parser.add_argument("--out", help="output PDF (default: alongside the source)")
    parser.add_argument("--no-toc", action="store_true", help="skip the contents page")
    parser.add_argument("--keep-html", action="store_true", help="keep the intermediate HTML")
    args = parser.parse_args()

    src = Path(args.source).resolve()
    if not src.is_file():
        sys.exit(f"not found: {src}")
    out = Path(args.out).resolve() if args.out else src.with_suffix(".pdf")

    html, _ = render_html(src, with_toc=not args.no_toc)
    html_path = (
        src.with_suffix(".html")
        if args.keep_html
        else Path(tempfile.gettempdir()) / f"{src.stem}.html"
    )
    html_path.write_text(html, encoding="utf-8")

    browser = find_browser()
    result = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=10000",
            f"--print-to-pdf={out}",
            html_path.as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if not out.is_file():
        print(result.stderr.strip() or "browser produced no PDF", file=sys.stderr)
        return 1

    print(f"wrote {out} ({out.stat().st_size // 1024} KB) via {Path(browser).name}")
    if args.keep_html:
        print(f"kept {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
