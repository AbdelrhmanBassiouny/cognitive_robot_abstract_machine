"""
Report where a separately installed CRAMERA wheel resolves its package.
"""

import json
from pathlib import Path

import cramera

print(json.dumps({"package": str(Path(cramera.__file__).resolve().parent)}))
