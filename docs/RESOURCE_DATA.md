# Database resource data

Azure SQL is represented by databases, Cosmos DB by accounts, and PostgreSQL by flexible servers. These resource levels expose ARM state and billing identities without obtaining SQL passwords, document keys, or data-plane access.

## Implemented reads

| Service | On current-page refresh | On expansion / row refresh |
| --- | --- | --- |
| Azure SQL | Database state, SKU/tier, compute model, location; parent public-network setting; CPU/data I/O/log I/O metrics | Earliest restore date, short-term retention days, weekly/monthly/yearly long-term retention, backup storage redundancy, zone redundancy, matching failover groups and role/policy, maintenance configuration |
| Cosmos DB | Account provisioning state, API, serverless/provisioned mode, location, public network access, normalized RU use | Periodic/continuous backup policy, interval and retention, backup storage redundancy, regional failover priorities, automatic failover, multi-region writes, consistency |
| PostgreSQL flexible server | Server state, SKU/tier, location, public-network setting, CPU/memory/storage metrics | Backup retention, earliest restore, geo-redundant backup, HA mode/state and standby zone, engine version, custom or system-managed maintenance window |

SQL uses database GET, `backupShortTermRetentionPolicies/default`, `backupLongTermRetentionPolicies/default`, and parent `failoverGroups` list (API 2023-08-01). The failover list is filtered to groups that explicitly include the selected database. A failed read remains Unavailable; it is not reported as None. Cosmos uses account GET (2024-05-15); PostgreSQL uses flexible-server GET (2024-08-01). Returned policy fields describe configuration; they do not prove that a restore drill succeeded or a particular backup is usable.

Missing optional fields are omitted. Cosmos does not expose a PostgreSQL-style customer maintenance window in this account shape, so none is invented. Continuous backup tiers specify configured retention; exact recoverable intervals need the dedicated restorable-resource APIs. SQL long-term-retention values are ISO 8601 policy durations, not lists of completed backup files.

## Additional useful reads

| Data | Value | Read/cost implications |
| --- | --- | --- |
| SQL replication links and lag | Distinguish healthy geo-replication from a configured failover policy | Per-database replication-link reads; avoid polling every off-page database |
| SQL completed LTR backups | Concrete recovery points and expiration dates | Additional location/server/database LTR listings; paginate and require relevant read permissions |
| SQL transparent data encryption and security findings | Separate encrypted-at-rest state from public endpoint exposure | TDE/security APIs and potentially different RBAC scopes; an unreadable state must stay unknown |
| Cosmos restorable accounts/databases/containers | Precise available restore periods and resource lifetimes | Dedicated restorable-resource listings, region/API-specific shapes and permissions |
| Cosmos RU, requests, throttling, latency and partition skew | Explain contention and 429 errors | Different metric aggregations and high-cardinality dimensions; scope to selected accounts/containers |
| PostgreSQL replication lag, connections and IOPS | Find capacity and replica health issues | Additional engine-specific metric names, dimensions and availability vary with configuration |
| Resource Health / Azure Service Health | Separate an Azure incident from resource configuration | Separate resource-health and subscription-level APIs; fresh timestamps are essential |
| Maintenance events | Upcoming or ongoing platform maintenance versus configured window | Service-specific scheduled-event/activity-log APIs; a configured window does not prove an event is scheduled |
| Backup / failover execution | Restore drills or recovery actions | Write operations with material impact; intentionally outside this read-only desktop panel |

## Primary references

- [SQL database resource schema](https://learn.microsoft.com/en-us/rest/api/sql/databases/get?view=rest-sql-2023-08-01)
- [SQL short-term retention](https://learn.microsoft.com/en-us/rest/api/sql/backup-short-term-retention-policies/get?view=rest-sql-2023-08-01)
- [SQL long-term retention](https://learn.microsoft.com/en-us/rest/api/sql/long-term-retention-policies/get?view=rest-sql-2023-08-01)
- [SQL failover groups](https://learn.microsoft.com/en-us/rest/api/sql/failover-groups/get?view=rest-sql-2025-01-01)
- [Cosmos account schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.documentdb/2024-05-15/databaseaccounts)
- [Cosmos continuous-backup resource model](https://learn.microsoft.com/en-us/azure/cosmos-db/continuous-backup-restore-resource-model)
- [PostgreSQL flexible-server schema](https://learn.microsoft.com/en-us/rest/api/postgresql/servers/list?view=rest-postgresql-2024-08-01)
- [Azure Monitor batch metrics](https://learn.microsoft.com/en-us/rest/api/monitor/metrics-batch/batch?view=rest-monitor-2023-10-01)
- [Cost Management query dataset](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01)

## Catalog operational filters

Version 0.6.6 filters backup storage redundancy, time since the reported earliest restore point, maintenance configuration, zone redundancy and read scale-out. Resource Graph applies these predicates before paging and cost ranking. A left join to elastic pools supplies inherited maintenance/zone settings; missing or unreadable pool metadata remains unknown. Standard public maintenance suffixes `_DB_1` and `_DB_2` identify weekday/weekend categories; unrecognized nonempty configurations are Other. Missing configurations are Not reported.

Restore-history buckets measure elapsed time since `earliestRestoreDate`, not policy retention or backup validity. Catalog metadata can lag ARM. PITR/LTR policy and failover-group child resources are not in the supported Resource Graph SQL resource list; this feature keeps those reads on expansion instead of scanning every database via ARM. Expanded pooled resources read their parent pool once for maintenance/availability settings.
