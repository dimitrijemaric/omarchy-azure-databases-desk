#!/usr/bin/env bash
# Explicit, user-started onboarding. Omarchy does not run this at plugin install time.
set -uo pipefail

usage() {
  printf 'Usage: bash scripts/setup.sh install | login [profile|new] [tenant-id] [cloud]\n'
}

finish() {
  local code=$1
  if [[ -t 0 ]]; then
    printf '\nPress Enter to close this window.'
    read -r _ || true
  fi
  exit "$code"
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  install|login) action=$1 ;;
  *) usage >&2; exit 2 ;;
esac
if (( $# > 4 )) || [[ $action == install && $# != 1 ]]; then usage >&2; exit 2; fi

export AZURE_CORE_COLLECT_TELEMETRY=no
export AZURE_CORE_CHECK_VERSION=false
export AZURE_EXTENSION_USE_DYNAMIC_INSTALL=no

if [[ $action == install ]]; then
  printf 'Azure Databases Desk — Azure CLI setup\n\n'
  if ! command -v az >/dev/null 2>&1; then
    printf 'Installing the azure-cli package from the configured Arch repositories.\n'
    printf 'Omarchy may ask for your password.\n\n'
    if ! omarchy pkg add azure-cli; then
      printf '\nAzure CLI installation failed. You can retry from the panel.\n' >&2
      finish 1
    fi
  fi
  if ! command -v az >/dev/null 2>&1 || ! az version --only-show-errors; then
    printf '\nAzure CLI is not usable yet. Check the package installation and retry.\n' >&2
    finish 1
  fi
  printf '\nAzure CLI is ready. Choose Sign in in Azure Databases Desk to connect your account.\n'
else
  if ! command -v az >/dev/null 2>&1; then
    printf 'Install Azure CLI from the panel first.\n' >&2
    finish 1
  fi
  printf 'Azure Databases Desk — sign in to Microsoft Azure\n\n'
  script_dir=${BASH_SOURCE[0]%/*}
  if ! /usr/bin/python3 -B "$script_dir/accounts.py" --profile "${2:-cli}" --tenant "${3:-}" --cloud "${4:-AzureCloud}"; then
    printf '\nSign-in did not complete. You can retry from the panel.\n' >&2
    finish 1
  fi
  printf '\nSign-in completed. Returning to Azure Databases Desk.\n'
fi

# Keep package installation usable before the plugin is installed too.
# With a live shell these calls leave demo mode and refresh the open panel.
omarchy bar set dimitrije.azure-sql demoMode false --json >/dev/null 2>&1 || true
omarchy-shell -q shell summon dimitrije.azure-sql >/dev/null 2>&1 || true
finish 0
