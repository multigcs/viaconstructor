"""dxfpreview tool."""

import argparse
import importlib
import os.path
import sys
from os import environ

from PIL import Image, ImageDraw, ImageFont

reader_plugins: dict = {}
for reader in ("dxfread", "hpglread", "stlread", "svgread", "ttfread"):
    try:
        drawing_reader = importlib.import_module(
            f".{reader}", "viaconstructor.input_plugins"
        )
        reader_plugins[reader] = drawing_reader.DrawReader
    except Exception as reader_error:  # pylint: disable=W0703
        print(f"ERRO while loading input plugin {reader}: {reader_error}")


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
    parser.add_argument("filename", help="input file", type=str)
    parser.add_argument("-x", "--width", help="screen width", type=int, default=800)
    parser.add_argument("-y", "--height", help="screen height", type=int, default=600)
    parser.add_argument("-o", "--output", help="save to image", type=str, default=None)
    parser.add_argument("-g", "--grid", help="show grid", type=int, default=1)
    parser.add_argument("-l", "--legend", help="show legend", type=int, default=1)

    for reader_plugin in reader_plugins.values():
        reader_plugin.arg_parser(parser)

    args = parser.parse_args()

    # setup
    filename = args.filename
    screen_width = args.width
    screen_height = args.height
    screen_color = (0, 0, 0)
    offset_x = 10
    offset_y = 10

    suffix = filename.split(".")[-1].lower()
    for reader_plugin in reader_plugins.values():
        if suffix in reader_plugin.suffix():
            reader = reader_plugin(filename, args)
            break

    if not reader:
        print(f"ERROR: can not load file: {filename}")
        sys.exit(1)

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
    if args.grid == 1:
        for pos_x in range(0, int(size[0]), 10):
            draw_line((pos_x, 0.0), (pos_x, size[1]), color=(27, 27, 27))
        for pos_y in range(0, int(size[1]), 10):
            draw_line((0.0, pos_y), (size[0], pos_y), color=(27, 27, 27))

    # draw path
    reader.draw(draw_line)

    # draw info
    if args.legend == 1:
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
