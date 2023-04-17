import math

from ..calc import angle_of_line, calc_distance  # pylint: disable=E0402
from ..machine_cmd import PostProcessor  # pylint: disable=E0402


class PostProcessorHpgl(PostProcessor):
    def __init__(self, project):
        self.project = project
        self.comments = self.project["setup"]["machine"]["comments"]
        self.project = project
        self.hpgl: list[str] = []
        self.last_x: int = 0
        self.last_y: int = 0
        self.x_pos: int = 0
        self.y_pos: int = 0
        self.z_pos: int = 0
        self.rate: int = 0
        self.toolrun: bool = False
        self.offsets: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.scale: float = 40.0

    def separation(self) -> None:
        if self.comments:
            self.hpgl.append("")

    def raw(self, cmd) -> None:
        if cmd:
            self.hpgl.append(cmd)

    def absolute(self, active=True) -> None:
        if active:
            self.hpgl.append("PA")
        else:
            self.hpgl.append("PR")

    def program_start(self) -> None:
        self.toolrun = False
        self.hpgl.append("PU")

    def machine_offsets(
        self, offsets: tuple[float, float, float] = (0.0, 0.0, 0.0), soft: bool = True
    ) -> None:
        self.offsets = offsets

    def program_end(self) -> None:
        self.toolrun = False
        self.hpgl.append("PU")

    def comment(self, text) -> None:
        if self.comments:
            self.hpgl.append(f"CO {text}")

    def tool(self, number="1") -> None:
        self.hpgl.append(f"SP{number}")

    def coolant_mist(self) -> None:
        pass

    def coolant_flood(self) -> None:
        pass

    def coolant_off(self) -> None:
        pass

    def spindle_cw(self, speed: int, pause: int = 1) -> None:  # pylint: disable=W0613
        self.toolrun = True

    def spindle_ccw(self, speed: int, pause: int = 1) -> None:  # pylint: disable=W0613
        self.toolrun = True

    def spindle_off(self) -> None:
        self.toolrun = False

    def move(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        if x_pos is not None:
            self.x_pos = int((x_pos + self.offsets[0]) * self.scale)
        if y_pos is not None:
            self.y_pos = int((y_pos + self.offsets[1]) * self.scale)
        if z_pos is not None:
            self.z_pos = int((z_pos + self.offsets[2]) * self.scale)
        if x_pos is not None or y_pos is not None:
            self.hpgl.append("PU")
            self.hpgl.append(f"{int(self.x_pos)},{int(self.y_pos)}")
            self.last_x = self.x_pos
            self.last_y = self.y_pos

    def linear(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        if x_pos is not None:
            self.x_pos = int((x_pos + self.offsets[0]) * self.scale)
        if y_pos is not None:
            self.y_pos = int((y_pos + self.offsets[1]) * self.scale)
        if z_pos is not None:
            self.z_pos = int((z_pos + self.offsets[2]) * self.scale)
        if x_pos is not None or y_pos is not None:
            self.hpgl.append(f"P{'D' if self.toolrun else 'U'}")
            self.hpgl.append(f"{int(self.x_pos)},{int(self.y_pos)}")
            self.last_x = self.x_pos
            self.last_y = self.y_pos

    def arc_move(self, last_x, last_y, new_x, new_y, center_x, center_y, angle_dir):
        self.hpgl.append(f"P{'D' if self.toolrun else 'U'}")
        radius = calc_distance((center_x, center_y), (last_x, last_y))
        start_angle = angle_of_line((center_x, center_y), (last_x, last_y))
        end_angle = angle_of_line((center_x, center_y), (new_x, new_y))
        if angle_dir == 2:
            if start_angle < end_angle:
                end_angle = end_angle - math.pi * 2
        elif angle_dir == 3:
            if start_angle > end_angle:
                end_angle = end_angle + math.pi * 2
        if abs(end_angle - start_angle) < math.pi * 2:
            if start_angle < end_angle:
                angle = start_angle
                while angle < end_angle:
                    x_pos = int(center_x - radius * math.sin(angle - math.pi / 2))
                    y_pos = int(center_y + radius * math.cos(angle - math.pi / 2))
                    if x_pos != last_x and y_pos != last_y:
                        self.hpgl.append(f"{int(x_pos)},{int(y_pos)}")
                    last_x = x_pos
                    last_y = y_pos
                    angle += 0.2
            elif start_angle > end_angle:
                angle = start_angle
                while angle > end_angle:
                    x_pos = center_x - radius * math.sin(angle - math.pi / 2)
                    y_pos = center_y + radius * math.cos(angle - math.pi / 2)
                    if x_pos != last_x and y_pos != last_y:
                        self.hpgl.append(f"{int(x_pos)},{int(y_pos)}")
                    last_x = x_pos
                    last_y = y_pos
                    angle -= 0.2
        self.hpgl.append(f"{int(new_x)},{int(new_y)}")

    def arc_cw(
        self,
        x_pos=None,
        y_pos=None,
        z_pos=None,
        i_pos=None,  # pylint: disable=W0613
        j_pos=None,  # pylint: disable=W0613
        r_pos=None,  # pylint: disable=W0613
    ) -> None:
        if x_pos is not None:
            self.x_pos = int((x_pos + self.offsets[0]) * self.scale)
        if y_pos is not None:
            self.y_pos = int((y_pos + self.offsets[1]) * self.scale)
        if z_pos is not None:
            self.z_pos = int((z_pos + self.offsets[2]) * self.scale)
        if x_pos is not None and y_pos is not None:
            center_x = self.last_x + i_pos * self.scale
            center_y = self.last_y + j_pos * self.scale
            self.arc_move(
                self.last_x, self.last_y, self.x_pos, self.y_pos, center_x, center_y, 2
            )
            self.last_x = self.x_pos
            self.last_y = self.y_pos

    def arc_ccw(
        self,
        x_pos=None,
        y_pos=None,
        z_pos=None,
        i_pos=None,  # pylint: disable=W0613
        j_pos=None,  # pylint: disable=W0613
        r_pos=None,  # pylint: disable=W0613
    ) -> None:
        if x_pos is not None:
            self.x_pos = int((x_pos + self.offsets[0]) * self.scale)
        if y_pos is not None:
            self.y_pos = int((y_pos + self.offsets[0]) * self.scale)
        if z_pos is not None:
            self.z_pos = int((z_pos + self.offsets[0]) * self.scale)
        if x_pos is not None and y_pos is not None:
            center_x = self.last_x + i_pos * self.scale
            center_y = self.last_y + j_pos * self.scale
            self.arc_move(
                self.last_x, self.last_y, self.x_pos, self.y_pos, center_x, center_y, 3
            )
            self.last_x = self.x_pos
            self.last_y = self.y_pos

    def get(self, numbers=False) -> str:  # pylint: disable=W0613
        output = ""
        last_word = ""
        for cmd in self.hpgl:
            if cmd == "":
                output = output.strip(",")
                output += ";\n"
            elif cmd[0].isnumeric() or cmd[0] == "-":
                output += cmd + ","
            else:
                if last_word != cmd:
                    output = output.strip(",")
                    output += ";\n" + cmd
                    last_word = cmd
        return output

    @staticmethod
    def suffix() -> str:
        return "hpgl"

    @staticmethod
    def axis() -> list[str]:
        return ["X", "Y"]
