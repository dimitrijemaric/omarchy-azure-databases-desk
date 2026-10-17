pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons
import "Model.js" as Model

FocusScope {
  id: root
  required property Controller controller
  signal closeRequested()
  signal setupRequested(string action)
  signal accountLoginRequested(string profile, string tenant, string cloud)
  signal liveModeRequested()
  signal queryClientRequested()
  property string expandedDatabaseId: ""
  property real preservedScroll: 0
  property bool advancedFilters: false
  property bool identityControlsVisible: false
  function selectionCount(keys) { return keys.reduce(function(total,key) { return total + root.controller.filters[key].length; },0); }
  implicitWidth: Style.space(1120)
  implicitHeight: Style.space(760)
  Keys.onEscapePressed: closeRequested()
  Keys.onPressed: function(event) { if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_R) { controller.reload(); event.accepted = true; } }
  function toggleDatabase(index) {
    var row = controller.databaseRows[index]; if (!row) return;
    if (expandedDatabaseId === row.id.toLowerCase()) { expandedDatabaseId = ""; controller.collapseDatabase(); }
    else { expandedDatabaseId = row.id.toLowerCase(); controller.chooseDatabase(index); }
  }
  function options(key) {
    return controller.filterOptions(key);
  }
  Connections {
    target: root.controller
    function onPanelActiveChanged() { if (!root.controller.panelActive) root.identityControlsVisible = false; }
    function onViewSaved() { saveViewDialog.close(); }
    function onCatalogReset() { root.expandedDatabaseId = ""; databaseList.contentY = 0; }
    function onDetailsVisibleChanged() { root.expandedDatabaseId = root.controller.detailsVisible && root.controller.database ? root.controller.database.id.toLowerCase() : ""; }
    function onDatabaseChanged() { if (root.controller.database && root.controller.detailsVisible) root.expandedDatabaseId = root.controller.database.id.toLowerCase(); }
    function onFiltersChanged() { searchDelay.stop(); search.text = root.controller.filters.filter; }
    function onLiveRowsUpdating() { root.preservedScroll = databaseList.contentY; }
    function onLiveRowsUpdated() { Qt.callLater(function() { databaseList.contentY = Math.max(0,Math.min(root.preservedScroll,databaseList.contentHeight-databaseList.height)); }); }
  }
  Timer { id: searchDelay; interval: 600; onTriggered: root.controller.setFilter("filter", search.text.trim()) }
  Controls.Popup {
    id: saveViewDialog
    objectName: "saveViewDialog"
    readonly property bool updating: root.controller.selectedViewId !== ""
    function save(update) { root.controller.saveView(savedViewName.text,search.text.trim(),saveAsDefault.checked,update); }
    x: (root.width-width)/2; y: (root.height-height)/2
    width: Style.space(400); implicitHeight: saveViewForm.implicitHeight + padding*2
    padding: Style.space(18); modal: true; focus: true
    closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
    onOpened: {
      var index = Model.indexOf(root.controller.availableViews,root.controller.selectedViewId);
      savedViewName.text = index >= 0 ? root.controller.availableViews[index].name : "";
      saveAsDefault.checked = index >= 0 && root.controller.availableViews[index].id === root.controller.defaultViewId;
      savedViewName.forceActiveFocus(); savedViewName.selectAll();
    }
    background: Rectangle { color: Color.background; border.width: 1; border.color: Color.accent; radius: Style.cornerRadius }
    contentItem: ColumnLayout {
      id: saveViewForm
      spacing: Style.space(12)
      Text { text: saveViewDialog.updating ? "Save changes to view" : "Save view"; color: Color.foreground; font.bold: true; font.family: Style.font.family; font.pixelSize: Style.font.body }
      Controls.TextField {
        id: savedViewName
        Layout.fillWidth: true; implicitHeight: Style.space(34); maximumLength: 80
        placeholderText: "Name this view…"; selectByMouse: true
        color: Color.foreground; placeholderTextColor: Color.muted
        font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
        onAccepted: if (text.trim() && !root.controller.viewsBusy) saveViewDialog.save(saveViewDialog.updating)
        background: Rectangle { color: "transparent"; border.width: 1; border.color: Color.muted; radius: Style.cornerRadius }
      }
      SqlCheckDelegate {
        id: saveAsDefault
        objectName: "saveAsDefault"
        text: "Make default view"; Layout.fillWidth: true
        palette.text: Color.foreground; palette.buttonText: Color.foreground
        font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
      }
      Text { text: root.controller.viewError; visible: text !== ""; color: Color.urgent; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText; font.pixelSize: Style.font.caption }
      RowLayout {
        Item { Layout.fillWidth: true }
        SqlButton { text: "Cancel"; onClicked: saveViewDialog.close() }
        SqlButton { text: "Save as new"; visible: saveViewDialog.updating; enabled: savedViewName.text.trim() !== "" && !root.controller.viewsBusy; onClicked: saveViewDialog.save(false) }
        SqlButton { text: saveViewDialog.updating ? "Update" : "Save"; enabled: savedViewName.text.trim() !== "" && !root.controller.viewsBusy; onClicked: saveViewDialog.save(saveViewDialog.updating) }
      }
    }
  }
  ColumnLayout {
    anchors.fill: parent; spacing: Style.space(10)
    RowLayout {
      Layout.fillWidth: true
      Text {
        text: "Azure Databases Desk" + (root.controller.demoMode ? " · DEMO" : "")
        Layout.fillWidth: true; color: Color.foreground; font.bold: true
        font.family: Style.font.family; font.pixelSize: Style.font.title
      }
      SqlButton {
        objectName: "identityToggleButton"
        text: "Accounts " + (root.identityControlsVisible ? "▴" : "▾")
        visible: !root.controller.demoMode
        tooltip: root.identityControlsVisible ? "Hide account and directory" : "Show account and directory"
        checkable: true; checked: root.identityControlsVisible
        onClicked: root.identityControlsVisible = !root.identityControlsVisible
      }
      SqlButton {
        objectName: "createDatabaseButton"; text: "Create database ↗"
        enabled: !root.controller.demoMode && root.controller.createDatabaseUrl !== ""
        tooltip: "Create in Azure Portal"
        Accessible.description: tooltip
        onClicked: Qt.openUrlExternally(root.controller.createDatabaseUrl)
      }
      SqlButton {
        objectName: "costCalculatorButton"; text: "Cost Calculator"
        enabled: false
        tooltip: "Coming soon"; Accessible.description: tooltip
      }
      SqlButton {
        objectName: "azureSignInButton"; text: "Sign in to Azure"
        visible: !root.controller.demoMode && root.controller.authenticationKnown && !root.controller.authenticated && root.controller.errorCode !== "missing_cli"
        onClicked: root.setupRequested("login")
      }
      SqlButton {
        text: "Install Azure CLI"; visible: root.controller.errorCode === "missing_cli"
        onClicked: root.setupRequested("install")
      }
      SqlIconButton { text: "↻"; tooltip: "Refresh page"; enabled: !root.controller.busy; onClicked: root.controller.reload() }
    }
    IdentityBar {
      objectName: "identityControls"
      visible: root.identityControlsVisible && !root.controller.demoMode
      controller: root.controller
      Layout.fillWidth: true
      onLoginRequested: function(profile,tenant,cloud) { root.accountLoginRequested(profile,tenant,cloud); }
    }
    Controls.TabBar {
      Layout.fillWidth: true
      currentIndex: ["sql","cosmos","postgres"].indexOf(root.controller.engine)
      ServiceTab { text: "Azure SQL"; onClicked: root.controller.setEngine("sql") }
      ServiceTab { text: "Cosmos DB"; enabled: false; tooltip: "Coming soon"; Accessible.description: tooltip }
      ServiceTab { text: "PostgreSQL"; enabled: false; tooltip: "Coming soon"; Accessible.description: tooltip }
    }
    Controls.ProgressBar { visible: root.controller.busy; indeterminate: true; Layout.fillWidth: true; Layout.preferredHeight: Style.space(3); palette.highlight: Color.accent }
    Text {
      text: root.controller.error || root.controller.throttleWarning || root.controller.warning; visible: text !== ""
      Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
      color: Color.urgent; font.family: Style.font.family; font.pixelSize: Style.font.caption
    }
    RowLayout {
      Layout.fillWidth: true; Layout.fillHeight: true; spacing: Style.space(16)
      ColumnLayout {
        objectName: "databasePane"
        Layout.fillWidth: true; Layout.fillHeight: true; spacing: Style.space(8)
        Text {
          text: root.controller.totalCount.toLocaleString(Qt.locale(),"f",0) + (root.controller.engine === "cosmos" ? " account" : root.controller.engine === "postgres" ? " server" : " database") + (root.controller.totalCount === 1 ? "" : "s")
          Layout.fillWidth: true; color: Color.foreground; opacity: 0.55
          font.family: Style.font.family; font.pixelSize: Style.font.caption
        }
        ListView {
          id: databaseList
          objectName: "databaseList"
          Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: Style.space(180)
          model: root.controller.databaseRows; reuseItems: true; clip: true
          boundsBehavior: Flickable.StopAtBounds
          Controls.ScrollBar.vertical: Controls.ScrollBar {}
          Keys.onReturnPressed: if (currentIndex >= 0) root.toggleDatabase(currentIndex)
          delegate: Item {
            id: option
            required property var modelData
            required property int index
            readonly property bool expanded: root.expandedDatabaseId === modelData.id.toLowerCase()
            width: databaseList.width
            height: header.height + (expanded ? details.height + Style.space(20) : 0)
            Controls.AbstractButton {
              id: header
              width: parent.width; height: Style.space(64)
              onClicked: { databaseList.currentIndex = option.index; root.toggleDatabase(option.index); }
              Accessible.name: option.modelData.name + ", " + option.modelData.status + ", " + Model.cost(option.modelData.cost)
              background: Rectangle {
                radius: Style.cornerRadius
                color: option.modelData.publicNetworkAccess === "Enabled" ? Qt.rgba(Color.urgent.r,Color.urgent.g,Color.urgent.b,0.16)
                  : option.expanded || header.hovered ? Qt.rgba(Color.accent.r,Color.accent.g,Color.accent.b,0.1) : "transparent"
                border.width: header.visualFocus ? 1 : 0; border.color: Color.accent
              }
              contentItem: RowLayout {
                anchors.fill: parent; anchors.margins: Style.space(8); spacing: Style.space(10)
                Text { text: option.expanded ? "▾" : "▸"; color: Color.foreground; opacity: 0.5; font.family: Style.font.family; font.pixelSize: Style.font.body }
                ColumnLayout {
                  Layout.fillWidth: true; spacing: Style.space(3)
                  Item {
                    id: nameRow
                    Layout.fillWidth: true; implicitHeight: Style.space(22)
                    Text {
                      id: resourceName
                      text: option.modelData.name; textFormat: Text.PlainText
                      width: Math.min(implicitWidth,Math.max(0,nameRow.width - Style.space(option.expanded ? 75 : 50)))
                      anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                      color: Color.foreground; font.bold: option.expanded
                      font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
                    }
                    SqlIconButton {
                      id: portal
                      objectName: "databasePortalLink"
                      x: resourceName.width + Style.space(5); anchors.verticalCenter: parent.verticalCenter
                      text: "↗"; tooltip: "Azure Portal"; enabled: !root.controller.demoMode
                      onClicked: Qt.openUrlExternally(Model.portalUrl(root.controller.cloudFor(option.modelData),option.modelData.id))
                    }
                    SqlIconButton {
                      id: query
                      objectName: "databaseQueryLink"
                      x: portal.x + portal.width + Style.space(5); anchors.verticalCenter: parent.verticalCenter
                      visible: root.controller.engine !== "cosmos"; enabled: !root.controller.demoMode
                      text: "󰆼"; tooltip: "Open DB Studio"; onClicked: root.queryClientRequested()
                    }
                    SqlIconButton {
                      objectName: "databaseRefreshButton"
                      x: query.x + (query.visible ? query.width + Style.space(5) : 0); anchors.verticalCenter: parent.verticalCenter
                      visible: option.expanded; enabled: !root.controller.busy
                      text: "↻"; tooltip: "Refresh database"; onClicked: root.controller.refreshStatus()
                    }
                  }
                  Text {
                    text: [root.controller.engine === "sql" ? option.modelData.serverName : option.modelData.tier,option.modelData.location].filter(function(v) { return !!v; }).join(" · ")
                    Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText
                    color: Color.foreground; opacity: 0.5; font.family: Style.font.family; font.pixelSize: Style.font.caption
                  }
                }
                ColumnLayout {
                  Layout.alignment: Qt.AlignRight; spacing: Style.space(4)
                  RowLayout {
                    Text { text: "⚠ PUBLIC"; visible: option.modelData.publicNetworkAccess === "Enabled"; color: Color.urgent; font.bold: true; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                    Text {
                      text: Model.cost(option.modelData.cost); color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption
                      HoverHandler { id: costHover }
                      Controls.ToolTip.visible: costHover.hovered; Controls.ToolTip.text: Model.costDescription(option.modelData.cost)
                    }
                    Text {
                      text: option.modelData.status + (option.modelData.liveError ? " ⚠" : ""); textFormat: Text.PlainText
                      color: option.modelData.liveError ? Color.urgent : Color.foreground
                      font.family: Style.font.family; font.pixelSize: Style.font.caption
                      HoverHandler { id: stateHover }
                      Controls.ToolTip.visible: stateHover.hovered && !!option.modelData.liveError; Controls.ToolTip.text: option.modelData.liveError || ""
                    }
                  }
                  Text {
                    text: Model.metricSummary(option.modelData)
                    color: option.modelData.liveError ? Color.urgent : Color.foreground; opacity: 0.7
                    Layout.alignment: Qt.AlignRight; font.family: Style.font.family; font.pixelSize: Style.font.caption
                    HoverHandler { id: metricHover }
                    Controls.ToolTip.visible: metricHover.hovered && (!!option.modelData.liveError || !!option.modelData.liveAt)
                    Controls.ToolTip.text: option.modelData.liveError || Model.updatedAt(option.modelData.liveAt)
                  }
                }
              }
            }
            Loader {
              id: details
              active: option.expanded
              x: Style.space(12); y: header.height + Style.space(10)
              width: parent.width - Style.space(24); height: item ? item.implicitHeight : 0
              sourceComponent: Component { DatabaseDetails { controller: root.controller } }
            }
          }
          Text {
            anchors.centerIn: parent; width: parent.width - Style.space(30)
            visible: !databaseList.count && !root.controller.pageLoading
            text: root.controller.authenticated ? (!root.controller.demoMode && !root.controller.subscriptionRows.length ? "No subscriptions available in this directory" : "No matching resources") : root.controller.authenticationKnown ? "Sign in to browse resources" : ""
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
            color: Color.foreground; opacity: 0.55; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
          }
        }
        RowLayout {
          Layout.fillWidth: true
          SqlButton { objectName: "previousPageButton"; text: "Previous"; enabled: !root.controller.pageLoading && root.controller.pageIndex > 0; onClicked: root.controller.goToPage(root.controller.pageIndex-1) }
          Item { Layout.fillWidth: true }
          Controls.TextField {
            text: String(root.controller.pageIndex + 1); implicitWidth: Style.space(48); implicitHeight: Style.space(30)
            color: Color.foreground; selectByMouse: true; horizontalAlignment: Text.AlignHCenter
            validator: IntValidator { bottom: 1; top: root.controller.pageCount }
            onAccepted: if (acceptableInput) root.controller.goToPage(Number(text)-1)
            background: Rectangle { color: "transparent"; border.width: 1; border.color: Color.muted; radius: Style.cornerRadius }
            Accessible.name: "Page number"
          }
          Text { text: "/ " + root.controller.pageCount; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
          Item { Layout.fillWidth: true }
          SqlButton { objectName: "nextPageButton"; text: "Next"; enabled: !root.controller.pageLoading && root.controller.pageIndex+1 < root.controller.pageCount; onClicked: root.controller.goToPage(root.controller.pageIndex+1) }
        }
      }
      Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Color.foreground; opacity: 0.15 }
      Flickable {
        objectName: "filtersPane"
        Layout.preferredWidth: Style.space(265); Layout.fillHeight: true
        contentWidth: width; contentHeight: filterColumn.implicitHeight
        clip: true; boundsBehavior: Flickable.StopAtBounds
        Controls.ScrollBar.vertical: Controls.ScrollBar {}
        ColumnLayout {
          id: filterColumn
          width: parent.width - Style.space(10); spacing: Style.space(7)
          Text { text: "Sort by"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
          SqlComboBox {
            id: sortSelector
            Layout.fillWidth: true
            model: [{id:"nameAsc",name:"Name · A–Z"},{id:"nameDesc",name:"Name · Z–A"},{id:"costDesc",name:"Cost · highest first"},{id:"costAsc",name:"Cost · lowest first"},{id:"location",name:"Location"},{id:"tier",name:"Service tier"},{id:"state",name:"State"}]
            currentIndex: Model.indexOf(model,root.controller.filters.sortBy)
            onActivated: function(index) { root.controller.setFilter("sortBy",model[index].id); }
          }
          Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.foreground; opacity: 0.15 }
          Text { text: "Database name"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
          Controls.TextField {
            id: search
            objectName: "databaseNameFilter"
            Layout.fillWidth: true; implicitHeight: Style.space(34)
            text: root.controller.filters.filter; maximumLength: 256; placeholderText: "Filter by database name…"
            color: Color.foreground; placeholderTextColor: Color.muted; selectByMouse: true
            font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
            onTextEdited: searchDelay.restart()
            background: Rectangle { color: "transparent"; radius: Style.cornerRadius; border.width: 1; border.color: Color.muted }
          }
          SqlButton { objectName: "saveViewButton"; text: "Save view"; enabled: !root.controller.viewsBusy; onClicked: { root.controller.viewError = ""; saveViewDialog.open(); } }
          Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.foreground; opacity: 0.15 }
          Text { text: "SAVED VIEWS" + (root.controller.viewDirty ? " · Modified" : ""); color: Color.foreground; opacity: 0.6; font.family: Style.font.family; font.pixelSize: Style.font.caption }
          SqlComboBox {
            objectName: "savedViewSelector"; Layout.fillWidth: true; model: root.controller.availableViews
            currentIndex: Model.indexOf(model,root.controller.selectedViewId); emptyText: "Load a saved view…"; enabled: count > 0
            onActivated: function(index) { root.controller.applyView(index); }
          }
          RowLayout {
            Layout.fillWidth: true
            SqlButton { text: "Delete view"; enabled: root.controller.selectedViewId !== "" && !root.controller.viewsBusy; onClicked: root.controller.deleteView(root.controller.selectedViewId) }
            SqlButton {
              readonly property bool isDefault: root.controller.selectedViewId !== "" && root.controller.selectedViewId === root.controller.defaultViewId
              text: isDefault ? "✓ Default" : "Make default"
              enabled: root.controller.selectedViewId !== "" && !isDefault && !root.controller.viewsBusy
              onClicked: root.controller.setDefaultView(root.controller.selectedViewId)
            }
          }
          Text {
            text: root.controller.viewError; visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
            color: Color.urgent; font.family: Style.font.family; font.pixelSize: Style.font.caption
          }
          Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.foreground; opacity: 0.15 }
          RowLayout {
            Layout.fillWidth: true
            Text { text: "FILTERS"; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption; Layout.fillWidth: true }
            SqlButton { objectName: "resetFiltersButton"; text: "Reset"; tooltip: "Clear filters and sorting"; onClicked: root.controller.resetFilters() }
          }
          Repeater {
            model: [
              {key:"subscriptionIds",label:"Subscriptions"},{key:"serverIds",label:"Servers"},
              {key:"locations",label:"Locations"},{key:"tiers",label:"Service tiers"},{key:"computeModels",label:"Compute models"},
              {key:"backupRedundancies",label:"Backup redundancy",section:"BACKUP & RESTORE"},
              {key:"restoreHistories",label:"Restore history",tip:"Time since the earliest reported restore point"},
              {key:"maintenanceWindows",label:"Maintenance window",section:"MAINTENANCE",tip:"Configured window; pool settings apply"},
              {key:"zoneRedundancies",label:"Zone redundancy",section:"AVAILABILITY"},
              {key:"readScales",label:"Read scale-out"}
            ]
            ColumnLayout {
              id: filterGroup
              required property var modelData
              readonly property bool advanced: ["subscriptionIds","serverIds","locations","tiers","computeModels"].indexOf(modelData.key) < 0
              visible: !advanced || root.advancedFilters || modelData.key === "backupRedundancies"
              Layout.fillWidth: true; spacing: Style.space(4)
              SqlButton {
                visible: filterGroup.modelData.key === "backupRedundancies"
                objectName: "advancedFiltersButton"
                readonly property int selectedCount: root.selectionCount(["backupRedundancies","restoreHistories","maintenanceWindows","zoneRedundancies","readScales"])
                text: (root.advancedFilters ? "▾" : "▸") + " Advanced filters" + (selectedCount ? " (" + selectedCount + ")" : "")
                Layout.fillWidth: true
                onClicked: root.advancedFilters = !root.advancedFilters
              }
              Text {
                visible: root.advancedFilters && !!filterGroup.modelData.section; text: filterGroup.modelData.section || ""
                Layout.topMargin: visible ? Style.space(8) : 0
                color: Color.foreground; opacity: 0.6; font.family: Style.font.family; font.pixelSize: Style.font.caption
              }
              Text { visible: !filterGroup.advanced || root.advancedFilters; text: filterGroup.modelData.label; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
              MultiSelectCombo {
                visible: !filterGroup.advanced || root.advancedFilters
                Layout.fillWidth: true
                label: filterGroup.modelData.label; tooltip: filterGroup.modelData.tip || ""; options: root.options(filterGroup.modelData.key)
                selectedIds: root.controller.filters[filterGroup.modelData.key]
                onSelectionEdited: function(values) { root.controller.setFilter(filterGroup.modelData.key,values,true); }
                onEditingFinished: root.controller.applyPendingFilters()
              }
            }
          }
          SqlButton { text: "Use Azure account"; visible: root.controller.demoMode; onClicked: root.liveModeRequested() }
        }
      }
    }
  }
}
