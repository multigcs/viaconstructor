from ..machine_cmd import PostProcessor  # pylint: disable=E0402


class PostProcessorHpgl(PostProcessor):
    def __init__(self):
        self.hpgl: list[str] = []
        self.x_pos: float = None
        self.y_pos: float = None
        self.z_pos: float = None
        self.rate: int = 0
        self.toolrun: bool = False

    def separation(self) -> None:
        self.hpgl.append("")

    def absolute(self, active=True) -> None:
        if active:
            self.hpgl.append("PA")
        else:
            self.hpgl.append("PR")

    def program_end(self) -> None:
        self.hpgl.append("PU")

    def comment(self, text) -> None:
        self.hpgl.append(f"CO {text}")

    def tool(self, number="1") -> None:
        self.hpgl.append(f"SP{number}")

    def spindel_cw(self, speed: int, pause: int = 1) -> None:  # pylint: disable=W0613
        self.toolrun = True

    def spindel_ccw(self, speed: int, pause: int = 1) -> None:  # pylint: disable=W0613
        self.toolrun = True

    def spindel_off(self) -> None:
        self.toolrun = False

    def move(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        if x_pos:
            self.x_pos = x_pos
        if y_pos:
            self.y_pos = y_pos
        if z_pos:
            self.z_pos = z_pos
        if x_pos or y_pos:
            self.hpgl.append(f"PU{self.x_pos},{self.y_pos}")

    def linear(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        if x_pos:
            self.x_pos = x_pos
        if y_pos:
            self.y_pos = y_pos
        if z_pos:
            self.z_pos = z_pos
        if x_pos or y_pos:
            self.hpgl.append(
                f"P{'D' if self.toolrun else 'U'}{self.x_pos},{self.y_pos}"
            )

    def arc_cw(
        self,
        x_pos=None,
        y_pos=None,
        z_pos=None,
        i_pos=None,  # pylint: disable=W0613
        j_pos=None,  # pylint: disable=W0613
        r_pos=None,  # pylint: disable=W0613
    ) -> None:
        if x_pos:
            self.x_pos = x_pos
        if y_pos:
            self.y_pos = y_pos
        if z_pos:
            self.z_pos = z_pos
        if x_pos or y_pos:
            self.hpgl.append(
                f"P{'D' if self.toolrun else 'U'}{self.x_pos},{self.y_pos}"
            )

    def arc_ccw(
        self,
        x_pos=None,
        y_pos=None,
        z_pos=None,
        i_pos=None,  # pylint: disable=W0613
        j_pos=None,  # pylint: disable=W0613
        r_pos=None,  # pylint: disable=W0613
    ) -> None:
        if x_pos:
            self.x_pos = x_pos
        if y_pos:
            self.y_pos = y_pos
        if z_pos:
            self.z_pos = z_pos
        if x_pos or y_pos:
            self.hpgl.append(
                f"P{'D' if self.toolrun else 'U'}{self.x_pos},{self.y_pos}"
            )

    def get(self) -> list[str]:
        return self.hpgl

    @staticmethod
    def suffix() -> str:
        return "hpgl"

    @staticmethod
    def axis() -> str:
        return ["X", "Y"]
