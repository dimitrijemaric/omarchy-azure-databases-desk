#!/usr/bin/env bash
# DB Studio is a separate marketplace plugin. Opening it never executes SQL.
set -euo pipefail

plugin_id=andean-bridge.db-browser
plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$plugin_id"
script_path="$(readlink -f -- "${BASH_SOURCE[0]}")"

finish() {
  local code=$?
  if [[ ${1:-} == install && -t 0 ]]; then
    printf '\nPress Enter to close this window.'
    read -r _ || true
  fi
  exit "$code"
}

case "${1:-open}" in
  open)
    if [[ -f "$plugin_dir/node_modules/mssql/package.json" ]] && command -v node >/dev/null 2>&1; then
      if omarchy-shell shell summon "$plugin_id" '{}'; then exit 0; fi
    fi
    if command -v notify-send >/dev/null 2>&1; then
      notify-send 'DB Studio' 'DB Studio is not installed or enabled. Install the marketplace plugin to use this shortcut.'
    fi
    exit 1
    ;;
  install)
    trap 'finish install' EXIT
    printf 'Azure SQL Desk — DB Studio setup\n\n'
    if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
      omarchy pkg add npm
    fi
    if (( $(node -p 'Number(process.versions.node.split(".")[0])') < 20 )); then
      printf 'DB Studio requires Node.js 20 or newer. Update Node.js and retry.\n' >&2
      exit 1
    fi
    if [[ ! -d "$plugin_dir" ]]; then
      omarchy plugin add https://github.com/Andean-Bridge/omarchy-db-browser.git --enable --yes
    else
      omarchy plugin enable "$plugin_id"
    fi
    # The workbench's database drivers are JavaScript; dependency lifecycle scripts are unnecessary.
    (cd -- "$plugin_dir" && npm ci --omit=dev --no-bin-links --ignore-scripts)
    printf '\nDB Studio is ready. Add or select your Azure SQL connection in its workbench.\n'
    omarchy-shell shell summon "$plugin_id" '{}'
    ;;
  *) printf 'Usage: bash query_client.sh [open|install]\n' >&2; exit 2 ;;
esac
