import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

RowLayout {
    id: page
    required property var backend
    readonly property var info: backend.info
    spacing: 14
    ScrollView {
        id: controls
        Layout.preferredWidth: 350
        Layout.minimumWidth: 315
        Layout.fillHeight: true
        contentWidth: availableWidth
        clip: true
        ShopCard {
            title: "Controle"
            width: controls.availableWidth
            RowLayout {
                Layout.fillWidth: true
                ShopButton {
                    objectName: "startBot"
                    Layout.fillWidth: true
                    text: "Iniciar"
                    primary: true
                    enabled: !page.info.running
                    onClicked: page.backend.action("start")
                }
                ShopButton {
                    objectName: "stopBot"
                    Layout.fillWidth: true
                    text: "Parar"
                    danger: true
                    enabled: page.info.running
                    onClicked: page.backend.action("stop")
                }
            }
            Label {
                Layout.fillWidth: true
                text: page.info.hotkey
                color: "#b7c5d8"
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: ["gems", "gold"]
                delegate: ColumnLayout {
                    required property string modelData
                    Layout.fillWidth: true
                    RowLayout {
                        Layout.fillWidth: true
                        CurrencyHeading {
                            Layout.fillWidth: true
                            currency: modelData
                            title: modelData === "gems" ? page.info.gemText : page.info.goldText
                        }
                        ShopButton { text: "Editar"; onClicked: page.backend.action("budget") }
                    }
                    ShopProgress {
                        Layout.fillWidth: true
                        value: modelData === "gems" ? page.info.gemProgress : page.info.goldProgress
                        tint: modelData === "gems" ? "#6eaaff" : "#f3bb55"
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                text: "Itens procurados"
                color: "#b7c5d8"
                font.bold: true
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: page.backend.items
                    delegate: CheckBox {
                        id: itemCheck
                        required property var modelData
                        required property int index
                        checked: modelData.enabled
                        text: modelData.preview ? "" : modelData.name
                        Accessible.name: modelData.name
                        ToolTip.visible: hovered
                        ToolTip.text: modelData.name
                        rightPadding: modelData.preview ? 35 : 8
                        Image {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: 30
                            height: 30
                            fillMode: Image.PreserveAspectFit
                            source: itemCheck.modelData.preview
                        }
                        onClicked: page.backend.toggleItem(index, checked)
                    }
                }
            }
            ShopButton {
                Layout.fillWidth: true
                visible: page.info.running
                text: "Voltar ao jogo e retomar"
                onClicked: page.backend.action("resume")
            }
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                columnSpacing: 10
                rowSpacing: 10
                Repeater {
                    model: [
                        ["refreshes", "Renovações", ""], ["purchases_verified", "Compras verificadas", ""],
                        ["gems_estimated", "Gemas estimadas", "gems"], ["gold_estimated", "Ouro estimado", "gold"]
                    ]
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        CurrencyHeading {
                            Layout.fillWidth: true
                            visible: modelData[2] !== ""
                            title: modelData[1]
                            currency: modelData[2]
                        }
                        Label { visible: modelData[2] === ""; text: modelData[1]; color: "#b7c5d8" }
                        Label { text: page.info.metrics[modelData[0]]; font.pixelSize: 20; font.bold: true }
                    }
                }
            }
        }
    }
    ShopCard {
        title: "Registro de atividade"
        Layout.fillWidth: true
        Layout.fillHeight: true
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Eventos desta sessão"; color: "#b7c5d8" }
            Item { Layout.fillWidth: true }
            ShopButton {
                text: "Copiar registro"
                enabled: events.count > 0
                onClicked: page.backend.copyActivity()
            }
        }
        ActivityFeed {
            id: events
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: page.backend.activity
        }
    }
}
