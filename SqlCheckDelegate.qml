pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.CheckDelegate {
  id: root
  implicitHeight: Style.space(34)
  font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
  palette.window: Color.background; palette.base: Color.background
  palette.button: Color.background; palette.text: Color.foreground
  palette.windowText: Color.foreground; palette.buttonText: Color.foreground
  palette.highlight: Color.accent; palette.highlightedText: Color.foreground
  contentItem: Text {
    text: root.text; textFormat: Text.PlainText; color: Color.foreground
    font: root.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
    rightPadding: Style.space(26)
  }
  indicator: Rectangle {
    x: root.width - width - Style.space(8); y: (root.height-height)/2
    width: Style.space(16); height: width; radius: Style.space(3)
    color: Color.background; border.width: 1; border.color: root.checked ? Color.accent : Color.muted
    Text { anchors.centerIn: parent; text: root.checked ? "✓" : ""; color: Color.foreground; font: root.font }
  }
  background: Rectangle {
    color: root.highlighted || root.hovered ? Qt.rgba(Color.accent.r,Color.accent.g,Color.accent.b,0.18) : Color.background
    radius: Style.cornerRadius; border.width: root.visualFocus ? 1 : 0; border.color: Color.accent
  }
}
