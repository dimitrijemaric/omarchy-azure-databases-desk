# Security policy

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/dimitrijemaric/omarchy-azure-databases-desk/security/advisories/new) when available. If private reporting is unavailable, open an issue requesting a private contact channel without including vulnerability details. Do not publish passwords, access tokens, Azure identifiers, billing data, query results, or personal information in issues or screenshots.

## Runtime access

This plugin runs unsandboxed in the Omarchy shell and starts a Python helper. Review the source before enabling it. Marketplace compatibility validation and listing approval are not a security audit or a guarantee of safety.

- Python invokes Azure CLI with fixed argument arrays and no shell interpolation. Azure operations read subscription metadata, Resource Graph, ARM resource properties, backup/failover metadata, Monitor metrics, and Cost Management aggregates. There are no Azure resource writes or SQL queries.
- Azure CLI owns credentials. The existing CLI profile can be used, and added accounts use isolated CLI profiles under the plugin's local state directory. Passwords and tokens are never requested through QML or saved in the preferences databases. The helper requests only token expiry metadata when checking authentication.
- Account metadata and saved views use SQLite files with mode 0600. Added CLI profile directories use mode 0700, and interactive sign-in creates CLI files under umask 077. Credential caches remain sensitive local files, even though the plugin does not parse them.
- The helper validates subscription scope against the selected account and directory before resource requests. Switching identities cancels requests and discards previous database data and cost ordering. In-flight responses are checked against the controller's request generation.
- Azure CLI stderr is mapped to bounded error messages instead of being returned to the panel. Output sizes and request durations are bounded; cancellation terminates the helper's CLI children.
- Authentication uses Microsoft's interactive browser/terminal flow, including MFA and consent. No password authentication flow is implemented by the plugin.

## Installation and commands

Installing the repository runs no setup hooks. Enabling it starts the bar widget and helper. **Install Azure CLI** opens a terminal and invokes `omarchy pkg add azure-cli` only after a user action; the package manager may ask for privilege elevation. Sign-in opens a terminal and runs Azure CLI. No sudoers policy, background service, or scheduled task is created.

Portal actions open the appropriate Azure Portal URL. The optional workbench action only asks an already-installed DB Studio plugin to open. It does not install remote code, pass credentials, configure a connection, or execute a query. DB Studio is independent software with its own behavior and dependencies.

## Data, network and removal

The plugin contacts Azure management, monitoring, billing and identity services through Azure CLI. Portal actions open Microsoft Azure Portal in the browser. The plugin has no independent analytics endpoint and disables Azure CLI telemetry for commands it launches.

No resource or billing catalog is persisted. Current-page data and a temporary cost-sort ranking exist in memory. Preferences and added CLI credential profiles remain under `${XDG_STATE_HOME:-~/.local/state}/azure-sql-desk/`. Removing the plugin stops its panel and polling but intentionally preserves that directory and the shared Azure CLI profile. See the README's removal instructions before deleting any saved accounts.

Unknown or unreadable public-network settings are never treated as Disabled. An Enabled warning reports Azure's public endpoint setting; firewall rules, private endpoints, authentication and effective reachability need separate assessment.

## Supported version and limits

Security fixes target the latest release. Metric batching currently targets Azure public cloud. Offline tests do not establish production performance, Azure RBAC permissions, quota availability, or every sovereign-cloud API behavior. Azure CLI, Quickshell and optional DB Studio are external dependencies; keep them updated through their supported channels.
