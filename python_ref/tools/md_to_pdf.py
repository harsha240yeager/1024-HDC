#!/usr/bin/env python3
"""
Convert a Markdown file to a styled PDF using headless Microsoft Edge.

Usage:
    python md_to_pdf.py <input.md> [--out <output.pdf>] [--keep-md]

Notes:
  - Project convention: notes are delivered as PDF, not .md.
  - By default the source .md is DELETED after a successful conversion
    (pass --keep-md to retain it, e.g. for README files).
  - Requires the `markdown` package and an installed Microsoft Edge.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown


EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm;
  @bottom-center { content: "page " counter(page) " of " counter(pages);
    font-family: "Segoe UI", sans-serif; font-size: 8.5pt; color: #94a3b8; } }
@page :first { @bottom-center { content: ""; } }
body { font-family: "Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif;
  color: #1e293b; line-height: 1.5; font-size: 10.6pt; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1, h2, h3, h4 { font-family: "Segoe UI Semibold", "Segoe UI", sans-serif; color: #0a2540; line-height: 1.25; }
h1 { font-size: 22pt; margin: 0 0 10pt 0; border-bottom: 2px solid #1e6091; padding-bottom: 6pt; }
h2 { font-size: 15pt; margin: 18pt 0 8pt 0; border-bottom: 1.5px solid #1e6091; padding-bottom: 4pt; }
h3 { font-size: 12pt; margin: 13pt 0 4pt 0; color: #1e6091; }
h4 { font-size: 10.6pt; margin: 10pt 0 3pt 0; color: #2563eb; }
p { margin: 5pt 0 7pt 0; }
ul, ol { margin: 4pt 0 7pt 20pt; }
li { margin: 2pt 0; }
li::marker { color: #1e6091; }
strong, b { color: #0a2540; }
a { color: #1d4ed8; text-decoration: none; word-break: break-all; }
code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 9.4pt;
  background: #eef2f7; color: #0a2540; padding: 0.5pt 4pt; border-radius: 3px; }
pre { background: #0f172a; color: #e2e8f0; border-left: 3px solid #f59e0b;
  padding: 9pt 12pt; border-radius: 4px; overflow-x: auto; white-space: pre-wrap;
  font-size: 9pt; line-height: 1.45; }
pre code { background: transparent; color: inherit; padding: 0; }
table { border-collapse: separate; border-spacing: 0; width: 100%; margin: 8pt 0 12pt 0;
  font-size: 9.6pt; border: 1px solid #cbd5e1; border-radius: 5px; overflow: hidden; }
th, td { padding: 5pt 8pt; vertical-align: top; border-bottom: 1px solid #e2e8f0; text-align: left; }
th { background: #0a2540; color: #f1f5f9; font-weight: 600; border-bottom: 0; }
tr:last-child td { border-bottom: 0; }
tr:nth-child(even) td { background: #f8fafc; }
blockquote { border-left: 4px solid #f59e0b; background: #fffbeb; margin: 8pt 0;
  padding: 6pt 12pt; border-radius: 3px; color: #4b3a12; }
hr { border: 0; border-top: 1px dashed #cbd5e1; margin: 14pt 0; }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>{title}</title>
<style>{css}</style></head><body>{body}</body></html>
"""


def find_edge() -> str:
    for path in EDGE_CANDIDATES:
        if os.path.exists(path):
            return path
    found = shutil.which("msedge")
    if found:
        return found
    raise FileNotFoundError("Microsoft Edge not found; cannot render PDF.")


def md_to_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
    )
    return TEMPLATE.format(title=md_path.stem, css=CSS, body=html_body)


def render_pdf(html: str, pdf_path: Path) -> None:
    edge = find_edge()
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "doc.html"
        html_path.write_text(html, encoding="utf-8")
        if pdf_path.exists():
            pdf_path.unlink()
        cmd = [
            edge,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            "--virtual-time-budget=15000",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, capture_output=True, text=True)
    if not pdf_path.exists():
        raise RuntimeError(f"PDF was not produced at {pdf_path}")


def convert(md_path: Path, out: Path | None = None, keep_md: bool = False) -> Path:
    md_path = md_path.resolve()
    if not md_path.exists():
        raise FileNotFoundError(md_path)
    pdf_path = (out or md_path.with_suffix(".pdf")).resolve()
    render_pdf(md_to_html(md_path), pdf_path)
    size_kb = pdf_path.stat().st_size / 1024
    print(f"  PDF  {pdf_path}  ({size_kb:.1f} KB)")
    if not keep_md:
        md_path.unlink()
        print(f"  del  {md_path}")
    return pdf_path


def main() -> int:
    p = argparse.ArgumentParser(description="Convert Markdown to styled PDF (Edge headless)")
    p.add_argument("input", type=Path, help="input .md file")
    p.add_argument("--out", type=Path, default=None, help="output .pdf path")
    p.add_argument("--keep-md", action="store_true", help="keep the source .md file")
    args = p.parse_args()
    try:
        convert(args.input, args.out, args.keep_md)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
