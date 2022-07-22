"""gcodepreview tool."""

import argparse
import os.path
import sys
from os import environ

from PIL import Image, ImageDraw, ImageFont

from viaconstructor.preview_plugins.gcode import GcodeParser


def main() -> int:
    """main function."""

    def draw_line(p_1, p_2, fast=False, color=None):
        """drawing function."""
        p_from = (
            offset_x + (p_1["X"] - minmax[0]) * scale,
            screen_height - (offset_y + (p_1["Y"] - minmax[1]) * scale),
        )
        p_to = (
            offset_x + (p_2["X"] - minmax[0]) * scale,
            screen_height - (offset_y + (p_2["Y"] - minmax[1]) * scale),
        )
        if not color:
            if p_2["Z"] <= 0.0 and fast:
                color = (255, 0, 0)
            if p_1["Z"] > 0.0 and p_2["Z"] > 0.0:
                color = (0, 255, 0)
            else:
                color = (200, 200, 255)
        draw.line(p_from + p_to, fill=color)

    # arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="gcode file", type=str)
    parser.add_argument("-x", "--width", help="screen width", type=int, default=800)
    parser.add_argument("-y", "--height", help="screen height", type=int, default=600)
    parser.add_argument("-o", "--output", help="save to image", type=str, default=None)
    args = parser.parse_args()

    # setup
    filename = args.filename
    screen_width = args.width
    screen_height = args.height
    screen_color = (0, 0, 0)
    offset_x = 10
    offset_y = 10

    # parse gcode
    if not os.path.isfile(filename):
        print("file not found:", filename)
        sys.exit(1)
    gcode = open(filename, "r").read()
    gcode_parser = GcodeParser(gcode)
    minmax = gcode_parser.get_minmax()
    size = gcode_parser.get_size()

    # calc scale
    scale_x = (screen_width - 10) / size[0]
    scale_y = (screen_height - 10) / size[1]
    scale = min(scale_x, scale_y)

    offset_x = (screen_width - (size[0] * scale)) / 2.0
    offset_y = (screen_height - (size[1] * scale)) / 2.0

    # init output
    out = Image.new("RGB", (screen_width, screen_height), screen_color)
    fnt = ImageFont.truetype("FreeMono.ttf", 24)
    draw = ImageDraw.Draw(out)

    # draw grid
    for pos_x in range(0, int(size[0]), 10):
        draw_line(
            {"X": pos_x, "Y": 0.0}, {"X": pos_x, "Y": size[1]}, color=(27, 27, 27)
        )
    for pos_y in range(0, int(size[1]), 10):
        draw_line(
            {"X": 0.0, "Y": pos_y}, {"X": size[0], "Y": pos_y}, color=(27, 27, 27)
        )

    # draw path
    gcode_parser.draw(draw_line)

    # draw info
    if screen_width >= 320 or screen_height >= 240:
        info = f"W={round(size[0], 2)}\nH={round(size[1], 2)}\nminZ={minmax[2]}"
        draw.multiline_text((5, 5), info, font=fnt, fill=(255, 255, 255))

    if args.output:
        # save to image
        out.save(args.output)
    else:
        # display with pygame
        environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        import pygame  # pylint: disable=C0415
        from pygame.locals import QUIT  # pylint: disable=C0415,E0611

        pygame.init()  # pylint: disable=E1101
        pygame.display.set_caption(f"gcodepreview ({filename})")
        screen = pygame.display.set_mode((screen_width, screen_height))
        screen.blit(
            pygame.image.fromstring(out.tobytes(), out.size, out.mode).convert(), (0, 0)
        )
        pygame.display.flip()
        while True:
            for events in pygame.event.get():
                if events.type == QUIT:
                    return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
