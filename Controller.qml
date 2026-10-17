import QtQuick
import Quickshell.Io
import "Model.js" as Model

Item {
  id: root
  property var settings: ({})
  property bool panelActive: false
  readonly property bool demoMode: settings.demoMode === true
  readonly property bool busy: activeRequest !== null
  readonly property bool viewsBusy: viewWorker.running
  property bool authenticated: false
  property bool authenticationKnown: false
  property string error: ""
  property string errorCode: ""
  property string viewError: ""
  property string warning: ""
  property bool pageLoading: false
  property var accountRows: []
  property var directoryRows: []
  property string profileId: "cli"
  property string tenantId: ""
  property bool identitySwitching: false
  property var subscriptionRows: []
  property var sqlLocations: []
  property bool filtersPending: false
  property bool facetsPending: false
  property var cooldowns: ({})
  property var throttleCounts: ({})
  readonly property bool refreshThrottled: !!cooldowns.arm
  readonly property string throttleWarning: Object.keys(cooldowns).map(function(scope) {
    return ({billing:"Costs",arm:"Database refresh",metrics:"Metrics",graph:"Resource discovery",discovery:"Region options"})[scope] + " paused by Azure rate limits.";
  }).join(" ")
  // Ephemeral cost ordering only: discarded on close, reopen, filter change or explicit refresh.
  property var costRanking: null
  property string rankingMonth: ""
  property bool viewDirty: false
  signal viewSaved()
  function filterOptions(key) {
    if (key === "subscriptionIds") return withMissingOptions(subscriptionRows, key);
    var operational = {
      backupRedundancies: [{id:"Local",name:"Local (LRS)"},{id:"Zone",name:"Zone (ZRS)"},{id:"Geo",name:"Geo (GRS)"},{id:"GeoZone",name:"Geo-zone (GZRS)"},{id:"Unknown",name:"Unknown"}],
      restoreHistories: [{id:"Under1Day",name:"Under 1 day"},{id:"Days1To7",name:"1–7 days"},{id:"Days7To14",name:"7–14 days"},{id:"Days14Plus",name:"14 days or more"},{id:"Unknown",name:"Not reported"}],
      maintenanceWindows: [{id:"SystemDefault",name:"System default"},{id:"Weekday",name:"Weekday · Mon–Thu"},{id:"Weekend",name:"Weekend · Fri–Sun"},{id:"Other",name:"Other configured window"},{id:"Unknown",name:"Not reported"}],
      zoneRedundancies: [{id:"Enabled",name:"Enabled"},{id:"Disabled",name:"Disabled"},{id:"Unknown",name:"Unknown"}],
      readScales: [{id:"Enabled",name:"Enabled"},{id:"Disabled",name:"Disabled"},{id:"Unknown",name:"Unknown"}]
    };
    if (operational[key]) return operational[key];
    var names = {serverIds: "servers", locations: "locations", tiers: "tiers", computeModels: "computeModels"};
    var rows = (facets[names[key]] || []).slice();
    var defaults = key === "tiers" ? [
      {id:"Basic",name:"Basic"},{id:"Standard",name:"Standard"},{id:"Premium",name:"Premium"},
      {id:"GeneralPurpose",name:"General Purpose (GP)"},{id:"BusinessCritical",name:"Business Critical (BC)"},{id:"Hyperscale",name:"Hyperscale"}
    ] : key === "computeModels" ? [{id:"Provisioned",name:"Provisioned"},{id:"Serverless",name:"Serverless"}] : key === "locations" ? sqlLocations : [];
    defaults.forEach(function(row) { var index = Model.indexOf(rows,row.id); if (index < 0) rows.push(row); else rows[index] = row; });
    return withMissingOptions(rows, key).sort(function(a,b) { return a.name.localeCompare(b.name); });
  }
  function withMissingOptions(rows, key) {
    var result = rows.slice();
    (filters[key] || []).forEach(function(id) {
      if (Model.indexOf(result,id) < 0) result.push({id:id, name:(key === "serverIds" ? id.split('/').pop() : id) + " (Unavailable)"});
    });
    return result;
  }
  property var facets: ({servers: [], locations: [], tiers: [], computeModels: []})
  property var databaseRows: []
  property var savedViews: []
  readonly property var availableViews: savedViews.filter(function(view) { return !view.engine || view.engine === "sql"; })
  readonly property string createDatabaseUrl: {
    var preferred = filters.subscriptionIds.length ? filters.subscriptionIds[0] : "";
    var index = Model.indexOf(subscriptionRows, preferred);
    var subscription = subscriptionRows[index >= 0 ? index : 0];
    return Model.createDatabaseUrl(subscription ? subscription.cloud : "AzureCloud");
  }
  property string defaultViewId: ""
  property string selectedViewId: ""
  property var filters: emptyFilters()
  readonly property string engine: filters.engine
  property int pageIndex: 0
  readonly property int pageSize: 25
  property int totalCount: 0
  readonly property int pageCount: Math.max(1, Math.ceil(totalCount / 25))
  property var database: null
  property var detail: null
  property bool detailsVisible: false
  property int generation: 0
  property var activeRequest: null
  property var pendingRequest: null
  property bool stdoutDone: false
  property bool stderrDone: false
  property bool exited: false
  property int exitCode: 0
  property string responseText: ""
  property bool watchdogExpired: false
  property string viewOperation: ""
  property string viewName: ""
  signal catalogReset()
  signal liveRowsUpdating()
  signal liveRowsUpdated()

  function emptyFilters() {
    return {engine: "sql", subscriptionIds: [], serverIds: [], locations: [], tiers: [], computeModels: [], backupRedundancies: [], restoreHistories: [], maintenanceWindows: [], zoneRedundancies: [], readScales: [], filter: "", sortBy: "nameAsc"};
  }
  function helper() { return decodeURIComponent(Qt.resolvedUrl("scripts/azure_sql.py").toString().replace(/^file:\/\//, "")); }
  function cancelWorker() { if (worker.running) { worker.signal(15); if (!killDeadline.running) killDeadline.start(); } }
  function invalidate() { generation++; pendingRequest = null; cancelWorker(); }
  function clearRanking() { costRanking = null; rankingMonth = ""; }
  function receiveIdentity(data) {
    if (data.accounts) accountRows = data.accounts.map(function(row) {
      var duplicates = data.accounts.filter(function(other) { return other.name === row.name; }).length;
      return duplicates > 1 ? Object.assign({},row,{name:row.name + " · " + row.id.slice(0,8)}) : row;
    });
    if (data.directories) directoryRows = data.directories.map(function(row) {
      return row.name !== row.id ? Object.assign({},row,{name:row.name + " · " + row.id.slice(0,8)}) : row;
    });
    if (data.profileId) profileId = data.profileId;
    if (data.tenantId !== undefined) tenantId = data.tenantId;
  }
  function switchIdentity(accountId, directoryId) {
    if (demoMode || (accountId === profileId && directoryId === tenantId)) return;
    filterDelay.stop(); filtersPending = false; facetsPending = false;
    invalidate(); clearRanking(); clearSelection(); databaseRows = []; subscriptionRows = []; sqlLocations = [];
    facets = {servers:[],locations:[],tiers:[],computeModels:[]};
    var next = Object.assign({}, filters, {subscriptionIds:[],serverIds:[]}); filters = next;
    selectedViewId = ""; viewDirty = false; pageIndex = 0; totalCount = 0;
    error = ""; warning = ""; authenticated = false; authenticationKnown = false;
    pageLoading = true; identitySwitching = true;
    request("identity-select", {profileId:accountId, tenantId:directoryId});
  }
  function switchAccount(index) {
    var row = accountRows[index]; if (row) switchIdentity(row.id,row.tenantId || "");
  }
  function switchDirectory(index) {
    var row = directoryRows[index]; if (row) switchIdentity(profileId,row.id);
  }
  function constrainIdentityFilters() {
    var allowed = subscriptionRows.map(function(row) { return row.id.toLowerCase(); });
    var next = Object.assign({}, filters);
    next.subscriptionIds = next.subscriptionIds.filter(function(id) { return allowed.indexOf(id.toLowerCase()) >= 0; });
    next.serverIds = next.serverIds.filter(function(id) { return allowed.indexOf(id.split('/')[2].toLowerCase()) >= 0; });
    filters = next;
  }
  function livePayload(ids, detailsId) { return {engine: engine, ids: ids, detailsId: detailsId || "", skipMetrics: !!cooldowns.metrics}; }
  function clearSelection() { database = null; detail = null; detailsVisible = false; catalogReset(); }
  function panelOpened() {
    clearRanking(); viewDirty = false;
    filterDelay.stop(); filtersPending = false; facetsPending = false;
    panelActive = true; invalidate(); error = ""; warning = ""; viewError = "";
    pageIndex = 0; databaseRows = []; totalCount = 0; facets = {servers: [],locations: [],tiers: [],computeModels: []}; clearSelection(); pageLoading = true;
    authenticationKnown = false; request("views", {});
  }
  function panelClosed() { clearRanking(); panelActive = false; filterDelay.stop(); filtersPending = false; facetsPending = false; invalidate(); pageLoading = false; }
  function reload() { clearRanking(); loadPage(true); }
  function receiveViews(data) { savedViews = data.views; defaultViewId = data.defaultViewId || ""; }
  function filtersFor(view) {
    var result = emptyFilters();
    for (var key in result) if (view[key] !== undefined) result[key] = view[key];
    return result;
  }
  function applyView(index) {
    var view = availableViews[index]; if (!view) return;
    clearRanking(); filters = filtersFor(view); selectedViewId = view.id; viewDirty = false; pageIndex = 0; loadPage(true);
  }
  function setEngine(value) {
    if (value !== "sql" || value === engine) return;
    var next = Object.assign({}, filters, {engine: value, serverIds: [], tiers: [], computeModels: []});
    filters = next; selectedViewId = ""; pageIndex = 0; facets = {servers: [],locations: [],tiers: [],computeModels: []}; loadPage(true);
  }
  function setFilter(key, value, deferApply) {
    if (!filtersPending) invalidate();
    var next = Object.assign({}, filters); next[key] = value;
    if (key === "subscriptionIds" && value.length) {
      var allowed = value.map(function(id) { return id.toLowerCase(); });
      next.serverIds = next.serverIds.filter(function(id) { return allowed.indexOf(id.split('/')[2].toLowerCase()) >= 0; });
    }
    clearRanking(); filters = next; viewDirty = selectedViewId !== ""; pageIndex = 0;
    filtersPending = true; facetsPending = facetsPending || key === "subscriptionIds";
    filterDelay.stop();
    if (!deferApply) filterDelay.restart();
  }
  function applyPendingFilters() { if (filtersPending) loadPage(facetsPending); }
  function resetFilters() {
    clearRanking(); filters = emptyFilters(); selectedViewId = ""; viewDirty = false; pageIndex = 0; loadPage(true);
  }
  function backOff(seconds, scope) {
    scope = scope || "arm";
    var counts = Object.assign({}, throttleCounts); counts[scope] = Math.min((counts[scope] || 0) + 1, 3); throttleCounts = counts;
    var delay = Math.max(Number(seconds) || 0, Math.min(3600,900 * Math.pow(2,counts[scope]-1)));
    var next = Object.assign({}, cooldowns); next[scope] = Date.now() + delay * 1000; cooldowns = next;
  }
  function expireCooldowns() {
    var next = Object.assign({}, cooldowns), changed = false, armExpired = false;
    for (var scope in next) if (next[scope] <= Date.now()) { delete next[scope]; changed = true; armExpired = armExpired || scope === "arm"; }
    if (changed) { cooldowns = next; if (armExpired) refreshLive(); }
  }
  function goToPage(index) {
    if (index < 0 || index >= pageCount || index === pageIndex) return;
    pageIndex = index; loadPage(false);
  }
  function loadPage(includeFacets) {
    if (!panelActive) return;
    filterDelay.stop(); filtersPending = false; facetsPending = false;
    invalidate(); error = ""; warning = ""; databaseRows = []; clearSelection(); pageLoading = true;
    if (!authenticationKnown) { request("session", {}); return; }
    if (!authenticated) { pageLoading = false; return; }
    var query = Object.assign({}, filters);
    if (!query.subscriptionIds.length) query.subscriptionIds = subscriptionRows.map(function(row) { return row.id; });
    if (cooldowns.graph) { pageLoading = false; error = "Resource discovery is paused by Azure. Retry after the cooldown."; return; }
    var payload = {filters: query, page: pageIndex, facets: includeFacets === true, skipCosts: !!cooldowns.billing};
    var month = new Date().toISOString().slice(0,7);
    if (costRanking !== null && rankingMonth === month && filters.sortBy.indexOf("cost") === 0) {
      payload.rankedIds = costRanking.slice(pageIndex * 25, pageIndex * 25 + 25).map(function(row) { return row.id; });
      payload.rankedTotal = costRanking.length;
    } else clearRanking();
    request("catalog", payload);
  }
  function chooseDatabase(index) {
    if (!databaseRows[index]) return;
    if (!activeRequest || activeRequest.kind !== "live") invalidate();
    error = ""; database = databaseRows[index]; detail = null; detailsVisible = true;
    if (refreshThrottled) { error = "Database refresh is paused by Azure. Retry after the cooldown."; return; }
    request("live", livePayload([database.id], database.id));
  }
  function collapseDatabase() {
    detailsVisible = false;
    if (pendingRequest && pendingRequest.kind === "detail") pendingRequest = null;
    if (activeRequest && activeRequest.kind === "detail") invalidate();
  }
  function refreshStatus() {
    if (database && detailsVisible && !busy && !refreshThrottled) request("live", livePayload([database.id], database.id));
  }
  function refreshLive() {
    if (!panelActive || busy || filtersPending || refreshThrottled || !authenticated || !databaseRows.length) return;
    request("live", livePayload(databaseRows.map(function(row) { return row.id; })));
  }
  function publicAccessFor(row) { return row.publicNetworkAccess || "Unknown"; }
  function cloudFor(row) {
    var id = row.id.split('/')[2];
    var index = Model.indexOf(subscriptionRows, id);
    return index >= 0 ? subscriptionRows[index].cloud : "AzureCloud";
  }
  function saveView(name, nameFilter, makeDefault, updateExisting) {
    if (nameFilter !== undefined && nameFilter !== filters.filter) setFilter("filter", nameFilter);
    viewName = name.trim(); runView("view-save", {id: updateExisting ? selectedViewId : "", name: name, filters: filters, makeDefault: makeDefault === true});
  }
  function deleteView(id) { runView("view-delete", {id: id}); }
  function setDefaultView(id) { runView("view-default", {id: id}); }
  function runView(operation, payload) {
    if (viewsBusy) return;
    viewError = ""; viewOperation = operation;
    var command = ["python3", "-B", helper()];
    if (demoMode) command.push("--demo");
    viewWorker.command = command.concat([operation, "--payload", JSON.stringify(payload)]); viewWorker.running = true;
  }
  function request(kind, payload) {
    var context = Object.assign({profileId: profileId, tenantId: tenantId}, payload);
    var next = {kind: kind, payload: context, generation: generation, demo: demoMode};
    if (busy) { pendingRequest = next; return; } launch(next);
  }
  function launch(next) {
    activeRequest = next; stdoutDone = false; stderrDone = false; exited = false;
    exitCode = 0; responseText = ""; watchdogExpired = false;
    var command = ["python3", "-B", helper()];
    if (next.demo) command.push("--demo");
    worker.command = command.concat([next.kind, "--payload", JSON.stringify(next.payload)]);
    worker.running = true; watchdog.restart();
  }
  function finish() {
    if (!activeRequest || !stdoutDone || !stderrDone || !exited) return;
    watchdog.stop(); killDeadline.stop(); var completed = activeRequest;
    if (completed.generation === generation) {
      var reply = null; try { reply = JSON.parse(responseText); } catch (_) {}
      if (reply && reply.schemaVersion === 1 && reply.ok === true && exitCode === 0) applyReply(completed, reply.data);
      else {
        var message = watchdogExpired ? "Azure refresh timed out. Retry or narrow the selected scope."
          : reply && reply.error ? reply.error.message : "Could not run the Azure Databases helper.";
        if (completed.kind === "views") { viewError = message; filters = emptyFilters(); request("identities", {}); }
        else {
          error = message; errorCode = reply && reply.error ? reply.error.code : "helper_failed"; pageLoading = false;
          if (errorCode === "rate_limit") backOff(reply.error.retryAfterSec, completed.kind === "catalog" ? "graph" : "arm");
          if (completed.kind === "session" || errorCode === "authentication" || errorCode === "missing_cli") { authenticated = false; authenticationKnown = true; }
          identitySwitching = false;
        }
      }
    }
    activeRequest = null; var next = pendingRequest; pendingRequest = null;
    if (next && next.generation === generation) Qt.callLater(function() { if (next.generation === root.generation && !root.busy) root.launch(next); });
  }
  function applyReply(completed, data) {
    var kind = completed.kind;
    error = ""; errorCode = "";
    if (data.throttles) data.throttles.forEach(function(item) { root.backOff(item.retryAfterSec, item.scope); });
    else if (data.rateLimited) backOff(data.retryAfterSec, data.throttleScope || "arm");
    if (kind === "views") {
      receiveViews(data); var selected = Model.indexOf(availableViews, defaultViewId);
      filters = selected >= 0 ? filtersFor(availableViews[selected]) : emptyFilters();
      selectedViewId = selected >= 0 ? defaultViewId : ""; request("identities", {});
    } else if (kind === "identities" || kind === "identity-select") {
      receiveIdentity(data); request("session", {});
    } else if (kind === "session") {
      receiveIdentity(data); identitySwitching = false;
      subscriptionRows = data.subscriptions; sqlLocations = data.sqlLocations || [];
      if (data.optionsWarning) warning = data.optionsWarning;
      constrainIdentityFilters();
      authenticated = data.authenticated; authenticationKnown = true;
      if (authenticated) loadPage(true); else pageLoading = false;
    } else if (kind === "catalog") {
      if (data.costRanking !== null && data.costRanking !== undefined) {
        costRanking = data.costRanking; rankingMonth = new Date().toISOString().slice(0,7);
      }
      if (completed.payload.rankedIds && costRanking !== null) {
        var rankedCosts = {}; costRanking.slice(pageIndex * 25, pageIndex * 25 + 25).forEach(function(row) { rankedCosts[row.id.toLowerCase()] = row.cost; });
        data.rows.forEach(function(row) { row.cost = rankedCosts[row.id.toLowerCase()]; });
      }
      databaseRows = data.rows; totalCount = data.totalCount; pageLoading = false;
      if (data.facets && data.facets.servers) facets = data.facets;
      warning = (data.warnings || []).join("\n");
      if (pageIndex >= pageCount) { pageIndex = pageCount - 1; loadPage(false); return; }
      if (databaseRows.length && !refreshThrottled) request("live", livePayload(databaseRows.map(function(row) { return row.id; })));
    } else if (kind === "live") {
      liveRowsUpdating();
      var rows = databaseRows.slice();
      for (var i = 0; i < data.rows.length; i++) {
        var index = Model.indexOf(rows, data.rows[i].id);
        if (index >= 0) rows[index] = Object.assign({}, rows[index], data.rows[i]);
      }
      databaseRows = rows;
      liveRowsUpdated();
      if (database) { var current = Model.indexOf(rows, database.id); if (current >= 0) database = rows[current]; }
      if (data.authenticationRequired) { authenticated = false; authenticationKnown = true; }
      if (!refreshThrottled && completed.payload.detailsId && detailsVisible && database && database.id === completed.payload.detailsId)
        request("detail", {engine: engine, id: database.id});
    } else if (kind === "detail") detail = data;
  }
  Process {
    id: worker
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: { root.responseText = text; root.stdoutDone = true; root.finish(); } }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: { root.stderrDone = true; root.finish(); } }
    onStarted: if (root.activeRequest && root.activeRequest.generation !== root.generation) root.cancelWorker()
    onExited: function(code) { root.exitCode = code; root.exited = true; root.finish(); }
  }
  Process {
    id: viewWorker
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var reply = null; try { reply = JSON.parse(text); } catch (_) {}
        if (reply && reply.ok) {
          root.receiveViews(reply.data);
          if (root.viewOperation === "view-save") for (var i = 0; i < root.savedViews.length; i++)
            if (root.savedViews[i].name === root.viewName) root.selectedViewId = root.savedViews[i].id;
          if (root.selectedViewId && Model.indexOf(root.savedViews, root.selectedViewId) < 0) root.selectedViewId = "";
          if (root.viewOperation === "view-save") { root.viewDirty = false; root.viewSaved(); }
        } else root.viewError = reply && reply.error ? reply.error.message : "Could not save view preferences.";
      }
    }
    stderr: StdioCollector { waitForEnd: true }
  }
  Timer { id: filterDelay; interval: 700; onTriggered: root.applyPendingFilters() }
  Timer { interval: 1000; running: Object.keys(root.cooldowns).length > 0; repeat: true; onTriggered: root.expireCooldowns() }
  Timer { id: killDeadline; interval: 3000; onTriggered: if (worker.running) worker.signal(9) }
  Timer { id: watchdog; interval: 600000; onTriggered: { root.watchdogExpired = true; root.cancelWorker(); } }
  Timer {
    interval: Math.max(600, Math.min(3600, Number(root.settings.liveRefreshIntervalSec) || 600)) * 1000
    running: root.panelActive && root.authenticated && !root.filtersPending && !root.busy && !root.refreshThrottled && root.databaseRows.length > 0
    repeat: true; onTriggered: root.refreshLive()
  }
}
