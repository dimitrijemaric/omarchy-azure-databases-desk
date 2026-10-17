#!/usr/bin/env python3
"""Read-only Azure CLI adapter. Standard library only; emits one JSON envelope."""

import argparse
import datetime as dt
import json
import math
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import uuid
import sqlite3
import threading

MAX_OUTPUT = 4 * 1024 * 1024
TIMEOUT = 20
SERVER_ID = re.compile(
    r"^/subscriptions/([0-9a-f-]{36})/resourceGroups/([^/]+)/providers/"
    r"Microsoft\.Sql/servers/([a-z0-9-]+)$", re.I
)
DATABASE_ID = re.compile(SERVER_ID.pattern[:-1] + r"/databases/([^/]+)$", re.I)
METRICS = ("cpu_percent", "physical_data_read_percent", "log_write_percent")
GRAPH_URL = "/providers/Microsoft.ResourceGraph/resources?api-version=2024-04-01"
_child = None
_children = set()
_children_lock = threading.Lock()
_cancel_signal = 0
_azure_config_dir = None
_identity_context = None
_session_subscriptions = None


class AzureError(Exception):
    def __init__(self, code, message, retry_after=0):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


def clean(value, limit=300):
    return " ".join(str(value or "").split())[:limit]


def subscription_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise AzureError("invalid_input", "A valid subscription UUID is required.") from None


RESOURCE_ID = re.compile(
    r"^/subscriptions/([0-9a-f-]{36})/resourceGroups/[^/]+/providers/"
    r"(?:Microsoft\.Sql/servers/[^/]+(?:/databases/[^/]+)?|Microsoft\.DocumentDB/databaseAccounts/[^/]+|Microsoft\.DBforPostgreSQL/flexibleServers/[^/]+)$", re.I)


def resource_id(value, database=False):
    pattern = DATABASE_ID if database else RESOURCE_ID
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value) or not pattern.fullmatch(value):
        raise AzureError("invalid_input", "Expected a supported Azure database resource ID.")
    subscription_id(pattern.fullmatch(value)[1])
    return value


def stop_child():
    with _children_lock:
        children = list(_children)
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in children:
        child.wait()


def interrupted(signum, _frame):
    # Signal handlers must never acquire locks or wait for children.
    # Each active run_az loop observes this flag and cleans up in its finally block.
    global _cancel_signal
    _cancel_signal = signum


def run_az(arguments):
    """Run fixed argv, cap both streams, and kill descendants on timeout/cancel."""
    global _child
    child = None
    if _cancel_signal:
        raise AzureError("cancelled", "Request canceled.")
    executable = shutil.which("az")
    if not executable:
        raise AzureError("missing_cli", "Azure CLI is missing. Install Azure CLI, run az login in a terminal, then Refresh.")
    env = dict(os.environ, AZURE_CORE_COLLECT_TELEMETRY="no",
               AZURE_CORE_CHECK_VERSION="false", AZURE_EXTENSION_USE_DYNAMIC_INSTALL="no")
    if _azure_config_dir is not None:
        env["AZURE_CONFIG_DIR"] = _azure_config_dir
    command = [executable, *arguments, "--only-show-errors", "--output", "json"]
    buffers = {"out": bytearray(), "err": bytearray()}
    try:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, start_new_session=True)
        with _children_lock:
            _children.add(child)
        if _cancel_signal:
            raise AzureError("cancelled", "Request canceled.")
        _child = child
        deadline = time.monotonic() + TIMEOUT
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ, "out")
            selector.register(child.stderr, selectors.EVENT_READ, "err")
            while selector.get_map():
                if _cancel_signal:
                    raise AzureError("cancelled", "Request canceled.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AzureError("timeout", "Azure did not respond within 20 seconds. Check your network and retry.")
                for key, _ in selector.select(min(remaining, 0.25)):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    target = buffers[key.data]
                    target.extend(chunk)
                    if len(target) > MAX_OUTPUT:
                        raise AzureError("response_too_large", "Azure CLI returned more than 4 MiB. Narrow the resource scope.")
            while True:
                if _cancel_signal:
                    raise AzureError("cancelled", "Request canceled.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AzureError("timeout", "Azure CLI timed out. Retry the request.")
                try:
                    code = child.wait(timeout=min(0.25, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        if code:
            # Do not echo CLI stderr: it can contain account identifiers or tokens.
            reason = buffers["err"].decode("utf-8", "replace").lower()
            if any(word in reason for word in ("az login", "aadsts", "expired", "invalid_grant", "interaction_required")):
                raise AzureError("authentication", "Azure sign-in is required or expired. Run az login in a terminal, then Refresh.")
            if any(word in reason for word in ("authorizationfailed", "forbidden", "does not have authorization")):
                raise AzureError("permission", "Your Azure identity cannot read this resource. Check the subscription and Azure RBAC access.")
            if any(word in reason for word in ("resourcenotfound", "notfound", "could not be found")):
                raise AzureError("not_found", "The Azure SQL resource was not found. Refresh the resource list.")
            if re.search(r"\b429\b|\b529\b|toomanyrequests|too many requests|rate.?limit|throttl", reason):
                retry = re.search(r"retry[- ]after[^0-9]*(\d{1,7})", reason)
                raise AzureError("rate_limit", "Azure requests are rate limited. Wait before retrying.",
                                 min(86400, int(retry[1])) if retry else 900)
            raise AzureError("azure_error", "Azure CLI could not complete this request. Check az login, connectivity, and resource permissions.")
        try:
            return json.loads(buffers["out"])
        except (ValueError, UnicodeDecodeError):
            raise AzureError("invalid_response", "Azure CLI returned invalid JSON.") from None
    except OSError:
        raise AzureError("cli_failed", "Azure CLI could not be started.") from None
    finally:
        if child is not None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            child.stdout.close()
            child.stderr.close()
            with _children_lock:
                _children.discard(child)
        _child = None


def object_value(value):
    if not isinstance(value, dict):
        raise AzureError("invalid_response", "Expected an Azure resource object.")
    return value


def list_value(value):
    if not isinstance(value, list):
        raise AzureError("invalid_response", "Expected an Azure resource list.")
    if any(not isinstance(row, dict) for row in value):
        raise AzureError("invalid_response", "Azure returned an invalid resource list.")
    return value


def finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def database_summary(row):
    row = object_value(row)
    sku = row.get("sku") or {}
    if not isinstance(sku, dict):
        sku = {}
    identifier = resource_id(row.get("id"), database=True)
    return {
        "id": identifier,
        "serverId": identifier[:identifier.lower().rindex("/databases/")],
        "serverName": DATABASE_ID.fullmatch(identifier)[3],
        "name": clean(row.get("name")), "status": clean(row.get("status") or "Unknown"),
        "location": clean(row.get("location")), "tier": clean(sku.get("tier")),
        "sku": clean(sku.get("name")), "capacity": finite(sku.get("capacity")),
        "computeModel": clean(row.get("computeModel") or
                              ("Serverless" if row.get("autoPauseDelay") is not None else "Provisioned")),
        "maxSizeBytes": finite(row.get("maxSizeBytes")),
        "autoPauseDelay": row.get("autoPauseDelay"),
        "elasticPool": clean((row.get("elasticPoolId") or "").split("/")[-1]),
    }


def metric_values(response):
    values = {name: {"value": None, "timestamp": ""} for name in METRICS}
    for row in list_value(object_value(response).get("value", [])):
        name = (row.get("name") or {}).get("value")
        if name not in values:
            continue
        points = []
        for series in row.get("timeseries") or []:
            for point in series.get("data") or []:
                value = finite(point.get("average"))
                if value is not None:
                    points.append((clean(point.get("timeStamp"), 50), value))
        if points:
            timestamp, value = max(points)
            values[name] = {"value": value, "timestamp": timestamp}
    return values


def subscriptions():
    rows = list_value(run_az(["account", "list"]))
    result = [{"id": subscription_id(row.get("id")), "name": clean(row.get("name")),
               "isDefault": row.get("isDefault") is True,
               "cloud": clean(row.get("environmentName") or "AzureCloud")}
              for row in rows if row.get("state") == "Enabled"]
    return sorted(result, key=lambda row: (not row["isDefault"], row["name"].casefold()))


def servers(subscription):
    sub = subscription_id(subscription)
    rows = list_value(run_az(["sql", "server", "list", "--subscription", sub]))
    result = [{"id": resource_id(row.get("id")), "name": clean(row.get("name")),
               "fqdn": clean(row.get("fullyQualifiedDomainName")), "location": clean(row.get("location")),
               "publicNetworkAccess": network_access(row.get("publicNetworkAccess"))}
              for row in rows]
    return sorted(result, key=lambda row: row["name"].casefold())



def network_access(value):
    states = {"enabled": "Enabled", "disabled": "Disabled", "securedbyperimeter": "SecuredByPerimeter"}
    return states.get(str(value or "").lower(), "Unknown")


def status(database):
    database = resource_id(database, database=True)
    match = DATABASE_ID.fullmatch(database)
    scope = ["--subscription", match[1]]
    row = database_summary(run_az(["sql", "db", "show", "--ids", database, *scope]))
    result = {"database": row, "storage": None, "metrics": {}, "warnings": [],
              "network": {"publicNetworkAccess": "Unknown", "source": "server", "checkedAt": ""}}
    try:
        usages = list_value(run_az(["sql", "db", "list-usages", "--name", match[4],
                                   "--resource-group", match[2], "--server", match[3], *scope]))
        for usage in usages:
            if usage.get("name") == "database_size":
                properties = usage.get("properties") or usage
                if str(properties.get("unit", "")).lower() == "bytes":
                    result["storage"] = {"usedBytes": finite(properties.get("currentValue")),
                                         "limitBytes": finite(properties.get("limit"))}
                break
    except AzureError as error:
        result["warnings"].append("Storage unavailable. " + str(error))
    if row["status"] == "Online":
        try:
            response = run_az(["monitor", "metrics", "list", "--resource", database,
                               "--metrics", *METRICS, "--aggregation", "Average",
                               "--interval", "PT1M", "--offset", "15m", *scope])
            result["metrics"] = metric_values(response)
        except AzureError as error:
            result["warnings"].append("Metrics unavailable. " + str(error))
    try:
        server = object_value(run_az(["sql", "server", "show", "--ids", row["serverId"], *scope]))
        result["network"] = {"publicNetworkAccess": network_access(server.get("publicNetworkAccess")),
                             "source": "server", "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat()}
    except AzureError as error:
        result["warnings"].append("Public network access could not be checked. " + str(error))
    return result


def main(argv=None):
    import cloud_resources
    import accounts
    import views
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("operation", choices=["identities", "identity-select", "session", "catalog", "live", "detail", "views", "view-save", "view-delete", "view-default"])
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise AzureError("invalid_input", "Invalid request payload.")
        if args.operation in ("identities", "identity-select"):
            data = ({"accounts": [], "profileId": "cli", "tenantId": "", "directories": []} if args.demo else
                    accounts.listing() if args.operation == "identities" else accounts.select(sys.modules[__name__], payload))
        elif args.operation in ("views", "view-save", "view-delete", "view-default"):
            data = views.execute(sys.modules[__name__], args.operation, payload, args.demo)
        elif args.demo:
            from demo import simulate
            data = simulate(args.operation, payload)
        else:
            accounts.configure(sys.modules[__name__], payload)
            if args.operation != "session":
                accounts.authorize(sys.modules[__name__], args.operation, payload)
            data = cloud_resources.execute(sys.modules[__name__], args.operation, payload)
        envelope = {"schemaVersion": 1, "ok": True, "data": data,
                    "fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat()}
        code = 0
    except AzureError as error:
        envelope = {"schemaVersion": 1, "ok": False, "error": {"code": error.code, "message": str(error), "retryAfterSec": error.retry_after}}
        code = 1
    except (TypeError, ValueError, KeyError, AttributeError):
        envelope = {"schemaVersion": 1, "ok": False,
                    "error": {"code": "invalid_response", "message": "Azure returned an unexpected response. Refresh and retry."}}
        code = 1
    except (OSError, sqlite3.Error):
        envelope = {"schemaVersion": 1, "ok": False,
                    "error": {"code": "local_state", "message": "Could not access saved views. Check local directory permissions and disk space."}}
        code = 1
    if _cancel_signal:
        stop_child()
        return 128 + _cancel_signal
    print(json.dumps(envelope, allow_nan=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
