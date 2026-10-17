"""Saved filter preferences only. Resource data is never persisted."""
import json
import os
from pathlib import Path
import sqlite3
import uuid

ENGINES = ("sql", "cosmos", "postgres")
SQL_FILTER_OPTIONS = {
    "backupRedundancies": ("Local", "Zone", "Geo", "GeoZone", "Unknown"),
    "restoreHistories": ("Under1Day", "Days1To7", "Days7To14", "Days14Plus", "Unknown"),
    "maintenanceWindows": ("SystemDefault", "Weekday", "Weekend", "Other", "Unknown"),
    "zoneRedundancies": ("Enabled", "Disabled", "Unknown"),
    "readScales": ("Enabled", "Disabled", "Unknown"),
}
SORTS = ("nameAsc", "nameDesc", "costDesc", "costAsc", "location", "tier", "state")


def filters(api, value):
    if not isinstance(value, dict):
        raise api.AzureError("invalid_input", "Invalid database filters.")
    result = {"engine": value.get("engine", "sql"), "sortBy": value.get("sortBy", "nameAsc"),
              "filter": str(value.get("filter", "")).strip()}
    if result["engine"] not in ENGINES or result["sortBy"] not in SORTS or len(result["filter"]) > 256:
        raise api.AzureError("invalid_input", "Invalid database filters or sorting.")
    for key in ("subscriptionIds", "serverIds", "locations", "tiers", "computeModels", *SQL_FILTER_OPTIONS):
        values = value.get(key, [])
        if key == "subscriptionIds" and not values and value.get("subscriptionId"):
            values = [value["subscriptionId"]]
        if key == "serverIds" and not values and value.get("serverId"):
            values = [value["serverId"]]
        if not isinstance(values, list) or len(values) > 500 or any(not isinstance(v, str) or not v or len(v) > 2048 for v in values):
            raise api.AzureError("invalid_input", "Invalid multi-select filter values.")
        if key == "subscriptionIds":
            values = [api.subscription_id(v) for v in values]
        if key == "serverIds":
            values = [api.resource_id(v) for v in values]
        if key in SQL_FILTER_OPTIONS and any(v not in SQL_FILTER_OPTIONS[key] for v in values):
            raise api.AzureError("invalid_input", "Invalid operational filter option.")
        result[key] = list(dict.fromkeys(values))
    if len(json.dumps(result)) > 48000:
        raise api.AzureError("invalid_input", "Too many selected filter values. Narrow the selection.")
    return result


def execute(api, operation, payload, demo=False):
    folder = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "azure-sql-desk"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / ("demo-views.sqlite3" if demo else "views.sqlite3")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(descriptor)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=10)
    try:
        with db:
            db.execute("CREATE TABLE IF NOT EXISTS views (id TEXT PRIMARY KEY,name TEXT,name_key TEXT UNIQUE,payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY,value TEXT)")
            if operation == "view-save":
                name = str(payload.get("name", "")).strip()
                if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
                    raise api.AzureError("invalid_input", "Enter a view name of 1–80 characters.")
                row = filters(api, payload.get("filters", {}))
                if "makeDefault" in payload and not isinstance(payload["makeDefault"], bool):
                    raise api.AzureError("invalid_input", "Invalid default view preference.")
                identifier = str(payload.get("id") or "")
                if identifier and not db.execute("SELECT 1 FROM views WHERE id=?", (identifier,)).fetchone():
                    raise api.AzureError("invalid_input", "The view no longer exists. Save it as a new view.")
                old = db.execute("SELECT id FROM views WHERE name_key=?", (name.casefold(),)).fetchone()
                if old and old[0] != identifier:
                    raise api.AzureError("view_exists", "A view with this name exists. Choose another name or select that view to update it.")
                row.update({"id": identifier or str(uuid.uuid4()), "name": name})
                db.execute("INSERT OR REPLACE INTO views VALUES(?,?,?,?)", (row["id"], name, name.casefold(), json.dumps(row)))
                if payload.get("makeDefault") is True:
                    db.execute("INSERT OR REPLACE INTO preferences VALUES('defaultView',?)", (row["id"],))
                elif payload.get("makeDefault") is False:
                    db.execute("DELETE FROM preferences WHERE key='defaultView' AND value=?", (row["id"],))
            elif operation in ("view-delete", "view-default"):
                identifier = str(payload.get("id", ""))
                if identifier and not db.execute("SELECT 1 FROM views WHERE id=?", (identifier,)).fetchone():
                    raise api.AzureError("invalid_input", "The selected view no longer exists.")
                if operation == "view-delete":
                    db.execute("DELETE FROM views WHERE id=?", (identifier,))
                    db.execute("DELETE FROM preferences WHERE key='defaultView' AND value=?", (identifier,))
                else:
                    db.execute("INSERT OR REPLACE INTO preferences VALUES('defaultView',?)", (identifier,))
            rows = []
            for (serialized,) in db.execute("SELECT payload FROM views ORDER BY name_key"):
                raw = json.loads(serialized)
                row = filters(api, raw)
                row.update({"id": raw["id"], "name": raw["name"]})
                rows.append(row)
            default = db.execute("SELECT value FROM preferences WHERE key='defaultView'").fetchone()
            return {"views": rows, "defaultViewId": default[0] if default else ""}
    finally:
        db.close()
