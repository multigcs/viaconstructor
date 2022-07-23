from ..machine_cmd import PostProcessor  # pylint: disable=E0402


class PostProcessorGcodeLinuxCNC(PostProcessor):
    def __init__(self):
        self.gcode: list[str] = []
        self.x_pos: float = None
        self.y_pos: float = None
        self.z_pos: float = None
        self.rate: int = 0

    def separation(self) -> None:
        self.gcode.append("")

    def g64(self, value) -> None:
        self.gcode.append(f"G64 P{value}")

    def feedrate(self, feedrate) -> None:
        self.gcode.append(f"F{feedrate}")

    def unit(self, unit="mm") -> None:
        if unit == "mm":
            self.gcode.append("G21 (Metric/mm)")
        else:
            self.gcode.append("G20 (Imperial/inches)")

    def absolute(self, active=True) -> None:
        if active:
            self.gcode.append("G90 (Absolute-Mode)")
        else:
            self.gcode.append("G91 (Incremental-Mode)")

    def offsets(self, offset="none") -> None:
        if offset == "none":
            self.gcode.append("G40 (No Offsets)")
        elif offset == "left":
            self.gcode.append("G41 (left offsets)")
        else:
            self.gcode.append("G42 (right offsets)")

    def program_end(self) -> None:
        self.gcode.append("M02")

    def comment(self, text) -> None:
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

    def spindel_off(self) -> None:
        self.gcode.append("M05 (Spindle off)")

    def spindel_cw(self, speed: int, pause: int = 1) -> None:
        self.gcode.append(f"M03 S{speed} (Spindle on / CW)")
        if pause:
            self.gcode.append(f"G04 P{pause} (pause in sec)")

    def spindel_ccw(self, speed: int, pause: int = 1) -> None:
        self.gcode.append(f"M04 S{speed} (Spindle on / CCW)")
        if pause:
            self.gcode.append(f"G04 P{pause} (pause in sec)")

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
            line.append(f"I{round(i_pos, 6)}")
        if j_pos is not None:
            line.append(f"J{round(j_pos, 6)}")
        if r_pos is not None:
            line.append(f"R{round(r_pos, 6)}")
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
            line.append(f"I{round(i_pos, 6)}")
        if j_pos is not None:
            line.append(f"J{round(j_pos, 6)}")
        if r_pos is not None:
            line.append(f"R{round(r_pos, 6)}")
        if line:
            self.gcode.append("G03 " + " ".join(line))

    def get(self) -> list[str]:
        return "\n".join(self.gcode)

    @staticmethod
    def suffix() -> str:
        return "ngc"

    @staticmethod
    def axis() -> str:
        return ["X", "Y", "Z"]
