import QtQuick
import QtQuick.Controls.Basic

ProgressBar {
    id: meter
    property color tint: "#6eaaff"
    implicitHeight: 6
    background: Rectangle {
        implicitHeight: 6
        radius: 3
        color: "#35465d"
    }
    contentItem: Item {
        Rectangle {
            width: parent.width * meter.visualPosition
            height: parent.height
            radius: 3
            color: meter.tint
        }
    }
}
