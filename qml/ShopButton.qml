import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property bool primary: false
    property bool danger: false
    property bool selected: false
    property bool wrapLabel: false
    implicitHeight: 35
    leftPadding: 12
    rightPadding: 12
    Accessible.name: qsTr(control.text)
    contentItem: Text {
        text: qsTr(control.text)
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: control.wrapLabel ? Text.Wrap : Text.NoWrap
        color: !control.enabled ? "#8996a9" : control.primary ? "#101c2d" : "#edf1f7"
    }
    background: Rectangle {
        radius: 6
        color: !control.enabled ? "#202936"
             : control.primary ? (control.down ? "#82b6ff" : "#a6ccff")
             : control.danger ? (control.hovered ? "#8c3947" : "#6b2835")
             : control.selected ? "#365374"
             : control.hovered || control.down ? "#34455b" : "#263246"
        border.color: control.visualFocus ? "#83b6ff" : "transparent"
    }
}
