"""dxf reading."""

import math

import ezdxf

from .calc import angle_of_line, calc_distance


class HpglReader:
    def __init__(self, filename: str):
        """converting hpgl into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

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

        hpgl = open(self.filename, "r").read()

        last_x = 0
        last_y = 0
        draw = False
        absolute = True
        hpgl = hpgl.replace(";", "\n")
        for line in hpgl.split("\n"):
            line = line.strip()
            if line[0:2] in {"IN", "LT", "CO", "CI", "IP", "SC", "CT", "SP"}:
                line = ""
            elif line.startswith("PU"):
                draw = False
                # self.linear_move({"Z": 1.0}, True)
                line = line[2:]
            elif line.startswith("PD"):
                draw = True
                # self.linear_move({"Z": -1.0}, False)
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
                        self.add_line(
                            (last_x, last_y),
                            (new_x, new_y),
                        )
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
                        self.add_line(
                            (last_x, last_y),
                            (new_x, new_y),
                        )
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
                        new_x = float(cord)
                    else:
                        new_y = float(cord)
                        if not absolute:
                            new_x += last_x
                            new_y += last_y

                        if draw:
                            self.add_line(
                                (last_x, last_y),
                                (new_x, new_y),
                            )

                        last_x = new_x
                        last_y = new_y

                    is_x = not is_x

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
