.pragma library

function indexOf(rows, wanted) {
  for (var i = 0; i < rows.length; i++) if (String(rows[i].id).toLowerCase() === String(wanted).toLowerCase()) return i;
  return -1;
}

function pick(rows, wanted) {
  for (var i = 0; i < rows.length; i++) if (String(rows[i].id).toLowerCase() === String(wanted).toLowerCase()) return i;
  return rows.length ? 0 : -1;
}

function bytes(value) {
  if (value === null || value === undefined || !isFinite(Number(value))) return "—";
  var n = Number(value);
  var units = ["B", "KiB", "MiB", "GiB", "TiB"];
  var i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(i ? 1 : 0) + " " + units[i];
}

function percent(metric) {
  return metric && metric.value !== null && metric.value !== undefined
    ? Number(metric.value).toFixed(1) + "%" : "—";
}

function cost(value) {
  if (!value || value.amount === null || value.amount === undefined || !isFinite(Number(value.amount))) return "— MTD";
  return (value.currency ? value.currency + " " : "") + Number(value.amount).toFixed(2) + " MTD";
}

function updatedAt(iso) {
  var date = new Date(iso || "");
  return isNaN(date.getTime()) ? "" : "Updated " + Qt.formatDateTime(date,"d MMM, HH:mm");
}

function costDescription(value) {
  if (!value || value.amount === null || value.amount === undefined) return value && value.directOnly
    ? "Cost unavailable. Shared pool compute is excluded." : "Cost unavailable";
  return "Month-to-date charges" + (value.month ? " · " + value.month : "")
    + (value.asOf ? "\n" + updatedAt(value.asOf) : "")
    + (value.directOnly ? "\nShared pool compute excluded" : "");
}

function portalUrl(cloud, id) {
  var portals = {AzureCloud: "https://portal.azure.com", AzureUSGovernment: "https://portal.azure.us", AzureChinaCloud: "https://portal.azure.cn"};
  if (!portals[cloud] || !/^\/subscriptions\/[0-9a-f-]{36}\/resourceGroups\/[^/]+\/providers\/(?:Microsoft\.Sql\/servers\/[^/]+\/databases\/[^/]+|Microsoft\.DocumentDB\/databaseAccounts\/[^/]+|Microsoft\.DBforPostgreSQL\/flexibleServers\/[^/]+)$/i.test(id || "")) return "";
  return portals[cloud] + "/#resource" + id.split("/").map(encodeURIComponent).join("/") + "/overview";
}

function createDatabaseUrl(cloud) {
  var portals = {AzureCloud: "https://portal.azure.com", AzureUSGovernment: "https://portal.azure.us", AzureChinaCloud: "https://portal.azure.cn"};
  return portals[cloud] ? portals[cloud] + "/#create/Microsoft.SQLDatabase" : "";
}

function metricSummary(row) {
  if (row.status === "Paused") return "";
  var metrics = row.metrics || {};
  if (row.engine === "cosmos") return "RU " + percent(metrics.NormalizedRUConsumption);
  return "CPU " + percent(metrics.cpu_percent) + (row.engine === "postgres" ? " · Memory " + percent(metrics.memory_percent) : " · Data I/O " + percent(metrics.physical_data_read_percent));
}

function age(iso, now) {
  var seconds = Math.max(0, Math.floor((now - Date.parse(iso)) / 1000));
  if (!isFinite(seconds)) return "";
  return seconds < 60 ? "just now" : seconds < 3600 ? Math.floor(seconds / 60) + "m ago" : Math.floor(seconds / 3600) + "h ago";
}
