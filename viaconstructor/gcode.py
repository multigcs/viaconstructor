"""generates gcode"""
from typing import Union

import ezdxf

from .calc import calc_distance, rotate_list, vertex2points


class PostProcessor:
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
        self.gcode.append(f"G04 P{pause} (pause in sec)")

    def spindel_ccw(self, speed: int, pause: int = 1) -> None:
        self.gcode.append(f"M04 S{speed} (Spindle on / CCW)")
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
        return self.gcode


def gcode_begin(project: dict, post: PostProcessor) -> None:
    """gcode-header"""
    post.comment("--------------------------------------------------")
    post.comment("Generator: viaConstructor")
    post.comment(f"Filename: {project['filename_dxf']}")
    post.comment("--------------------------------------------------")
    post.separation()
    post.unit("mm")
    post.offsets("none")
    post.absolute(True)
    post.feedrate(project["setup"]["mill"]["rate_v"])
    if project["setup"]["mill"]["G64"] > 0.0:
        post.g64(project["setup"]["mill"]["G64"])
    post.spindel_off()
    post.tool(project["setup"]["tool"]["number"])
    post.spindel_cw(project["setup"]["tool"]["speed"])
    post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
    post.move(x_pos=0.0, y_pos=0.0)
    post.separation()


def gcode_end(project: dict, post: PostProcessor) -> None:
    """gcode-footer"""
    post.separation()
    post.comment("- end -")
    post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
    post.spindel_off()
    if project["setup"]["mill"]["back_home"]:
        post.move(x_pos=0.0, y_pos=0.0)
    post.program_end()
    post.separation()


def segment2gcode(
    project: dict, post: PostProcessor, last: list, point: list, set_depth: float
) -> None:
    bulge = last[2]
    if last[0] == point[0] and last[1] == point[1] and last[2] == point[2]:
        return

    if bulge > 0.0:
        (
            center,
            start_angle,  # pylint: disable=W0612
            end_angle,  # pylint: disable=W0612
            radius,
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)
        if project["setup"]["gcode"]["arc_r"]:
            post.arc_ccw(x_pos=point[0], y_pos=point[1], z_pos=set_depth, r_pos=radius)
        else:
            i = center[0] - last[0]
            j = center[1] - last[1]
            post.arc_ccw(
                x_pos=point[0], y_pos=point[1], z_pos=set_depth, i_pos=i, j_pos=j
            )
    elif bulge < 0.0:
        (
            center,
            start_angle,
            end_angle,
            radius,
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)
        if project["setup"]["gcode"]["arc_r"]:
            post.arc_cw(x_pos=point[0], y_pos=point[1], z_pos=set_depth, r_pos=radius)
        else:
            i = center[0] - last[0]
            j = center[1] - last[1]
            post.arc_cw(
                x_pos=point[0], y_pos=point[1], z_pos=set_depth, i_pos=i, j_pos=j
            )
    else:
        post.linear(x_pos=point[0], y_pos=point[1], z_pos=set_depth)


def get_nearest_free_object(
    polylines, level: int, last_pos: list, milling: dict
) -> tuple:
    found: bool = False
    nearest_dist: Union[None, float] = None
    nearest_idx: int = 0
    nearest_point = 0
    for offset_num, offset in polylines.items():
        if (
            offset_num not in milling
            and offset.level == level
            and offset.mill["active"]
        ):
            vertex_data = offset.vertex_data()
            if offset.is_closed():
                for point_num, pos_x in enumerate(vertex_data[0]):
                    pos_y = vertex_data[1][point_num]
                    dist = calc_distance(last_pos, (pos_x, pos_y))
                    if nearest_dist is None or dist < nearest_dist:
                        nearest_dist = dist
                        nearest_idx = offset_num
                        nearest_point = point_num
                        found = True
            else:
                # on open obejcts, test first and last point
                dist = calc_distance(last_pos, (vertex_data[0][0], vertex_data[1][0]))
                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = offset_num
                    nearest_point = 0
                    found = True
                dist = calc_distance(last_pos, (vertex_data[0][-1], vertex_data[1][-1]))
                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = offset_num
                    nearest_point = len(vertex_data[0]) - 1
                    found = True
    return (found, nearest_idx, nearest_point)


def polylines2gcode(project: dict) -> list[str]:
    """generates gcode from polilines"""
    # found milling order (nearest obj next)

    post = PostProcessor()

    milling: dict = {}
    last_pos: list = [0, 0]
    polylines = project["offsets"]
    gcode_begin(project, post)

    order = 0
    for level in range(project["maxOuter"], -1, -1):
        while True:

            (found, nearest_idx, nearest_point) = get_nearest_free_object(
                polylines, level, last_pos, milling
            )

            if found:
                milling[nearest_idx] = nearest_idx
                polyline = polylines[nearest_idx]

                vertex_data = polyline.vertex_data()
                is_closed = polyline.is_closed()

                points = vertex2points(vertex_data)
                if is_closed:
                    points = rotate_list(points, nearest_point)
                elif nearest_point != 0:
                    # redir open line and reverse bulge
                    x_start = list(vertex_data[0])
                    x_start.reverse()
                    y_start = list(vertex_data[1])
                    y_start.reverse()
                    bulges = list(vertex_data[2])
                    bulges.reverse()
                    bulges = rotate_list(bulges, 1)
                    for num, point in enumerate(bulges):
                        bulges[num] = -bulges[num]
                    points = vertex2points((x_start, y_start, bulges))

                helix_mode = polyline.mill["helix_mode"]

                # get object distance
                obj_distance = 0
                last = points[0]
                for point in points:
                    obj_distance += calc_distance(point, last)
                    last = point
                if is_closed:
                    obj_distance += calc_distance(point, points[0])

                post.separation()
                post.comment("--------------------------------------------------")
                post.comment(f"Level: {level}")
                post.comment(f"Order: {order}")
                post.comment(f"Object: {nearest_idx}")
                post.comment(f"Distance: {obj_distance}mm")
                post.comment(f"Closed: {is_closed}")
                post.comment(f"isPocket: {polyline.is_pocket}")
                post.comment(
                    f"Depth: {polyline.mill['depth']}mm / {polyline.mill['step']}mm"
                )
                post.comment(f"Tool-Diameter: {project['setup']['tool']['diameter']}mm")
                if polyline.tool_offset:
                    post.comment(
                        f"Tool-Offset: {project['setup']['tool']['diameter'] / 2.0}mm {polyline.tool_offset}"
                    )
                post.comment("--------------------------------------------------")

                if is_closed:
                    post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
                    post.move(x_pos=points[0][0], y_pos=points[0][1])

                depth = polyline.mill["step"]

                last_depth = 0.0
                while True:
                    if depth < polyline.mill["depth"]:
                        depth = polyline.mill["depth"]

                    post.comment(f"- Depth: {depth}mm -")

                    if not is_closed:
                        post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
                        post.move(x_pos=points[0][0], y_pos=points[0][1])

                    post.feedrate(project["setup"]["mill"]["rate_v"])

                    if helix_mode:
                        post.linear(z_pos=last_depth)
                    else:
                        post.linear(z_pos=depth)
                    post.feedrate(project["setup"]["mill"]["rate_h"])

                    trav_distance = 0
                    last = points[0]
                    for point in points:
                        if helix_mode:
                            trav_distance += calc_distance(point, last)
                            depth_diff = depth - last_depth
                            set_depth = last_depth + (
                                trav_distance / obj_distance * depth_diff
                            )
                        else:
                            set_depth = depth
                        segment2gcode(project, post, last, point, set_depth)
                        last = point

                    if is_closed:
                        point = points[0]

                        if helix_mode:
                            trav_distance += calc_distance(point, last)
                            depth_diff = depth - last_depth
                            set_depth = last_depth + (
                                trav_distance / obj_distance * depth_diff
                            )
                        else:
                            set_depth = depth
                        segment2gcode(project, post, last, point, set_depth)

                    last_depth = depth

                    if depth <= polyline.mill["depth"]:
                        if helix_mode:
                            helix_mode = False
                            continue
                        break
                    depth += polyline.mill["step"]

                post.move(z_pos=project["setup"]["mill"]["fast_move_z"])

                if is_closed:
                    last_pos = points[0]
                else:
                    last_pos = points[-1]
                order += 1
            else:
                break

    gcode_end(project, post)
    return post.get()
