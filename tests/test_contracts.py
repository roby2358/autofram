import asyncio
from pathlib import Path

from autofram.contracts import _find_pending, _is_pending, _parse_title, execute_contracts

SAMPLE_CONTRACT = """# Fix the widget

## Status
pending

## Task
Fix the broken widget in src/widget.py by handling the None case.

## Constraints
- Files: src/widget.py

## Result
"""


def test_parse_title():
    assert _parse_title(SAMPLE_CONTRACT) == "Fix the widget"


def test_parse_title_no_heading():
    assert _parse_title("no heading here") == "no heading here"


def test_parse_title_empty():
    assert _parse_title("") == "empty"


def test_is_pending():
    assert _is_pending(SAMPLE_CONTRACT) is True


def test_is_pending_completed():
    assert _is_pending(SAMPLE_CONTRACT.replace("pending", "completed")) is False


def test_find_pending_no_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("autofram.contracts.contracts_dir", lambda: tmp_path / "nonexistent")
    assert _find_pending() == []


def test_find_pending_none(tmp_path, monkeypatch):
    cdir = tmp_path / "contracts"
    cdir.mkdir()
    monkeypatch.setattr("autofram.contracts.contracts_dir", lambda: cdir)
    assert _find_pending() == []


def test_find_pending_finds_pending(tmp_path, monkeypatch):
    cdir = tmp_path / "contracts"
    cdir.mkdir()
    (cdir / "001-fix.md").write_text(SAMPLE_CONTRACT)
    (cdir / "002-done.md").write_text(SAMPLE_CONTRACT.replace("pending", "completed"))
    monkeypatch.setattr("autofram.contracts.contracts_dir", lambda: cdir)
    result = _find_pending()
    assert len(result) == 1
    assert result[0].name == "001-fix.md"


def test_execute_contracts_no_pending(tmp_path, monkeypatch):
    cdir = tmp_path / "contracts"
    cdir.mkdir()
    monkeypatch.setattr("autofram.contracts.contracts_dir", lambda: cdir)

    result = asyncio.run(execute_contracts())
    assert "No pending contracts" in result
