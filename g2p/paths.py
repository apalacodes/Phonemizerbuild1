"""Where the G2P's data files live.

In the repo they are in data/ (linguist-editable). An installed wheel carries a copy in g2p/data/
(see [tool.hatch.build.targets.wheel.force-include] in pyproject.toml).
"""

from pathlib import Path

_BUNDLED = Path(__file__).resolve().parent / "data"
DATA_DIR = _BUNDLED if _BUNDLED.is_dir() else Path(__file__).resolve().parent.parent / "data"
