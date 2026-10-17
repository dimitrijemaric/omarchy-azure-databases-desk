import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.Button {
  id: root
  property string tooltip: ""
  HoverTooltip { anchorItem: root; text: root.tooltip }
  implicitHeight: Style.space(34)
  font.family: Style.font.family
  font.pixelSize: Style.font.bodySmall
  leftPadding: Style.space(12)
  rightPadding: Style.space(12)
  opacity: enabled ? 1 : 0.4
  contentItem: Text {
    text: root.text
    textFormat: Text.PlainText
    font: root.font
    color: Color.foreground
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    elide: Text.ElideRight
  }
  background: Rectangle {
    radius: Style.cornerRadius
    color: root.down ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.25)
      : Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, root.hovered ? 0.12 : 0.06)
    border.width: root.visualFocus ? 2 : 0
    border.color: Color.accent
  }
}
