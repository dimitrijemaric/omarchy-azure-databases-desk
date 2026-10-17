pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import "Model.js" as Model

ColumnLayout {
  id: root
  required property Controller controller
  readonly property var database: controller.database
  readonly property var detail: controller.detail
  spacing: Style.space(10)
  Rectangle {
    visible: root.database && root.database.publicNetworkAccess === "Enabled"
    objectName: "publicAccessWarning"
    Layout.fillWidth: true; implicitHeight: warningText.implicitHeight + Style.space(24)
    radius: Style.cornerRadius; color: Qt.rgba(Color.urgent.r,Color.urgent.g,Color.urgent.b,0.28)
    border.width: 2; border.color: Color.urgent
    ColumnLayout {
      id: warningText
      x: Style.space(12); y: Style.space(12); width: parent.width - Style.space(24)
      Text { text: "⚠ PUBLIC NETWORK ACCESS ENABLED"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Color.urgent; font.bold: true; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
      Text { text: "The public endpoint is enabled. Firewall rules and authentication still apply."; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
    }
  }
  Text {
    text: root.database ? [root.database.tier,root.database.computeModel,root.database.location].filter(function(v) { return !!v; }).join(" · ") : ""
    textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.Wrap
    color: Color.foreground; opacity: 0.65; font.family: Style.font.family; font.pixelSize: Style.font.caption
  }
  RowLayout {
    Layout.fillWidth: true
    Repeater {
      model: root.controller.engine === "cosmos" ? [{label: "RU USE",key: "NormalizedRUConsumption"}]
        : root.controller.engine === "postgres" ? [{label: "CPU",key:"cpu_percent"},{label:"MEMORY",key:"memory_percent"},{label:"STORAGE",key:"storage_percent"}]
        : [{label:"CPU",key:"cpu_percent"},{label:"DATA I/O",key:"physical_data_read_percent"},{label:"LOG I/O",key:"log_write_percent"}]
      MetricTile {
        required property var modelData
        Layout.fillWidth: true; label: modelData.label
        readonly property var metric: root.database && root.database.metrics ? root.database.metrics[modelData.key] : null
        value: Model.percent(metric); timestamp: metric ? metric.timestamp : ""
      }
    }
  }
  Repeater {
    model: root.detail && root.detail.id === (root.database ? root.database.id : "") ? root.detail.sections : []
    ColumnLayout {
      id: section
      required property var modelData
      Layout.fillWidth: true; spacing: Style.space(5)
      Text { text: section.modelData.title; color: Color.foreground; font.bold: true; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
      Repeater {
        model: section.modelData.rows
        RowLayout {
          required property var modelData
          Layout.fillWidth: true; spacing: Style.space(12)
          Text { text: parent.modelData.name; textFormat: Text.PlainText; Layout.preferredWidth: Style.space(150); color: Color.foreground; opacity: 0.55; font.family: Style.font.family; font.pixelSize: Style.font.caption }
          Text { text: parent.modelData.value; textFormat: Text.PlainText; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
        }
      }
    }
  }
  Text {
    text: [root.database ? root.database.liveError : "",root.detail ? root.detail.warnings.join("\n") : ""].filter(function(v) { return !!v; }).join("\n")
    visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
    color: Color.urgent; font.family: Style.font.family; font.pixelSize: Style.font.caption
  }
}
