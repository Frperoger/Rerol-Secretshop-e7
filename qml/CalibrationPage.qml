import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ScrollView {
    id: page
    required property var backend
    readonly property var values: backend.calibration
    readonly property var info: backend.info
    contentWidth: availableWidth
    clip: true

    component CoordinateFields: GridLayout {
        id: grid
        property bool overlay: false
        Layout.fillWidth: true
        columns: 4
        Repeater {
            model: ["x0", "y0", "x1", "y1"]
            delegate: LabeledField {
                required property int index
                required property string modelData
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                title: modelData
                value: Number((grid.overlay ? page.values.overlayArea : page.values.safeArea)[index])
                       .toLocaleString(Qt.locale(i18n.localeName), "f", grid.overlay ? 3 : 2)
                validator: DoubleValidator { bottom: 0; top: 1; decimals: 3; locale: i18n.localeName; notation: DoubleValidator.StandardNotation }
                onCommitted: function(text) {
                    page.backend.editCoordinate(grid.overlay, index, Number.fromLocaleString(Qt.locale(i18n.localeName), text))
                }
            }
        }
    }

    ColumnLayout {
        width: page.availableWidth
        spacing: 14
        RowLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            spacing: 14
            ShopCard {
                objectName: "detectionCard"
                title: "Janela e detecção"
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                LabeledField {
                    Layout.fillWidth: true
                    title: "Título da janela"
                    value: page.values.window_title
                    onCommitted: function(text) { page.backend.editCalibration("window_title", text) }
                }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        id: shortcut
                        objectName: "recordHotkey"
                        property bool recording: false
                        Layout.fillWidth: true
                        readOnly: true
                        text: recording ? qsTr("Pressione o atalho…") : page.values.hotkey
                        Accessible.name: qsTr("Atalho de emergência")
                        onActiveFocusChanged: if (!activeFocus) recording = false
                        Keys.onPressed: function(event) {
                            if (!recording)
                                return
                            event.accepted = true
                            if (event.key === Qt.Key_Escape) {
                                recording = false
                                return
                            }
                            if ([Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta].indexOf(event.key) >= 0)
                                return
                            page.backend.recordKey(event.key, event.modifiers)
                            recording = false
                        }
                    }
                    ShopButton {
                        text: qsTr("Gravar teclas")
                        onClicked: {
                            shortcut.forceActiveFocus()
                            shortcut.recording = true
                        }
                    }
                }
                Label {
                    Layout.fillWidth: true
                    text: page.info.hotkeyHint
                    color: "#b7c5d8"
                    wrapMode: Text.WordWrap
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    Repeater {
                        model: [
                            ["threshold", "Limiar de match", 0.6, 0.99, 2], ["max_scrolls", "Scrolls máximos", 0, 8, 0],
                            ["pause_min", "Pausa mínima (s)", 0, 10, 2], ["pause_max", "Pausa máxima (s)", 0, 10, 2],
                            ["focus_timeout", "Espera por foco (s)", 1, 300, 1],
                            ["modal_timeout", "Timeout de confirmação (s)", 0.5, 10, 1]
                        ]
                        delegate: LabeledField {
                            id: numberField
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            title: modelData[1]
                            value: Number(page.values[modelData[0]]).toLocaleString(Qt.locale(i18n.localeName), "f", modelData[4])
                            validator: DoubleValidator {
                                bottom: numberField.modelData[2]
                                top: numberField.modelData[3]
                                decimals: numberField.modelData[4]
                                locale: i18n.localeName
                                notation: DoubleValidator.StandardNotation
                            }
                            onCommitted: function(text) {
                                page.backend.editCalibration(modelData[0], String(Number.fromLocaleString(Qt.locale(i18n.localeName), text)))
                            }
                        }
                    }
                }
                ShopButton {
                    Layout.fillWidth: true
                    text: qsTr("Restaurar velocidade original")
                    onClicked: page.backend.action("resetSpeed")
                }
            }
            ShopCard {
                objectName: "safeAreaCard"
                title: "Área de clique seguro"
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Layout.alignment: Qt.AlignTop
                AreaPreview { backend: page.backend; Layout.fillWidth: true }
                RowLayout {
                    Layout.fillWidth: true
                    ShopButton { text: qsTr("Abrir imagem"); onClicked: page.backend.action("image") }
                    ShopButton { text: qsTr("Capturar janela"); onClicked: page.backend.action("capture") }
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Arraste a área verde ou redimensione pelo canto inferior direito.")
                    wrapMode: Text.WordWrap
                    color: "#b7c5d8"
                }
                CoordinateFields {}
                CheckBox {
                    text: qsTr("Mostrar painel compacto sobre a loja")
                    checked: page.values.compact
                    onClicked: page.backend.setCompact(checked)
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("A área azul posiciona o painel. Mantenha as regiões separadas.")
                    color: "#b7c5d8"
                    wrapMode: Text.WordWrap
                }
                CoordinateFields { overlay: true }
                Label {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: page.info.areaWarning
                    color: "#ffb3bc"
                    wrapMode: Text.WordWrap
                }
            }
        }
        ShopCard {
            Layout.fillWidth: true
            title: "Diagnóstico visual"
            Label {
                Layout.fillWidth: true
                text: qsTr("Para calibrar a escala, use a loja aberta e sem diálogos. Para testar a compra, use uma imagem da janela inteira com a confirmação de preço aberta ou com o item já vendido.")
                color: "#b7c5d8"
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                ShopButton { text: qsTr("Abrir PNG"); onClicked: page.backend.action("png") }
                ShopButton { text: qsTr("Capturar janela"); onClicked: page.backend.action("capture") }
                ShopButton {
                    text: qsTr("Calibrar e salvar escala")
                    primary: true
                    onClicked: page.backend.action("diagnostic")
                }
                ShopButton {
                    text: qsTr("Testar compra")
                    onClicked: page.backend.action("diagnosticPurchase")
                }
            }
            Label {
                Layout.fillWidth: true
                text: page.info.capturePath
                visible: text !== ""
                color: "#b7c5d8"
                wrapMode: Text.Wrap
            }
            Label {
                Layout.fillWidth: true
                text: page.info.diagnostic
                wrapMode: Text.WordWrap
            }
            Image {
                Layout.fillWidth: true
                Layout.preferredHeight: 265
                visible: source.toString() !== ""
                source: page.info.diagnosticImage
                cache: false
                fillMode: Image.PreserveAspectFit
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ShopButton { text: qsTr("Pasta de templates"); onClicked: page.backend.action("templates") }
            ShopButton { text: qsTr("Restaurar padrões"); onClicked: page.backend.action("resetCalibration") }
            Item { Layout.fillWidth: true }
            ShopButton { text: qsTr("Salvar calibração"); primary: true; onClicked: page.backend.action("saveCalibration") }
        }
        Label {
            Layout.fillWidth: true
            text: page.info.calibrationNotice || page.info.templates
            color: "#b7c5d8"
            wrapMode: Text.Wrap
        }
    }
}
