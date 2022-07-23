"""dxf reading."""

import math

from .calc import angle_of_line, calc_distance


class HpglReader:
    def __init__(self, filename: str):
        """converting hpgl into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        self.state: dict = {
            "move_mode": "",
            "offsets": "OFF",
            "user": (100, 100),
            "plotter": (4000, 4000),
            "scale": (40, 40),
            "metric": "",
            "absolute": True,
            "feedrate": "0",
            "tool": None,
            "spindle": {"dir": "OFF", "rpm": 0},
            "position": {"X": 0, "Y": 0, "Z": 0},
        }
        hpgl = open(self.filename, "r").read()

        last_x = 0
        last_y = 0
        draw = False
        absolute = True
        hpgl = hpgl.replace(";", "\n")
        for line in hpgl.split("\n"):
            line = line.strip()
            if line[0:2] in {"IN", "LT", "CO", "CI", "CT", "SP"}:
                line = ""
            if line[0:2] in {"IP", "SC"}:
                coords = line[2:].split(",")
                if line.startswith("IP"):
                    min_x = float(coords[0])
                    min_y = float(coords[1])
                    max_x = float(coords[2])
                    max_y = float(coords[3])
                    self.state["plotter"] = (max_x - min_x, max_y - min_y)
                else:
                    min_x = float(coords[0])
                    max_x = float(coords[1])
                    min_y = float(coords[2])
                    max_y = float(coords[3])
                    self.state["user"] = (max_x - min_x, max_y - min_y)
                self.state["scale"] = (
                    self.state["plotter"][0] / self.state["user"][0],
                    self.state["plotter"][1] / self.state["user"][1],
                )
                line = ""
            elif line.startswith("PU"):
                draw = False
                line = line[2:]
            elif line.startswith("PD"):
                draw = True
                line = line[2:]
            elif line[0:2] in {"AA", "AR"}:
                params = line[2:].split(",")
                center_x = float(params[0]) / self.state["scale"][0]
                center_y = float(params[1]) / self.state["scale"][1]
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
                        new_x = float(cord) / self.state["scale"][0]
                    else:
                        new_y = float(cord) / self.state["scale"][1]
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

    def add_line(self, start, end, layer="0") -> None:
        dist = round(calc_distance(start, end), 6)
        if dist > 0.0:
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
