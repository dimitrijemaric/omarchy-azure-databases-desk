pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.ToolTip {
  id: root
  required property Item anchorItem
  // Track hover on the enabled parent so disabled controls can explain themselves.
  parent: anchorItem.parent
  x: anchorItem.x + (anchorItem.width - implicitWidth) / 2
  y: anchorItem.y + anchorItem.height + Style.space(4)
  visible: text !== "" && anchorItem.visible && hover.hovered
    && anchorItem.contains(anchorItem.mapFromItem(hover.parent,hover.point.position))
  delay: 500
  timeout: 4000
  HoverHandler {
    id: hover
    parent: root.anchorItem.parent
    enabled: root.text !== "" && root.anchorItem.visible
  }
}
