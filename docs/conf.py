"""Sphinx configuration."""

from __future__ import annotations

import os
import sys


ROOT = os.path.abspath("..").replace("\\", "/")
SRC = os.path.join(ROOT, "src")

if SRC not in sys.path:
    sys.path.insert(0, SRC)


project = "Watopnet"
author = "KERI Foundation"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_mock_imports = [
    "PySide6",
    "keri",
    "hio",
    "qasync",
]
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "alabaster"