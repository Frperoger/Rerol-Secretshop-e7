import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: page
    required property var backend
    property var selection: []
    spacing: 12
    Connections {
        target: page.backend
        function onHistoryChanged() { page.selection = [] }
    }
    ShopCard {
        title: "Relatório da última execução"
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: page.backend.info.report
            wrapMode: Text.Wrap
        }
    }
    ShopCard {
        title: "Histórico de execuções"
        Layout.fillWidth: true
        Layout.fillHeight: true
        RowLayout {
            Layout.fillWidth: true
            Item { Layout.preferredWidth: 32 }
            Repeater {
                model: [["Início", 145], ["Renovações", 80], ["Compras", 65],
                        ["Gemas", 65], ["Ouro", 88], ["Motivo de parada", 110]]
                delegate: Label {
                    required property var modelData
                    required property int index
                    Layout.preferredWidth: modelData[1]
                    Layout.fillWidth: index === 5
                    text: modelData[0]
                    color: "#b7c5d8"
                    font.bold: true
                }
            }
        }
        ListView {
            id: rows
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: page.backend.history
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                id: record
                required property int index
                required property var modelData
                width: rows.width
                height: Math.max(34, dataRow.implicitHeight + 8)
                color: page.selection.includes(index) ? "#324967" : index % 2 ? "#212c3c" : "#192332"
                RowLayout {
                    id: dataRow
                    anchors.fill: parent
                    CheckBox {
                        Layout.preferredWidth: 32
                        checked: page.selection.includes(record.index)
                        Accessible.name: "Selecionar execução de " + record.modelData[0]
                        onClicked: {
                            page.selection = checked ? page.selection.concat([record.index])
                                                       : page.selection.filter(row => row !== record.index)
                        }
                    }
                    Repeater {
                        model: [145, 80, 65, 65, 88, 110]
                        delegate: Label {
                            required property int index
                            required property int modelData
                            Layout.preferredWidth: modelData
                            Layout.fillWidth: index === 5
                            text: record.modelData[index]
                            wrapMode: index === 5 ? Text.Wrap : Text.NoWrap
                            elide: index === 5 ? Text.ElideNone : Text.ElideRight
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ShopButton {
                text: "Apagar selecionados"
                enabled: page.selection.length > 0
                danger: true
                onClicked: page.backend.deleteHistory(page.selection)
            }
            ShopButton { text: "Apagar todo o histórico"; danger: true; onClicked: page.backend.action("clearHistory") }
        }
        Label {
            Layout.fillWidth: true
            text: page.backend.info.historyNotice
            color: "#b7c5d8"
            wrapMode: Text.WordWrap
        }
    }
}
