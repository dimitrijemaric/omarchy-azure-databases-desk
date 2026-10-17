Adversarial review of Azure Databases Desk 0.6.6 — 17 October 2026

## Resolution — 0.6.7

All twelve findings below have been addressed. The original observations are retained as review history; their line numbers refer to 0.6.6.

| Finding | Resolution |
| --- | --- |
| 1 | Separate billing, metrics, ARM and discovery cooldowns; billing cannot suppress initial security reads. |
| 2 | Signal handler only sets a flag; normal execution cancels/reaps CLI children. Controller force-kills an unresponsive helper after three seconds. |
| 3 | Shared stop flag skips undispatched ARM reads; metric groups stop after their first throttle. |
| 4 | Validated failover continuation traversal; incomplete lists show Unavailable. |
| 5 | Empty scopes skip billing, narrow scopes use resource IDs, broad cost rankings are bounded and reused only in panel memory for pagination. No persistent resource/cost cache. |
| 6 | Expansion performs a one-database live refresh before fetching operational details. |
| 7 | Migrated helper/QML fixtures and added regressions for all reviewed failure paths. |
| 8 | Name search, Save view and Saved views moved below Sort by; advanced operational filters collapse. |
| 9 | Arrow navigation, highlighted choice, Enter/Space toggles and keyboard-accessible Done. |
| 10 | Explicit themed text, background, checkbox indicators and focus; dark/light QML assertions. |
| 11 | Preserve selected view identity and default state; explicit Update/Save as new; duplicate names rejected. |
| 12 | Subscription changes remove incompatible server selections; missing restored choices are labeled and removable; Reset clears filters. |

Validation uses isolated fixtures and actual QML components. See `tests/test_resources.py`, `tests/test_backend.py`, `tests/test_setup.py` and `tests/Smoke.qml`. Live Azure quota behavior and large-tenant latency remain deployment checks.

## Original review

The highest-priority finding is that Cost Management throttling suppresses the initial ARM/security refresh. The cancellation path also has a reproducible deadlock. I would resolve these before marketplace submission. This review did not change the implementation or the installed plugin.

Severity: P1 means high-priority correctness/security behavior; P2 means a material reliability, scalability or usability defect. Findings below distinguish reproducible failures from source-level observations.

Code review was completed first.

1. **[P1] A billing throttle suppresses public-network checks.** In [Controller.qml](../Controller.qml#L210), any `rateLimited` result activates a single global cooldown. The catalog branch at line 225 then skips the first `live` request. Catalog rows initialize `publicNetworkAccess` to `Unknown`, so a public-enabled server can receive no PUBLIC warning for the 15-minute initial cooldown, or longer after repeated throttles. This couples Cost Management availability to security visibility. An isolated run of the actual controller with a throttled catalog response produced `liveRequestQueued:false`, `network:"Unknown"`, and `pause:true`. Fix: maintain separate backoff state for billing, ARM metadata and metrics; complete readable network checks independently of billing.

2. **[P2] Cancellation can deadlock the helper and leave the panel permanently busy.** [azure_sql.py](../scripts/azure_sql.py#L66) acquires `_children_lock` from the SIGTERM handler. The same non-reentrant lock is acquired by `run_az` on the main thread at lines 100 and 155. If SIGTERM arrives during either critical section, the handler waits for a lock that the interrupted stack cannot release. I reproduced this interleaving in an isolated subprocess; it required an external timeout/kill. The controller watchdog sends another SIGTERM rather than escalating to a hard kill. Fix: keep signal handlers nonblocking and defer cleanup to normal execution; add a bounded hard-kill fallback.

3. **[P2] A refresh continues issuing requests after throttling.** [cloud_resources.py](../scripts/cloud_resources.py#L328) submits all current-page reads to the executor and waits for every result. There is no shared stop condition on 429. With every fake ARM read returning a throttle, all 25 reads were still attempted. The sequential metric-group loop can also continue to subsequent groups after a throttle. Fix: stop undispatched work for the affected quota scope and propagate Retry-After immediately. Limiting concurrency to three does not limit the total requests made after the first failure.

4. **[P2] Failover-group pagination can produce a false “None.”** [cloud_resources.py](../scripts/cloud_resources.py#L403) consumes only the first `value` array and ignores `nextLink`; line 415 reports None if no match appears there. A fixture with an empty first page plus a continuation link resulted in one list call and `Failover groups: None`. Azure's [documented response](https://learn.microsoft.com/en-us/rest/api/sql/failover-groups/list-by-server?view=rest-sql-2023-08-01#failovergrouplistresult) includes `nextLink`. Fix: follow validated continuation links, and report Unavailable if traversal is incomplete. This is a conditional defect when Azure returns multiple pages, not a claim that the current live server has a paginated response.

5. **[P2] Cost sorting repeats whole-scope work even for an empty or narrow result.** [cloud_resources.py](../scripts/cloud_resources.py#L209) materializes every matching resource and calls billing without the matching resource IDs. [costs.py](../scripts/costs.py#L21) therefore queries all SQL database costs in every selected subscription. This repeats on each page navigation and filter change. The empty-result fixture still issued a whole-service billing request. This is particularly expensive for the intended tens-of-thousands-of-databases use case. Fix: skip billing for empty results, constrain narrow matches with resource IDs, and define a bounded strategy for broad cost ordering that respects the no-persistent-cache requirement.

6. **[P2] Expanding a database does not refresh the displayed database state or public-access setting.** [Controller.qml](../Controller.qml#L138) requests only `detail` on expansion; its reply handler at line 239 updates only the operational-detail object. The helper's detail response contains sections rather than a refreshed database summary and does not read the parent server's network access. The row can therefore remain stale for the ten-minute polling interval even though expansion has just fetched other metadata. This is a source-confirmed behavior; the row's explicit refresh icon does invoke both live and detail reads. Fix: perform a bounded live refresh for the expanded database and merge the result before/alongside its operational details.

7. **[P2] The existing test suite does not protect the current implementation.** `python3 -B -m unittest discover -s tests` ran 34 tests and reported 12 errors, including subtest errors. Several tests call removed catalog/cache APIs or old CLI operations. The QML smoke suite failed with `Controller did not settle at stage 0`; [Smoke.qml](../tests/Smoke.qml#L33) still expects a 50-row page although the application now uses 25. The newer catalog, cost, operational-filter and view workflows lack corresponding working coverage in that suite. Fix: migrate the fixtures and add focused coverage for the failures above, pagination, default-view persistence and inherited pool settings. A successful manifest validation is not evidence that these behaviors work.

The UX review used the actual QML components in a separate offline Quickshell window, with fictional data, temporary preferences and Qt's Basic control style. No live Azure writes or account changes were made.

8. **[P2] Common actions are buried below the initial viewport.** At 1120×760, the right pane had a 646px viewport and 978px of content. The database-name field began at y=792, Save view at y=833, and the saved-view selector at y=903 relative to the pane. Users must scroll past advanced backup/maintenance/availability settings to perform basic name search or load a view. This worsens at 800×540. Relevant layout: [PanelContent.qml](../PanelContent.qml#L283). Recommendation: keep name search and view selection readily accessible and make advanced filter groups collapsible, preserving Save view directly below the name field.

9. **[P2] Multiselect keyboard navigation does not reach the options normally.** Open Service tiers, press Down twice, then Return: focus remains in `Search service tiers…`, and Basic is selected because Return always toggles the first filtered option. This was reproduced with QtTest keyboard events. [MultiSelectCombo.qml](../MultiSelectCombo.qml#L59) has no search-to-list arrow navigation or highlighted-option activation. Recommendation: add Up/Down navigation, visible focus, Space/Return selection, and a clear keyboard action to finish the multiselect edit.

10. **[P2] Theme styling makes some controls hard to read.** In the supported Basic style, multiselect delegates render light foreground text on a default white background; the Save view dialog's “Make default view” label renders black on a dark background. The checkbox's actual `contentItem.color` was `#000000`. [PanelContent.qml](../PanelContent.qml#L64) sets `palette.text` and `palette.buttonText`, while Basic CheckBox uses `palette.windowText`. [MultiSelectCombo.qml](../MultiSelectCombo.qml#L79) does not style the delegate background/palette consistently. Recommendation: theme the complete controls, including background, text, indicator and focus state, then inspect both dark and light palettes. These observations are specific to the tested style, not a claim about every possible Qt theme.

11. **[P2] Editing a saved view can silently overwrite it and remove its default status.** A filter change clears `selectedViewId` in [Controller.qml](../Controller.qml#L112). The Save dialog consequently opens with a blank name and an unchecked default checkbox. Re-entering the existing name updates that view by name, and [views.py](../scripts/views.py#L65) clears the default when `makeDefault:false`. The isolated storage probe changed a default view from set to unset while retaining one overwritten view. Recommendation: distinguish Update view from Save as, retain the edited view's identity/default state, and make replacement/default removal explicit in the save interaction.

12. **[P2] Subscription changes can retain an incompatible server filter.** Changing from subscription A to B leaves A's selected server IDs intact in [Controller.qml](../Controller.qml#L110). The refreshed server options can omit those IDs while the query still filters by them, producing an unexplained empty result; the closed dropdown may show an opaque resource ID. The controller probe confirmed that B was selected while A's server filter remained. Recommendation: remove incompatible dependent selections or clearly surface them with a one-click clear action. Also expose the applied-filter summary or a Reset filters action so restrictions farther down the scroll pane remain discoverable.

Checks completed: manifest validation passed; the existing Python and QML suites failed as described; targeted isolated backend/controller probes reproduced findings 1–5 and 11–12; offline keyboard, hover and layout inspection reproduced findings 8–10. The disabled Cost Calculator “Coming soon” tooltip did display correctly in the hover check. The read-only helper uses fixed subprocess argument arrays and redacts CLI stderr; no straightforward shell-command injection path was identified in the reviewed flow.

Review limits: fixtures exercised adverse response shapes and timing interleavings, not real Azure throttling or production failover. I did not load-test a live tenant with tens of thousands of resources, exercise sovereign-cloud metrics, or validate every operational filter against live Azure resources. Those remain release-validation gaps rather than additional confirmed findings.

The original review used temporary offline probes and fictional screenshots. Permanent regression coverage now lives in `tests/test_resources.py`, `tests/test_accounts.py` and `tests/Smoke.qml`.
