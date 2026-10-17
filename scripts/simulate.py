#!/usr/bin/env python3
"""Open an interactive fictional Azure SQL panel without touching the live widget."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    shell = Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")) / "shell"
    with tempfile.TemporaryDirectory(prefix="azure-sql-simulation-") as temporary:
        directory = Path(temporary)
        for name in ("Commons", "Ui"):
            (directory / name).symlink_to(shell / name, target_is_directory=True)
        (directory / "AzureSql").symlink_to(root, target_is_directory=True)
        shutil.copyfile(root / "scripts/Simulation.qml", directory / "shell.qml")
        env = dict(os.environ, XDG_CACHE_HOME=str(directory / "cache"),
                   XDG_STATE_HOME=str(directory / "state"), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.call(["qs", "-p", str(directory), "--no-color"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
