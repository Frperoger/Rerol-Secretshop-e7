import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ScrollView {
    id: page
    required property var backend
    readonly property var values: backend.budget
    readonly property var budgetLocale: Qt.locale("pt_BR")
    contentWidth: availableWidth
    clip: true
    function focusGems() { currencies.itemAt(0).balanceEditor.forceActiveFocus() }

    component Amount: LabeledField {
        property string key
        editor.objectName: key + "Field"
        Layout.fillWidth: true
        value: Number(page.values[key]).toLocaleString(page.budgetLocale, "f", 0)
        inputMethodHints: Qt.ImhDigitsOnly
        validator: IntValidator { bottom: 0; top: 2147483647; locale: page.budgetLocale.name }
        onCommitted: function(text) { page.backend.editBudget(key, Number.fromLocaleString(page.budgetLocale, text)) }
    }

    ColumnLayout {
        width: page.availableWidth
        spacing: 14
        Label { text: "Orçamento da execução"; font.pixelSize: 22; font.bold: true }
        Label {
            Layout.fillWidth: true
            text: "Defina o saldo e quanto o bot pode gastar. As alterações válidas são salvas ao confirmar o campo."
            color: "#b7c5d8"
            wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Repeater {
                id: currencies
                model: [["gems", "Gemas", "#6eaaff"], ["gold", "Ouro", "#f3bb55"]]
                delegate: ShopCard {
                    id: currencyCard
                    required property var modelData
                    readonly property string currency: modelData[0]
                    property alias balanceEditor: available.editor
                    readonly property real balance: Number(page.values[currency + "_available"])
                    readonly property real limit: Number(page.values[currency + "_limit"]) || balance
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    CurrencyHeading { Layout.fillWidth: true; currency: currencyCard.currency; title: modelData[1] }
                    Amount { id: available; key: currencyCard.currency + "_available"; title: "Saldo disponível" }
                    Amount { key: currencyCard.currency + "_limit"; title: "Limite de gasto · 0 usa todo o saldo" }
                    ShopProgress {
                        Layout.fillWidth: true
                        Accessible.name: "Proporção do limite em relação ao saldo"
                        value: currencyCard.balance > 0 ? Math.min(1, currencyCard.limit / currencyCard.balance) : 0
                        tint: modelData[2]
                        Behavior on value { NumberAnimation { duration: 160 } }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.preferredWidth: 250
                Layout.maximumWidth: 260
                CurrencyHeading { currency: "gems"; title: "Custo de renovação em gemas" }
                Amount { key: "refresh_cost"; enabled: !page.backend.info.running }
            }
            Item { Layout.fillWidth: true }
            ShopButton {
                Layout.alignment: Qt.AlignBottom
                text: "Salvar orçamento"
                primary: true
                onClicked: page.backend.action("saveBudget")
            }
        }
        Label {
            Layout.fillWidth: true
            text: page.backend.info.budgetNotice
            color: "#b7c5d8"
            wrapMode: Text.WordWrap
        }
    }
}
