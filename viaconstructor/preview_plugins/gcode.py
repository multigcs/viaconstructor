"""gcodeparser"""

import math
import re
from typing import Union

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402


class GcodeParser:
    REGEX = re.compile(r"([a-zA-Z])([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")

    def __init__(self, gcode: Union[str, list[str]]):
        if isinstance(gcode, str):
            gcode = gcode.split("\n")

        self.state: dict = {
            "scale": 1.0,
            "move_mode": "",
            "offsets": "OFF",
            "metric": "",
            "absolute": True,
            "feedrate": "0",
            "tool": None,
            "spindle": {"dir": "OFF", "rpm": 0},
            "position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "minmax": {},
        }

        self.path: list[list] = []
        self.gcode = gcode
        for line in self.gcode:
            line = line.strip()
            if not line or line[0] == "(":
                continue
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
                    if self.state["tool"] != int(ldata["T"]):
                        self.state["tool"] = int(ldata["T"])
                        self.path.append(
                            [
                                self.state["position"],
                                self.state["position"],
                                self.state["spindle"]["dir"],
                                f"TOOLCHANGE:{self.state['tool']}",
                            ]
                        )
                elif ldata["M"] == 5:
                    self.state["spindle"]["dir"] = "OFF"
                elif ldata["M"] == 3:
                    self.state["spindle"]["dir"] = "CW"
                    if "S" in ldata:
                        self.state["spindle"]["rpm"] = ldata["S"]
                elif ldata["M"] == 4:
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
                    self.state["scale"] = 1.0 / 25.4
                elif ldata["G"] == 21:
                    self.state["metric"] = "MM"
                    self.state["scale"] = 1.0
                elif ldata["G"] == 40:
                    self.state["offsets"] = "OFF"
                elif ldata["G"] == 41:
                    self.state["offsets"] = "LEFT"
                elif ldata["G"] == 42:
                    self.state["offsets"] = "RIGHT"
                elif ldata["G"] == 54:
                    pass
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
                    if "R" in cords:
                        self.arc_move_r(self.state["move_mode"], cords, cords["R"])
                    elif "I" in ldata and "J" in ldata:
                        self.arc_move_ij(
                            self.state["move_mode"], cords, ldata["I"], ldata["J"]
                        )

        minp = {}
        maxp = {}
        for axis in ("X", "Y", "Z"):
            minp[axis] = self.path[0][0][axis]
            maxp[axis] = self.path[0][0][axis]
        for segment in self.path:
            for axis in ("X", "Y", "Z"):
                minp[axis] = min(minp[axis], segment[0][axis])
                maxp[axis] = max(maxp[axis], segment[0][axis])
                minp[axis] = min(minp[axis], segment[1][axis])
                maxp[axis] = max(maxp[axis], segment[1][axis])

        self.min_max = []
        for axis in ("X", "Y", "Z"):
            self.min_max.append(minp[axis])
        for axis in ("X", "Y", "Z"):
            self.min_max.append(maxp[axis])

        self.size = []
        for axis in ("X", "Y", "Z"):
            self.size.append(maxp[axis] - minp[axis])

    def get_minmax(self) -> list[float]:
        return self.min_max

    def get_size(self) -> list[float]:
        return self.size

    def get_state(self) -> dict:
        return self.state

    def get_path(self, rounding: bool = True) -> list[list]:
        if rounding:
            for segment in self.path:
                for axis in ("X", "Y", "Z"):
                    segment[0][axis] = round(segment[0][axis], 6)
                    segment[1][axis] = round(segment[1][axis], 6)
        return self.path

    def openscad(self, tool_diameter: float) -> str:
        # code from https://github.com/pvdbrand/cnc-3d-gcode-viewer
        movements = []
        for line in self.path:
            movements.append((line[0]["X"], line[0]["Y"], line[0]["Z"]))
        minmax = self.get_minmax()
        size = self.get_size()
        stock_x = size[0] + tool_diameter * 4
        stock_y = size[1] + tool_diameter * 4
        stock_z = size[2] - minmax[5]
        tool_length = stock_z + 10
        scad_data = [
            f"module tool() {{cylinder(h={tool_length},d={tool_diameter},center=false,$fn={8});}}"
        ]
        scad_data.append(
            f"module stock() {{translate(v=[{minmax[0] - tool_diameter * 2},{minmax[1] - tool_diameter * 2},{-stock_z}]) cube(size=[{stock_x},{stock_y},{stock_z}],center=false);}}"
        )
        scad_data.append("difference() {")
        scad_data.append("  stock();")
        scad_data.append("  union() {")
        for (s_x, s_y, s_z), (e_x, e_y, e_z) in zip(movements, movements[1:]):
            scad_data.append(
                f"    hull() {{translate(v=[{s_x},{s_y},{s_z}]) tool(); translate(v=[{e_x},{e_y},{e_z-0.01}]) tool();}}"
            )
        scad_data.append("  }")
        scad_data.append("}")
        return "\n".join(scad_data)

    def linear_move(
        self, cords: dict, fast: bool = False  # pylint: disable=W0613
    ) -> None:
        for axis in self.state["position"]:
            if axis in cords:
                cords[axis] /= self.state["scale"]
            else:
                cords[axis] = self.state["position"][axis]

        self.path.append([self.state["position"], cords, self.state["spindle"]["dir"]])
        self.state["position"] = cords

    def arc_move_r(self, angle_dir, cords, radius) -> None:  # pylint: disable=W0613
        for axis in self.state["position"]:
            if axis in cords:
                cords[axis] /= self.state["scale"]
            else:
                cords[axis] = self.state["position"][axis]
        last_pos = self.state["position"]
        diff_x = cords["X"] - last_pos["X"]
        diff_y = cords["Y"] - last_pos["Y"]
        arc_r = cords["R"]
        if diff_x == 0.0 and diff_y == 0.0:
            return
        h_x2_div_d = 4.0 * arc_r * arc_r - diff_x * diff_x - diff_y * diff_y
        if h_x2_div_d < 0:
            print("### ARC ERROR ###")
            self.path.append(
                [self.state["position"], cords, self.state["spindle"]["dir"]]
            )
            self.state["position"] = cords
            return
        h_x2_div_d = -math.sqrt(h_x2_div_d) / math.hypot(diff_x, diff_y)
        if angle_dir == 3:
            h_x2_div_d = -h_x2_div_d
        if arc_r < 0:
            h_x2_div_d = -h_x2_div_d
            arc_r = -arc_r
        i = 0.5 * (diff_x - (diff_y * h_x2_div_d))
        j = 0.5 * (diff_y + (diff_x * h_x2_div_d))
        self.arc_move_ij(angle_dir, cords, i, j, radius)

    def arc_move_ij(self, angle_dir, cords, i, j, radius=None) -> None:
        for axis in self.state["position"]:
            if axis in cords:
                cords[axis] /= self.state["scale"]
            else:
                cords[axis] = self.state["position"][axis]

        last_pos = self.state["position"]
        center_x = last_pos["X"] + i
        center_y = last_pos["Y"] + j
        if radius is None:
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

        start_z = last_pos["Z"]
        diff_z = cords["Z"] - last_pos["Z"]
        diff_angle = end_angle - start_angle
        if start_angle < end_angle:
            angle = start_angle
            while angle < end_angle:
                new_x = center_x - radius * math.sin(angle - math.pi / 2)
                new_y = center_y + radius * math.cos(angle - math.pi / 2)
                new_z = start_z + ((angle - start_angle) / diff_angle) * diff_z
                new_pos = {"X": new_x, "Y": new_y, "Z": new_z}
                self.path.append([last_pos, new_pos, self.state["spindle"]["dir"]])
                last_pos = new_pos
                angle += 0.2
            self.path.append([last_pos, cords, self.state["spindle"]["dir"]])
        elif start_angle > end_angle:
            angle = start_angle
            while angle > end_angle:
                new_x = center_x - radius * math.sin(angle - math.pi / 2)
                new_y = center_y + radius * math.cos(angle - math.pi / 2)
                new_z = start_z + ((angle - start_angle) / diff_angle) * diff_z
                new_pos = {"X": new_x, "Y": new_y, "Z": new_z}
                self.path.append([last_pos, new_pos, self.state["spindle"]["dir"]])
                last_pos = new_pos
                angle -= 0.2
            self.path.append([last_pos, cords, self.state["spindle"]["dir"]])
        self.state["position"] = cords
