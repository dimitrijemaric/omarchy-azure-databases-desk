#!/usr/bin/env bash
# Open a separately installed workbench. Never install dependencies or execute SQL.
set -euo pipefail

plugin_id=andean-bridge.db-browser
plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$plugin_id"

case "${1:-open}" in
  open)
    if [[ -f "$plugin_dir/node_modules/mssql/package.json" ]] && command -v node >/dev/null 2>&1; then
      if omarchy-shell shell summon "$plugin_id" '{}'; then exit 0; fi
    fi
    if command -v notify-send >/dev/null 2>&1; then
      notify-send 'DB Studio' 'Install and enable DB Studio separately through its marketplace listing to use this shortcut.'
    fi
    exit 1
    ;;
  *) printf 'Usage: bash query_client.sh [open]\nInstall DB Studio separately through its marketplace listing.\n' >&2; exit 2 ;;
esac
