"""Read-only Azure resource discovery, current-page monitoring and operational details."""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import datetime as dt
import json
import re
import threading
from urllib.parse import urlencode, urlsplit

import costs
import views

MAX_COST_MATCHES = 100000
TYPES = costs.TYPES
VERSIONS = {'sql': '2023-08-01', 'cosmos': '2024-05-15', 'postgres': '2024-08-01'}
METRICS = {'sql': ('cpu_percent', 'physical_data_read_percent', 'log_write_percent'),
           'cosmos': ('NormalizedRUConsumption',), 'postgres': ('cpu_percent', 'memory_percent', 'storage_percent')}


def scope_of(identifier):
    return identifier.split('/')[2].lower()


def validate_resource(api, identifier, engine):
    api.resource_id(identifier)
    if '/providers/' + TYPES[engine].split('/')[0] + '/' not in identifier.lower():
        raise api.AzureError('invalid_input', 'Resource type and selected service do not match.')
    if engine == 'sql' and not api.DATABASE_ID.fullmatch(identifier):
        raise api.AzureError('invalid_input', 'Expected an Azure SQL database.')
    return identifier


def rest(api, identifier, engine, suffix=''):
    validate_resource(api, identifier, engine)
    return api.object_value(api.run_az(['rest', '--method', 'get', '--url', identifier + suffix + '?api-version=' + VERSIONS[engine],
                                       '--subscription', scope_of(identifier)]))


def session(api):
    import accounts
    # Unit callers without a context retain the standalone adapter behavior.
    identity = accounts.inspect(api) if api._identity_context is not None else {}
    rows = identity.get('subscriptions') if identity else api.subscriptions()
    result = dict(identity, subscriptions=rows, authenticated=False, sqlLocations=[])
    if identity.get('directorySignInRequired'):
        result['signInRequired'] = True
        result['optionsWarning'] = 'Sign in to access the selected directory with this account.'
        return result
    try:
        arguments = ['account', 'get-access-token', '--query', '{expiresOn:expiresOn}']
        if rows:
            arguments += ['--subscription', rows[0]['id']]
        elif identity.get('tenantId'):
            arguments += ['--tenant', identity['tenantId']]
        else:
            return result
        # Filter before stdout: access tokens never enter this adapter's output or QML.
        api.run_az(arguments)
        result['authenticated'] = True
    except api.AzureError as error:
        if error.code != 'authentication':
            raise
        result['signInRequired'] = True
        return result
    if not rows:
        return result
    try:
        locations = api.run_az(['provider', 'show', '--namespace', 'Microsoft.Sql', '--subscription', rows[0]['id'],
                               '--query', "resourceTypes[?resourceType=='servers'].locations | [0]"])
        if not isinstance(locations, list) or any(not isinstance(name, str) for name in locations):
            raise api.AzureError('invalid_response', 'Azure omitted SQL-supported locations.')
        result['sqlLocations'] = [{'id': name.replace(' ', '').lower(), 'name': name} for name in locations]
    except api.AzureError as error:
        result['optionsWarning'] = 'Supported SQL regions unavailable; showing discovered regions. ' + str(error)
        result['rateLimited'] = error.code == 'rate_limit'
        result['retryAfterSec'] = error.retry_after
        result['throttleScope'] = 'discovery'
    return result


def base(engine):
    query = "Resources | where type =~ " + json.dumps(TYPES[engine])
    if engine == 'sql':
        query += (" | extend displayName=tostring(split(id,'/')[10]),parentId=substring(id,0,indexof(tolower(id),'/databases/')),"
                  "parentName=tostring(split(id,'/')[8]),serviceTier=tostring(sku.tier),"
                  "compute=case(tostring(properties.computeModel) =~ 'Serverless' or tostring(sku.name) contains '_S_' or todouble(properties.minCapacity)>0.0,'Serverless','Provisioned'),"
                  "resourceState=tostring(properties.status) | where displayName !~ 'master' and serviceTier !~ 'DataWarehouse'")
    elif engine == 'cosmos':
        query += (" | extend displayName=name,parentId=id,parentName=name,"
                  "serviceTier=case(kind =~ 'MongoDB','MongoDB',tostring(properties.capabilities) contains 'EnableCassandra','Cassandra',"
                  "tostring(properties.capabilities) contains 'EnableGremlin','Gremlin',tostring(properties.capabilities) contains 'EnableTable','Table','NoSQL'),"
                  "compute=case(tostring(properties.capabilities) contains 'EnableServerless','Serverless','Provisioned'),"
                  "resourceState=tostring(properties.provisioningState)")
    else:
        query += (" | extend displayName=name,parentId=id,parentName=name,serviceTier=tostring(sku.tier),"
                  "compute='Provisioned',resourceState=tostring(properties.state)")
    return query


# All predicates run in Resource Graph before paging. Pool settings are inherited.
SQL_OPERATIONAL_QUERY = (
    " | extend poolKey=tolower(tostring(properties.elasticPoolId))"
    " | join kind=leftouter (Resources | where type =~ 'microsoft.sql/servers/elasticpools'"
    " | project poolKey=tolower(id),poolMaintenance=tostring(properties.maintenanceConfigurationId),"
    "poolZone=tostring(properties.zoneRedundant)) on poolKey"
    " | extend maintenanceId=iff(isnotempty(poolKey),poolMaintenance,tostring(properties.maintenanceConfigurationId)),"
    "zoneValue=iff(isnotempty(poolKey),poolZone,tostring(properties.zoneRedundant)),"
    "backupRedundancy=iff(isempty(tostring(properties.currentBackupStorageRedundancy)),'Unknown',tostring(properties.currentBackupStorageRedundancy)),"
    "restoreDate=todatetime(properties.earliestRestoreDate),readScaleValue=tostring(properties.readScale)"
    " | extend maintenanceWindow=case(isempty(maintenanceId),'Unknown',maintenanceId endswith 'SQL_Default','SystemDefault',"
    "maintenanceId endswith '_DB_1','Weekday',maintenanceId endswith '_DB_2','Weekend','Other'),"
    "zoneRedundancy=case(zoneValue =~ 'true','Enabled',zoneValue =~ 'false','Disabled','Unknown'),"
    "readScale=case(readScaleValue =~ 'Enabled','Enabled',readScaleValue =~ 'Disabled','Disabled','Unknown'),"
    "restoreHistory=case(isnull(restoreDate) or restoreDate > now(),'Unknown',restoreDate > ago(1d),'Under1Day',"
    "restoreDate > ago(7d),'Days1To7',restoreDate > ago(14d),'Days7To14','Days14Plus')"
)

SQL_FILTER_COLUMNS = [('backupRedundancies', 'backupRedundancy'), ('restoreHistories', 'restoreHistory'),
                      ('maintenanceWindows', 'maintenanceWindow'), ('zoneRedundancies', 'zoneRedundancy'),
                      ('readScales', 'readScale')]


def operational_fields(properties, maintenance=None, zone=None):
    """Classify reported metadata without treating missing values as disabled."""
    maintenance = properties.get('maintenanceConfigurationId') if maintenance is None else maintenance
    zone = properties.get('zoneRedundant') if zone is None else zone
    name = str(maintenance or '').lower()
    window = ('Unknown' if not name else 'SystemDefault' if name.endswith('sql_default') else
              'Weekday' if name.endswith('_db_1') else 'Weekend' if name.endswith('_db_2') else 'Other')
    history = 'Unknown'
    try:
        earliest = dt.datetime.fromisoformat(str(properties.get('earliestRestoreDate') or '').replace('Z', '+00:00'))
        days = (dt.datetime.now(dt.timezone.utc) - earliest).total_seconds() / 86400
        if days >= 0:
            history = 'Under1Day' if days < 1 else 'Days1To7' if days < 7 else 'Days7To14' if days < 14 else 'Days14Plus'
    except (TypeError, ValueError, OverflowError):
        pass
    return {'backupRedundancy': properties.get('currentBackupStorageRedundancy') or 'Unknown',
            'earliestRestoreDate': properties.get('earliestRestoreDate') or '', 'restoreHistory': history,
            'maintenanceWindow': window, 'maintenanceConfigurationId': maintenance or '',
            'zoneRedundancy': 'Enabled' if zone is True else 'Disabled' if zone is False else 'Unknown',
            'readScale': properties.get('readScale') if properties.get('readScale') in ('Enabled','Disabled') else 'Unknown'}


def graph(api, subscriptions, query, top=25, skip=0, token=None):
    options = {'$top': top, 'resultFormat': 'objectArray'}
    options['$skipToken' if token else '$skip'] = token if token else skip
    response = api.object_value(api.run_az(['rest', '--method', 'post', '--url', api.GRAPH_URL,
        '--body', json.dumps({'subscriptions': subscriptions, 'query': query, 'options': options}), '--subscription', subscriptions[0]]))
    rows = api.list_value(response.get('data'))
    total = response.get('totalRecords')
    if type(total) is not int or total < 0 or len(rows) > top:
        raise api.AzureError('invalid_response', 'Invalid Azure Resource Graph page.')
    for row in rows:
        identifier = row.get('id')
        if identifier and scope_of(api.resource_id(identifier)) not in subscriptions:
            raise api.AzureError('invalid_response', 'Resource Graph returned a resource outside the requested subscriptions.')
    return rows, total, response.get('$skipToken')


def graph_all(api, subscriptions, query):
    offset, token, seen = 0, None, set()
    while True:
        rows, total, next_token = graph(api, subscriptions, query, 1000, offset, token)
        yield from rows
        offset += len(rows)
        if offset >= total:
            return
        if not rows or next_token and next_token in seen:
            raise api.AzureError('invalid_response', 'Incomplete resource discovery response.')
        if next_token:
            seen.add(next_token)
        token = next_token


def selection(query, filters):
    if filters['filter']:
        query += ' | where displayName contains ' + json.dumps(filters['filter'])
    for key, column in ([('serverIds', 'parentId'), ('locations', 'location'), ('tiers', 'serviceTier'), ('computeModels', 'compute')]
                        + (SQL_FILTER_COLUMNS if filters['engine'] == 'sql' else [])):
        if filters[key]:
            query += ' | where ' + column + ' in~ (' + ','.join(json.dumps(v) for v in filters[key]) + ')'
    return query


PROJECT = (' | project id,name=displayName,serverId=parentId,serverName=parentName,location,tier=serviceTier,'
           'computeModel=compute,status=resourceState,elasticPool=tostring(properties.elasticPoolId)')


def normalized_graph(api, row, engine):
    identifier = validate_resource(api, row.get('id'), engine)
    return {'id': identifier, 'name': api.clean(row.get('name')), 'serverId': row.get('serverId') or identifier,
            'serverName': api.clean(row.get('serverName')), 'engine': engine,
            'location': api.clean(row.get('location')), 'tier': api.clean(row.get('tier')),
            'computeModel': api.clean(row.get('computeModel')), 'status': api.clean(row.get('status') or 'Unknown'),
            'elasticPool': row.get('elasticPool') or '', 'publicNetworkAccess': 'Unknown', 'metrics': {}, 'liveError': '',
            **{key: row.get(key) or ('Unknown' if key not in ('maintenanceConfigurationId','earliestRestoreDate') else '')
               for key in ('backupRedundancy','restoreHistory','maintenanceWindow','zoneRedundancy','readScale','maintenanceConfigurationId','earliestRestoreDate')}}


def catalog(api, payload):
    filters = views.filters(api, payload.get('filters', {}))
    subscriptions = filters['subscriptionIds']
    page = payload.get('page', 0)
    if type(page) is not int or not 0 <= page <= 21474836:
        raise api.AzureError('invalid_input', 'Invalid page number.')
    if not subscriptions:
        return {'rows': [], 'totalCount': 0, 'page': 0, 'facets': {}, 'warnings': []}
    engine = filters['engine']
    query = selection(base(engine) + (SQL_OPERATIONAL_QUERY if engine == 'sql' else ''), filters)
    project = PROJECT + (',backupRedundancy,restoreHistory,maintenanceWindow,zoneRedundancy,readScale,maintenanceConfigurationId=maintenanceId,earliestRestoreDate=tostring(restoreDate)' if engine == 'sql' else '')
    facets = {}
    if payload.get('facets', True):
        sets = {key: {} for key in ('servers', 'locations', 'tiers', 'computeModels')}
        facet_query = base(engine) + ' | summarize by parentId,parentName,location,serviceTier,compute | order by parentId asc,location asc,serviceTier asc,compute asc'
        if engine == 'sql':
            # Discover every accessible SQL server, including servers without databases.
            # Tiers/compute are the full SQL taxonomy; regions come from provider metadata.
            facet_query = "Resources | where type =~ 'microsoft.sql/servers' | project id,name | order by id asc"
            for row in graph_all(api, subscriptions, facet_query):
                identifier = api.resource_id(row.get('id'))
                sets['servers'][identifier] = {'id': identifier, 'name': api.clean(row.get('name'))}
        else:
            for row in graph_all(api, subscriptions, facet_query):
                for key, identifier, label in [('servers', row.get('parentId'), row.get('parentName')),
                                                ('locations', row.get('location'), row.get('location')),
                                                ('tiers', row.get('serviceTier'), row.get('serviceTier')),
                                                ('computeModels', row.get('compute'), row.get('compute'))]:
                    if identifier:
                        sets[key][str(identifier)] = {'id': str(identifier), 'name': api.clean(label)}
        facets = {key: sorted(value.values(), key=lambda r: r['name'].casefold()) for key, value in sets.items()}
    sort_by = filters['sortBy']
    warnings, ranking = [], None
    empty_billing = {"costs": {}, "currencies": {}, "warnings": [], "month": ""}
    ranked_ids = payload.get("rankedIds")
    if ranked_ids is not None:
        if sort_by not in ("costDesc", "costAsc") or not isinstance(ranked_ids, list) or len(ranked_ids) > 25:
            raise api.AzureError("invalid_input", "Invalid ranked page.")
        for identifier in ranked_ids:
            validate_resource(api, identifier, engine)
            if scope_of(identifier) not in subscriptions:
                raise api.AzureError("invalid_input", "Ranked resource is outside the selected subscriptions.")
        total = payload.get("rankedTotal")
        if type(total) is not int or not 0 <= total <= MAX_COST_MATCHES:
            raise api.AzureError("invalid_input", "Invalid ranked resource count.")
        raw = graph(api, subscriptions, query + " | where id in~ (" + ",".join(json.dumps(i) for i in ranked_ids) + ")" + project, 25)[0] if ranked_ids else []
        by_id = {r["id"].lower(): normalized_graph(api, r, engine) for r in raw}
        rows = [by_id[i.lower()] for i in ranked_ids if i.lower() in by_id]
        billing = empty_billing
    elif sort_by in ('costDesc', 'costAsc'):
        # Cost Management cannot join Resource Graph. Read only a lightweight matching ID index;
        # the full ARM resource and live metrics are still read for just the selected 25 rows.
        if payload.get('skipCosts'):
            raise api.AzureError('billing_cooldown', 'Cost sorting is paused by Azure. Choose another sort or retry after the billing cooldown.')
        rows = []
        for raw in graph_all(api, subscriptions, query + project + ' | order by id asc'):
            if len(rows) >= MAX_COST_MATCHES:
                raise api.AzureError('scope_too_large', 'Cost sorting supports up to 100,000 matches. Narrow the filters.')
            rows.append(normalized_graph(api, raw, engine))
        # Narrow matches use ResourceId, broad matches use one service-wide query per subscription.
        # The ranking is returned once and held only in the open panel's memory.
        matched_subs = sorted({scope_of(r['id']) for r in rows})
        billing = costs.fetch(api, matched_subs, engine, [r['id'] for r in rows] if len(rows) <= 100 else None) if rows else empty_billing
        costs.attach(rows, billing)
        denominations = {r['cost']['currency'] for r in rows if r['cost']['amount'] is not None and r['cost']['currency']}
        if len(denominations) > 1:
            raise api.AzureError('currency', 'Choose subscriptions with the same billing currency to sort by cost.')
        rows.sort(key=lambda r: (r['cost']['amount'] is None,
            (r['cost']['amount'] or 0) * (-1 if sort_by == 'costDesc' else 1), r['name'].casefold(), r['id'].lower()))
        total = len(rows)
        ranking = [{"id": r["id"], "cost": r["cost"]} for r in rows]
        rows = rows[page * 25:page * 25 + 25]
        warnings = billing['warnings']
    else:
        order = {'nameAsc': 'displayName asc', 'nameDesc': 'displayName desc', 'location': 'location asc,displayName asc',
                 'tier': 'serviceTier asc,displayName asc', 'state': 'resourceState asc,displayName asc'}[sort_by]
        raw, total, _ = graph(api, subscriptions, query + ' | order by ' + order + ',id asc' + project, 25, page * 25)
        rows = [normalized_graph(api, r, engine) for r in raw]
        billing = costs.fetch(api, subscriptions, engine, [r['id'] for r in rows]) if rows and not payload.get('skipCosts') else empty_billing
        costs.attach(rows, billing)
        warnings = billing['warnings']
    if facets:
        for key, column in [('locations', 'location'), ('tiers', 'tier'), ('computeModels', 'computeModel')]:
            known = {r['id'].lower() for r in facets[key]}
            for row in rows:
                value = row.get(column)
                if value and value.lower() not in known:
                    facets[key].append({'id': value, 'name': value})
                    known.add(value.lower())
    return {'rows': rows, 'totalCount': total, 'page': page, 'facets': facets, 'warnings': warnings, 'rateLimited': billing.get('rateLimited', False), 'retryAfterSec': billing.get('retryAfterSec', 0),
            'throttleScope': 'billing', 'costRanking': ranking}


def normalize_arm(api, raw, engine):
    identifier = validate_resource(api, raw.get('id'), engine)
    p, sku = api.object_value(raw.get('properties', {})), raw.get('sku') or {}
    name = identifier.split('/')[-1]
    server_id = identifier[:identifier.lower().rindex('/databases/')] if engine == 'sql' else identifier
    caps = [str(c.get('name', '')) for c in p.get('capabilities') or []]
    tier = sku.get('tier', '')
    if engine == 'cosmos':
        tier = 'MongoDB' if raw.get('kind') == 'MongoDB' else next((n for n in ('Cassandra', 'Gremlin', 'Table') if 'Enable' + n in caps), 'NoSQL')
    serverless = 'EnableServerless' in caps or p.get('computeModel') == 'Serverless' or '_S_' in str(sku.get('name', '')) or (api.finite(p.get('minCapacity')) or 0) > 0
    network = p.get('network') or {}
    return {'id': identifier, 'name': name, 'engine': engine, 'serverId': server_id,
            'serverName': server_id.split('/')[-1], 'location': api.clean(raw.get('location')),
            'tier': api.clean(tier), 'computeModel': 'Serverless' if serverless else 'Provisioned',
            'status': api.clean(p.get('status') or p.get('state') or p.get('provisioningState') or 'Unknown'),
            'publicNetworkAccess': api.network_access(p.get('publicNetworkAccess') or network.get('publicNetworkAccess')),
            'elasticPool': p.get('elasticPoolId') or '', 'metrics': {}, 'liveError': '',
            'sku': api.clean(sku.get('name')), 'capacity': api.finite(sku.get('capacity')),
            'maxSizeBytes': api.finite(p.get('maxSizeBytes')), 'fqdn': p.get('fullyQualifiedDomainName') or p.get('documentEndpoint') or '',
            **(operational_fields(p) if engine == 'sql' else {})}


def metric_values(api, value):
    result = {}
    for metric in api.list_value(value or []):
        name = (metric.get('name') or {}).get('value')
        points = []
        for series in metric.get('timeseries') or []:
            for point in series.get('data') or []:
                value = api.finite(point.get('average', point.get('maximum')))
                if value is not None:
                    points.append((str(point.get('timeStamp', '')), value))
        if points and name:
            timestamp, value = max(points)
            result[name] = {'value': value, 'timestamp': timestamp}
    return result


def batch_metrics(api, rows, engine):
    groups = defaultdict(list)
    for row in rows:
        if row.get('liveError') or engine == 'sql' and row['status'] == 'Paused':
            continue
        location = row['location'].replace(' ', '').lower()
        if re.fullmatch('[a-z0-9]+', location):
            groups[(scope_of(row['id']), location)].append(row)
    now = dt.datetime.now(dt.timezone.utc)
    throttled = None
    for (sub, region), group in groups.items():
        params = {'api-version': '2023-10-01', 'starttime': (now-dt.timedelta(minutes=15)).isoformat(),
                  'endtime': now.isoformat(), 'interval': 'PT1M', 'metricnamespace': TYPES[engine],
                  'metricnames': ','.join(METRICS[engine]), 'aggregation': 'Maximum' if engine == 'cosmos' else 'Average'}
        try:
            if throttled is not None:
                raise throttled
            response = api.object_value(api.run_az(['rest', '--method', 'post', '--url',
                f'https://{region}.metrics.monitor.azure.com/subscriptions/{sub}/metrics:getBatch?' + urlencode(params),
                '--resource', 'https://metrics.monitor.azure.com/', '--body', json.dumps({'resourceids': [r['id'] for r in group]}), '--subscription', sub]))
            results = {str(r.get('resourceid', '')).lower(): r for r in api.list_value(response.get('values', []))}
            for row in group:
                result = results.get(row['id'].lower())
                if result is None:
                    row['liveError'] = 'Metrics unavailable for this resource.'
                else:
                    row['metrics'] = metric_values(api, result.get('value', []))
                    errors = [m for m in result.get('value', []) if m.get('errorCode') not in (None, '', 'Success')]
                    if errors:
                        row['liveError'] = 'Some metrics are unavailable.'
        except api.AzureError as error:
            if error.code == 'rate_limit':
                throttled = error
            for row in group:
                row['liveError'] = 'Metrics unavailable. ' + str(error)
                row['errorCode'] = error.code
                row['throttleScope'] = 'metrics'
                row['retryAfterSec'] = error.retry_after


def live(api, payload):
    engine = payload.get('engine', 'sql')
    identifiers = payload.get('ids')
    if engine not in TYPES or not isinstance(identifiers, list) or not 0 <= len(identifiers) <= 25:
        raise api.AzureError('invalid_input', 'Live monitoring is limited to the current 25 resources.')
    for identifier in identifiers:
        validate_resource(api, identifier, engine)
    stopped = threading.Event()
    throttle_errors = []
    def guard():
        if stopped.is_set():
            raise throttle_errors[0]
    def note(error):
        if error.code == 'rate_limit':
            throttle_errors.append(error)
            stopped.set()
    def read(identifier):
        try:
            guard()
            row = normalize_arm(api, rest(api, identifier, engine), engine)
            row['liveAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            if engine == 'sql' and row.get('elasticPool'):
                for key in ('maintenanceWindow','maintenanceConfigurationId','zoneRedundancy'):
                    row.pop(key, None)
            return row
        except api.AzureError as error:
            note(error)
            return {'id': identifier, 'liveError': str(error), 'errorCode': error.code, 'throttleScope': 'arm', 'retryAfterSec': error.retry_after, 'metrics': {}, 'liveAt': ''}
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(read, identifiers))
        if engine == 'sql' and not any(r.get('errorCode') == 'rate_limit' for r in rows):
            parents = {r['serverId'] for r in rows if not r.get('liveError')}
            def read_parent(identifier):
                try:
                    guard()
                    response = api.object_value(api.run_az(['rest', '--method', 'get', '--url', identifier + '?api-version=2023-08-01', '--subscription', scope_of(identifier)]))
                    return identifier.lower(), api.network_access((response.get('properties') or {}).get('publicNetworkAccess'))
                except api.AzureError as error:
                    note(error)
                    return identifier.lower(), error
            networks = dict(pool.map(read_parent, parents))
            for row in rows:
                if row.get('serverId'):
                    network = networks.get(row['serverId'].lower(), 'Unknown')
                    if isinstance(network, api.AzureError):
                        row['publicNetworkAccess'] = 'Unknown'
                        row['liveError'] = 'Public access unavailable. ' + str(network)
                        row['errorCode'] = network.code
                        row['throttleScope'] = 'arm'
                        row['retryAfterSec'] = network.retry_after
                    else:
                        row['publicNetworkAccess'] = network
    if not payload.get('skipMetrics'):
        batch_metrics(api, rows, engine)
    throttles = [{'scope': scope, 'retryAfterSec': max(r.get('retryAfterSec', 0) for r in rows if r.get('throttleScope') == scope and r.get('errorCode') == 'rate_limit')}
                 for scope in ('arm', 'metrics') if any(r.get('throttleScope') == scope and r.get('errorCode') == 'rate_limit' for r in rows)]
    return {'rows': rows, 'throttles': throttles, 'authenticationRequired': any(r.get('errorCode') == 'authentication' for r in rows),
            'rateLimited': any(r.get('errorCode') == 'rate_limit' for r in rows),
            'retryAfterSec': max((r.get('retryAfterSec', 0) for r in rows), default=0)}


def pretty_window(window):
    if not window or str(window.get('customWindow', '')).lower() not in ('enabled', 'true'):
        return 'System managed'
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    day = window.get('dayOfWeek')
    label = days[day] if type(day) is int and 0 <= day < 7 else str(day or '')
    return f"{label} {int(window.get('startHour') or 0):02d}:{int(window.get('startMinute') or 0):02d} UTC"


def detail(api, payload):
    engine, identifier = payload.get('engine'), payload.get('id')
    if engine not in TYPES:
        raise api.AzureError('invalid_input', 'Unknown database service.')
    raw = rest(api, identifier, engine)
    row, p, warnings = normalize_arm(api, raw, engine), raw.get('properties') or {}, []
    sections = []
    def section(title, values):
        sections.append({'title': title, 'rows': [{'name': key, 'value': str(value)} for key, value in values if value is not None and value != '']})
    if engine == 'sql':
        if row.get('elasticPool'):
            pool_id = row['elasticPool']
            if not isinstance(pool_id, str) or not re.fullmatch(re.escape(row['serverId']) + r'/elasticPools/[^/]+', pool_id, re.I):
                raise api.AzureError('invalid_response', 'Invalid elastic pool resource ID.')
            try:
                pool = api.object_value(api.run_az(['rest', '--method', 'get', '--url', pool_id + '?api-version=2023-08-01',
                                                   '--subscription', scope_of(identifier)])).get('properties') or {}
            except api.AzureError as error:
                if error.code == 'rate_limit':
                    raise
                warnings.append('Pool maintenance and availability: ' + str(error))
                pool = {}
            p = dict(p, maintenanceConfigurationId=pool.get('maintenanceConfigurationId'), zoneRedundant=pool.get('zoneRedundant'))
        operational = operational_fields(p)
        retention, ltr, groups = {}, {}, []
        for suffix, label in [('/backupShortTermRetentionPolicies/default', 'Short-term retention'), ('/backupLongTermRetentionPolicies/default', 'Long-term retention')]:
            try:
                value = rest(api, identifier, engine, suffix).get('properties') or {}
                if suffix.startswith('/backupShort'):
                    retention = value
                else:
                    ltr = value
            except api.AzureError as error:
                if error.code == 'rate_limit':
                    raise
                warnings.append(label + ': ' + str(error))
        parent = row['serverId']
        try:
            path = parent + '/failoverGroups'
            url, seen = path + '?api-version=2023-08-01', set()
            while url:
                if url in seen or len(seen) >= 1000:
                    raise api.AzureError('invalid_response', 'Incomplete failover group pagination.')
                seen.add(url)
                response = api.object_value(api.run_az(['rest', '--method', 'get', '--url', url, '--subscription', scope_of(identifier)]))
                for group in api.list_value(response.get('value')):
                    gp = group.get('properties') or {}
                    if identifier.lower() in [str(i).lower() for i in gp.get('databases') or []]:
                        groups.append(api.clean(group.get('name')) + ' · ' + str(gp.get('replicationRole') or '') + ' · ' + str((gp.get('readWriteEndpoint') or {}).get('failoverPolicy') or ''))
                continuation = response.get('nextLink')
                if not continuation:
                    break
                parsed = urlsplit(continuation)
                if parsed.scheme != 'https' or parsed.hostname not in ('management.azure.com', 'management.usgovcloudapi.net', 'management.chinacloudapi.cn') or parsed.path.lower() != path.lower() or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment or not parsed.query:
                    raise api.AzureError('invalid_response', 'Unexpected failover continuation URL.')
                url = parsed.path + '?' + parsed.query
        except api.AzureError as error:
            if error.code == 'rate_limit':
                raise
            warnings.append('Failover groups: ' + str(error))
        section('Backup & restore', [('Earliest restore', p.get('earliestRestoreDate')), ('PITR retention (days)', retention.get('retentionDays')),
            ('Backup redundancy', p.get('currentBackupStorageRedundancy')), ('Weekly LTR', ltr.get('weeklyRetention')),
            ('Monthly LTR', ltr.get('monthlyRetention')), ('Yearly LTR', ltr.get('yearlyRetention'))])
        section('Availability', [('Zone redundancy', operational['zoneRedundancy']), ('Read scale-out', p.get('readScale')), ('Failover groups', 'Unavailable' if any('Failover groups:' in w for w in warnings) else ('\n'.join(groups) or 'None'))])
        section('Maintenance', [('Window', {'SystemDefault':'System default','Weekday':'Weekday · Mon–Thu','Weekend':'Weekend · Fri–Sun','Other':'Other configured window','Unknown':'Not reported'}[operational['maintenanceWindow']]),
            ('Configuration', (p.get('maintenanceConfigurationId') or '').split('/')[-1]), ('Settings from', 'Elastic pool' if row.get('elasticPool') else 'Database')])
    elif engine == 'cosmos':
        backup = p.get('backupPolicy') or {}
        periodic, continuous = backup.get('periodicModeProperties') or {}, backup.get('continuousModeProperties') or {}
        section('Backup & restore', [('Backup mode', backup.get('type')), ('Continuous retention', continuous.get('tier')),
            ('Interval (minutes)', periodic.get('backupIntervalInMinutes')), ('Retention (hours)', periodic.get('backupRetentionIntervalInHours')),
            ('Storage redundancy', periodic.get('backupStorageRedundancy'))])
        regions = [str(r.get('locationName', '')) + ' (' + str(r.get('failoverPriority', '')) + ')' for r in p.get('failoverPolicies') or []]
        section('Availability', [('Automatic failover', p.get('enableAutomaticFailover')), ('Multi-region writes', p.get('enableMultipleWriteLocations')),
            ('Failover priorities', ', '.join(regions)), ('Consistency', (p.get('consistencyPolicy') or {}).get('defaultConsistencyLevel'))])
    else:
        backup, ha = p.get('backup') or {}, p.get('highAvailability') or {}
        section('Backup & restore', [('Retention (days)', backup.get('backupRetentionDays')), ('Earliest restore', backup.get('earliestRestoreDate')),
            ('Geo-redundant backup', backup.get('geoRedundantBackup'))])
        section('Availability', [('High availability', ha.get('mode')), ('HA state', ha.get('state')),
            ('Availability zone', p.get('availabilityZone')), ('Standby zone', ha.get('standbyAvailabilityZone')), ('PostgreSQL version', p.get('version'))])
        section('Maintenance', [('Window', pretty_window(p.get('maintenanceWindow')))])
    return {'id': identifier, 'sections': sections, 'warnings': warnings}


def execute(api, operation, payload):
    return {'session': session, 'catalog': catalog, 'live': live, 'detail': detail}[operation](api, payload) if operation != 'session' else session(api)
