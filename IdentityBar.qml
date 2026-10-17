pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import qs.Commons
import "Model.js" as Model

RowLayout {
  id: root
  required property Controller controller
  signal loginRequested(string profile, string tenant, string cloud)
  spacing: Style.space(8)
  visible: !controller.demoMode
  Text { text: "Account"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
  SqlComboBox {
    id: accountSelector
    objectName: "accountSelector"
    Layout.fillWidth: true; Layout.preferredWidth: Style.space(270); Layout.minimumWidth: Style.space(130)
    model: root.controller.accountRows
    currentIndex: Model.indexOf(model,root.controller.profileId)
    emptyText: "Azure CLI account"
    enabled: count > 0 && !root.controller.identitySwitching
    onActivated: function(index) { root.controller.switchAccount(index); }
    HoverTooltip { anchorItem: accountSelector; text: "Switch Azure sign-in" }
    Accessible.description: "Remembered Azure sign-ins. Each added account has its own CLI profile."
  }
  SqlIconButton {
    objectName: "addAzureAccountButton"; text: "+"; tooltip: "Sign in with another account"
    onClicked: { loginDialog.directoryOnly = false; loginDialog.open(); }
  }
  Rectangle { implicitWidth: 1; implicitHeight: Style.space(24); color: Color.muted; opacity: 0.5 }
  Text { text: "Directory"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
  SqlComboBox {
    id: directorySelector
    objectName: "directorySelector"
    Layout.fillWidth: true; Layout.preferredWidth: Style.space(270); Layout.minimumWidth: Style.space(130)
    model: root.controller.directoryRows
    currentIndex: Model.indexOf(model,root.controller.tenantId)
    emptyText: "No directory available"
    enabled: count > 0 && !root.controller.identitySwitching
    onActivated: function(index) { root.controller.switchDirectory(index); }
    HoverTooltip { anchorItem: directorySelector; text: "Switch directory for this account" }
    Accessible.description: "Microsoft Entra directories for the selected account. Subscriptions are limited to this directory."
  }
  SqlIconButton {
    objectName: "addAzureDirectoryButton"; text: "+"; tooltip: "Sign in to another directory"
    enabled: !root.controller.identitySwitching
    onClicked: { loginDialog.directoryOnly = true; loginDialog.open(); }
  }
  Controls.Popup {
    id: loginDialog
    objectName: "accountLoginDialog"
    property bool directoryOnly: false
    parent: Controls.Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(Style.space(420), parent ? parent.width - Style.space(32) : Style.space(420))
    implicitHeight: form.implicitHeight + padding*2
    padding: Style.space(18); modal: true; focus: true
    closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
    onOpened: { tenant.text = ""; cloud.currentIndex = 0; tenant.forceActiveFocus(); }
    function start() {
      root.loginRequested(directoryOnly ? root.controller.profileId : "new",tenant.text.trim(),cloud.model[cloud.currentIndex].id);
      close();
    }
    background: Rectangle { color: Color.background; border.color: Color.accent; border.width: 1; radius: Style.cornerRadius }
    contentItem: ColumnLayout {
      id: form
      spacing: Style.space(12)
      Text {
        text: loginDialog.directoryOnly ? "Sign in to a directory" : "Add Azure account"
        color: Color.foreground; font.bold: true; font.family: Style.font.family; font.pixelSize: Style.font.body
      }
      Text {
        Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
        text: loginDialog.directoryOnly ? "Use the same account to sign in to another Microsoft Entra tenant. Its directories will remain in the list."
          : "Complete sign-in in the terminal and browser. This account will be remembered separately from your other sign-ins."
        color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
      }
      Text { text: "Directory (tenant ID)" + (loginDialog.directoryOnly ? "" : " · optional"); color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
      Controls.TextField {
        id: tenant
        objectName: "loginTenantField"
        Layout.fillWidth: true; implicitHeight: Style.space(34); selectByMouse: true
        maximumLength: 36; placeholderText: "00000000-0000-0000-0000-000000000000"
        color: Color.foreground; placeholderTextColor: Color.muted
        font.family: Style.font.family; font.pixelSize: Style.font.bodySmall
        validator: RegularExpressionValidator { regularExpression: /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/ }
        onAccepted: if (acceptableInput || (!loginDialog.directoryOnly && !text.trim())) loginDialog.start()
        background: Rectangle { color: Color.background; border.color: Color.muted; border.width: 1; radius: Style.cornerRadius }
      }
      Text { visible: !loginDialog.directoryOnly; text: "Azure cloud"; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption }
      SqlComboBox {
        id: cloud
        visible: !loginDialog.directoryOnly; Layout.fillWidth: true
        model: [{id:"AzureCloud",name:"Azure public cloud"},{id:"AzureUSGovernment",name:"Azure Government"},{id:"AzureChinaCloud",name:"Azure China"}]
        currentIndex: 0
        onActivated: function(index) { currentIndex = index; }
      }
      RowLayout {
        Item { Layout.fillWidth: true }
        SqlButton { text: "Cancel"; onClicked: loginDialog.close() }
        SqlButton {
          objectName: "startAccountLoginButton"; text: "Continue to sign in"
          enabled: tenant.acceptableInput || (!loginDialog.directoryOnly && !tenant.text.trim())
          onClicked: loginDialog.start()
        }
      }
    }
  }
}
