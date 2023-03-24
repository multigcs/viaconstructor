"""img reading."""

import argparse

from PIL import Image

from ..calc import lines_to_path  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase


class DrawReader(DrawReaderBase):
    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--imgread-scale",
            help="imgread: scale (mm/pixel)",
            type=float,
            default=0.1,
        )
        parser.add_argument(
            "--imgread-threshold",
            help="imgread: threshold value (1-255)",
            type=int,
            default=127,
        )
        parser.add_argument(
            "--imgread-lines",
            help="imgread: do not merge lines",
            action="store_true",
        )

    def __init__(
        self, filename: str, args: argparse.Namespace = None  # pylint: disable=W0613
    ):
        """slicing and converting stl into single segments."""
        self.filename = filename
        self.segments = []

        image_data = Image.open(filename).convert("L")

        print(f"Image-Size: {image_data.width}x{image_data.height}")

        scale = args.imgread_scale
        laser_on = False
        last = (0, 0)
        lines = []

        pixel = image_data.getpixel((0, 0))
        mid_value = args.imgread_threshold
        if isinstance(pixel, tuple):
            mid_value = tuple([mid_value] * len(pixel))

        height = image_data.height
        for y_pos in range(0, image_data.height):
            for x_pos in range(0, image_data.width):
                pixel = image_data.getpixel((x_pos, y_pos))
                if not laser_on and pixel < mid_value:
                    laser_on = True
                    last = (x_pos, height - y_pos)
                elif laser_on and pixel >= mid_value:
                    laser_on = False
                    lines.append((last, (x_pos, height - y_pos)))
            if laser_on:
                laser_on = False
                lines.append((last, (x_pos, height - y_pos)))

        output_lines = lines_to_path(lines, max_vdist=1, max_dist=3)

        for line in output_lines:
            self._add_line(
                (line[0][0] * scale, line[0][1] * scale),
                (line[1][0] * scale, line[1][1] * scale),
            )

        self._calc_size()

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        return ["jpg", "bmp", "png", "gif", "tif"]
