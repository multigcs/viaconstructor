"""hpglparser"""

import math
from typing import Union

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402


class HpglParser:
    def __init__(self, hpgl: Union[str, list[str]]):
        if isinstance(hpgl, str):
            hpgl = hpgl.split("\n")

        self.state: dict = {
            "move_mode": "",
            "offsets": "OFF",
            "metric": "",
            "absolute": True,
            "feedrate": "0",
            "tool": None,
            "spindle": {"dir": "OFF", "rpm": 0},
            "position": {"X": 0, "Y": 0, "Z": 0},
        }
        self.path: list[list] = []

        last_x = 0
        last_y = 0
        draw = False
        absolute = True
        hpgl = "\n".join(hpgl)
        hpgl = hpgl.replace(";", "\n")
        for line in hpgl.split("\n"):
            line = line.strip()
            if line[0:2] in {"IN", "LT", "CO", "CI", "IP", "SC", "CT", "SP"}:
                line = ""
            elif line.startswith("PU"):
                draw = False
                self.linear_move({"Z": 1.0}, True)
                self.state["spindle"]["dir"] = "OFF"
                line = line[2:]
            elif line.startswith("PD"):
                draw = True
                self.linear_move({"Z": -1.0}, False)
                self.state["spindle"]["dir"] = "CW"
                line = line[2:]
            elif line[0:2] in {"AA", "AR"}:
                params = line[2:].split(",")
                center_x = float(params[0])
                center_y = float(params[1])
                if line[0:2] == "AR":
                    center_x += last_x
                    center_y += last_y
                angle = float(params[2])
                # if len(params) == 4:
                #    resolution = params[3]
                radius = calc_distance((last_x, last_y), (center_x, center_y))
                start_angle = (
                    angle_of_line((last_x, last_y), (center_x, center_y))
                    * 180
                    / math.pi
                )
                if angle < 0:
                    for angle_set in range(0, int(abs(angle)) + 1):
                        new_x = center_x + radius * math.sin(
                            (start_angle + angle_set) * math.pi / 180 + math.pi / 2
                        )
                        new_y = center_y + radius * math.cos(
                            (start_angle + angle_set) * math.pi / 180 + math.pi / 2
                        )
                        self.linear_move({"X": new_x, "Y": new_y}, False)
                        last_x = new_x
                        last_y = new_y
                else:
                    for angle_set in range(int(abs(angle)), -1, -1):
                        new_x = center_x - radius * math.sin(
                            (start_angle + angle_set) * math.pi / 180 + math.pi / 2
                        )
                        new_y = center_y - radius * math.cos(
                            (start_angle + angle_set) * math.pi / 180 + math.pi / 2
                        )
                        self.linear_move({"X": new_x, "Y": new_y}, False)
                        last_x = new_x
                        last_y = new_y

                line = ""
            elif line.startswith("PA"):
                absolute = True
                line = line[2:]
            elif line.startswith("PR"):
                absolute = False
                line = line[2:]

            line = line.strip()
            if line:
                is_x = True
                for cord in line.split(","):
                    if is_x:
                        new_x = float(cord) / 40.0
                    else:
                        new_y = float(cord) / 40.0
                        if not absolute:
                            new_x += last_x
                            new_y += last_y

                        if draw:
                            self.linear_move({"X": new_x, "Y": new_y}, False)
                        else:
                            self.linear_move({"X": new_x, "Y": new_y}, True)

                        last_x = new_x
                        last_y = new_y

                    is_x = not is_x

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

    def linear_move(
        self, cords: dict, fast: bool = False  # pylint: disable=W0613
    ) -> None:
        for axis in self.state["position"]:
            if axis not in cords:
                cords[axis] = self.state["position"][axis]
        self.path.append([self.state["position"], cords, self.state["spindle"]["dir"]])
        self.state["position"] = cords

    def arc_move_r(self, angle_dir, cords, radius) -> None:  # pylint: disable=W0613
        for axis in self.state["position"]:
            if axis not in cords:
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
            if axis not in cords:
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
