import math
import re
from .calc import (
    angle_of_line,
    calc_distance,
)


class GcodeParser:
    REGEX = re.compile(r"([a-zA-Z])([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")

    def __init__(self, gcode):
        if isinstance(gcode, str):
            gcode = gcode.split("\n")

        self.state = {
            "move_mode": "",
            "offsets": "OFF",
            "metric": "",
            "absolute": True,
            "feedrate": "0",
            "tool": None,
            "spindle": {
                "dir": "OFF",
                "rpm": 0,
            },
            "position": {
                "X": 0,
                "Y": 0,
                "Z": 0,
            },
        }

        self.path = []
        self.gcode = gcode
        for line in self.gcode:
            line = line.strip()
            ldata = {}
            matches = self.REGEX.findall(line)
            if not matches:
                continue
            first = matches[0][0].upper()
            for match in matches:
                cmd = match[0].upper()
                ldata[cmd] = float(match[1])
            if first == "M":
                if ldata["M"] == 6:
                    self.state["tool"] = int(ldata["T"])
                elif ldata["M"] == 5:
                    self.state["spindle"]["dir"] = "OFF"
                elif ldata["M"] == 3:
                    self.state["spindle"]["dir"] = "CW"
                    if "S" in ldata:
                        self.state["spindle"]["rpm"] = ldata["S"]
                elif ldata["M"] == 3:
                    self.state["spindle"]["dir"] = "CCW"
                    if "S" in ldata:
                        self.state["spindle"]["rpm"] = ldata["S"]
            elif first == "G":
                if ldata["G"] < 4:
                    self.state["move_mode"] = int(ldata["G"])
                elif ldata["G"] == 4:
                    if "P" in ldata:
                        pass
                elif ldata["G"] == 20:
                    self.state["metric"] = "INCH"
                elif ldata["G"] == 21:
                    self.state["metric"] = "MM"
                elif ldata["G"] == 40:
                    self.state["offsets"] = "OFF"
                elif ldata["G"] == 41:
                    self.state["offsets"] = "R?"
                elif ldata["G"] == 42:
                    self.state["offsets"] = "L?"
                elif ldata["G"] == 64:
                    if "P" in ldata:
                        pass
                elif ldata["G"] == 90:
                    self.state["absolute"] = True
                elif ldata["G"] == 91:
                    self.state["absolute"] = False
                else:
                    print("##### UNSUPPORTED GCODE #####", f"G{ldata['G']}", line)

            if "F" in ldata:
                self.state["feedrate"] = ldata["F"]
            cords = {}
            for axis in ("X", "Y", "Z", "R"):
                if axis in ldata:
                    cords[axis] = ldata[axis]
            if cords:
                if self.state["move_mode"] == 0:
                    self.linear_move(cords, True)
                elif self.state["move_mode"] == 1:
                    self.linear_move(cords, False)
                elif self.state["move_mode"] in {2, 3}:
                    if "X" in ldata and "Y" in ldata:
                        if "R" in cords:
                            self.arc_move_r(self.state["move_mode"], cords, cords["R"])
                        elif "I" in ldata and "J" in ldata:
                            self.arc_move_ij(
                                self.state["move_mode"], cords, ldata["I"], ldata["J"]
                            )
                self.state["position"] = cords

        minp = {}
        maxp = {}
        for axis in ("X", "Y", "Z"):
            minp[axis] = self.path[0][0][axis]
            maxp[axis] = self.path[0][0][axis]
        for line in self.path:
            for axis in ("X", "Y", "Z"):
                minp[axis] = min(minp[axis], line[0][axis])
                maxp[axis] = max(maxp[axis], line[0][axis])
                minp[axis] = min(minp[axis], line[1][axis])
                maxp[axis] = max(maxp[axis], line[1][axis])

        self.min_max = []
        for axis in ("X", "Y", "Z"):
            self.min_max.append(minp[axis])
        for axis in ("X", "Y", "Z"):
            self.min_max.append(maxp[axis])

        self.size = []
        for axis in ("X", "Y", "Z"):
            self.size.append(maxp[axis] - minp[axis])

    def get_minmax(self):
        return self.min_max

    def get_size(self):
        return self.size

    def get_path(self):
        return self.path

    def draw(self, draw_function, user_data=()):
        for line in self.path:
            draw_function(line[0], line[1], *user_data)

    def linear_move(self, cords, fast=False):  # pylint: disable=W0613
        for axis in self.state["position"]:
            if axis not in cords:
                cords[axis] = self.state["position"][axis]
        self.path.append((self.state["position"], cords))
        self.state["position"] = cords

    def arc_move_r(self, angle_dir, cords, radius):  # pylint: disable=W0613
        for axis in self.state["position"]:
            if axis not in cords:
                cords[axis] = self.state["position"][axis]
        self.path.append((self.state["position"], cords))
        self.state["position"] = cords

    def arc_move_ij(self, angle_dir, cords, i, j):
        for axis in self.state["position"]:
            if axis not in cords:
                cords[axis] = self.state["position"][axis]

        last_pos = self.state["position"]
        center_x = last_pos["X"] + i
        center_y = last_pos["Y"] + j
        radius = calc_distance((center_x, center_y), (last_pos["X"], last_pos["Y"]))
        start_angle = angle_of_line(
            (center_x, center_y), (last_pos["X"], last_pos["Y"])
        )
        end_angle = angle_of_line((center_x, center_y), (cords["X"], cords["Y"]))

        if angle_dir == 2:
            if start_angle < end_angle:
                end_angle = end_angle - math.pi * 2
        elif angle_dir == 3:
            if start_angle > end_angle:
                end_angle = end_angle + math.pi * 2
        if start_angle < end_angle:
            angle = start_angle
            while angle < end_angle:
                scenter_x = center_x - radius * math.sin(angle - math.pi / 2)
                scenter_y = center_y + radius * math.cos(angle - math.pi / 2)
                new_pos = {"X": scenter_x, "Y": scenter_y, "Z": last_pos["Z"]}
                self.path.append((last_pos, new_pos))
                last_pos = new_pos
                angle += 0.2
            self.path.append((last_pos, cords))
        elif start_angle > end_angle:
            angle = start_angle
            while angle > end_angle:
                scenter_x = center_x - radius * math.sin(angle - math.pi / 2)
                scenter_y = center_y + radius * math.cos(angle - math.pi / 2)
                new_pos = {"X": scenter_x, "Y": scenter_y, "Z": last_pos["Z"]}
                self.path.append((last_pos, new_pos))
                last_pos = new_pos
                angle -= 0.2
            self.path.append((last_pos, cords))
