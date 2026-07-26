#!/usr/bin/env python3
"""Build an anonymized snapshot of this repository for double-blind review.

The public repository cannot be anonymized in place: the URL, the commit
authors, and the lab hostnames baked into board logs all identify us. This
script instead exports the tracked working tree (never the ``.git`` directory,
so no commit metadata travels with it), rewrites the identifying strings in
text files, and refuses to finish while any of them survive.

Standard library only, so it works in a bare clone with no dependencies:

    python3 scripts/make_anon_artifact.py
    python3 scripts/make_anon_artifact.py --out dist/anon --zip

Exit code is 0 when the snapshot is clean, 1 when identifying strings remain.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Longest patterns first: emails must be rewritten before the surname inside
# them is, or the substitution leaves a half-scrubbed address behind. Bare
# names are anchored on word boundaries so "Narra" does not eat "narrative".
SUBSTITUTIONS: list[tuple[str, str]] = [
    (r"hnarra@usc\.edu", "anonymous@example.com"),
    (r"srinivas@iitbbs\.ac\.in", "anonymous@example.com"),
    (r"Harshavardhan Reddy Narra", "Anonymous Author"),
    (r"Srinivas Boppu", "Anonymous Author"),
    (r"University of Southern California", "Anonymous Institution"),
    (r"IIT Bhubaneswar", "Anonymous Institution"),
    (r"harsha240yeager", "anon-authors"),
    (r"\bHarshavardhan\b", "Anonymous"),
    (r"\bSrinivas\b", "Anonymous"),
    (r"iitbbs\.ac\.in", "example.com"),
    (r"\busc\.edu\b", "example.com"),
    (r"\bhnarra\b", "anon"),
    (r"bsp-lab", "anon-host"),
    (r"\bNarra\b", "Anonymous"),
    (r"\bBoppu\b", "Anonymous"),
    (r"\bBhubaneswar\b", "Anonymous City"),
]

PATTERNS = [(re.compile(p, re.IGNORECASE), r) for p, r in SUBSTITUTIONS]
BYTE_PATTERNS = [
    (re.compile(p.encode("utf-8"), re.IGNORECASE), p) for p, _ in SUBSTITUTIONS
]

NOTICE = """# Anonymized artifact

This is a double-blind review snapshot of the code, configurations, and result
files behind the submission. It was produced by `scripts/make_anon_artifact.py`
from the authors' repository.

Three things differ from the repository that will be released on acceptance:

- Commit history is omitted, so there is no `.git` directory to clone from.
- Author names, institutions, e-mail addresses, the repository URL, and the
  lab hostname that appears in board and JTAG logs have been replaced with
  neutral placeholders. Measured values, timestamps, and log structure are
  untouched.
- Compiled board images (`.elf`, BSP `.a` archives) are omitted because the
  toolchain records the absolute build path inside them. Sources, scripts, and
  every result file they produced are present.

Everything needed to check the paper is here. `scripts/check_paper_numbers.py`
re-derives every numerical claim from the committed artifacts, and
`scripts/reproduce_paper.sh` reruns the Python pipeline in staged tiers.
"""


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def is_binary(data: bytes) -> bool:
    return b"\x00" in data[:8192]


def scrub(text: str) -> str:
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def residual_hits(data: bytes) -> list[str]:
    return [label for pattern, label in BYTE_PATTERNS if pattern.search(data)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="dist/anon-artifact",
        help="output directory, relative to the repository root",
    )
    parser.add_argument(
        "--zip", action="store_true", help="also write <out>.zip for upload"
    )
    args = parser.parse_args()

    out_dir = (ROOT / args.out).resolve()
    if ROOT in out_dir.parents and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rewritten = 0
    dropped: list[str] = []
    text_leaks: list[tuple[str, list[str]]] = []

    for rel in tracked_files():
        src = ROOT / rel
        if not src.is_file():  # submodule or deleted-but-tracked path
            continue
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()

        # Compiled outputs (ELF images, BSP archives) embed the absolute build
        # path of the machine that produced them. They cannot be rewritten
        # without corrupting the file, and they are rebuildable, so drop them.
        if is_binary(data):
            if residual_hits(data):
                dropped.append(rel)
            else:
                dst.write_bytes(data)
            continue

        text = data.decode("utf-8", errors="surrogateescape")
        scrubbed = scrub(text)
        if scrubbed != text:
            rewritten += 1
        dst.write_bytes(scrubbed.encode("utf-8", errors="surrogateescape"))

        hits = residual_hits(scrubbed.encode("utf-8", errors="surrogateescape"))
        if hits:
            text_leaks.append((rel, hits))

    (out_dir / "ANONYMIZED.md").write_text(NOTICE, encoding="utf-8")

    total = len(list(out_dir.rglob("*")))
    print(f"staged {total} paths under {out_dir}")
    print(f"scrubbed identifying strings in {rewritten} files")
    for rel in dropped:
        print(f"dropped {rel} (binary with embedded build path)")

    for rel, hits in text_leaks:
        print(f"LEAK  {rel}: {', '.join(sorted(set(hits)))}", file=sys.stderr)

    if text_leaks:
        print(
            "\nidentifying strings remain; fix them before uploading",
            file=sys.stderr,
        )
        return 1

    if args.zip:
        archive = shutil.make_archive(str(out_dir), "zip", root_dir=out_dir)
        print(f"wrote {archive}")

    print("no identifying strings remain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
