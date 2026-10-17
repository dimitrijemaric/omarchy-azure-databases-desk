pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons

Controls.AbstractButton {
  id: root
  property var options: []
  property var selectedIds: []
  property string label: "Filter"
  property string tooltip: ""
  HoverTooltip { anchorItem: root; text: root.tooltip }
  property string query: ""
  readonly property var filteredOptions: options.filter(function(row) { return (row.name + " " + row.id).toLowerCase().indexOf(query.toLowerCase()) >= 0; })
  signal selectionEdited(var values)
  signal editingFinished()
  implicitHeight: Style.space(34)
  Accessible.name: label + ", " + summary()
  function contains(id) { return selectedIds.some(function(value) { return String(value).toLowerCase() === String(id).toLowerCase(); }); }
  function summary() {
    if (!selectedIds.length) return "All";
    if (selectedIds.length > 1) return selectedIds.length + " selected";
    for (var i = 0; i < options.length; i++) if (String(options[i].id).toLowerCase() === String(selectedIds[0]).toLowerCase()) return options[i].name;
    return String(selectedIds[0]);
  }
  function toggle(id) {
    var values = selectedIds.slice(); var index = values.map(function(v) { return String(v).toLowerCase(); }).indexOf(String(id).toLowerCase());
    if (index >= 0) values.splice(index, 1); else values.push(id);
    selectionEdited(values);
  }
  Keys.onPressed: function(event) {
    if (!popup.visible && event.key === Qt.Key_Down) { query = ""; popup.open(); event.accepted = true; return; }
    if (!popup.visible && event.key !== Qt.Key_Space && event.text && event.text.trim() && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
      query = event.text; popup.open(); event.accepted = true;
    }
  }
  onClicked: { if (popup.visible) popup.close(); else { query = ""; popup.open(); } }
  contentItem: Text {
    text: root.summary() + "  ▾"; elide: Text.ElideRight
    color: Color.foreground; leftPadding: Style.space(10); rightPadding: Style.space(10)
    verticalAlignment: Text.AlignVCenter
    font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
  }
  background: Rectangle {
    radius: Style.cornerRadius; color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.05)
    border.width: root.visualFocus ? 2 : 1; border.color: root.visualFocus ? Color.accent : Color.muted
  }
  Controls.Popup {
    id: popup
    y: root.height + Style.space(4); width: root.width
    height: Math.min(Style.space(370), Math.max(Style.space(144), root.filteredOptions.length * Style.space(34) + Style.space(126)))
    padding: Style.space(6); focus: true
    closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutsideParent
    onOpened: { choices.currentIndex = -1; search.text = root.query; search.forceActiveFocus(); search.cursorPosition = search.text.length; }
    onClosed: { root.editingFinished(); root.forceActiveFocus(); }
    background: Rectangle { color: Color.background; border.width: 1; border.color: Color.accent; radius: Style.cornerRadius }
    contentItem: ColumnLayout {
      spacing: Style.space(4)
      Controls.TextField {
        id: search
        Layout.fillWidth: true; implicitHeight: Style.space(30)
        maximumLength: 256; placeholderText: "Search " + root.label.toLowerCase() + "…"
        color: Color.foreground; placeholderTextColor: Color.muted
        font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
        onTextEdited: { root.query = text; choices.currentIndex = -1; }
        onAccepted: if (root.filteredOptions.length) root.toggle(root.filteredOptions[Math.max(0,choices.currentIndex)].id)
        Keys.onDownPressed: if (choices.count) { choices.currentIndex = 0; choices.forceActiveFocus(); }
        Keys.onUpPressed: if (choices.count) { choices.currentIndex = choices.count-1; choices.forceActiveFocus(); }
        background: Rectangle { color: "transparent"; border.width: 1; border.color: Color.muted; radius: Style.cornerRadius }
      }
      SqlCheckDelegate {
        text: "All"; checked: root.selectedIds.length === 0; Layout.fillWidth: true; implicitHeight: Style.space(30)
        palette.text: Color.foreground; palette.buttonText: Color.foreground
        font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
        onClicked: root.selectionEdited([])
      }
      ListView {
        id: choices
        currentIndex: -1; keyNavigationEnabled: true
        Keys.onReturnPressed: if (currentIndex >= 0) root.toggle(root.filteredOptions[currentIndex].id)
        Keys.onEnterPressed: if (currentIndex >= 0) root.toggle(root.filteredOptions[currentIndex].id)
        Keys.onSpacePressed: if (currentIndex >= 0) root.toggle(root.filteredOptions[currentIndex].id)
        Keys.onTabPressed: done.forceActiveFocus()
        Keys.onBacktabPressed: search.forceActiveFocus()
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; reuseItems: true
        model: root.filteredOptions
        Controls.ScrollBar.vertical: Controls.ScrollBar {}
        delegate: SqlCheckDelegate {
          required property var modelData
          required property int index
          highlighted: ListView.isCurrentItem && choices.activeFocus
          width: ListView.view.width; height: Style.space(34)
          text: modelData.name; checked: root.contains(modelData.id)
          palette.text: Color.foreground; palette.buttonText: Color.foreground
          font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
          onClicked: { choices.currentIndex = index; root.toggle(modelData.id); }
          Controls.ToolTip.visible: hovered && text.length > 30; Controls.ToolTip.text: text
        }
        Text { anchors.centerIn: parent; text: "No matches"; visible: choices.count === 0; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
      }
      SqlButton { id: done; text: "Done"; Layout.alignment: Qt.AlignRight; onClicked: popup.close() }
    }
  }
}
