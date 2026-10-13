"""
Imports the module named by the first argument and prints, as a JSON list, the top-level
packages the interpreter loaded for it that are not part of the standard library.
"""

import importlib
import json
import sys

loaded_at_startup = set(sys.modules)
importlib.import_module(sys.argv[1])
loaded = {name.partition(".")[0] for name in set(sys.modules) - loaded_at_startup}

print(json.dumps(sorted(loaded - sys.stdlib_module_names - {"krrood_core"})))
