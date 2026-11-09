import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: summary
    property var items: []
    property var counts: ({})
    property int total: 0
    property bool compact: false
    readonly property int inset: compact ? 6 : 10
    readonly property var entries: {
        const result = []
        const names = []
        for (const item of items) {
            const name = item.name.trim()
            const count = counts[name] || 0
            if ((item.enabled || count > 0) && !names.includes(name)) {
                result.push({ name: name, preview: item.preview, count: count })
                names.push(name)
            }
        }
        // Keep completed purchases visible if an item is later removed or renamed.
        for (const name of Object.keys(counts)) {
            if (counts[name] > 0 && !names.includes(name))
                result.push({ name: name, preview: "", count: counts[name] })
        }
        return result
    }

    color: "#121c29"
    border.color: "#30485b"
    radius: 8
    implicitWidth: 280
    implicitHeight: body.implicitHeight + inset * 2

    ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: summary.inset
        spacing: summary.compact ? 4 : 6
        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: qsTr("Itens comprados")
                color: "#c2d0df"
                font.pixelSize: summary.compact ? 12 : 13
                font.bold: true
            }
            Label {
                objectName: "purchasedTotal"
                text: summary.total.toLocaleString(Qt.locale(i18n.localeName), "f", 0)
                color: "#74e0bb"
                font.pixelSize: summary.compact ? 19 : 24
                font.bold: true
                Accessible.name: qsTr("%1 itens comprados nesta sessão").arg(summary.total)
            }
        }
        Flow {
            id: chips
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: summary.entries
                delegate: Rectangle {
                    id: chip
                    required property var modelData
                    required property int index
                    objectName: "purchasedItem" + index
                    readonly property bool hasIcon: modelData.preview !== ""
                    width: Math.min(chips.width, (hasIcon ? (summary.compact ? 22 : 28)
                                     : Math.min(100, itemName.implicitWidth)) + amount.implicitWidth + 22)
                    height: summary.compact ? 30 : 38
                    radius: 6
                    color: "#1e2d3e"
                    Accessible.name: qsTr("%1: %2 compras").arg(modelData.name).arg(modelData.count)
                    ToolTip.visible: hover.hovered
                    ToolTip.text: Accessible.name
                    HoverHandler { id: hover }
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 6
                        Image {
                            visible: chip.hasIcon
                            source: chip.modelData.preview
                            Layout.preferredWidth: summary.compact ? 22 : 28
                            Layout.preferredHeight: summary.compact ? 22 : 28
                            fillMode: Image.PreserveAspectFit
                        }
                        Label {
                            id: itemName
                            visible: !chip.hasIcon
                            Layout.fillWidth: true
                            Layout.maximumWidth: 100
                            text: chip.modelData.name
                            elide: Text.ElideRight
                            color: "#c2d0df"
                            font.pixelSize: summary.compact ? 11 : 12
                        }
                        Label {
                            id: amount
                            objectName: "purchasedQuantity"
                            text: "× " + chip.modelData.count.toLocaleString(Qt.locale(i18n.localeName), "f", 0)
                            color: "#edf1f7"
                            font.pixelSize: summary.compact ? 14 : 16
                            font.bold: true
                        }
                    }
                }
            }
        }
    }
}
