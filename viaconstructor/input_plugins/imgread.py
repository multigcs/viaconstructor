"""dxf reading."""

import argparse

from PIL import Image

from ..calc import calc_distance  # pylint: disable=E0402
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

        image_data = Image.open(filename)
        print(f"Image-Size: {image_data.width}x{image_data.height}")

        def get_next_line(end_point):
            selected = -1
            nearest = 1000000
            reverse = 0
            for idx, line in enumerate(lines):
                dist = calc_distance(end_point, line[0])
                if dist < nearest:
                    selected = idx
                    nearest = dist
                    reverse = 0

                dist = calc_distance(end_point, line[1])
                if dist < nearest:
                    selected = idx
                    nearest = dist
                    reverse = 1

            if selected != -1:
                line = lines.pop(selected)
                if reverse:
                    line = (line[1], line[0])
                return (nearest, line)
            return None

        scale = args.imgread_scale
        laser_on = False
        last = (0, 0)
        lines = []
        height = image_data.height
        for y_pos in range(0, image_data.height):
            for x_pos in range(0, image_data.width):
                pixel = image_data.getpixel((x_pos, y_pos))
                if not laser_on and pixel < 127:
                    laser_on = True
                    last = (x_pos, height - y_pos)
                elif laser_on and pixel >= 127:
                    laser_on = False
                    lines.append((last, (x_pos, height - y_pos)))
            if laser_on:
                laser_on = False
                lines.append((last, (x_pos, height - y_pos)))

        # optimize / adding bridges
        output_lines = []
        if args.imgread_lines:
            output_lines = lines
        else:
            last_line = lines.pop(0)
            output_lines.append((last_line[0], last_line[1]))
            while True:
                check = get_next_line(last_line[1])
                if check is None:
                    break
                dist = check[0]
                next_line = check[1]
                vdist = abs(last_line[0][1] - next_line[0][1])
                if vdist == 1:
                    if dist <= 3:
                        output_lines.append((last_line[1], next_line[0]))
                    elif last_line[0][0] <= next_line[0][0] <= last_line[1][0]:
                        output_lines.append((last_line[1], next_line[0]))
                    elif last_line[1][0] <= next_line[0][0] <= last_line[0][0]:
                        output_lines.append((last_line[1], next_line[0]))
                    elif next_line[0][0] <= last_line[1][0] <= next_line[1][0]:
                        output_lines.append((last_line[1], next_line[0]))
                    elif next_line[1][0] <= last_line[1][0] <= next_line[0][0]:
                        output_lines.append((last_line[1], next_line[0]))
                output_lines.append((next_line[0], next_line[1]))
                last_line = next_line

        for line in output_lines:
            self._add_line(
                (line[0][0] * scale, line[0][1] * scale),
                (line[1][0] * scale, line[1][1] * scale),
            )

        self._calc_size()

    @staticmethod
    def suffix() -> list[str]:
        return ["jpg", "bmp", "png", "gif", "tif"]
