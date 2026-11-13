"""The repository itself passes the hygiene check, and the check catches what it should."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location("check_repo_hygiene", ROOT / "tools" / "check_repo_hygiene.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_is_clean():
    tool = _tool()
    assert tool.check(ROOT, tool.candidate_files(ROOT)) == []


def test_check_catches_content_keys_and_personal_data(tmp_path):
    tool = _tool()
    (tmp_path / "open_pdfs").mkdir()
    (tmp_path / "open_pdfs" / "paper.pdf").write_bytes(b"%PDF-1.7")
    (tmp_path / "harvest_report.jsonl").write_text("{}\n")
    (tmp_path / ".env").write_text("X=1\n")
    # assembled at run time so this file itself stays clean for every scanner
    secret = "WILEY_TDM_TOKEN" + '="' + "a1b2c3d4e5f6a7b8c9d0" + '"'
    mail = "someone" + "@" + "institute.example.ch"
    home = "/" + "Users" + "/somebody/x"
    (tmp_path / "notes.md").write_text(f"{secret}\nmail me: {mail}\n{home}\n")
    findings = "\n".join(tool.check(tmp_path, tool.candidate_files(tmp_path)))
    for expected in ("open_pdfs/paper.pdf", "harvest_report.jsonl", ".env", "notes.md:1: key-value",
                     "notes.md:2: e-mail", "notes.md:3: home-path"):
        assert expected in findings
    assert "a1b2c3d4e5f6" not in findings  # matched text is never printed
