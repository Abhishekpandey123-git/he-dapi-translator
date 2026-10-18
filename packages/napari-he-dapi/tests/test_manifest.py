"""Tests for the napari-he-dapi plugin packaging.

These are intentionally lightweight (no napari/Qt import) so they can run in the
fast guards job. The widget import is checked separately and skipped when napari
is not installed.
"""
import tomllib
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
SRC = PKG / "src" / "napari_he_dapi"


def test_manifest_exists_and_is_valid():
    yaml = pytest.importorskip("yaml")
    manifest = yaml.safe_load((SRC / "napari.yaml").read_text())
    assert manifest["name"] == "napari-he-dapi"
    commands = {c["id"] for c in manifest["contributions"]["commands"]}
    assert "napari-he-dapi.translate" in commands
    widget = manifest["contributions"]["widgets"][0]
    assert widget["command"] in commands


def test_entry_point_declared():
    cfg = tomllib.loads((PKG / "pyproject.toml").read_text())
    eps = cfg["project"]["entry-points"]["napari.manifest"]
    assert eps["napari-he-dapi"] == "napari_he_dapi:napari.yaml"


def test_widget_importable():
    pytest.importorskip("napari")
    pytest.importorskip("magicgui")
    from napari_he_dapi._widget import translate

    assert callable(translate)
