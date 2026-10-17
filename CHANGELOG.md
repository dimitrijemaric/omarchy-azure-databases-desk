# Changelog

## [0.8.0] - 2026-10-17

- Rename the plugin ID to `azure-databases-desk` and the repository to `omarchy-azure-databases-desk`.
- Update shell IPC, setup actions, installation instructions, test harness imports and marketplace metadata.
- Keep the display name Azure Databases Desk and retain the existing state directory for saved views and logins.

## [0.7.1] - 2026-10-17

- Prepare the first marketplace submission with complete installation, updates, removal, dependencies and security documentation.
- Add portable release preflight and GitHub CI for offline regression checks.
- Add full author metadata; the plugin identity is updated in 0.8.0.
- Keep DB Studio as an optional launcher for a separately installed plugin; remove the bundled third-party installer.
- Include a fictional preview, MIT license, contribution guidance and release checklist.

## [0.7.0] - 2026-10-17

- Browse Azure SQL with fresh pages of 25 databases and current-page monitoring.
- Show posted month-to-date resource costs and public-network warnings.
- Filter by subscriptions, servers, region, tier, compute model, backup, maintenance and availability; save default views.
- Read backup/restore policies, failover groups and maintenance details on expansion.
- Remember isolated Azure sign-ins and switch account or directory; hide identity controls behind the Accounts toggle by default.
- Add request cancellation, independent service cooldowns, validated continuations and in-memory cost ordering.
- Keep Cosmos DB, PostgreSQL and Cost Calculator disabled with Coming soon tooltips.
