"""dxfpreview tool."""

import argparse
import os.path
import sys
from os import environ

from PIL import Image, ImageDraw, ImageFont

from viaconstructor.dxfread import DxfReader
from viaconstructor.hpglread import HpglReader
from viaconstructor.svgread import SvgReader


def main() -> int:
    """main function."""

    def draw_line(p_1, p_2, fast=False, color=None):
        """drawing function."""
        p_from = (
            offset_x + (p_1[0] - minmax[0]) * scale,
            screen_height - (offset_y + (p_1[1] - minmax[1]) * scale),
        )
        p_to = (
            offset_x + (p_2[0] - minmax[0]) * scale,
            screen_height - (offset_y + (p_2[1] - minmax[1]) * scale),
        )
        if not color:
            color = (200, 200, 255)
        draw.line(p_from + p_to, fill=color)

    # arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="dxf file", type=str)
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

    # parse dxf
    if not os.path.isfile(filename):
        print("file not found:", filename)
        sys.exit(1)
    if filename.lower().endswith(".svg"):
        reader = SvgReader(filename)
    elif filename.lower().endswith(".hpgl"):
        reader = HpglReader(filename)
    else:
        reader = DxfReader(filename)
    minmax = reader.get_minmax()

    size = reader.get_size()

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
        draw_line((pos_x, 0.0), (pos_x, size[1]), color=(27, 27, 27))
    for pos_y in range(0, int(size[1]), 10):
        draw_line((0.0, pos_y), (size[0], pos_y), color=(27, 27, 27))

    # draw path
    reader.draw(draw_line)

    # draw info
    if screen_width >= 320 or screen_height >= 240:
        info = f"W={round(size[0], 2)}\nH={round(size[1], 2)}"
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
        pygame.display.set_caption(f"dxfpreview ({filename})")
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
