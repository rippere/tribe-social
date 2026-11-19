"""Shared fixture: the scorer module with the GPU-only `tribev2` stubbed.

The package is loaded from this checkout under a private name, so an installed
copy of `tribe_scoring` elsewhere cannot shadow it.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

PKG_DIR = Path(__file__).resolve().parents[1]
PKG_NAME = "_tribe_scoring_under_test"


@pytest.fixture(scope="module")
def ras():
    saved = {k: sys.modules.get(k) for k in ("tribev2", "tribev2.demo_utils")}
    tribev2 = types.ModuleType("tribev2")
    demo_utils = types.ModuleType("tribev2.demo_utils")
    demo_utils.TribeModel = object
    tribev2.demo_utils = demo_utils
    sys.modules["tribev2"] = tribev2
    sys.modules["tribev2.demo_utils"] = demo_utils
    try:
        spec = importlib.util.spec_from_file_location(
            PKG_NAME, PKG_DIR / "__init__.py", submodule_search_locations=[str(PKG_DIR)]
        )
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[PKG_NAME] = pkg
        spec.loader.exec_module(pkg)
        yield importlib.import_module(f"{PKG_NAME}.run_and_save")
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        for k in [k for k in sys.modules if k == PKG_NAME or k.startswith(PKG_NAME + ".")]:
            sys.modules.pop(k)
