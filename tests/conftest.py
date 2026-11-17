"""Make the pure modules importable without Home Assistant installed.

The package `__init__.py` imports Home Assistant, so the tests register an empty
package module for `custom_components.imhd` and load only the submodules
they need (`const`, `link`, `search`, `protocol`, `board`).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.imhd", ROOT / "custom_components" / "imhd"),
):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
