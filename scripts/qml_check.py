#!/usr/bin/env python3
"""Exercise the real QML controller offline, or render a sample panel preview."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from demo import SERVER, PRIVATE_SERVER, SUBSCRIPTION

ROOT = Path(__file__).resolve().parents[1]


def fake_cli(directory):
    executable = directory / "az"
    shutil.copyfile(ROOT / "tests/fake_az.py", executable)
    executable.chmod(0o755)
    return directory / "unused-fixtures.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, help="Render demo mode to this PNG instead of running interaction checks")
    parser.add_argument("--omarchy-path", type=Path, default=Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")))
    args = parser.parse_args()
    shell = args.omarchy_path / "shell"
    qs = shutil.which("qs")
    if not qs or not (shell / "Commons").is_dir():
        parser.error("Quickshell and the Omarchy shell sources are required for QML checks.")
    with tempfile.TemporaryDirectory(prefix="azure-sql-qml-") as temp:
        directory = Path(temp)
        (directory / "Commons").symlink_to(shell / "Commons", target_is_directory=True)
        (directory / "Ui").symlink_to(shell / "Ui", target_is_directory=True)
        (directory / "AzureDesk").symlink_to(ROOT, target_is_directory=True)
        runtime = directory / "runtime"
        runtime.mkdir(mode=0o700)
        source = ROOT / ("scripts/Preview.qml" if args.preview else "tests/Smoke.qml")
        shutil.copyfile(source, directory / "shell.qml")
        fixture = fake_cli(directory)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                   QT_QUICK_CONTROLS_STYLE="Basic", QSG_RHI_BACKEND="software",
                   XDG_RUNTIME_DIR=str(runtime), XDG_CACHE_HOME=str(directory / "cache"), XDG_STATE_HOME=str(directory / "state"),
                   SQL_TEST_FAILURE=str(directory / "failure"), SQL_TEST_FIXTURES=str(fixture), SQL_TEST_SCRIPTS=str(ROOT / "scripts"),
                   PYTHONDONTWRITEBYTECODE="1",
                   PATH=str(directory) + os.pathsep + os.environ.get("PATH", ""))
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        if not args.preview:
            # Remember a second offline login so the real selectors can exercise profile changes.
            fixture_code = """import accounts
from pathlib import Path
folder=accounts.state_dir()/'azure-profiles'/'44444444-4444-4444-8444-444444444444'
folder.mkdir(parents=True,mode=0o700)
db=accounts.connect()
with db: db.execute('INSERT INTO logins VALUES(?,?,?,?,?,?)',('44444444-4444-4444-8444-444444444444','second@example.test','second@example.test','AzureCloud','','[]'))
db.close()
"""
            subprocess.run([sys.executable, '-B', '-c', fixture_code], env=dict(env, PYTHONPATH=str(ROOT/'scripts')), check=True)
        if args.preview:
            env["SQL_PREVIEW_OUTPUT"] = str(args.preview.resolve())
        result = subprocess.run([qs, "-p", str(directory), "--no-color"], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
        output = result.stdout
        if result.returncode or "QML_CHECK_PASSED" not in output or "QML_CHECK_FAILED" in output or any(
                word in output for word in ("TypeError", "ReferenceError", "Binding loop", "Failed to load configuration")):
            print(output)
            return 1
        print("Preview rendered: " + str(args.preview) if args.preview else "QML checks passed: fresh 25-row pages, expansion, cost ranking, cooldowns, views, account/directory switching, cancellation, keyboard navigation, layout and theme contrast.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
