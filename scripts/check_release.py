#!/usr/bin/env python3
"""Portable repository preflight; native validation still uses omarchy plugin validate."""
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    require(type(manifest.get('schemaVersion')) is int and manifest['schemaVersion'] == 1, 'Unsupported schemaVersion')
    for key in ('id', 'name', 'version', 'author', 'description'):
        require(isinstance(manifest.get(key), str) and bool(manifest[key].strip()), 'Missing manifest ' + key)
    identifier = manifest['id']
    require(re.fullmatch(r'[a-z0-9][a-z0-9._-]*', identifier) and '..' not in identifier and not identifier.startswith('omarchy.'), 'Invalid or reserved plugin ID')
    require(re.fullmatch(r'\d+\.\d+\.\d+', manifest['version']), 'Use a semantic release version')
    require(manifest.get('license') == 'MIT', 'Expected MIT license metadata')
    require(manifest.get('kinds') == ['bar-widget'], 'Expected one bar-widget plugin')
    entries = manifest.get('entryPoints')
    require(isinstance(entries, dict) and entries.get('barWidget'), 'Missing barWidget entry point')
    for value in entries.values():
        require(isinstance(value, str) and value, 'Invalid entry point')
        path = PurePosixPath(value)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in value, 'Unsafe entry point path')
        require((ROOT / path).is_file(), 'Missing entry point ' + value)
    require(manifest.get('barWidget', {}).get('defaultSection') in ('left', 'center', 'right'), 'Invalid default bar section')
    for name in ('README.md', 'LICENSE', 'SECURITY.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'preview.png'):
        require((ROOT / name).is_file(), 'Missing release file ' + name)
    readme = (ROOT / 'README.md').read_text()
    for text in ('omarchy plugin add', 'omarchy plugin update', 'omarchy plugin remove', 'Azure CLI', 'Python', 'Quickshell'):
        require(text in readme, 'README must document ' + text)
    require('MIT License' in (ROOT / 'LICENSE').read_text(), 'MIT license text missing')
    require(('## [' + manifest['version'] + ']') in (ROOT / 'CHANGELOG.md').read_text(), 'Changelog does not describe current version')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    for name in filter(None, tracked):
        path = ROOT / name
        require(not path.is_symlink(), 'Symlinks cannot be installed: ' + name)
        require(path.name != 'manifest.json' or name == 'manifest.json', 'Only one root plugin manifest is allowed')
        require(not name.endswith(('.sqlite3', '.log', '.pyc')) and '.azure' not in path.parts and 'azure-profiles' not in path.parts, 'Local runtime data is tracked: ' + name)
    print('Release preflight passed: ' + identifier + ' ' + manifest['version'])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as error:
        print('Release preflight failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
