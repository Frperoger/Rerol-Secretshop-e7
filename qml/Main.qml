import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: main
    required property var backend
    width: 1110
    height: 760
    minimumWidth: 780
    minimumHeight: 560
    visible: false
    title: "Epic7 Shop Bot — Desktop"
    color: "#10151d"
    palette.window: "#10151d"
    palette.windowText: "#edf1f7"
    palette.text: "#edf1f7"
    palette.base: "#121923"
    palette.button: "#263246"
    palette.buttonText: "#edf1f7"
    palette.highlight: "#83b6ff"
    palette.highlightedText: "#10151d"
    palette.mid: "#35465d"

    onClosing: function(event) { event.accepted = backend.closeWindow() }
    Connections {
        target: main.backend
        function onBudgetFocusRequested() { budgetPage.focusGems() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Label {
                text: "Epic7&nbsp; · &nbsp;<font color='#ff5d68'>Shop Bot</font>"
                textFormat: Text.StyledText
                font.pixelSize: 25
                font.bold: true
                topPadding: 7
                leftPadding: 8
                Accessible.name: "Epic7 Shop Bot"

                Image {
                    anchors.top: parent.top
                    anchors.topMargin: 3
                    anchors.left: parent.left
                    width: 24
                    height: 17
                    source: "logos/fedora.svg"
                    fillMode: Image.PreserveAspectFit
                    Accessible.ignored: true
                }
            }
            Item { Layout.fillWidth: true }
            Label {
                text: main.backend.info.status
                color: ["erro", "resultado_incerto"].includes(main.backend.info.statusCode) ? "#ff9aa8"
                     : main.backend.info.statusCode.startsWith("pausado") ? "#f3bb55"
                     : main.backend.info.running ? "#83b6ff" : "#b8c7db"
                font.bold: true
            }
        }
        RowLayout {
            spacing: 6
            Repeater {
                model: ["Bot", "Itens", "Orçamento", "Calibração", "Relatório", "Donates"]
                delegate: ShopButton {
                    required property int index
                    required property string modelData
                    objectName: "tab" + index
                    text: modelData
                    selected: main.backend.page === index
                    enabled: !main.backend.info.running || index === 0 || index === 2 || index === 4 || index === 5
                    onClicked: main.backend.selectPage(index)
                }
            }
        }
        StackLayout {
            objectName: "pageStack"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: main.backend.page
            BotPage { backend: main.backend }
            ItemsPage { backend: main.backend }
            BudgetPage { id: budgetPage; backend: main.backend }
            CalibrationPage { backend: main.backend }
            ReportsPage { backend: main.backend }
            DonatesPage {}
        }
    }

    CompactWindow { objectName: "compactWindow" }
}
