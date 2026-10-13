"""
Imports every module of ``krrood_core`` and prints, as a JSON list, the top-level
packages the interpreter loaded for them that it had not loaded at startup.
"""

import importlib
import json
import pkgutil
import sys

loaded_at_startup = set(sys.modules)
package = importlib.import_module("krrood_core")
for module in pkgutil.walk_packages(package.__path__, "krrood_core."):
    importlib.import_module(module.name)

print(
    json.dumps(
        sorted(
            {name.partition(".")[0] for name in set(sys.modules) - loaded_at_startup}
        )
    )
)
