import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: preview
    required property var backend
    readonly property var settings: backend.calibration
    implicitHeight: 245
    radius: 7
    color: "#121923"
    clip: true

    Image {
        id: capture
        anchors.fill: parent
        source: preview.backend.info.captureImage
        cache: false
        fillMode: Image.PreserveAspectFit
    }
    Label {
        anchors.centerIn: parent
        visible: capture.status !== Image.Ready
        text: qsTr("Carregue uma imagem da loja")
        color: "#b7c5d8"
    }

    component Outline: Rectangle {
        id: outline
        required property var coords
        required property color tint
        property bool overlay: false
        x: coords[0] * canvas.width
        y: coords[1] * canvas.height
        width: Math.max(0, (coords[2] - coords[0]) * canvas.width)
        height: Math.max(0, (coords[3] - coords[1]) * canvas.height)
        border.color: tint
        border.width: 2
        color: Qt.rgba(tint.r, tint.g, tint.b, 0.20)
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            width: 9
            height: 9
            color: outline.tint
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            property point origin
            property var initial
            property bool resizing
            function isCorner(x, y) { return x >= width - 12 && y >= height - 12 }
            cursorShape: isCorner(mouseX, mouseY) ? Qt.SizeFDiagCursor : Qt.SizeAllCursor
            onPressed: function(mouse) {
                origin = mapToItem(canvas, mouse.x, mouse.y)
                initial = [outline.coords[0], outline.coords[1], outline.coords[2], outline.coords[3]]
                resizing = isCorner(mouse.x, mouse.y)
            }
            onPositionChanged: function(mouse) {
                if (!pressed || !initial || canvas.width <= 0 || canvas.height <= 0)
                    return
                const point = mapToItem(canvas, mouse.x, mouse.y)
                preview.backend.dragRectangle(outline.overlay, initial,
                    (point.x - origin.x) / canvas.width, (point.y - origin.y) / canvas.height, resizing)
            }
        }
    }

    Item {
        id: canvas
        anchors.centerIn: parent
        width: capture.status === Image.Ready ? capture.paintedWidth : preview.width
        height: capture.status === Image.Ready ? capture.paintedHeight : preview.height
        Outline { objectName: "safeAreaOutline"; coords: preview.settings.safeArea; tint: "#7fe58f" }
        Outline {
            coords: preview.settings.overlayArea
            tint: "#6eaaff"
            overlay: true
            visible: preview.settings.compact
        }
    }
}
