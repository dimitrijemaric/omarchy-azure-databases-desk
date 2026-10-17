import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "dimitrije.azure-sql"
  manageIpc: false
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Controller { id: azure; settings: root.settings }

  function open() {
    root.controller.show();
  }

  function startSetup(action) {
    if (action !== "install" && action !== "login") return;
    var helper = decodeURIComponent(Qt.resolvedUrl("scripts/setup.sh").toString().replace(/^file:\/\//, ""));
    Quickshell.execDetached(["omarchy", "launch", "terminal", "bash", helper, action]);
    root.close();
  }
  function startAccountLogin(profile, tenant, cloud) {
    var helper = decodeURIComponent(Qt.resolvedUrl("scripts/setup.sh").toString().replace(/^file:\/\//, ""));
    Quickshell.execDetached(["omarchy", "launch", "terminal", "bash", helper, "login", profile, tenant, cloud]);
    root.close();
  }
  function openQueryClient() {
    var helper = decodeURIComponent(Qt.resolvedUrl("scripts/query_client.sh").toString().replace(/^file:\/\//, ""));
    root.close();
    Quickshell.execDetached(["bash", helper, "open"]);
  }

  onOpenedChanged: { if (opened) azure.panelOpened(); else azure.panelClosed(); }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰆼"
    active: root.opened
    tooltipText: (azure.demoMode ? "Demo · " : "") + "Azure Databases Desk"
    onPressed: function(code) {
      if (code === Qt.RightButton || code === Qt.MiddleButton) azure.reload();
      else root.toggle();
    }
    Rectangle {
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: Style.space(4)
      width: Style.space(4); height: width; radius: width / 2
      visible: azure.database !== null || azure.error !== ""
      color: azure.error || (azure.database && azure.database.publicNetworkAccess === "Enabled") ? Color.urgent : Color.accent
      opacity: azure.database && azure.database.status === "Paused" ? 0.4 : 1
    }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panelContent
    contentWidth: popup.fittedContentWidth(Style.space(1120))
    contentHeight: popup.fittedContentHeight(panelContent.implicitHeight, Style.space(760))

    PanelContent {
      id: panelContent
      anchors.fill: parent
      controller: azure
      onCloseRequested: root.close()
      onSetupRequested: function(action) { if (action === "login") root.startAccountLogin(azure.profileId,azure.tenantId,"AzureCloud"); else root.startSetup(action); }
      onAccountLoginRequested: function(profile,tenant,cloud) { root.startAccountLogin(profile,tenant,cloud); }
      onQueryClientRequested: root.openQueryClient()
      onLiveModeRequested: Quickshell.execDetached(["omarchy", "bar", "set", "dimitrije.azure-sql", "demoMode", "false", "--json"])
    }
  }
}
