# Release checks — 0.8.0

- Validate the plugin manifest and inspect the native popup on a laptop and an external monitor.
- Open the panel repeatedly: default view, service tab, first page and exactly 25 rows must reset correctly and come from fresh reads.
- Set the default in the Save view dialog or with Make default beside Delete view; confirm the Default view dropdown is absent. Uncheck the default option when saving the existing default and confirm the built-in view is restored.
- Save, update, delete and select default views; restart the shell and confirm persistence. Existing single-select views must migrate.
- Confirm the Rebuild action and resource-cache files are absent. Saved preferences and Azure CLI credentials are separate.
- Confirm tier/compute options remain complete with a single-database inventory and supported regions are available. Search Sort by and Saved views; verify the Save view dialog replaces the inline name field.
- Confirm multiselect edits make one catalog request on close and live polling waits at least ten minutes, with backoff after 429/529.
- Exercise backup redundancy, restore-history boundaries, maintenance windows, zone redundancy and read scale-out across pages and cost sorts. Missing metadata must stay Unknown/Not reported; pooled databases must inherit maintenance and zone settings. Save and restore these filters in old and new views.
- Check all multi-select dropdowns, search inside them, All semantics, restored unavailable filter values and scopes with many servers.
- Confirm the left list fills to its bottom pager while the right filter column scrolls independently.
- Compare current-page ARM state and metric timestamps with Azure. Only the current 25 rows may refresh periodically; closing the panel stops requests.
- Change pages, service tabs and filters during an in-flight request. Old replies must not replace the current page.
- Verify name, location, tier and state sorts in Resource Graph and cost sorts across page boundaries. Mixed currencies must be rejected.
- Check cost-denied scopes, valid empty cost results, negative charges and elastic-pool members.
- Expand SQL rows and compare backup policies, restore bounds, failover groups and maintenance configuration. Confirm no recovery action is performed.
- Confirm Cosmos DB and PostgreSQL tabs remain disabled with Coming soon tooltips.
- Verify missing optional fields, insufficient permissions, expired login, missing CLI and network failures. Sign in appears only when signed out.
- Open DB Studio only after its separate approved installation; the query icon must not install it implicitly.
- Exercise the Azure SQL demo simulation without an Azure CLI call.

The Python and QML fixtures now use the current protocol. Run `python3 -B -m unittest discover -s tests`, `python3 -B scripts/qml_check.py` and `omarchy plugin validate .`. Offline fixtures cannot establish live Azure latency, tenant quotas or API permissions.

Regression requirements for 0.6.7:

- Billing/metrics throttling must not prevent ARM security checks; no more than the three already-started ARM reads may complete after a throttle.
- SIGTERM during child registration must not deadlock; cancellation must reap active CLI children. The controller has a three-second SIGKILL fallback.
- Follow validated failover-group continuation URLs; incomplete traversal reports Unavailable.
- Empty cost results make no billing request. Narrow matches use resource IDs. Broad cost rankings are bounded to 100,000 matches and held in panel memory only; paging does not rebuild them.
- Expansion refreshes state/public access before details. Explicit refresh and reopen discard the cost ranking.
- Name search/Save view/Saved views fit the initial viewport at 1120×760 and 800×540. Advanced operational filters collapse and show active selection counts.
- Keyboard navigation reaches multiselect options; Enter/Space toggle and Done applies. Inspect dark/light control backgrounds, labels, checks and focus.
- View edits retain identity/default state. Update is explicit; Save as new rejects duplicate names. Subscription changes prune incompatible servers.


Account switching requirements for 0.7.0:

- Add two identities; confirm each is remembered after shell restart and uses a separate CLI directory. Switching must not change the terminal CLI profile.
- Switch between home and guest directories for one identity. Scope the subscription list and Resource Graph reads to one tenant; restore each account's last directory.
- Switch during a resource refresh and verify no old rows, metrics or billing ranking appear.
- Cancel browser/terminal sign-in, expire a session, and sign into a tenant without subscriptions. Preserve choices, show Sign in only when needed, and never display another tenant's resources.
- Try a wrong identity during reauthentication; require the remembered account rather than silently relabeling an isolated profile.
- Confirm passwords/tokens are absent from helper output and preference databases; account metadata remains 0600 and new CLI profile directories 0700.
- Search both selectors, use their keyboard controls, inspect the 800×540 layout, and verify new-account/tenant dialogs validate tenant UUIDs.
