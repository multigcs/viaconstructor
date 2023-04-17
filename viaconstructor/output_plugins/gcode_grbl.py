from ..machine_cmd import PostProcessor  # pylint: disable=E0402


class PostProcessorGcodeGrbl(PostProcessor):
    def __init__(self, project):
        self.project = project
        self.comments = self.project["setup"]["machine"]["comments"]
        self.gcode: list[str] = []
        self.x_pos: float = None
        self.y_pos: float = None
        self.z_pos: float = None
        self.rate: int = 0
        self.speed: int = -1
        self.offsets: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.offsets_reset = False
        self.scale: float = 1.0
        self.tool_active = -1
        self.tool_running = 0

    def separation(self) -> None:
        if self.comments:
            self.gcode.append("")

    def raw(self, cmd) -> None:
        if cmd:
            self.gcode.append(cmd)

    def g64(self, value) -> None:
        # self.gcode.append(f"G64 P{value}")
        pass

    def feedrate(self, feedrate) -> None:
        self.gcode.append(f"F{feedrate}")

    def unit(self, unit="mm") -> None:
        if unit == "mm":
            if self.comments:
                self.gcode.append("G21 (Metric/mm)")
            else:
                self.gcode.append("G21")
            self.scale = 1.0
        else:
            if self.comments:
                self.gcode.append("G20 (Imperial/inches)")
            else:
                self.gcode.append("G20")
            self.scale = 1.0 / 25.4

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
        self, offsets: tuple[float, float, float] = (0.0, 0.0, 0.0), soft: bool = True
    ) -> None:
        self.offsets_reset = False
        if not soft and offsets != (0.0, 0.0, 0.0):
            self.offsets_reset = True
            self.gcode.append(
                f"G10 L2 P1 X{offsets[0]:.12f} Y{offsets[1]:.12f} Z{offsets[2]:.12f} (workpiece offsets for G54)"
            )
            self.gcode.append("G54")
        if soft:
            self.offsets = (
                offsets[0] / self.scale,
                offsets[1] / self.scale,
                offsets[2] / self.scale,
            )

    def program_end(self) -> None:
        if self.offsets_reset:
            self.gcode.append("G10 L2 P1 X0 Y0 Z0 (reset offsets for G54)")
        self.gcode.append("M02")

    def comment(self, text) -> None:
        if self.comments:
            self.gcode.append(f"({text})")

    def move(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{(x_pos + self.offsets[0]) * self.scale:.12f}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{(y_pos + self.offsets[1]) * self.scale:.12f}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{(z_pos + self.offsets[2]) * self.scale:.12f}")
            self.z_pos = z_pos
        if line:
            self.gcode.append("G00 " + " ".join(line))

    def tool(self, number="1") -> None:
        if self.tool_active != number:
            fast_move_z = self.project["setup"]["mill"]["fast_move_z"]

            # tool to safe z
            self.gcode.append(f"G00 Z{fast_move_z}")

            # tool off
            if self.speed > 0:
                self.spindle_off()

            if self.project["setup"]["machine"]["toolchange_pre"]:
                for part in self.project["setup"]["machine"]["toolchange_pre"].split(
                    "\n"
                ):
                    self.gcode.append(part)
            self.gcode.append(f"M06 T{number}")
            if self.project["setup"]["machine"]["toolchange_post"]:
                for part in self.project["setup"]["machine"]["toolchange_post"].split(
                    "\n"
                ):
                    self.gcode.append(part)

            # tool to safe z
            if self.z_pos != fast_move_z:
                self.gcode.append(f"G00 Z{fast_move_z}")

            # tool to last xy
            if self.x_pos is not None and self.y_pos is not None:
                self.gcode.append(f"G00 X{self.x_pos} Y{self.y_pos}")

            # tool to last z
            if self.z_pos is not None and self.z_pos != fast_move_z:
                self.gcode.append(f"G00 Z{self.z_pos}")

        self.tool_active = number

    def spindle_off(self) -> None:
        if self.comments:
            self.gcode.append("M05 (Spindle off)")
        else:
            self.gcode.append("M05")
        self.tool_running = 0
        if self.project["setup"]["machine"]["spindle_off_post"]:
            for part in self.project["setup"]["machine"]["spindle_off_post"].split(
                "\n"
            ):
                self.gcode.append(part)

    def coolant_mist(self) -> None:
        self.gcode.append("M07 (mist on)")

    def coolant_flood(self) -> None:
        self.gcode.append("M08 (flood on)")

    def coolant_off(self) -> None:
        self.gcode.append("M09 (coolant off)")

    def spindle_cw(self, speed: int, pause: int = 1) -> None:
        if self.tool_running != 0 and self.tool_running == speed:
            return
        if self.project["setup"]["machine"]["spindle_on_pre"]:
            for part in self.project["setup"]["machine"]["spindle_on_pre"].split("\n"):
                self.gcode.append(part)
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

        self.tool_running = self.speed

    def spindle_ccw(self, speed: int, pause: int = 1) -> None:
        # no if self.tool_running != 0 and self.tool_running == speed test?
        if self.project["setup"]["machine"]["spindle_on_pre"]:
            for part in self.project["setup"]["machine"]["spindle_on_pre"].split("\n"):
                self.gcode.append(part)
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
            line.append(f"X{(x_pos + self.offsets[0]) * self.scale:.12f}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{(y_pos + self.offsets[1]) * self.scale:.12f}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{(z_pos + self.offsets[2]) * self.scale:.12f}")
            self.z_pos = z_pos
        if line:
            self.gcode.append("G01 " + " ".join(line))

    def arc_cw(
        self, x_pos=None, y_pos=None, z_pos=None, i_pos=None, j_pos=None, r_pos=None
    ) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{(x_pos + self.offsets[0]) * self.scale:.12f}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{(y_pos + self.offsets[1]) * self.scale:.12f}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{(z_pos + self.offsets[2]) * self.scale:.12f}")
            self.z_pos = z_pos
        if i_pos is not None:
            line.append(f"I{i_pos:.12f}")
        if j_pos is not None:
            line.append(f"J{j_pos:.12f}")
        if r_pos is not None:
            line.append(f"R{r_pos:.12f}")
        if line:
            self.gcode.append("G02 " + " ".join(line))

    def arc_ccw(
        self, x_pos=None, y_pos=None, z_pos=None, i_pos=None, j_pos=None, r_pos=None
    ) -> None:
        line = []
        if x_pos is not None and self.x_pos != x_pos:
            line.append(f"X{(x_pos + self.offsets[0]) * self.scale:.12f}")
            self.x_pos = x_pos
        if y_pos is not None and self.y_pos != y_pos:
            line.append(f"Y{(y_pos + self.offsets[1]) * self.scale:.12f}")
            self.y_pos = y_pos
        if z_pos is not None and self.z_pos != z_pos:
            line.append(f"Z{(z_pos + self.offsets[2]) * self.scale:.12f}")
            self.z_pos = z_pos
        if i_pos is not None:
            line.append(f"I{i_pos:.12f}")
        if j_pos is not None:
            line.append(f"J{j_pos:.12f}")
        if r_pos is not None:
            line.append(f"R{r_pos:.12f}")
        if line:
            self.gcode.append("G03 " + " ".join(line))

    def get(self, numbers=False) -> str:
        output = []
        if numbers:
            line_number = 1
            nlen = len(str(len(self.gcode))) + 1
            for line in self.gcode:
                if not line or line[0] in {" ", "("}:
                    output.append(line)
                else:
                    output.append(f"N{str(line_number).zfill(nlen)} {line}")
                    line_number += 1
        else:
            output = self.gcode
        return "\n".join(output)

    @staticmethod
    def suffix() -> str:
        return "ngc"

    @staticmethod
    def axis() -> list[str]:
        return ["X", "Y", "Z"]
