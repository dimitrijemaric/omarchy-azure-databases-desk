import QtQuick
import qs.Commons

Rectangle {
  id: root
  property string label: ""
  property string value: "—"
  property string timestamp: ""
  implicitHeight: Style.space(70)
  color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.04)
  radius: Style.cornerRadius
  Column {
    anchors.left: parent.left
    anchors.leftMargin: Style.space(12)
    anchors.verticalCenter: parent.verticalCenter
    spacing: Style.space(5)
    Text {
      text: root.label; textFormat: Text.PlainText
      color: Color.foreground; opacity: 0.6
      font.family: Style.font.family; font.pixelSize: Style.font.caption
    }
    Text {
      text: root.value; textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family; font.pixelSize: Style.font.title
    }
  }
  Accessible.name: label + " " + value + (timestamp ? ", sampled " + timestamp : "")
}
