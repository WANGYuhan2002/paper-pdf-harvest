"""Test isolation: every test starts with a pristine engine, no keys and no developer settings.

The upgrade layer patches ``fullbundle_harvest`` in place (that is how SeismoHub ships it), and
``load_harvest_keys`` writes into ``os.environ``. Both are undone after each test.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
REPO_ROOT = TESTS.parent
for path in (str(REPO_ROOT), str(TESTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from paper_pdf_harvest import fullbundle_harvest as fb  # noqa: E402

SETTINGS = ("WILEY_TDM_TOKEN", "ELSEVIER_API_KEY", "ELSEVIER_INSTTOKEN", "OPENALEX_API_KEY",
            "SEISMO_HARVEST_KEYS_FILE", "SEISMO_HARVEST_UA", "SEISMO_HARVEST_MAX_BYTES", "SEISMO_DB_PATH")


def _copy(value):
    return dict(value) if isinstance(value, dict) else value


@pytest.fixture(autouse=True)
def pristine_engine(tmp_path, monkeypatch):
    module_state = {k: _copy(v) for k, v in vars(fb).items() if not k.startswith("__")}
    class_state = {cls: dict(vars(cls)) for cls in (fb.PoliteSession, fb.FullBundleHarvester)}
    env_state = dict(os.environ)
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(fb, "DEFAULT_KEYS_FILE", tmp_path / "no-such-keys.env")  # never the developer's keys
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)  # no ./.env of the developer is picked up
    yield
    for cls, state in class_state.items():
        for name in [n for n in vars(cls) if n not in state]:
            delattr(cls, name)
        for name, value in state.items():
            if vars(cls).get(name) is not value:
                setattr(cls, name, value)
    for name in [n for n in vars(fb) if not n.startswith("__") and n not in module_state]:
        delattr(fb, name)
    for name, value in module_state.items():
        current = vars(fb).get(name)
        if isinstance(value, dict):
            if current != value:
                setattr(fb, name, dict(value))
        elif current is not value:
            setattr(fb, name, value)
    for name in [n for n in os.environ if n not in env_state]:
        del os.environ[name]
    for name, value in env_state.items():
        if os.environ.get(name) != value:
            os.environ[name] = value
