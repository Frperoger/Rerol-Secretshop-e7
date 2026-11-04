import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: card
    property string title
    default property alias contents: body.data
    color: "#1a222e"
    border.color: "#2e3b4d"
    radius: 10
    implicitWidth: body.implicitWidth + 28
    implicitHeight: body.implicitHeight + 28

    children: [ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10
        Label {
            text: card.title
            visible: text !== ""
            color: "#edf1f7"
            font.bold: true
            font.pixelSize: 15
        }
    }]
}
