"""dxf reading."""

import argparse

import freetype

from ..calc import quadratic_bezier  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase


class DrawReader(DrawReaderBase):
    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--tftread-text",
            help="tftread: text for the Truetype reader",
            type=str,
            default="ViaConstructor",
        )
        parser.add_argument(
            "--tftread-height",
            help="text height for the Truetype reader",
            type=float,
            default=100,
        )

    def __init__(self, filename: str, args: argparse.Namespace = None):
        """slicing and converting stl into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        face = freetype.Face(self.filename)
        face.set_char_size(18 * 64)

        scale = args.tftread_height / 1000.0  # type: ignore

        ctx = {
            "last": (),
            "pos": [0, 0],
            "max": 0,
            "scale": (scale, scale),
        }

        for char in args.tftread_text:  # type: ignore
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
        print(
            f"UNSUPPORTED 2nd Cubic Bezier: {point_a.x},{point_a.y} {point_b.x},{point_b.y} {point_c.x},{point_c.y}: {ctx}"
        )

    @staticmethod
    def suffix() -> list[str]:
        return ["ttf"]
