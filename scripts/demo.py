"""Fictional, paginated catalog with 20,002 databases. Never calls Azure."""
import datetime as dt

SUBSCRIPTION = "11111111-1111-4111-8111-111111111111"
SERVER = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/demo-rg/providers/Microsoft.Sql/servers/demo-sql"
PRIVATE_SERVER = SERVER.rsplit("/", 1)[0] + "/private-sql"
TOTAL = 20002


def database(index):
    name = "app-development" if index == 0 else "integration-tests" if index == 1 else f"tenant-{index - 2:05d}"
    server = SERVER if index % 2 == 0 else PRIVATE_SERVER
    return {"id": server + "/databases/" + name, "name": name, "serverId": server,
            "serverName": server.rsplit("/", 1)[-1], "status": "Online" if index % 2 == 0 else "Paused",
            "location": "westeurope", "tier": "GeneralPurpose", "sku": "GP_S_Gen5", "capacity": 4,
            "computeModel": "Serverless", "maxSizeBytes": 34359738368, "autoPauseDelay": 60, "elasticPool": "",
            "cost": {"amount": round(640.0 - index * 0.031, 2), "currency": "USD",
                     "month": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m"), "asOf": "", "directOnly": False}}


def sample(args):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if args.operation == "subscriptions":
        return [{"id": SUBSCRIPTION, "name": "Demo · Engineering", "isDefault": True, "cloud": "AzureCloud"}]
    if args.operation == "servers":
        return [{"id": server, "name": server.rsplit("/", 1)[-1], "fqdn": server.rsplit("/", 1)[-1] + ".database.windows.net",
                 "location": "westeurope", "publicNetworkAccess": access}
                for server, access in [(SERVER, "Enabled"), (PRIVATE_SERVER, "Disabled")]]
    if args.operation == "databases":
        indices = [i for i in range(TOTAL)
                   if (not args.server_id or (SERVER if i % 2 == 0 else PRIVATE_SERVER) == args.server_id)
                   and (not args.filter or args.filter.casefold() in database(i)["name"].casefold())]
        indices.sort(key=lambda i: (-database(i)["cost"]["amount"], database(i)["name"], database(i)["id"]))
        start = args.page * args.page_size
        return {"rows": [database(i) for i in indices[start:start + args.page_size]],
                "totalCount": len(indices), "page": args.page, "pageSize": args.page_size}
    name = args.database_id.rsplit("/", 1)[-1]
    index = 0 if name == "app-development" else 1 if name == "integration-tests" else int(name.split("-")[-1]) + 2
    row = database(index)
    metrics = {} if row["status"] == "Paused" else {name: {"value": value, "timestamp": now}
        for name, value in [("cpu_percent", 18.4), ("physical_data_read_percent", 6.2), ("log_write_percent", 2.8)]}
    return {"database": row, "storage": {"usedBytes": 4831838208, "limitBytes": 34359738368},
            "metrics": metrics, "warnings": [], "network": {"publicNetworkAccess": "Enabled" if index % 2 == 0 else "Disabled",
                                                            "source": "server", "checkedAt": now}}


def simulate(operation, payload):
    """Interactive service tabs; all resources and monitoring values are fictional."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if operation == 'session':
        return {'subscriptions': [{'id': SUBSCRIPTION, 'name': 'Demo · Engineering', 'isDefault': True, 'cloud': 'AzureCloud'}], 'authenticated': True}
    engine = payload.get('engine') or payload.get('filters', {}).get('engine', 'sql')
    def resource(index):
        if engine == 'sql':
            row = database(index)
            row.update(engine='sql', tier=['GeneralPurpose', 'Hyperscale', 'BusinessCritical'][index % 3],
                       computeModel='Serverless' if index % 2 == 0 else 'Provisioned',
                       location=['westeurope', 'northeurope', 'eastus'][index % 3],
                       backupRedundancy=['Local','Zone','Geo','GeoZone','Unknown'][index % 5],
                       restoreHistory=['Under1Day','Days1To7','Days7To14','Days14Plus','Unknown'][index % 5],
                       maintenanceWindow=['SystemDefault','Weekday','Weekend','Other','Unknown'][index % 5],
                       zoneRedundancy=['Enabled','Disabled','Unknown'][index % 3],
                       readScale=['Enabled','Disabled','Unknown'][index % 3])
        else:
            kind = 'Microsoft.DocumentDB/databaseAccounts' if engine == 'cosmos' else 'Microsoft.DBforPostgreSQL/flexibleServers'
            name = ('demo-cosmos-' if engine == 'cosmos' else 'demo-postgres-') + str(index + 1)
            identifier = f'/subscriptions/{SUBSCRIPTION}/resourceGroups/demo-rg/providers/{kind}/{name}'
            row = {'id': identifier, 'name': name, 'serverId': identifier, 'serverName': name, 'engine': engine,
                   'location': ['westeurope', 'eastus'][index % 2],
                   'tier': ['NoSQL', 'MongoDB'][index % 2] if engine == 'cosmos' else ['GeneralPurpose', 'MemoryOptimized', 'Burstable'][index % 3],
                   'computeModel': 'Serverless' if engine == 'cosmos' and index % 2 else 'Provisioned',
                   'status': 'Succeeded' if engine == 'cosmos' else 'Ready', 'elasticPool': '',
                   'cost': {'amount': round(184.52 - index * 12.5, 2), 'currency': 'USD', 'month': now[:7], 'asOf': now}}
        row.update(publicNetworkAccess='Enabled' if index % 2 == 0 else 'Disabled', liveError='', metrics={}, liveAt=now)
        if row['status'] != 'Paused':
            names = ['NormalizedRUConsumption'] if engine == 'cosmos' else ['cpu_percent', 'memory_percent', 'storage_percent'] if engine == 'postgres' else ['cpu_percent', 'physical_data_read_percent', 'log_write_percent']
            row['metrics'] = {name: {'value': value, 'timestamp': now} for name, value in zip(names, [18.4, 6.2, 2.8])}
        return row
    count = TOTAL if engine == 'sql' else 8
    if operation == 'catalog':
        filters = payload['filters']
        indices = [i for i in range(count) if (not filters['filter'] or filters['filter'].casefold() in resource(i)['name'].casefold())
                   and all(not filters.get(key) or resource(i)[column].lower() in [v.lower() for v in filters[key]]
                           for key, column in ([('serverIds', 'serverId'), ('locations', 'location'), ('tiers', 'tier'), ('computeModels', 'computeModel')]
                               + ([('backupRedundancies','backupRedundancy'), ('restoreHistories','restoreHistory'), ('maintenanceWindows','maintenanceWindow'),
                                   ('zoneRedundancies','zoneRedundancy'), ('readScales','readScale')] if engine == 'sql' else [])))]
        sorting = filters['sortBy']
        if sorting.startswith('cost'):
            indices.sort(key=lambda i: (resource(i)['cost']['amount'] * (-1 if sorting == 'costDesc' else 1), resource(i)['name']))
        else:
            column = {'nameAsc': 'name', 'nameDesc': 'name', 'location': 'location', 'tier': 'tier', 'state': 'status'}[sorting]
            indices.sort(key=lambda i: (resource(i)[column].lower(), resource(i)['name']), reverse=sorting == 'nameDesc')
        facets = {}
        if payload.get('facets'):
            for key, column in [('servers', 'serverId'), ('locations', 'location'), ('tiers', 'tier'), ('computeModels', 'computeModel')]:
                # A few fixture rows cover every demo facet; avoid rebuilding 20k resources for options.
                unique = {resource(i)[column]: {'id': resource(i)[column], 'name': resource(i)['serverName'] if column == 'serverId' else resource(i)[column]} for i in range(min(count, 8))}
                facets[key] = sorted(unique.values(), key=lambda r: r['name'])
        start = payload.get('page', 0) * 25
        return {'rows': [resource(i) for i in indices[start:start + 25]], 'totalCount': len(indices), 'page': payload.get('page', 0), 'facets': facets, 'warnings': []}
    def locate(identifier):
        name = identifier.split('/')[-1]
        if engine != 'sql':
            return int(name.split('-')[-1]) - 1
        return 0 if name == 'app-development' else 1 if name == 'integration-tests' else int(name.split('-')[-1]) + 2
    if operation == 'live':
        return {'rows': [resource(locate(identifier)) for identifier in payload['ids']], 'authenticationRequired': False}
    values = [('Backup & restore', [('Retention (days)', '7'), ('Earliest restore', '2026-10-10T00:00:00Z')]),
              ('Availability', [('Zone redundant', 'Yes'), ('Failover group', 'demo-failover · Primary · Automatic')]),
              ('Maintenance', [('Window', 'Sunday 02:00 UTC')])]
    if engine == 'cosmos':
        values = [('Backup & restore', [('Backup mode', 'Continuous'), ('Retention', 'Continuous7Days')]),
                  ('Availability', [('Automatic failover', 'Yes'), ('Regions', 'West Europe, North Europe'), ('Consistency', 'Session')])]
    if engine == 'postgres':
        values[1] = ('Availability', [('High availability', 'ZoneRedundant'), ('HA state', 'Healthy'), ('PostgreSQL version', '17')])
    return {'id': payload['id'], 'sections': [{'title': title, 'rows': [{'name': key, 'value': value} for key, value in rows]} for title, rows in values], 'warnings': []}
