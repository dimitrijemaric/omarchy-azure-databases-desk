### Repository URL

https://github.com/dimitrijemaric/omarchy-azure-sql

### Category

Developer Tools

### Tags

bar, quickshell, security

### Suggest a missing tag

_No response_

### Maintainer notes

Azure Databases Desk (dimitrije.azure-sql), version 0.7.1, is an Omarchy bar widget for Azure SQL databases. It provides fresh 25-row pages, live metadata and metrics, posted month-to-date costs, public-network warnings, operational details, searchable filters, saved views, and remembered account/directory switching. Cosmos DB, PostgreSQL and Cost Calculator remain disabled.

The runtime uses QML, Bash and Python's standard library with Azure CLI. Azure operations are management-plane reads; no SQL queries, restores, failovers or resource writes are performed. Installing the repository runs no setup hooks. The explicit Install Azure CLI action opens a terminal and invokes Omarchy's package manager. Sign-in uses Microsoft's interactive flow. Added identities use separate Azure CLI profiles; credentials remain managed by Azure CLI. Preferences, profile directories, permissions and network behavior are documented in SECURITY.md and the README.

The optional query icon only opens a separately installed DB Studio plugin. This repository does not download or install that external workbench. The preview uses fictional resources created for this plugin.

Release checks: native Omarchy manifest validation, portable release preflight, Bash syntax checks, 71 offline Python tests, and native offscreen QML interaction checks. QML coverage includes paging, filtering, cancellation, public-access updates, saved views, account/directory switching, compact layout and dark/light controls. GitHub CI covers portable checks and Python tests. Live large-tenant performance and all sovereign-cloud metrics remain documented limitations. Please review the explicit Azure CLI setup/package-manager capabilities; no privileged background service or sudoers policy is installed.

### Submission checklist

- [x] The repository is public and contains installation and removal instructions.
- [x] I have documented the plugin license and any external dependencies.
- [x] I confirm that I own or have permission to submit this plugin and its preview assets.
- [x] The plugin does not overwrite user configuration without explicit consent.
- [x] I understand that approval is for listing and is not a security review.
