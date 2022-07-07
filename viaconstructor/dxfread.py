"""dxf reading."""

import math
import ezdxf


class DxfReader:
    def __init__(self, filename: str):
        """converting dxf into single segments."""
        doc = ezdxf.readfile(filename)

        # dxf to single segments
        self.segments: list[dict] = []
        model_space = doc.modelspace()
        for element in model_space:
            dxftype = element.dxftype()
            if dxftype == "LINE":
                self.segments.append(
                    {
                        "type": dxftype,
                        "object": None,
                        "start": (
                            element.dxf.start.x,
                            element.dxf.start.y,
                            element.dxf.start.z,
                        ),
                        "end": (
                            element.dxf.end.x,
                            element.dxf.end.y,
                            element.dxf.end.z,
                        ),
                        "bulge": 0.0,
                    }
                )

            elif dxftype == "SPLINE":
                last: list[float] = []
                for point in element._control_points:  # type: ignore
                    if last:
                        self.segments.append(
                            {
                                "type": "LINE",
                                "object": None,
                                "start": (last[0], last[1]),
                                "end": (point[0], point[1]),
                                "bulge": 0.0,
                            }
                        )
                    last = point

            elif dxftype == "LWPOLYLINE":
                with element.points("xyb") as points:  # type: ignore
                    last = []
                    for point in points:
                        if last:
                            self.segments.append(
                                {
                                    "type": "LINE",
                                    "object": None,
                                    "start": (last[0], last[1]),
                                    "end": (point[0], point[1]),
                                    "bulge": last[2],
                                }
                            )
                        else:
                            first = point
                        last = point
                    if element.dxf.flags == 1:
                        self.segments.append(
                            {
                                "type": "LINE",
                                "object": None,
                                "start": (last[0], last[1]),
                                "end": (first[0], first[1]),
                                "bulge": last[2],
                            }
                        )

            elif dxftype in {"ARC", "CIRCLE"}:
                if dxftype == "CIRCLE":
                    start_angle = 0.0
                    adiff = 360.0
                else:
                    start_angle = element.dxf.start_angle
                    adiff = element.dxf.end_angle - element.dxf.start_angle
                if adiff < 0.0:
                    adiff += 360.0
                # split arcs in maximum 20mm long segments and minimum 45°
                num_parts = (element.dxf.radius * 2 * math.pi) / 20.0
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
                            element.dxf.center,
                            angle / 180 * math.pi,
                            (angle + astep) / 180 * math.pi,
                            element.dxf.radius,
                        )
                        self.segments.append(
                            {
                                "type": dxftype,
                                "object": None,
                                "start": (start.x, start.y),
                                "end": (end.x, end.y),
                                "bulge": bulge,
                                "center": list(element.dxf.center),
                            }
                        )
                        angle += astep

                else:

                    (start, end, bulge) = ezdxf.math.arc_to_bulge(
                        element.dxf.center,
                        element.dxf.start_angle / 180 * math.pi,
                        element.dxf.end_angle / 180 * math.pi,
                        element.dxf.radius,
                    )
                    self.segments.append(
                        {
                            "type": dxftype,
                            "object": None,
                            "start": (start.x, start.y),
                            "end": (end.x, end.y),
                            "bulge": bulge,
                            "center": list(element.dxf.center),
                        }
                    )

            else:
                print("UNSUPPORTED TYPE: ", dxftype)
                for attrib in element.__dict__:
                    print(f"  element.{attrib} = {getattr(element, attrib)}")
                for attrib in element.dxf.__dict__:
                    print(f"  element.dxf.{attrib} = {getattr(element.dxf, attrib)}")

        self.min_max = [
            self.segments[0]["start"][0],
            self.segments[0]["start"][1],
            self.segments[0]["end"][0],
            self.segments[0]["end"][1],
        ]

        for segment in self.segments:
            for point in ("start", "end"):
                self.min_max[0] = min(self.min_max[0], segment[point][0])
                self.min_max[1] = min(self.min_max[1], segment[point][1])
                self.min_max[2] = max(self.min_max[2], segment[point][0])
                self.min_max[3] = max(self.min_max[3], segment[point][1])

        self.size = []
        self.size.append(self.min_max[2] - self.min_max[0])
        self.size.append(self.min_max[3] - self.min_max[1])

    def get_segments(self) -> list[dict]:
        return self.segments

    def get_minmax(self) -> list[float]:
        return self.min_max

    def get_size(self) -> list[float]:
        return self.size

    def draw(self, draw_function, user_data=()) -> None:
        for segment in self.segments:
            draw_function(segment["start"], segment["end"], *user_data)
