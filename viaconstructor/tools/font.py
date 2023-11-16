import os
from pathlib import Path

import freetype
from PyQt5.QtCore import QLineF, QStandardPaths, Qt  # pylint: disable=E0611
from PyQt5.QtGui import QPainter, QPen, QPixmap  # pylint: disable=E0611
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..calc import point_of_line, quadratic_bezier


class FontTool(QWidget):
    painter = None

    def __init__(self, app):
        super().__init__()
        self.setWindowTitle("Font-Tool")
        self.app = app
        layout = QVBoxLayout()
        self.setLayout(layout)

        message = QLabel("Font-File")
        layout.addWidget(message)

        self.ttfread_fontfile = QComboBox()
        self.ttfread_fontfile.setToolTip("Font-File")
        layout.addWidget(self.ttfread_fontfile)

        label = QLabel("Text")
        layout.addWidget(label)

        self.ttfread_text = QPlainTextEdit()
        self.ttfread_text.setPlainText("Via")
        layout.addWidget(self.ttfread_text)

        label = QLabel("Height")
        layout.addWidget(label)
        self.ttfread_height = QDoubleSpinBox()
        self.ttfread_height.setDecimals(3)
        self.ttfread_height.setSingleStep(0.1)
        self.ttfread_height.setMinimum(0.0001)
        self.ttfread_height.setMaximum(100000)
        self.ttfread_height.setValue(100.0)
        layout.addWidget(self.ttfread_height)

        label = QLabel("Space")
        layout.addWidget(label)
        self.ttfread_space = QDoubleSpinBox()
        self.ttfread_space.setDecimals(3)
        self.ttfread_space.setSingleStep(0.1)
        self.ttfread_space.setMinimum(-100000)
        self.ttfread_space.setMaximum(100000)
        self.ttfread_space.setValue(0.0)
        layout.addWidget(self.ttfread_space)

        label = QLabel("Border")
        layout.addWidget(label)
        self.ttfread_border = QDoubleSpinBox()
        self.ttfread_border.setDecimals(3)
        self.ttfread_border.setSingleStep(0.1)
        self.ttfread_border.setMinimum(-1000)
        self.ttfread_border.setMaximum(1000)
        self.ttfread_border.setValue(0.0)
        layout.addWidget(self.ttfread_border)

        self.qimage_label = QLabel()
        layout.addWidget(self.qimage_label)

        font_paths = QStandardPaths.standardLocations(QStandardPaths.FontsLocation)

        self.fontfiles = {}
        for fpath in font_paths:  # go through all font paths
            if not os.path.isdir(fpath):
                continue
            for filename in Path(fpath).rglob("*.ttf"):
                self.fontfiles[str(os.path.basename(filename))] = str(filename)
            for filename in Path(fpath).rglob("*.otf"):
                self.fontfiles[str(os.path.basename(filename))] = str(filename)

        self.ttfread_fontfile.addItems(list(self.fontfiles))
        self.ttfread_fontfile.setEditable(True)
        self.ttfread_fontfile.setInsertPolicy(QComboBox.NoInsert)
        self.ttfread_fontfile.completer().setCompletionMode(QCompleter.PopupCompletion)

        self.ttfread_text.textChanged.connect(self.preview)  # type: ignore
        self.ttfread_space.valueChanged.connect(self.preview)  # type: ignore
        self.ttfread_fontfile.currentTextChanged.connect(self.preview)  # type: ignore

        def open_font():
            self.hide()
            fontfile = self.fontfiles.get(self.ttfread_fontfile.currentText())
            self.app.args.ttfread_text = self.ttfread_text.toPlainText()
            self.app.args.ttfread_height = self.ttfread_height.value()
            self.app.args.ttfread_space = self.ttfread_space.value()
            self.app.args.ttfread_border = self.ttfread_border.value()

            if self.app.load_drawing(fontfile, no_setup=True):
                # self.app.update_object_setup()
                # self.app.global_changed(0)
                # self.app.update_drawing()
                # self.app.create_menubar()
                # self.app.create_toolbar()
                pass

        self.button_open = QPushButton("Open")
        self.button_open.clicked.connect(open_font)
        layout.addWidget(self.button_open)

        self.button_close = QPushButton("Cancel")
        self.button_close.clicked.connect(self.close)
        layout.addWidget(self.button_close)

        self.preview()

    def preview(self, value=0):  # pylint: disable=W0613
        scale = 0.1
        text = self.ttfread_text.toPlainText()
        space = self.ttfread_space.value()
        fontfile = self.fontfiles.get(self.ttfread_fontfile.currentText())

        ctx = {
            "last": (),
            "pos": [0, 0],
            "max": 0,
            "scale": (scale, scale),
            "draw_line": self.draw_line_preview,
        }

        canvas = QPixmap(800, 100)
        self.qimage_label.setPixmap(canvas)
        self.qimage_label.adjustSize()
        self.qimage_label.pixmap().fill(Qt.white)
        self.painter = QPainter()
        self.painter.begin(self.qimage_label.pixmap())
        self.painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))

        try:
            face = freetype.Face(fontfile)
            face.set_char_size(1000)
            for char in text:  # type: ignore
                if char == " ":
                    ctx["pos"][0] += 800 * scale  # type: ignore
                    continue
                if char == "\n":
                    ctx["pos"][0] = 0  # type: ignore
                    ctx["pos"][1] -= 1000 * scale  # type: ignore
                    continue
                face.load_char(
                    char,
                    freetype.FT_LOAD_DEFAULT  # pylint: disable=E1101
                    | freetype.FT_LOAD_NO_BITMAP,  # pylint: disable=E1101
                )
                face.glyph.outline.decompose(
                    ctx,
                    move_to=self.move_to,
                    line_to=self.line_to,
                    conic_to=self.conic_to,
                    cubic_to=self.cubic_to,
                )
                ctx["pos"][0] = ctx["max"] + space  # type: ignore
                ctx["max"] = 0

        except Exception as error:  # pylint: disable=W0703
            print(f"ERROR: while loading font file: {fontfile}: {error}")

        self.painter.end()

    def draw_line_preview(self, point, ctx):
        self.painter.drawLine(
            QLineF(ctx["last"][0], 90 - ctx["last"][1], point[0], 90 - point[1])
        )

    def move_to(self, point_a, ctx):
        point = (
            point_a.x * ctx["scale"][0] + ctx["pos"][0],
            point_a.y * ctx["scale"][1] + ctx["pos"][1],
        )
        ctx["max"] = max(ctx["max"], point[0])
        ctx["last"] = point

    def line_to(self, point_a, ctx):
        point = (
            point_a.x * ctx["scale"][0] + ctx["pos"][0],
            point_a.y * ctx["scale"][1] + ctx["pos"][1],
        )
        ctx["max"] = max(ctx["max"], point[0])
        ctx["draw_line"](point, ctx)
        ctx["last"] = point

    def conic_to(self, point_a, point_b, ctx):
        start = ctx["last"]
        curv_pos = 0.0
        while curv_pos <= 1.0:
            point = quadratic_bezier(
                curv_pos,
                (
                    start,
                    (
                        point_a.x * ctx["scale"][0] + ctx["pos"][0],
                        point_a.y * ctx["scale"][1] + ctx["pos"][1],
                    ),
                    (
                        point_b.x * ctx["scale"][0] + ctx["pos"][0],
                        point_b.y * ctx["scale"][1] + ctx["pos"][1],
                    ),
                ),
            )
            ctx["max"] = max(ctx["max"], point[0])
            ctx["draw_line"](point, ctx)
            ctx["last"] = point
            curv_pos += 0.1

    def cubic_to(self, point_a, point_b, point_c, ctx):
        start = ctx["last"]
        curv_pos = 0.0
        while curv_pos <= 1.0:
            ctrl1 = (
                point_a.x * ctx["scale"][0] + ctx["pos"][0],
                point_a.y * ctx["scale"][1] + ctx["pos"][1],
            )
            ctrl2 = (
                point_b.x * ctx["scale"][0] + ctx["pos"][0],
                point_b.y * ctx["scale"][1] + ctx["pos"][1],
            )
            nextp = (
                point_c.x * ctx["scale"][0] + ctx["pos"][0],
                point_c.y * ctx["scale"][1] + ctx["pos"][1],
            )

            ctrl3ab = point_of_line(start, ctrl1, curv_pos)
            ctrl3bc = point_of_line(ctrl1, ctrl2, curv_pos)
            ctrl3 = point_of_line(ctrl3ab, ctrl3bc, curv_pos)
            ctrl4ab = point_of_line(ctrl1, ctrl2, curv_pos)
            ctrl4bc = point_of_line(ctrl2, nextp, curv_pos)
            ctrl4 = point_of_line(ctrl4ab, ctrl4bc, curv_pos)
            point = point_of_line(ctrl3, ctrl4, curv_pos)

            ctx["max"] = max(ctx["max"], point[0])
            ctx["draw_line"](point, ctx)
            ctx["last"] = point
            curv_pos += 0.1
