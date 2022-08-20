from .calc import calc_distance  # pylint: disable=E0402
from .vc_types import VcSegment


class DrawReaderBase:
    can_save_tabs = False
    min_max: list[float] = [0.0, 0.0, 0.0, 0.0]
    size: list[float] = []
    segments: list[VcSegment] = []
    filename: str = ""

    def draw_3d(self):
        pass

    def save_tabs(self, tabs: list) -> None:
        pass

    def save_starts(self, objects: dict) -> None:
        pass

    def get_segments(self) -> list[VcSegment]:
        return self.segments

    def get_minmax(self) -> list[float]:
        return self.min_max

    def get_size(self) -> list[float]:
        return self.size

    def draw(self, draw_function, user_data=()) -> None:
        for segment in self.segments:
            draw_function(segment.start, segment.end, *user_data)

    def _add_line(self, start, end, layer="0") -> None:
        dist = round(calc_distance(start, end), 6)
        if dist > 0.001:
            self.segments.append(
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": layer,
                        "start": start,
                        "end": end,
                        "bulge": 0.0,
                    }
                )
            )

    def _calc_size(self):
        self.min_max = [0.0, 0.0, 10.0, 10.0]
        for seg_idx, segment in enumerate(self.segments):
            if seg_idx == 0:
                self.min_max[0] = segment.start[0]
                self.min_max[1] = segment.start[1]
                self.min_max[2] = segment.start[0]
                self.min_max[3] = segment.start[1]
            else:
                self.min_max[0] = min(self.min_max[0], segment.start[0])
                self.min_max[1] = min(self.min_max[1], segment.start[1])
                self.min_max[2] = max(self.min_max[2], segment.start[0])
                self.min_max[3] = max(self.min_max[3], segment.start[1])

                self.min_max[0] = min(self.min_max[0], segment.end[0])
                self.min_max[1] = min(self.min_max[1], segment.end[1])
                self.min_max[2] = max(self.min_max[2], segment.end[0])
                self.min_max[3] = max(self.min_max[3], segment.end[1])

        self.size = []
        self.size.append(self.min_max[2] - self.min_max[0])
        self.size.append(self.min_max[3] - self.min_max[1])

    @staticmethod
    def suffix() -> list[str]:
        return []
