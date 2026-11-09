import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Window {
    id: popup
    property bool waiting: false
    property var metrics: ({})
    property var items: []
    signal returnRequested()
    transientParent: null
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    color: "#0a1420"
    visible: false
    width: 300
    height: 166

    Rectangle {
        anchors.fill: parent
        color: "#0a1420"
        border.color: "#328dff"
        border.width: 2
        radius: 8
        Item {
            id: available
            anchors.fill: parent
            anchors.margins: 8
            ColumnLayout {
                id: content
                objectName: "compactContent"
                width: Math.max(284, available.width)
                height: implicitHeight
                scale: Math.min(1, available.width / width, available.height / height)
                transformOrigin: Item.TopLeft
                x: (available.width - width * scale) / 2
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
                Label { text: qsTr("Status: %1").arg(qsTr(popup.metrics.status || "preparando")); color: "#edf1f7" }
                Label {
                    text: qsTr("Gemas: %1  |  Ouro: %2")
                          .arg((popup.metrics.gems_estimated || 0).toLocaleString(Qt.locale(i18n.localeName), "f", 0))
                          .arg((popup.metrics.gold_estimated || 0).toLocaleString(Qt.locale(i18n.localeName), "f", 0))
                    color: "#edf1f7"
                }
                PurchaseSummary {
                    objectName: "compactPurchases"
                    Layout.fillWidth: true
                    compact: true
                    items: popup.items
                    counts: popup.metrics.purchases_by_item || ({})
                    total: popup.metrics.purchases_sent || 0
                }
                Label {
                    text: qsTr("Renovações: %1").arg((popup.metrics.refreshes || 0).toLocaleString(Qt.locale(i18n.localeName), "f", 0))
                    color: "#edf1f7"
                }
            }
        }
    }
}
