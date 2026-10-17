import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.TabButton {
  id: root
  property string tooltip: ""
  HoverTooltip { anchorItem: root; text: root.tooltip }
  implicitHeight: Style.space(36)
  opacity: enabled ? 1 : 0.35
  contentItem: Text {
    text: root.text; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    color: root.checked ? Color.accent : Color.foreground
    font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; font.bold: root.checked
  }
  background: Rectangle {
    color: root.checked ? Qt.rgba(Color.accent.r,Color.accent.g,Color.accent.b,0.12) : Qt.rgba(Color.foreground.r,Color.foreground.g,Color.foreground.b,0.03)
    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: Style.space(2); color: Color.accent; visible: root.checked }
  }
}
