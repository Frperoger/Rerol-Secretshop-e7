import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ScrollView {
    id: page
    required property var backend
    readonly property bool twoColumns: availableWidth >= 820
    contentWidth: availableWidth
    clip: true
    ColumnLayout {
        width: Math.min(page.availableWidth, page.twoColumns ? 920 : 460)
        x: (page.availableWidth - width) / 2
        spacing: 12
        Label { text: qsTr("Itens a comprar"); font.pixelSize: 22; font.bold: true }
        RowLayout {
            Layout.fillWidth: true
            ShopButton { text: qsTr("Adicionar item"); onClicked: page.backend.action("addItem") }
            ShopButton { text: qsTr("Pasta de templates"); onClicked: page.backend.action("templates") }
            Item { Layout.fillWidth: true }
            ShopButton { text: qsTr("Salvar itens"); primary: true; onClicked: page.backend.action("saveItems") }
        }
        Label {
            Layout.fillWidth: true
            text: page.backend.info.templates
            color: "#b7c5d8"
            wrapMode: Text.Wrap
        }
        GridLayout {
            Layout.fillWidth: true
            columns: page.twoColumns ? 2 : 1
            columnSpacing: 12
            rowSpacing: 12
            Repeater {
                model: page.backend.items
                delegate: ShopCard {
                    id: itemCard
                    required property var modelData
                    required property int index
                    objectName: "itemCard" + index
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.maximumWidth: 460
                    Layout.alignment: Qt.AlignTop
                    RowLayout {
                        Layout.fillWidth: true
                        Image {
                            source: itemCard.modelData.preview
                            Layout.preferredWidth: 40
                            Layout.preferredHeight: 40
                            fillMode: Image.PreserveAspectFit
                        }
                        CheckBox {
                            text: qsTr("Ativo")
                            checked: itemCard.modelData.enabled
                            onClicked: page.backend.toggleItem(itemCard.index, checked)
                        }
                        Item { Layout.fillWidth: true }
                        ShopButton { text: qsTr("Remover"); danger: true; onClicked: page.backend.removeItem(itemCard.index) }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        Repeater {
                            model: [
                                ["id", "ID"], ["name", "Nome"], ["price", "Preço em ouro"], ["icon", "Ícone PNG"],
                                ["buy", "Botão de compra PNG"], ["confirm", "Confirmação PNG"],
                                ["sold", "Vendido PNG (diagnóstico)"]
                            ]
                            delegate: LabeledField {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                title: modelData[1]
                                currency: modelData[0] === "price" ? "gold" : ""
                                value: itemCard.modelData[modelData[0]]
                                onCommitted: function(text) { page.backend.editItem(itemCard.index, modelData[0], text) }
                            }
                        }
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: page.backend.info.itemNotice || qsTr("Os nomes dos arquivos devem corresponder aos recortes PNG na pasta de templates.")
            color: "#b7c5d8"
            wrapMode: Text.WordWrap
        }
    }
}
