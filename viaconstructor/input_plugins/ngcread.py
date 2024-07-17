"""ngc reading."""

import argparse
import copy
import math
import math
import os
import re
import ezdxf

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402
from ..input_plugins_base import DrawReaderBase

COMMAND = re.compile("(?P<line>\d+) N\.* (?P<type>[A-Z_]+)\((?P<coords>.*)\)")

class DrawReader(DrawReaderBase):
    def __init__(self, filename: str, args: argparse.Namespace = None):  # pylint: disable=W0613
        """converting ngc into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        if os.path.isfile("/usr/bin/___rs274"):
            p = os.popen(f"rs274 -n 0 -g '{self.filename}'")
            output = p.readlines()
            r = p.close()
        else:
            print("WARNING: using fallback for rs274 interpreter, limited support")
            output = self.rs274(self.filename)

        last_pos = ()
        used_tools = []
        for line in output:
            result = COMMAND.match(line.strip())
            if result:
                if result["type"] in {"ARC_FEED"}:
                    coords = result["coords"].split(",")
                    new_x = float(coords[0].strip())
                    new_y = float(coords[1].strip())
                    center_x = float(coords[2].strip())
                    center_y = float(coords[3].strip())
                    new_z = float(coords[4].strip())
                    if coords[4].strip()[0] == "-":
                        direction = "cw"
                    else:
                        direction = "ccw"
                    if last_pos:
                        last_x, last_y, last_z = last_pos
                        color = "black"
                        radius = math.dist((last_x, last_y), (center_x, center_y))
                        start_angle = angle_of_line((center_x, center_y), (last_x, last_y))
                        end_angle = angle_of_line((center_x, center_y), (new_x, new_y))
                        if direction == "cw":
                            if start_angle < end_angle:
                                end_angle = end_angle - math.pi * 2
                        elif direction == "ccw":
                            if start_angle > end_angle:
                                end_angle = end_angle + math.pi * 2
                        diff_angle = end_angle - start_angle
                        if start_angle < end_angle:
                            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                                (center_x, center_y),
                                start_angle,
                                end_angle,
                                radius,
                            )
                        elif start_angle > end_angle:
                            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                                (center_x, center_y),
                                end_angle,
                                start_angle,
                                radius,
                            )
                            bulge = -bulge
                        self._add_line((last_x, last_y), (new_x, new_y), bulge=bulge)

                    last_pos = (new_x, new_y, new_z)
                elif result["type"] in {"STRAIGHT_FEED", "STRAIGHT_TRAVERSE", "ARC_FEED"}:
                    coords = result["coords"].split(",")
                    new_x = float(coords[0].strip())
                    new_y = float(coords[1].strip())
                    new_z = float(coords[2].strip())
                    if last_pos:
                        if result["type"] not in {"STRAIGHT_TRAVERSE"}:
                            last_x, last_y, last_z = last_pos
                            self._add_line((last_x, last_y), (new_x, new_y))

                    last_pos = (new_x, new_y, new_z)
                # else:
                #    print(result)

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        return ["gcode", "ngc", "nc"]


    def rs274(self, filename):
        output = []
        REGEX = re.compile(r"([a-zA-Z])([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")
        gcode = open(filename, "r").read()
        gcode = gcode.split("\n")

        state: dict = {
            "scale": 1.0,
            "move_mode": "",
            "offsets": "OFF",
            "metric": "",
            "absolute": True,
            "feedrate": "0",
            "tool": None,
            "spindle": {"dir": "OFF", "rpm": 0},
            "position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "last": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "minmax": {},
        }

        path: list[list] = []
        gcode = gcode
        for ln, line in enumerate(gcode):
            line = line.strip()
            if not line:
                continue
            elif line[0] == "(":
                comment = line.split('(', 1)[1].split(')', 1)[0]
                output.append(f"  {ln} N..... COMMENT(\"{comment}\")")
                continue
            ldata = {"T": 0}
            matches = REGEX.findall(line)
            if not matches:
                continue
            first = matches[0][0].upper()
            for match in matches:
                cmd = match[0].upper()
                ldata[cmd] = float(match[1])
            if first == "M":
                if ldata["M"] == 6:
                    if state["tool"] != int(ldata["T"]):
                        state["tool"] = int(ldata["T"])
                        path.append(
                            [
                                state["position"],
                                state["position"],
                                state["spindle"]["dir"],
                                f"TOOLCHANGE:{        state['tool']}",
                            ]
                        )
                elif ldata["M"] == 5:
                    state["spindle"]["dir"] = "OFF"
                    output.append(f"  {ln} N..... STOP_SPINDLE_TURNING(0)")
                elif ldata["M"] == 3:
                    state["spindle"]["dir"] = "CW"
                    if "S" in ldata:
                        state["spindle"]["rpm"] = ldata["S"]
                        output.append(f"  {ln} N..... SET_SPINDLE_SPEED(0, {ldata['S']})")
                    output.append(f"  {ln} N..... START_SPINDLE_CLOCKWISE(0)")
                elif ldata["M"] == 4:
                    state["spindle"]["dir"] = "CCW"
                    if "S" in ldata:
                        state["spindle"]["rpm"] = ldata["S"]
                        output.append(f"  {ln} N..... SET_SPINDLE_SPEED(0, {ldata['S']})")
                    output.append(f"  {ln} N..... START_SPINDLE_COUNTERCLOCKWISE(0)")
                elif ldata["M"] == 2:
                    output.append(f"  {ln} N..... PROGRAM_END()")
                    output.append(f"  {ln} N..... ON_RESET()")

            elif first == "G":
                if ldata["G"] < 4:
                            state["move_mode"] = int(ldata["G"])
                elif ldata["G"] == 4:
                    if "P" in ldata:
                        pass
                elif ldata["G"] == 20:
                    state["metric"] = "INCH"
                    state["scale"] = 1.0 / 25.4
                elif ldata["G"] == 21:
                    state["metric"] = "MM"
                    state["scale"] = 1.0
                elif ldata["G"] == 40:
                    state["offsets"] = "OFF"
                elif ldata["G"] == 41:
                    state["offsets"] = "LEFT"
                elif ldata["G"] == 42:
                    state["offsets"] = "RIGHT"
                elif ldata["G"] == 54:
                    pass
                elif ldata["G"] == 64:
                    if "P" in ldata:
                        pass
                elif ldata["G"] == 90:
                    state["absolute"] = True
                elif ldata["G"] == 91:
                    state["absolute"] = False
                else:
                    print("##### UNSUPPORTED GCODE #####", f"G{ldata['G']}", line)

            if "F" in ldata:
                state["feedrate"] = ldata["F"]
            cords = {}
            for axis in ("X", "Y", "Z", "R"):
                if axis in ldata:
                    cords[axis] = ldata[axis]

            state["last"] = copy.deepcopy(state["position"])
            for axis in ("X", "Y", "Z", "R"):
                if axis in cords:
                    state["position"][axis] = cords[axis]
            if cords:
                if state["move_mode"] == 0:
                    output.append(f"  {ln} N..... STRAIGHT_TRAVERSE({state['position']['X']}, {state['position']['Y']}, {state['position']['Z']}, 0.0000, 0.0000, 0.0000)")
                elif state["move_mode"] == 1:
                    output.append(f"  {ln} N..... STRAIGHT_FEED({state['position']['X']}, {state['position']['Y']}, {state['position']['Z']}, 0.0000, 0.0000, 0.0000)")
                elif state["move_mode"] in {2, 3}:
                    if "R" in cords:
                        pass
                        #arc_move_r(        state["move_mode"], cords, cords["R"])
                    elif "I" in ldata and "J" in ldata:
                        center_x = state['last']['X'] + ldata["I"]
                        center_y = state['last']['Y'] + ldata["J"]
                        #arc_move_ij(        state["move_mode"], cords, ldata["I"], ldata["J"])
                        output.append(f"  {ln} N..... ARC_FEED({state['position']['X']}, {state['position']['Y']}, {center_x}, {center_y}, -1, {state['position']['Z']}, 0.0000, 0.0000, 0.0000)")

        return output
