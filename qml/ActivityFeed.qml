import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ListView {
    id: feed
    objectName: "activityLog"
    spacing: 7
    clip: true
    rightMargin: 10
    property bool followLatest: true
    ScrollBar.vertical: ScrollBar {}

    footer: Item {
        width: feed.width
        height: feed.count === 0 ? 64 : 0
        visible: feed.count === 0
        Label {
            anchors.centerIn: parent
            text: "Os eventos da execução aparecerão aqui."
            color: "#b7c5d8"
        }
    }

    Connections {
        target: feed.model
        function onRowsAboutToBeInserted() {
            feed.followLatest = feed.atYEnd || feed.count === 0
        }
        function onRowsInserted() {
            if (feed.followLatest)
                Qt.callLater(feed.positionViewAtEnd)
        }
    }

    delegate: Rectangle {
        id: eventCard
        required property string eventTime
        required property string eventLevel
        required property string eventMessage
        readonly property var categories: ({
            "info": ["Informação", "#9ec7ff", "#253950"],
            "ok": ["Sucesso", "#8de3ab", "#1e4033"],
            "warn": ["Atenção", "#ffd284", "#463820"],
            "error": ["Erro", "#ffacb6", "#472831"]
        })
        readonly property var category: categories[eventLevel] || categories.info
        width: feed.width - feed.rightMargin
        height: content.implicitHeight + 20
        radius: 7
        color: "#141d29"
        border.color: "#2e3b4d"

        ColumnLayout {
            id: content
            anchors.fill: parent
            anchors.margins: 10
            spacing: 7
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Rectangle {
                    implicitWidth: levelLabel.implicitWidth + 14
                    implicitHeight: levelLabel.implicitHeight + 6
                    radius: 4
                    color: eventCard.category[2]
                    Label {
                        id: levelLabel
                        anchors.centerIn: parent
                        text: eventCard.category[0]
                        color: eventCard.category[1]
                        font.bold: true
                        font.pixelSize: 12
                    }
                }
                Item { Layout.fillWidth: true }
                Label { text: eventCard.eventTime; color: "#b7c5d8"; font.pixelSize: 12 }
            }
            TextEdit {
                Layout.fillWidth: true
                text: eventCard.eventMessage
                textFormat: TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: "#edf1f7"
                selectionColor: "#365374"
                selectedTextColor: "#ffffff"
            }
        }
    }
}
