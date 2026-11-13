#!/usr/bin/env python3
"""Repository hygiene check, run in CI: no harvested content, no keys and no personal data in the tree.

It fails on:
  - harvested content and state: PDFs, pack folders, reports (.jsonl), databases, metadata caches;
  - key material: .env files (except .env.example), key/certificate files, and key-shaped strings
    (Google, GitHub, Slack, OpenAI-style, AWS, private-key blocks, a long value assigned to one of the key
    variables the harvester reads);
  - personal data: e-mail addresses outside example domains, absolute home-directory paths;
  - files larger than 2 MB.

It checks the files git would commit (tracked plus untracked-but-not-ignored); outside a git checkout it walks the
tree. Findings name the file, the line and the rule, never the matched text.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".mypy_cache", ".ruff_cache", "build", "dist"}
FORBIDDEN_FILES = re.compile(
    r"(\.pdf|\.db|\.sqlite3?|\.jsonl|\.pem|\.key|\.p12|\.pfx|\.pyc|\.DS_Store)$"
    r"|(^|/)\.env$|(^|/)[^/]*\.env$"
    r"|(^|/)(open_pdfs|tdm_bundles|open_bundles|paper_bundles|literature_packs)/", re.I)
ALLOWED_FILES = {".env.example"}
MAX_BYTES = 2_000_000
PATTERNS = [
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{30,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9]{24,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("key-value", re.compile(r"(?:WILEY_TDM_TOKEN|ELSEVIER_API_KEY|ELSEVIER_INSTTOKEN|OPENALEX_API_KEY)[ \t]*[=:][ \t]*"
                             r"[\"']?[A-Za-z0-9_\-]{16,}")),
    ("home-path", re.compile(r"(?:/[U]sers/|/home/)[A-Za-z0-9._-]+/|[A-Za-z]:\\\\?[U]sers\\\\?[A-Za-z0-9._-]+")),
]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EXAMPLE_DOMAINS = {"example.com", "example.org", "example.net", "example.edu", "users.noreply.github.com"}
BINARY_SUFFIXES = {".png", ".gif", ".jpg", ".jpeg", ".webp", ".ico"}


def candidate_files(root: Path) -> List[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, check=True,
                             capture_output=True, text=True).stdout
        return sorted(line for line in out.splitlines() if line and (root / line).is_file())
    except (OSError, subprocess.CalledProcessError):
        files = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
            files += [(Path(dirpath) / f).relative_to(root).as_posix() for f in filenames]
        return sorted(files)


def check(root: Path, files: Iterable[str]) -> List[str]:
    findings: List[str] = []
    for rel in files:
        path = root / rel
        if FORBIDDEN_FILES.search(rel) and rel not in ALLOWED_FILES:
            findings.append(f"{rel}: forbidden file type or folder (harvested content, state or key material)")
        if path.stat().st_size > MAX_BYTES:
            findings.append(f"{rel}: larger than {MAX_BYTES // 1_000_000} MB")
        if path.suffix.lower() in BINARY_SUFFIXES or path.suffix.lower() == ".pdf":
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        for name, rx in PATTERNS:
            for m in rx.finditer(text):
                findings.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}: {name}")
        for m in EMAIL.finditer(text):
            if m.group(0).rsplit("@", 1)[1].lower() not in EXAMPLE_DOMAINS:
                findings.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}: e-mail address outside example domains")
    return findings


def main() -> int:
    files = candidate_files(ROOT)
    findings = check(ROOT, files)
    print(f"hygiene check: {len(files)} files")
    if findings:
        print("FAILED:")
        for finding in findings:
            print(f"  - {finding}")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
