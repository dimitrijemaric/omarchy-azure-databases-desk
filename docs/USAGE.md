# Azure Databases Desk

Browse **Azure SQL databases** from the Omarchy bar. Cosmos DB and PostgreSQL tabs are visible but temporarily disabled.

![Azure Databases Desk with fictional Azure SQL resources](../preview.png)

- Azure SQL browsing with fresh pages of **25 resources**; other service tabs are disabled.
- Header actions: **Create database** opens the Azure Portal SQL creation form; **Cost Calculator** is disabled with a Coming soon tooltip. Disabled service tabs show the same tooltip.
- Multi-select subscriptions, servers/accounts, locations, service tiers/APIs and compute models. Empty selections mean All.
- Name search and sorting by name, month-to-date cost, location, tier or state.
- Searchable multiselect filters for backup redundancy, reported restore history, maintenance window, zone redundancy and read scale-out.
- Remember multiple Azure sign-ins and switch accounts or Microsoft Entra directories from searchable selectors. Added accounts use independent Azure CLI profiles; the last selection is restored.
- Saved views retain the service, filters and sort order. Mark a view as default to load whenever the panel opens; opening always resets to page one.
- Current-page state, public-access settings and metrics refresh immediately and every ten minutes while the panel is open. Closing it cancels requests and stops polling.
- Expand a row to refresh its state and public-access setting, then read backup/restore, availability, failover and maintenance information. The small refresh icon refreshes that row and its operational details.
- Prominent public-network warning only when the setting is Enabled. Unknown settings are never inferred to be disabled.
- Portal links and an optional DB Studio workbench shortcut for SQL and PostgreSQL.
- No persistent resource or cost cache. Saved views, remembered account metadata and Azure CLI profiles are stored locally.

## Setup

Requires Omarchy Quattro/Quickshell, Python 3.10+, and Azure CLI. The panel provides **Install Azure CLI** when missing, and **Sign in to Azure** when signed out. Authenticated users do not see the sign-in action. Azure CLI owns credentials and token refresh; the plugin does not store or expose access tokens.

```bash
bash scripts/setup.sh install
bash scripts/setup.sh login
```

The identity needs Resource Graph and ARM read permissions for the resources, Azure Monitor metric-read permission, and Cost Management access for billing values. Individual metric, cost or operational-detail failures remain visible without inventing zero values or healthy states. Resource Graph metadata can lag Azure changes; current-page ARM reads obtain current state.

## Install

Install from GitHub:

```bash
omarchy plugin add https://github.com/dimitrijemaric/omarchy-azure-sql --enable
```

Or install from a local checkout:

```bash
omarchy plugin validate .
plugin_dir="$HOME/.config/omarchy/plugins/dimitrije.azure-sql"
mkdir -p "$plugin_dir/scripts"
cp *.qml Model.js manifest.json LICENSE README.md "$plugin_dir/"
cp scripts/*.py scripts/*.sh "$plugin_dir/scripts/"
omarchy plugin enable dimitrije.azure-sql
```

The plugin ID remains `dimitrije.azure-sql` to preserve an existing installation and its saved views. Its displayed name is **Azure Databases Desk**.

## Accounts and directories

Click **Accounts ▾** in the header to show the **Account** and **Directory** selectors above the service tabs. They start hidden whenever the panel opens; click Accounts again to collapse them. Account chooses a remembered sign-in; Directory chooses a Microsoft Entra tenant for that sign-in. Guest access uses the same account with a different directory. Subscription filters below are limited to the selected directory, preventing cross-tenant Resource Graph queries.

- The **+** beside Account opens a dialog with an optional tenant ID and cloud selection. Continue opens terminal/browser sign-in; choose the other Microsoft account there. A successful sign-in is remembered and selected automatically. Cancelling keeps the previous selection.
- Choose an account from the searchable list to reuse its CLI session and last directory. Azure may require sign-in again when its session expires.
- Choose a directory to reuse the same account there. Directory names include a short tenant ID to distinguish organizations with similar names; full tenant IDs are searchable. The **+** next to Directory signs the selected account into another tenant by UUID. If a discovered directory has no cached sign-in, select it and use **Sign in to Azure**.
- Switching accounts/directories cancels previous reads, clears database/cost data and subscription/server filters, then fetches a fresh first page. Backend requests also validate subscription scope against that profile and tenant. The last account and each account's last directory survive panel reopen and shell restart.

**Azure CLI account** uses the existing terminal CLI profile (`AZURE_CONFIG_DIR`, default `~/.azure`) for compatibility. Added accounts each use a separate CLI configuration under `${XDG_STATE_HOME:-~/.local/state}/azure-sql-desk/azure-profiles/<profile-id>/`. Switching an added account does not change the terminal's default account or subscription. Terminal sign-ins can change the shared CLI entry. Reauthenticating an added profile must use its remembered account; use **+** beside Account for another identity. Passwords and access tokens never enter QML or the preferences database; Azure CLI owns the credential files in its profiles. Added profile directories are mode 0700 and CLI files are created with a restrictive umask. Metadata and selections live in `accounts.sqlite3` (0600). Keep this state directory private; removing it signs the plugin's added profiles out locally and removes remembered choices.

These flows use documented [Azure CLI configuration directories](https://learn.microsoft.com/en-us/cli/azure/azure-cli-configuration?view=azure-cli-latest) and [interactive tenant sign-in](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli-interactively?view=azure-cli-latest#sign-in-to-a-specific-tenant). Microsoft controls MFA, consent and session expiry. No password login is implemented.

## Browsing and default views

Select any combination of subscription, server/account, location, tier/API and compute-model filters. Every dropdown is searchable, including Sort by and Saved views. Open a dropdown and type, or focus it and start typing. Multiselect dropdowns stay open while you check choices and apply the combined selection when you close them; name/sort changes are debounced. Use Up/Down to navigate choices, Space or Enter to toggle, and Tab then Enter on Done to apply. Select All to clear that category's selections. Changing subscriptions removes server selections outside the new scope; unavailable restored selections are labeled and can be cleared. Reset clears filters and sorting. Azure SQL offers all six [service tiers and both compute models](https://learn.microsoft.com/en-us/azure/azure-sql/database/purchasing-models?view=azuresql), even when your inventory has no matches. Locations come from Microsoft.Sql server provider metadata for the signed-in Azure cloud, merged with discovered regions. Subscription and server lists contain accessible resources, including empty SQL servers. Region choices describe service support; subscription restrictions and tier/compute compatibility can still limit deployment. Cosmos is shown at account level and PostgreSQL at flexible-server level, where management, billing and high-availability settings exist; internal databases/containers and query data are not enumerated.

Expand **Advanced filters** for Backup & restore, Maintenance and Availability. The collapsed heading shows how many advanced selections are active. Backup redundancy offers Local, Zone, Geo and Geo-zone storage. Restore history buckets the time since Azure's earliest reported restore point: under one day, 1–7 days, 7–14 days and 14+ days. This describes reported recovery history, not the configured retention policy or a guarantee that a restore will succeed. Maintenance offers system default, weekday, weekend and other configured windows; missing metadata stays Not reported. Zone redundancy and read scale-out offer Enabled, Disabled and Unknown. All these selections are saved with the view.

Operational filtering runs in Resource Graph across the selected scope before the 25-row page is returned, including cost sorting. Database and elastic-pool metadata are joined to inherit pool maintenance and zone settings. No individual backup-policy/failover calls are added for off-page databases. Resource Graph can lag ARM and omit properties; absent values match Unknown/Not reported. Exact PITR/LTR retention and failover-group details remain expansion-only reads. Standard SQL public maintenance configuration suffixes `_DB_1` and `_DB_2` are classified as weekday and weekend; unrecognized configurations stay Other.

Sort by has its own section above Filters. Save view sits directly below the database-name filter, followed by the Saved views section. The left list fills the available height. Use Previous, Next or enter a page number. Name, location, tier and state sorting is applied by Azure Resource Graph before the 25-row page is returned. The default built-in view uses Name A–Z for bounded first-page resource reads. Cost sorting additionally reads a lightweight matching resource-ID index and fresh billing aggregates to rank the whole scope correctly before returning its selected 25 resources; large inventories make cost sorting slower. The resulting ID/cost ranking stays only in the open panel's memory: subsequent pages fetch fresh metadata for their 25 IDs without repeating discovery or billing. Closing/reopening the panel, changing filters, changing the billing month, or explicitly refreshing discards it. Cost sorting supports up to 100,000 matches; larger scopes must be narrowed. Empty matches make no billing request; up to 100 matches use resource-ID billing filters.

Click **Save view** directly below the name filter. A new view requires a unique name. Editing a loaded view retains its identity and default setting; the dialog offers **Update** or **Save as new**. Save as new requires a different name. Duplicate names never silently overwrite another view. Check **Make default view** in the naming dialog to save the view and default preference together. Alternatively, load a saved view and click **Make default** beside **Delete view**; the button shows **✓ Default** for the current default. Unchecking the option while saving the existing default clears that preference. The default contains the service tab, multi-select filters, name filter and sort order. While Cosmos DB and PostgreSQL are disabled, their saved views are preserved but unavailable in view selectors; a default for either service falls back to the built-in Azure SQL view. Paging always starts at 25 rows on page one. Deleting the default view restores the built-in default.

`Ctrl R` refreshes the current page and available filter options. The header refresh icon does the same. Azure login/setup reopens the panel with its default view.

## Live monitoring

Only the current 25 resources receive ARM GETs and metric reads. Metadata reads run with at most three Azure CLI processes at once. SQL parent-server access settings are read once per distinct parent in the page. Metrics use Azure Monitor's regional [batch API](https://learn.microsoft.com/en-us/rest/api/monitor/metrics-batch/batch?view=rest-monitor-2023-10-01), grouped by subscription and location.

| Service | Displayed live metrics |
| --- | --- |
| Azure SQL | CPU, physical data reads, log writes; paused databases skip metric reads |
| Cosmos DB | Maximum normalized RU consumption |
| PostgreSQL flexible server | CPU, memory and storage percentages |

Metric samples use one-minute granularity over the last 15 minutes and can lag collection. No SQL or document-data connection is opened. Periodic refresh updates current-page ARM state and metrics; it does not enumerate other pages or repeat billing queries. Backup/restore and failover details are read on expansion or explicit row refresh. Rate-limit responses (429/529) use separate resource, metric, billing and discovery cooldowns with a 15, 30, then 60-minute backoff, or longer when the CLI exposes a Retry-After delay. Undispatched work stops when its service is throttled. A billing or metrics cooldown never suppresses ARM public-access checks. Manual actions also honor the affected cooldown; other services remain available. Billing queries are not retried automatically. These measures reduce API traffic; shared Azure quotas can still cause throttling.

The current regional batch endpoint implementation targets Azure public cloud. Portal shortcuts also recognize Azure Government and China; these environments need their regional metrics endpoints adapted before batch monitoring there. Use subscriptions within one Azure tenant for a single Resource Graph selection; cross-tenant discovery requires an appropriate delegated Azure scope.

Set the visible-page interval (600–3600 seconds; older shorter settings are clamped to ten minutes):

```bash
omarchy bar set dimitrije.azure-sql liveRefreshIntervalSec 600 --json
```

## Costs

Fresh [Cost Management queries](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01) use ActualCost, MonthToDate and ResourceId grouping. Normal paging requests billing for the current page only. Cost sorting reads resource-scoped costs for up to 100 matches; broader rankings read the selected service's aggregates once per matching subscription. Page navigation reuses the in-memory ordering until the ranking is discarded as described above. No billing response is persisted. Costs are delayed posted charges, not forecasts or an instantaneous meter. Currency comes from Azure; sorting across different billing currencies is rejected. Unknown values sort last. Shared elastic-pool compute is not allocated arbitrarily to its member databases; their values include only directly billed resource charges.

## Operational details

See [the resource-data analysis](RESOURCE_DATA.md) for the implemented fields, permissions, endpoint references, and useful further additions. All actions are read-only: this panel does not restore, initiate failover, change backup retention or schedule maintenance.

## Local preferences and removal

Saved views and the default preference live in `${XDG_STATE_HOME:-~/.local/state}/azure-sql-desk/views.sqlite3`, mode 0600, with a separate demo file. Existing single-select views are migrated on read. This is preference storage, not a resource cache. Azure CLI maintains the shared profile and the isolated credential profiles described under Accounts and directories. Remembered account metadata is in `accounts.sqlite3`; it contains account names, tenant IDs and profile choices, never token values.

Version 0.6 removes the previous catalog cache. When upgrading manually, remove `catalog-v1.sqlite3` and its journal/WAL sidecars from `${XDG_CACHE_HOME:-~/.cache}/azure-sql-desk/` after stopping the old shell instance. Preserve the state directory to keep saved views.

```bash
omarchy plugin remove dimitrije.azure-sql
```

## Simulation and optional query client

```bash
python3 scripts/simulate.py
```

Opens a separate fictional Azure SQL panel with a public-enabled resource expanded. Cosmos DB and PostgreSQL remain disabled. It uses temporary preferences and makes no Azure requests. Closing it exits the simulation. Live mode is selected with the widget setting `demoMode false`.

The query icon opens [DB Studio](https://github.com/Andean-Bridge/omarchy-db-browser) if separately installed. It supports SQL username/password connections to Azure SQL and PostgreSQL connections. It has no selected-resource deep link, so choose/create the connection in its workbench. The icon does not install software or execute a query. Install and configure DB Studio separately using its own marketplace documentation. This plugin only opens an already-installed workbench.

## Development

Run the current offline regression suites:

```bash
python3 -B -m unittest discover -s tests
python3 -B scripts/qml_check.py
omarchy plugin validate .
```

The Python tests cover the current helper protocol, pagination, cost scoping/ranking, throttled dispatch, cancellation, failover continuations, operational filters and view persistence. QML checks use the actual controller and controls with an offline CLI fixture: 20,002 databases, 25-row pages, expansion, keyboard navigation, dark/light controls, compact layout, views, remembered account/directory switching, cancelled sign-ins, and billing-independent security checks. Before publication, also exercise multiple subscriptions and regions, denied metric/billing access and cost-order boundaries on representative live Azure scopes. See [release checks](RELEASE.md).

MIT. See [LICENSE](../LICENSE).
