import QtQuick
import QtQuick.Window
import QtQuick.Controls as Controls
import Quickshell
import qs.Commons
import "AzureSql" as AzureSql

ShellRoot {
  AzureSql.Controller { id: backend; settings: ({demoMode: true, pageSize: 25}) }

  Component.onCompleted: {
    backend.panelOpened();
    // This palette belongs only to the separate simulation process.
    Color.background = "#111923"; Color.foreground = "#e6edf3";
    Color.accent = "#63b3ed"; Color.urgent = "#f28b82";
  }

  Window {
    id: window
    title: "Azure Databases Desk — security warning simulation"
    visible: true
    width: 1000; height: Math.min(800, Screen.height - 80)
    minimumWidth: 800; minimumHeight: 540
    color: Color.background
    onClosing: Qt.quit()

    Flickable {
      anchors.fill: parent; anchors.margins: 24
      contentWidth: width; contentHeight: panel.implicitHeight
      clip: true; boundsBehavior: Flickable.StopAtBounds
      Controls.ScrollBar.vertical: Controls.ScrollBar {}
      AzureSql.PanelContent {
        id: panel
        width: parent.width
        controller: backend
        onCloseRequested: Qt.quit()
        onLiveModeRequested: Qt.quit()
      }
    }
  }

  Timer {
    interval: 100; repeat: true; running: true
    onTriggered: {
      if (backend.busy || backend.pageLoading || !backend.databaseRows.length) return;
      stop(); backend.chooseDatabase(0);
    }
  }
}
