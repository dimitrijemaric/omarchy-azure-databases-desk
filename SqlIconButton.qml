import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.AbstractButton {
  id: root
  property string tooltip: ""
  implicitWidth: Style.space(20)
  implicitHeight: Style.space(20)
  Accessible.name: tooltip
  contentItem: Text {
    text: root.text
    color: Color.accent; opacity: root.enabled ? 1 : 0.4
    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    font.family: Style.font.family; font.pixelSize: Style.font.body
  }
  background: Rectangle {
    radius: Style.cornerRadius
    color: root.hovered ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.15) : "transparent"
    border.width: root.visualFocus ? 1 : 0; border.color: Color.accent
  }
  Controls.ToolTip.visible: hovered && tooltip !== ""
  Controls.ToolTip.text: tooltip
}
