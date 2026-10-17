import QtQuick
import QtQuick.Window
import Quickshell
import qs.Commons
import "AzureSql" as AzureSql

ShellRoot {
  property int ticks: 0
  Component.onCompleted: backend.panelOpened()
  AzureSql.Controller { id: backend; settings: ({demoMode: true}) }
  Window {
    id: window
    visible: true
    width: content.implicitWidth + 56
    height: content.implicitHeight + 56
    Rectangle { anchors.fill: parent; color: Color.background }
    AzureSql.PanelContent {
      id: content
      x: 28; y: 28
      width: parent.width - 56
      controller: backend
    }
  }
  Timer {
    id: capture
    interval: 150; running: true; repeat: true
    onTriggered: {
      ticks++;
      if (ticks > 60) { console.error("QML_CHECK_FAILED", "Demo did not load"); Qt.quit(); return; }
      if (backend.busy || backend.databaseRows.length === 0) return;
      if (!backend.detail) { backend.chooseDatabase(0); return; }
      capture.stop();
      // Preview palette is temporary and only affects this separate process.
      Color.background = "#111923"; Color.foreground = "#e6edf3";
      Color.accent = "#63b3ed"; Color.urgent = "#f28b82";
      Style.fontFamily = "DejaVu Sans"; Style.fontBaseSize = 14;
      settle.start();
    }
  }
  Timer {
    id: settle
    interval: 100
    onTriggered: window.contentItem.grabToImage(function(result) {
      if (result.saveToFile(Quickshell.env("SQL_PREVIEW_OUTPUT"))) console.log("QML_CHECK_PASSED");
      else console.error("QML_CHECK_FAILED", "Could not save preview");
      Qt.quit();
    })
  }
}
