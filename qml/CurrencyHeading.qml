import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

RowLayout {
    id: row
    property string currency
    property string title
    spacing: 7
    Image {
        source: "image://shop/" + row.currency
        Layout.preferredWidth: 20
        Layout.preferredHeight: 20
        fillMode: Image.PreserveAspectFit
    }
    Label {
        Layout.fillWidth: true
        text: row.title
        color: "#edf1f7"
        wrapMode: Text.WordWrap
    }
}
