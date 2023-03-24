"""ttf reading."""

import argparse

import freetype

from ..calc import point_of_line, quadratic_bezier  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase


class DrawReader(DrawReaderBase):
    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--ttfread-text",
            help="ttfread: text for the Truetype reader",
            type=str,
            default="Via",
        )
        parser.add_argument(
            "--ttfread-height",
            help="text height for the Truetype reader",
            type=float,
            default=100,
        )

    @staticmethod
    def preload_setup(filename: str, args: argparse.Namespace):  # pylint: disable=W0613
        from PyQt5.QtWidgets import (  # pylint: disable=E0611,C0415
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QLabel,
            QLineEdit,
            QVBoxLayout,
        )

        dialog = QDialog()
        dialog.setWindowTitle("SVG-Reader")

        dialog.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        dialog.buttonBox.accepted.connect(dialog.accept)

        dialog.layout = QVBoxLayout()
        message = QLabel("Import-Options")
        dialog.layout.addWidget(message)

        label = QLabel("Text")
        dialog.layout.addWidget(label)
        ttfread_text = QLineEdit()
        ttfread_text.setText("Via")
        dialog.layout.addWidget(ttfread_text)

        label = QLabel("Height")
        dialog.layout.addWidget(label)
        ttfread_height = QDoubleSpinBox()
        ttfread_height.setDecimals(4)
        ttfread_height.setSingleStep(0.1)
        ttfread_height.setMinimum(0.0001)
        ttfread_height.setMaximum(100000)
        ttfread_height.setValue(100.0)
        dialog.layout.addWidget(ttfread_height)

        dialog.layout.addWidget(dialog.buttonBox)
        dialog.setLayout(dialog.layout)

        if dialog.exec():
            args.ttfread_text = ttfread_text.text()
            args.ttfread_height = ttfread_height.value()

    def __init__(self, filename: str, args: argparse.Namespace = None):
        """slicing and converting stl into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        face = freetype.Face(self.filename)
        face.set_char_size(18 * 64)

        scale = args.ttfread_height / 1000.0  # type: ignore

        ctx = {
            "last": (),
            "pos": [0, 0],
            "max": 0,
            "scale": (scale, scale),
        }

        part_l = len(args.ttfread_text)
        for part_n, char in enumerate(args.ttfread_text):  # type: ignore
            print(f"loading file: {round((part_n + 1) * 100 / part_l, 1)}%", end="\r")
            if char == " ":
                ctx["pos"][0] += 500 * scale  # type: ignore
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
            ctx["pos"][0] = ctx["max"]  # type: ignore
            ctx["max"] = 0
        print("")

        self.min_max = [0.0, 0.0, 10.0, 10.0]
        for seg_idx, segment in enumerate(self.segments):
            if seg_idx == 0:
                self.min_max[0] = segment.start[0]
                self.min_max[1] = segment.start[1]
                self.min_max[2] = segment.start[0]
                self.min_max[3] = segment.start[1]
            else:
                self.min_max[0] = min(self.min_max[0], segment.start[0])
                self.min_max[1] = min(self.min_max[1], segment.start[1])
                self.min_max[2] = max(self.min_max[2], segment.start[0])
                self.min_max[3] = max(self.min_max[3], segment.start[1])

                self.min_max[0] = min(self.min_max[0], segment.end[0])
                self.min_max[1] = min(self.min_max[1], segment.end[1])
                self.min_max[2] = max(self.min_max[2], segment.end[0])
                self.min_max[3] = max(self.min_max[3], segment.end[1])

        self.size = []
        self.size.append(self.min_max[2] - self.min_max[0])
        self.size.append(self.min_max[3] - self.min_max[1])

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
        self._add_line(ctx["last"], point)
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
            self._add_line(ctx["last"], point)
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
            self._add_line(ctx["last"], point)
            ctx["last"] = point
            curv_pos += 0.1

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        return ["ttf", "otf"]
