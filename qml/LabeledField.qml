import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ColumnLayout {
    id: field
    property string title
    property string currency
    property string value
    property alias editor: entry
    property alias validator: entry.validator
    property alias inputMethodHints: entry.inputMethodHints
    signal committed(string value)
    spacing: 4

    RowLayout {
        Layout.fillWidth: true
        spacing: 5
        Image {
            objectName: field.currency ? field.currency + "FieldIcon" : ""
            visible: field.currency !== ""
            source: visible ? "image://shop/" + field.currency : ""
            Layout.preferredWidth: 15
            Layout.preferredHeight: 15
            fillMode: Image.PreserveAspectFit
        }
        Label {
            Layout.fillWidth: true
            text: field.title
            color: "#b7c5d8"
            wrapMode: Text.WordWrap
        }
    }
    TextField {
        id: entry
        Layout.fillWidth: true
        Layout.minimumWidth: 52
        implicitHeight: 34
        text: field.value
        selectByMouse: true
        Accessible.name: field.title
        onEditingFinished: {
            if (acceptableInput && text !== field.value)
                field.committed(text)
            if (!acceptableInput)
                text = Qt.binding(() => field.value)
        }
        background: Rectangle {
            color: entry.enabled ? "#121923" : "#202936"
            border.color: entry.activeFocus ? "#83b6ff" : "#35465d"
            radius: 6
        }
    }
}
