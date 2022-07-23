"""xncparser"""

import math
import re

import ezdxf

from .calc import angle_of_line


class XncReader:
    REGEX = re.compile(r"([a-zA-Z])([+-]?([0-9]+([.][0-9]*)?|[.][0-9]+))")

    def __init__(self, filename: str):
        self.filename = filename
        self.segments: list[dict] = []

        data = open(self.filename, "r").read()
        state: dict = {
            "header": False,
            "move_mode": "0",
            "position": {"X": 0, "Y": 0},
            "tools": {},
            "tool": "",
        }

        last_x = 0.0
        last_y = 0.0

        for line in data.split("\n"):
            line = line.strip()
            if not line or line[0] == "(":
                continue

            if line == "%":
                state["header"] = False
                print("end header")
                continue

            ldata = {}
            matches = self.REGEX.findall(line)
            if not matches:
                continue
            first = matches[0][0].upper()
            for match in matches:
                cmd = match[0].upper()
                ldata[cmd] = float(match[1])

            if first == "T":
                # set or select tool
                if ldata["T"] > 0:
                    if "C" in ldata:
                        print("set tool", ldata["T"], "diameter:", ldata["C"])
                        state["tools"][ldata["T"]] = ldata["C"]
                    else:
                        print("use tool", ldata["T"])
                        state["tool"] = ldata["T"]

            elif first == "M":
                if ldata["M"] == 48:
                    # header start
                    state["header"] = True

                elif ldata["M"] == 15:
                    # tool down
                    print("tool down")
                elif ldata["M"] == 16:
                    # tool up
                    print("tool up")

                elif ldata["M"] == 30:
                    # end of file
                    print("end")

                else:
                    print("??? ", ldata["M"])

            elif first == "G":
                if ldata["G"] <= 5:
                    state["move_mode"] = int(ldata["G"])
                    print("mode", state["move_mode"])
                else:
                    print("##### UNSUPPORTED GCODE #####", f"G{ldata['G']}", line)

            cords = {}
            for axis in ("X", "Y", "A"):
                if axis in ldata:
                    cords[axis] = ldata[axis]
            if cords:
                if state["move_mode"] == 0:
                    pass

                elif state["move_mode"] == 1:
                    self.add_line((last_x, last_y), (cords["X"], cords["Y"]))

                elif state["move_mode"] in {2, 3}:
                    angle_dir = int(state["move_mode"])
                    diff_x = cords["X"] - last_x
                    diff_y = cords["Y"] - last_y
                    arc_r = cords["A"]
                    if diff_x == 0.0 and diff_y == 0.0:
                        print("error1 no move")
                        continue

                    h_x2_div_d = 4.0 * arc_r * arc_r - diff_x * diff_x - diff_y * diff_y
                    if h_x2_div_d < 0:
                        print("### ARC ERROR ###")
                        continue

                    h_x2_div_d = -math.sqrt(h_x2_div_d) / math.hypot(diff_x, diff_y)
                    if angle_dir == 3:
                        h_x2_div_d = -h_x2_div_d
                    if arc_r < 0:
                        h_x2_div_d = -h_x2_div_d
                        arc_r = -arc_r
                    i = 0.5 * (diff_x - (diff_y * h_x2_div_d))
                    j = 0.5 * (diff_y + (diff_x * h_x2_div_d))

                    center_x = last_x + i
                    center_y = last_y + j
                    start = (
                        angle_of_line((center_x, center_y), (last_x, last_y))
                        * 180
                        / math.pi
                    )
                    end = (
                        angle_of_line((center_x, center_y), (cords["X"], cords["Y"]))
                        * 180
                        / math.pi
                    )
                    if state["move_mode"] == 2:
                        self.add_arc((center_x, center_y), arc_r, end, start)
                    else:
                        self.add_arc((center_x, center_y), arc_r, start, end)

                elif state["move_mode"] == 5:
                    diameter = state["tools"][state["tool"]]
                    self.add_arc((cords["X"], cords["Y"]), diameter / 2)

                last_x = cords["X"]
                last_y = cords["Y"]

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
            for step_n in range(0, steps):  # pylint: disable=W0612
                (start, end, bulge) = ezdxf.math.arc_to_bulge(
                    center,
                    angle / 180 * math.pi,
                    (angle + astep) / 180 * math.pi,
                    radius,
                )
                self.segments.append(
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
                angle += astep

        else:
            (start, end, bulge) = ezdxf.math.arc_to_bulge(
                center,
                start_angle / 180 * math.pi,
                end_angle / 180 * math.pi,
                radius,
            )
            self.segments.append(
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

    def add_line(self, start, end, layer="0") -> None:
        self.segments.append(
            {
                "type": "LINE",
                "object": None,
                "layer": layer,
                "start": start,
                "end": end,
                "bulge": 0.0,
            }
        )

    def get_segments(self) -> list[dict]:
        return self.segments

    def get_minmax(self) -> list[float]:
        return self.min_max

    def get_size(self) -> list[float]:
        return self.size

    def draw(self, draw_function, user_data=()) -> None:
        for segment in self.segments:
            draw_function(segment["start"], segment["end"], *user_data)

    def save_tabs(self, tabs: list) -> None:
        pass
