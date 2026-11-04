import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Window {
    id: popup
    property bool waiting: false
    property var metrics: ({})
    signal returnRequested()
    transientParent: null
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    color: "#0a1420"
    visible: false
    width: 300
    height: 108

    Rectangle {
        anchors.fill: parent
        color: "#0a1420"
        border.color: "#328dff"
        border.width: 2
        radius: 8
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 2
            RowLayout {
                Label {
                    Layout.fillWidth: true
                    text: "E7 SHOP BOT"
                    color: "#edf1f7"
                    font.bold: true
                    elide: Text.ElideRight
                }
                ShopButton {
                    objectName: "returnToApp"
                    text: popup.waiting ? "Aguarde…" : "Voltar ao app"
                    implicitHeight: 25
                    enabled: !popup.waiting
                    focusPolicy: Qt.NoFocus
                    onClicked: {
                        popup.waiting = true
                        popup.returnRequested()
                    }
                }
            }
            Label { text: "Status: " + (popup.metrics.status || "preparando"); color: "#edf1f7" }
            Label {
                text: "Gemas: " + (popup.metrics.gems_estimated || 0) + "  |  Ouro: " +
                      (popup.metrics.gold_estimated || 0).toLocaleString(Qt.locale("pt_BR"))
                color: "#edf1f7"
            }
            Label {
                text: "Renovações: " + (popup.metrics.refreshes || 0) +
                      "  |  Compras: " + (popup.metrics.purchases_verified || 0)
                color: "#edf1f7"
            }
            Item { Layout.fillHeight: true }
        }
    }
}
