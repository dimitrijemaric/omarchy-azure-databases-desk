pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons

Controls.AbstractButton {
  id: root
  property var model: []
  property int currentIndex: -1
  property string emptyText: "None found"
  property string query: ""
  readonly property int count: model.length
  readonly property var filteredOptions: model.map(function(row, index) { return {name: row.name, id: row.id, sourceIndex: index}; }).filter(function(row) { return (row.name + " " + row.id).toLowerCase().indexOf(query.toLowerCase()) >= 0; })
  signal activated(int index)
  implicitHeight: Style.space(34)
  Accessible.name: currentIndex >= 0 && currentIndex < count ? model[currentIndex].name : emptyText
  function choose(index) { activated(index); popup.close(); }
  Keys.onPressed: function(event) {
    if (!popup.visible && event.text && event.text.trim() && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
      query = event.text; popup.open(); event.accepted = true;
    }
  }
  onClicked: { query = ""; popup.open(); }
  contentItem: Text {
    text: (root.currentIndex >= 0 && root.currentIndex < root.count ? root.model[root.currentIndex].name : root.emptyText) + "  ▾"
    textFormat: Text.PlainText; elide: Text.ElideRight
    leftPadding: Style.space(10); rightPadding: Style.space(10)
    color: Color.foreground; opacity: root.enabled ? 1 : 0.5
    verticalAlignment: Text.AlignVCenter
    font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
  }
  background: Rectangle {
    radius: Style.cornerRadius
    color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.05)
    border.width: root.visualFocus ? 2 : 1; border.color: root.visualFocus ? Color.accent : Color.muted
  }
  Controls.Popup {
    id: popup
    y: root.height + Style.space(4); width: root.width
    height: Math.min(Style.space(300), Math.max(Style.space(110), root.filteredOptions.length * Style.space(34) + Style.space(50)))
    padding: Style.space(6); focus: true
    closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutsideParent
    onOpened: { search.text = root.query; search.forceActiveFocus(); search.cursorPosition = search.text.length; }
    background: Rectangle { color: Color.background; border.width: 1; border.color: Color.accent; radius: Style.cornerRadius }
    contentItem: ColumnLayout {
      spacing: Style.space(4)
      Controls.TextField {
        id: search
        Layout.fillWidth: true; implicitHeight: Style.space(30)
        maximumLength: 256; placeholderText: "Search options…"; selectByMouse: true
        color: Color.foreground; placeholderTextColor: Color.muted
        font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
        onTextEdited: root.query = text
        onAccepted: if (root.filteredOptions.length) root.choose(root.filteredOptions[0].sourceIndex)
        Keys.onDownPressed: { choices.currentIndex = 0; choices.forceActiveFocus(); }
        background: Rectangle { color: "transparent"; border.width: 1; border.color: Color.muted; radius: Style.cornerRadius }
      }
      ListView {
        id: choices
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; reuseItems: true
        model: root.filteredOptions
        Keys.onReturnPressed: if (currentIndex >= 0) root.choose(root.filteredOptions[currentIndex].sourceIndex)
        Controls.ScrollBar.vertical: Controls.ScrollBar {}
        delegate: Controls.ItemDelegate {
          id: option
          required property var modelData
          required property int index
          width: ListView.view.width; height: Style.space(34)
          highlighted: ListView.isCurrentItem && choices.activeFocus
          onClicked: root.choose(modelData.sourceIndex)
          contentItem: Text { text: option.modelData.name; textFormat: Text.PlainText; color: Color.foreground; elide: Text.ElideRight; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
          background: Rectangle { color: option.highlighted ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.18) : "transparent" }
        }
        Text { anchors.centerIn: parent; text: "No matches"; visible: choices.count === 0; color: Color.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
      }
    }
  }
}
