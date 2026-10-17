"""Fresh month-to-date resource costs. No files, tokens or persistent cache."""
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
from urllib.parse import urlsplit

TYPES = {"sql": "microsoft.sql/servers/databases", "cosmos": "microsoft.documentdb/databaseaccounts",
         "postgres": "microsoft.dbforpostgresql/flexibleservers"}


def fetch(api, subscriptions, engine, identifiers=None):
    result, currencies, warnings = {}, {}, []
    retry_after = 0
    rate_limited = False
    month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    for subscription in subscriptions:
        sub = api.subscription_id(subscription)
        scoped = [i for i in identifiers or [] if i.split('/')[2].lower() == sub]
        if identifiers is not None and not scoped:
            continue
        dimension = {"name": "ResourceId" if identifiers is not None else "ResourceType", "operator": "In",
                     "values": scoped if identifiers is not None else [TYPES[engine]]}
        body = {"type": "ActualCost", "timeframe": "MonthToDate", "dataset": {
            "granularity": "None", "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ResourceId"}], "filter": {"dimensions": dimension}}}
        path = f"/subscriptions/{sub}/providers/Microsoft.CostManagement/query"
        url, seen, totals, denominations = path + "?api-version=2025-03-01", set(), {}, set()
        try:
            while url:
                if url in seen or len(seen) > 10000:
                    raise api.AzureError("invalid_response", "Invalid cost pagination.")
                seen.add(url)
                properties = api.object_value(api.object_value(api.run_az([
                    "rest", "--method", "post", "--url", url, "--body", json.dumps(body), "--subscription", sub])).get("properties"))
                columns = [str(column.get("name", "")).casefold() for column in api.list_value(properties.get("columns"))]
                rows = properties.get("rows")
                try:
                    amount_index = next(columns.index(n) for n in ("cost", "pretaxcost", "costinbillingcurrency") if n in columns)
                    id_index, currency_index = columns.index("resourceid"), columns.index("currency")
                except (StopIteration, ValueError):
                    raise api.AzureError("invalid_response", "Azure omitted billing columns.") from None
                if not isinstance(rows, list):
                    raise api.AzureError("invalid_response", "Invalid billing rows.")
                for row in rows:
                    if not isinstance(row, list) or len(row) != len(columns):
                        raise api.AzureError("invalid_response", "Invalid billing row.")
                    identifier = api.resource_id(row[id_index]).lower()
                    if identifier.split('/')[2] != sub or (identifiers is not None and identifier not in [i.lower() for i in scoped]):
                        raise api.AzureError("invalid_response", "Unexpected billing resource scope.")
                    currency = str(row[currency_index] or '').upper()
                    try:
                        value = Decimal(str(row[amount_index]))
                        if isinstance(row[amount_index], bool) or not value.is_finite() or abs(value) >= Decimal('1e15'):
                            raise InvalidOperation
                    except (InvalidOperation, ValueError):
                        raise api.AzureError("invalid_response", "Invalid billing amount.") from None
                    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                        raise api.AzureError("invalid_response", "Invalid billing currency.")
                    denominations.add(currency)
                    totals[identifier] = totals.get(identifier, Decimal(0)) + value
                next_link = properties.get("nextLink")
                if not next_link:
                    break
                parsed = urlsplit(next_link)
                if parsed.scheme != 'https' or parsed.hostname not in ('management.azure.com', 'management.usgovcloudapi.net', 'management.chinacloudapi.cn') or parsed.path.lower() != path.lower() or parsed.username or parsed.fragment:
                    raise api.AzureError("invalid_response", "Unexpected billing continuation URL.")
                url = parsed.path + '?' + parsed.query
            if len(denominations) > 1 or month != dt.datetime.now(dt.timezone.utc).strftime('%Y-%m'):
                raise api.AzureError("invalid_response", "Billing currency or month changed during the request.")
            currency = next(iter(denominations), '')
            currencies[sub] = currency
            timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
            for identifier, amount in totals.items():
                result[identifier] = {"amount": float(amount), "currency": currency, "month": month, "asOf": timestamp}
        except api.AzureError as error:
            warnings.append("Month-to-date costs: " + str(error))
            rate_limited = rate_limited or error.code == "rate_limit"
            retry_after = max(retry_after, error.retry_after)
            if rate_limited:
                break
    return {"costs": result, "currencies": currencies, "warnings": list(dict.fromkeys(warnings)), "month": month, "rateLimited": rate_limited, "retryAfterSec": retry_after}


def attach(rows, billing):
    for row in rows:
        sub = row['id'].split('/')[2].lower()
        value = billing['costs'].get(row['id'].lower())
        if value is None:
            value = {"amount": 0 if sub in billing['currencies'] and not row.get('elasticPool') else None,
                     "currency": billing['currencies'].get(sub, ''), "month": billing['month'], "asOf": ''}
        row['cost'] = dict(value, directOnly=bool(row.get('elasticPool')))
