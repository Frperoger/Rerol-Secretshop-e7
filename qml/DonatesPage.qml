import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ScrollView {
    id: page
    objectName: "donatesPage"
    contentWidth: availableWidth
    clip: true

    readonly property string koFiUrl: "https://ko-fi.com/frperoger"
    readonly property string paypalUrl: ""
    readonly property string pixCode: "00020101021126580014br.gov.bcb.pix0136789a7654-3402-4298-b84f-04160c7f07d95204000053039865802BR5922ROGER DE FRANCA PELOSO6007DIADEMA62070503***63043414"
    readonly property url pixQrSource: Qt.resolvedUrl("images/pix-qr.png")
    readonly property int cardColumns: availableWidth >= 710 ? 3 : availableWidth >= 470 ? 2 : 1
    readonly property real cardSize: Math.min(232, Math.floor((availableWidth - (cardColumns - 1) * 12) / cardColumns))
    property string feedback: ""

    function openSupportPage(url) {
        feedback = Qt.openUrlExternally(url)
            ? "Obrigado por considerar apoiar o projeto! / Thanks for considering supporting the project!"
            : "Não foi possível abrir o navegador. / Couldn't open the browser."
    }

    function copyPixCode() {
        keyText.selectAll()
        keyText.copy()
        keyText.deselect()
        page.feedback = "Código Pix copiado. Obrigado pelo interesse em apoiar! / Pix code copied. Thanks for considering supporting the project!"
    }

    component Method: ShopCard {
        id: method
        objectName: method.title + "Card"
        property string description
        property string actionLabel
        property url logo
        property url qrCode
        readonly property bool hasQrCode: qrCode.toString() !== ""
        property bool available
        signal requested()
        signal qrRequested()
        Layout.preferredWidth: page.cardSize
        Layout.preferredHeight: page.cardSize
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 12
            Button {
                id: logoButton
                objectName: method.title + "Logo"
                implicitWidth: method.hasQrCode ? 72 : 90
                implicitHeight: 62
                enabled: method.available
                Accessible.name: method.actionLabel
                onClicked: method.requested()
                contentItem: Image {
                    source: method.logo
                    fillMode: Image.PreserveAspectFit
                }
                background: Rectangle {
                    radius: 7
                    color: logoButton.hovered ? "#d9e8fa" : "#ffffff"
                    border.color: logoButton.visualFocus ? "#6eaaff" : "transparent"
                }
            }
            Button {
                id: qrButton
                objectName: method.title + "Qr"
                visible: method.hasQrCode
                implicitWidth: 120
                implicitHeight: 120
                padding: 6
                Accessible.name: "Ampliar QR Code Pix / Enlarge Pix QR code"
                ToolTip.visible: hovered
                ToolTip.text: "Clique para ampliar / Click to enlarge"
                onClicked: method.qrRequested()
                contentItem: Image {
                    source: method.qrCode
                    fillMode: Image.PreserveAspectFit
                    smooth: false
                }
                background: Rectangle {
                    color: "#ffffff"
                    radius: 4
                    border.width: 2
                    border.color: qrButton.hovered || qrButton.visualFocus ? "#6eaaff" : "#ffffff"
                }
            }
        }
        Label {
            visible: !method.hasQrCode
            Layout.fillWidth: true
            Layout.fillHeight: true
            verticalAlignment: Text.AlignVCenter
            text: method.description
            wrapMode: Text.WordWrap
            color: "#b7c5d8"
        }
        ShopButton {
            objectName: method.title + "Action"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.preferredHeight: 46
            wrapLabel: true
            text: method.available ? method.actionLabel : "Indisponível\nUnavailable"
            enabled: method.available
            onClicked: method.requested()
        }
    }

    ColumnLayout {
        width: Math.min(page.availableWidth, 740)
        spacing: 12
        Label { text: "Apoie o projeto / Support the project"; font.pixelSize: 22; font.bold: true }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "O apoio é voluntário. / Contributions are optional."
            color: "#b7c5d8"
        }
        GridLayout {
            columns: page.cardColumns
            columnSpacing: 12
            rowSpacing: 12
            Method {
                title: "Ko-fi"
                logo: "logos/kofi.png"
                description: "Apoio internacional pela página do projeto. / International support via the project page."
                actionLabel: "Abrir Ko-fi\nOpen Ko-fi"
                available: /^https:\/\/ko-fi\.com\/[a-zA-Z0-9_-]+\/?$/.test(page.koFiUrl)
                onRequested: page.openSupportPage(page.koFiUrl)
            }
            Method {
                title: "PayPal"
                logo: "logos/paypal.svg"
                description: "Apoio direto pelo PayPal.Me. / Direct support via PayPal.Me."
                actionLabel: "Abrir PayPal\nOpen PayPal"
                available: /^https:\/\/paypal\.me\/[a-zA-Z0-9]+\/?$/.test(page.paypalUrl)
                onRequested: page.openSupportPage(page.paypalUrl)
            }
            Method {
                title: "Pix · Brasil"
                logo: "logos/pix.png"
                qrCode: page.pixQrSource
                description: "Cole o código no app do seu banco. / Paste the code into your banking app."
                actionLabel: "Copiar código Pix\nCopy Pix code"
                available: page.pixCode !== ""
                onRequested: page.copyPixCode()
                onQrRequested: pixQrDialog.open()
                TextEdit { id: keyText; visible: false; readOnly: true; text: page.pixCode }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: text !== ""
            text: page.feedback
            wrapMode: Text.WordWrap
            color: "#8de3ab"
        }
    }

    Popup {
        id: pixQrDialog
        objectName: "pixQrDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(392, parent.width - 36)
        readonly property real qrSide: Math.min(320, Math.max(144, parent.height - 280))
        property bool copied: false
        onOpened: copied = false
        padding: 16
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            color: "#1a222e"
            border.color: "#506680"
            radius: 10
        }
        contentItem: ColumnLayout {
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: "Pix · Brasil"
                    color: "#edf1f7"
                    font.pixelSize: 18
                    font.bold: true
                }
                ShopButton {
                    objectName: "closePixQr"
                    text: "Fechar / Close"
                    implicitHeight: 28
                    onClicked: pixQrDialog.close()
                }
            }
            Label {
                Layout.fillWidth: true
                text: "Escaneie no app do banco.\nScan with your banking app."
                color: "#b7c5d8"
                wrapMode: Text.WordWrap
            }
            Rectangle {
                objectName: "pixQrFrame"
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: pixQrDialog.qrSide
                Layout.preferredHeight: pixQrDialog.qrSide
                color: "#ffffff"
                Image {
                    objectName: "pixQrImage"
                    anchors.fill: parent
                    anchors.margins: 10
                    source: page.pixQrSource
                    fillMode: Image.PreserveAspectFit
                    smooth: false
                    Accessible.name: "QR Code para doação via Pix / Pix donation QR code"
                }
            }
            ShopButton {
                objectName: "copyPixFromQr"
                Layout.fillWidth: true
                implicitHeight: 46
                text: pixQrDialog.copied ? "Código Pix copiado\nPix code copied" : "Copiar código Pix\nCopy Pix code"
                wrapLabel: true
                primary: true
                onClicked: {
                    page.copyPixCode()
                    pixQrDialog.copied = true
                }
            }
        }
    }
}
