"""User-level config: the two remembered folders.

Settings live in ~/.config/mtps/config.json so they are independent of
where the app is launched from (the whole point of the `mtps` launcher)
and survive moving or re-cloning the repo.

Two folders are remembered:
  work_dir    — the active workbench. Holds input/, QR_Codes/, and the
                draft {YYYYMM}_ssPrayerTime.md/.pdf while you build the sheet.
  archive_dir — the permanent record, where finished zips land.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mtps"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "work_dir": str(Path.home() / "Documents/PGCC/Missions/MonthlyPrayerSheet/current"),
    "archive_dir": str(Path.home() / "Documents/PGCC/Missions/MonthlyPrayerSheet/archive"),
}


def load_config():
    """Return the config dict, falling back to DEFAULTS for missing keys."""
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg):
    """Write the config dict to ~/.config/mtps/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")
