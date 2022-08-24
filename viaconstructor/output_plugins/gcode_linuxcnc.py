from ..machine_cmd import PostProcessor  # pylint: disable=E0402


class PostProcessorGcodeLinuxCNC(PostProcessor):
    def __init__(self, comments=True):
        self.comments = comments
        self.gcode: list[str] = []
        self.x_pos: float = None
        self.y_pos: float = None
        self.z_pos: float = None
        self.rate: int = 0
        self.speed: int = -1

    def separation(self) -> None:
        if self.comments:
            self.gcode.append("")

    def g64(self, value) -> None:
        self.gcode.append(f"G64 P{value}")

    def feedrate(self, feedrate) -> None:
        self.gcode.append(f"F{feedrate}")

    def unit(self, unit="mm") -> None:
        if unit == "mm":
            if self.comments:
                self.gcode.append("G21 (Metric/mm)")
            else:
                self.gcode.append("G21")
        else:
            if self.comments:
                self.gcode.append("G20 (Imperial/inches)")
            else:
                self.gcode.append("G20")

    def absolute(self, active=True) -> None:
        if active:
            if self.comments:
                self.gcode.append("G90 (Absolute-Mode)")
            else:
                self.gcode.append("G90")
        else:
            if self.comments:
                self.gcode.append("G91 (Incremental-Mode)")
            else:
                self.gcode.append("G91")

    def tool_offsets(self, offset="none") -> None:
        if self.comments:
            if offset == "none":
                self.gcode.append("G40 (No Offsets)")
            elif offset == "left":
                self.gcode.append("G41 (left offsets)")
            else:
                self.gcode.append("G42 (right offsets)")
        else:
            if offset == "none":
                self.gcode.append("G40")
            elif offset == "left":
                self.gcode.append("G41")
            else:
                self.gcode.append("G42")

    def machine_offsets(
        self, offsets: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ) -> None:
        self.gcode.append(f"G54 X{offsets[0]} Y{offsets[1]} Z{offsets[2]}")

    def program_end(self) -> None:
        self.gcode.append("M02")

    def comment(self, text) -> None:
        if self.comments:
            self.gcode.append(f"({text})")

    def move(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{round(x_pos, 6)}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{round(y_pos, 6)}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{round(z_pos, 6)}")
            self.z_pos = z_pos
        if line:
            self.gcode.append("G00 " + " ".join(line))

    def tool(self, number="1") -> None:
        self.gcode.append(f"M06 T{number}")

    def spindle_off(self) -> None:
        if self.comments:
            self.gcode.append("M05 (Spindle off)")
        else:
            self.gcode.append("M05")

    def spindle_cw(self, speed: int, pause: int = 1) -> None:
        cmd = "M03"
        if self.speed != speed:
            self.speed = speed
            cmd += f" S{speed}"
        if self.comments:
            cmd += " (Spindle on / CW)"
        self.gcode.append(cmd)

        if pause:
            if self.comments:
                self.gcode.append(f"G04 P{pause} (pause in sec)")
            else:
                self.gcode.append(f"G04 P{pause}")

    def spindle_ccw(self, speed: int, pause: int = 1) -> None:
        cmd = "M04"
        if self.speed != speed:
            self.speed = speed
            cmd += f" S{speed}"
        if self.comments:
            cmd += " (Spindle on / CW)"
        self.gcode.append(cmd)

        if pause:
            if self.comments:
                self.gcode.append(f"G04 P{pause} (pause in sec)")
            else:
                self.gcode.append(f"G04 P{pause}")

    def linear(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{round(x_pos, 6)}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{round(y_pos, 6)}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{round(z_pos, 6)}")
            self.z_pos = z_pos
        if line:
            self.gcode.append("G01 " + " ".join(line))

    def arc_cw(
        self, x_pos=None, y_pos=None, z_pos=None, i_pos=None, j_pos=None, r_pos=None
    ) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{round(x_pos, 6)}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{round(y_pos, 6)}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{round(z_pos, 6)}")
            self.z_pos = z_pos
        if i_pos is not None:
            line.append(f"I{round(i_pos, 5)}")
        if j_pos is not None:
            line.append(f"J{round(j_pos, 5)}")
        if r_pos is not None:
            line.append(f"R{round(r_pos, 5)}")
        if line:
            self.gcode.append("G02 " + " ".join(line))

    def arc_ccw(
        self, x_pos=None, y_pos=None, z_pos=None, i_pos=None, j_pos=None, r_pos=None
    ) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{round(x_pos, 6)}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{round(y_pos, 6)}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{round(z_pos, 6)}")
            self.z_pos = z_pos
        if i_pos is not None:
            line.append(f"I{round(i_pos, 5)}")
        if j_pos is not None:
            line.append(f"J{round(j_pos, 5)}")
        if r_pos is not None:
            line.append(f"R{round(r_pos, 5)}")
        if line:
            self.gcode.append("G03 " + " ".join(line))

    def get(self) -> str:
        return "\n".join(self.gcode)

    @staticmethod
    def suffix() -> str:
        return "ngc"

    @staticmethod
    def axis() -> list[str]:
        return ["X", "Y", "Z"]
