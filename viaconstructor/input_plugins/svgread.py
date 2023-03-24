"""svg reading."""

import argparse
import math
import shutil
import time

import ezdxf

from ..calc import calc_distance  # pylint: disable=E0402
from ..ext import svgpathtools
from ..input_plugins_base import DrawReaderBase
from ..vc_types import VcSegment


class DrawReader(DrawReaderBase):
    MIN_DIST = 0.0001

    can_save_setup = True
    can_load_setup = True
    cam_setup = ""
    as_lines = False

    backup_ok = False

    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--svgread-as-lines",
            help="svgread: load arcs as lines",
            type=bool,
            default=False,
        )

    @staticmethod
    def preload_setup(filename: str, args: argparse.Namespace):  # pylint: disable=W0613
        from PyQt5.QtWidgets import (  # pylint: disable=E0611,C0415
            QCheckBox,
            QDialog,
            QDialogButtonBox,
            QLabel,
            QVBoxLayout,
        )

        dialog = QDialog()
        dialog.setWindowTitle("SVG-Reader")

        dialog.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        dialog.buttonBox.accepted.connect(dialog.accept)

        dialog.layout = QVBoxLayout()
        message = QLabel("Import-Options")
        dialog.layout.addWidget(message)

        svgread_as_lines = QCheckBox("arcs as lines ?")
        svgread_as_lines.setChecked(args.svgread_as_lines)
        dialog.layout.addWidget(svgread_as_lines)

        dialog.layout.addWidget(dialog.buttonBox)
        dialog.setLayout(dialog.layout)

        if dialog.exec():
            args.svgread_as_lines = svgread_as_lines.isChecked()

    def __init__(
        self, filename: str, args: argparse.Namespace = None
    ):  # pylint: disable=W0613
        """converting svg into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        (
            paths,
            attributes,  # pylint: disable=W0612
            svg_attributes,
        ) = svgpathtools.svg2paths2(self.filename)

        if args is not None:
            self.as_lines = args.svgread_as_lines

        # read setup data from svg
        rawdata = open(self.filename, "r").read()
        setupdata = []
        setupflag = False
        for line in rawdata.split("\n"):
            if line == "<!-- viaconstructor:setup":
                setupflag = True
            elif line == "-->":
                setupflag = False
            elif setupflag:
                setupdata.append(line)

        if setupdata:
            self.cam_setup = "\n".join(setupdata).strip()

        height = 0.0
        size_attr = svg_attributes.get("-viewBox", "").split()
        if len(size_attr) == 4:
            height = float(size_attr[3])
        else:
            height_attr = svg_attributes.get("height")
            if height_attr and height_attr.endswith("mm"):
                height = float(height_attr[0:-2])
        part_l = len(paths)
        for part_n, path in enumerate(paths):
            print(f"loading file: {round((part_n + 1) * 100 / part_l, 1)}%", end="\r")

            try:
                # check if circle
                if (  # pylint: disable=R0916
                    not self.as_lines
                    and len(path) == 2
                    and isinstance(path[0], svgpathtools.path.Arc)
                    and isinstance(path[1], svgpathtools.path.Arc)
                    and path.start == path.end
                    and path[0].radius.real == path[0].radius.imag
                    and path[1].radius.real == path[1].radius.imag
                    and path[0].rotation == 0.0
                    and path[1].rotation == 0.0
                    and path[0].delta == -180.0
                    and path[1].delta == -180.0
                ):
                    self.add_arc(
                        (path[0].center.real, height - path[0].center.imag),
                        path[0].radius.real,
                    )
                else:
                    # print("##path", path)
                    for segment in path:
                        if isinstance(segment, svgpathtools.path.Line) or self.as_lines:
                            self._add_line(
                                (segment.start.real, height - segment.start.imag),
                                (segment.end.real, height - segment.end.imag),
                            )
                            last_x = segment.end.real
                            last_y = segment.end.imag
                        else:
                            last_x = segment.start.real
                            last_y = segment.start.imag
                            nump = int(segment.length() / 10) + 1
                            for point_n in range(0, nump):
                                pos = segment.point(point_n / nump)
                                self._add_line(
                                    (last_x, height - last_y),
                                    (pos.real, height - pos.imag),
                                )
                                last_x = pos.real
                                last_y = pos.imag

                            self._add_line(
                                (last_x, height - last_y),
                                (segment.end.real, height - segment.end.imag),
                            )
                            last_x = segment.end.real
                            last_y = segment.end.imag

                    if path.iscontinuous():
                        self._add_line(
                            (last_x, height - last_y),
                            (path[0].start.real, height - path[0].start.imag),
                        )
            except Exception as error:  # pylint: disable=W0703
                print("SVG ERROR:", error)
        print("")

        self.min_max = [0.0, 0.0, 10.0, 10.0]
        for seg_idx, segment in enumerate(self.segments):
            for point in ("start", "end"):
                if seg_idx == 0:
                    self.min_max[0] = segment[point][0]
                    self.min_max[1] = segment[point][1]
                    self.min_max[2] = segment[point][0]
                    self.min_max[3] = segment[point][1]
                else:
                    self.min_max[0] = min(self.min_max[0], segment[point][0])
                    self.min_max[1] = min(self.min_max[1], segment[point][1])
                    self.min_max[2] = max(self.min_max[2], segment[point][0])
                    self.min_max[3] = max(self.min_max[3], segment[point][1])

        self.size = []
        self.size.append(self.min_max[2] - self.min_max[0])
        self.size.append(self.min_max[3] - self.min_max[1])

    def add_arc(
        self, center, radius, start_angle=0.0, end_angle=360.0, layer="0"
    ) -> None:
        adiff = end_angle - start_angle
        if adiff < 0.0:
            adiff += 360.0
        # split arcs in maximum 20mm long segments and minimum 45°
        num_parts = (radius * 2 * math.pi) / 20.0
        if num_parts > 0:
            gstep = 360.0 / num_parts
        else:
            gstep = 1.0
        gstep = min(gstep, 45.0)
        steps = abs(math.ceil(adiff / gstep))
        if steps > 0:
            astep = adiff / steps
            angle = start_angle
            for _step_n in range(0, steps):  # pylint: disable=W0612
                (start, end, bulge) = ezdxf.math.arc_to_bulge(
                    center,
                    angle / 180 * math.pi,
                    (angle + astep) / 180 * math.pi,
                    radius,
                )
                dist = calc_distance((start.x, start.y), (end.x, end.y))
                if dist > self.MIN_DIST:
                    self.segments.append(
                        VcSegment(
                            {
                                "type": "ARC",
                                "object": None,
                                "layer": layer,
                                "start": (start.x, start.y),
                                "end": (end.x, end.y),
                                "bulge": bulge,
                                "center": (
                                    center[0],
                                    center[1],
                                ),
                            }
                        )
                    )
                angle += astep

        else:
            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                center,
                start_angle / 180 * math.pi,
                end_angle / 180 * math.pi,
                radius,
            )
            dist = calc_distance((start.x, start.y), (end.x, end.y))
            if dist > self.MIN_DIST:
                self.segments.append(
                    VcSegment(
                        {
                            "type": "ARC",
                            "object": None,
                            "layer": layer,
                            "start": (start.x, start.y),
                            "end": (end.x, end.y),
                            "bulge": bulge,
                            "center": (
                                center[0],
                                center[1],
                            ),
                        }
                    )
                )

    def save_setup(self, setup: str) -> None:

        if not self.backup_ok:
            try:
                shutil.copy2(self.filename, f"{self.filename}.{int(time.time())}")
                self.backup_ok = True
            except Exception as error:  # pylint: disable=W0703
                print(f"ERROR: can not make backup of file: {self.filename}: {error}")
                return

        rawdata = open(self.filename, "r").read()
        svgdata = []
        setupflag = False
        for line in rawdata.split("\n"):
            if line == "<!-- viaconstructor:setup":
                setupflag = True
            elif line == "-->":
                setupflag = False
            elif not setupflag:
                svgdata.append(line)

        svgdata.append("<!-- viaconstructor:setup")
        svgdata.append(setup)
        svgdata.append("-->")
        try:
            open(self.filename, "w").write("\n".join(svgdata).strip())
            self.cam_setup = setup
        except Exception as save_error:  # pylint: disable=W0703
            print(
                f"ERROR while saving setup to svg file ({self.filename}): {save_error}"
            )

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        return ["svg"]
