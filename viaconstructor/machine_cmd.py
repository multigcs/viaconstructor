"""generates machine commands"""
import math
from typing import Union

import ezdxf

from .calc import (
    angle_of_line,
    calc_distance,
    lines_intersect,
    rotate_list,
    vertex2points,
)


class PostProcessor:
    def separation(self) -> None:
        pass

    def g64(self, value) -> None:
        pass

    def feedrate(self, feedrate) -> None:
        pass

    def unit(self, unit="mm") -> None:
        pass

    def absolute(self, active=True) -> None:
        pass

    def offsets(self, offset="none") -> None:
        pass

    def program_start(self) -> None:
        pass

    def program_end(self) -> None:
        pass

    def comment(self, text) -> None:
        pass

    def move(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        pass

    def tool(self, number="1") -> None:
        pass

    def spindel_off(self) -> None:
        pass

    def spindel_cw(self, speed: int, pause: int = 1) -> None:
        pass

    def spindel_ccw(self, speed: int, pause: int = 1) -> None:
        pass

    def linear(self, x_pos=None, y_pos=None, z_pos=None) -> None:
        pass

    def arc_cw(
        self, x_pos=None, y_pos=None, z_pos=None, i_pos=None, j_pos=None, r_pos=None
    ) -> None:
        pass

    def arc_ccw(
        self, x_pos=None, y_pos=None, z_pos=None, i_pos=None, j_pos=None, r_pos=None
    ) -> None:
        pass

    def get(self) -> list[str]:
        return []


def machine_cmd_begin(project: dict, post: PostProcessor) -> None:
    """machine_cmd-header"""
    post.comment("--------------------------------------------------")
    post.comment("Generator: viaConstructor")
    post.comment(f"Filename: {project['filename_draw']}")
    if project["setup"]["maschine"]["laser"]:
        post.comment("Laser-Mode: active")
    post.comment("--------------------------------------------------")
    post.separation()
    post.program_start()
    post.unit("mm")
    post.offsets("none")
    post.absolute(True)
    if not project["setup"]["maschine"]["laser"] and "Z" in project["axis"]:
        post.feedrate(project["setup"]["tool"]["rate_v"])
        if project["setup"]["mill"]["G64"] > 0.0:
            post.g64(project["setup"]["mill"]["G64"])
        post.spindel_off()
        post.tool(project["setup"]["tool"]["number"])
        post.spindel_cw(project["setup"]["tool"]["speed"])
        post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
    else:
        post.spindel_off()
        post.feedrate(project["setup"]["tool"]["rate_h"])

    post.separation()


def machine_cmd_end(project: dict, post: PostProcessor) -> None:
    """machine_cmd-footer"""
    post.separation()
    post.comment("- end -")
    if not project["setup"]["maschine"]["laser"] and "Z" in project["axis"]:
        post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
        post.spindel_off()
    if project["setup"]["mill"]["back_home"]:
        post.move(x_pos=0.0, y_pos=0.0)
    post.program_end()
    post.separation()


def segment2machine_cmd(
    post: PostProcessor,
    last: list,
    point: list,
    set_depth: float,
    max_depth: float,
    tabs: dict,
) -> None:
    bulge = last[2]
    if last[0] == point[0] and last[1] == point[1] and last[2] == point[2]:
        return

    tabs_height = tabs.get("height", 1.0)
    tab_width = tabs.get("width", 10.0)
    tabs_depth = max_depth + tabs_height
    tabs_depth = max(tabs_depth, set_depth)
    tabs_depth = min(tabs_depth, 0.0)

    if bulge > 0.0:
        (
            center,
            start_angle,  # pylint: disable=W0612
            end_angle,  # pylint: disable=W0612
            radius,  # pylint: disable=W0612
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)

        for tab in tabs.get("data", ()):
            inters = lines_intersect(
                (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
            )
            if inters:
                half_angle = start_angle + (end_angle - start_angle) / 4
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                post.arc_ccw(
                    x_pos=end[0],
                    y_pos=end[1],
                    z_pos=set_depth,
                    i_pos=(center[0] - last[0]),
                    j_pos=(center[1] - last[1]),
                )
                last = end

                half_angle = start_angle + (end_angle - start_angle) / 2
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                post.arc_ccw(
                    x_pos=end[0],
                    y_pos=end[1],
                    z_pos=tabs_depth,
                    i_pos=(center[0] - last[0]),
                    j_pos=(center[1] - last[1]),
                )
                last = end

                half_angle = start_angle + (end_angle - start_angle) / 4 * 3
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                post.arc_ccw(
                    x_pos=end[0],
                    y_pos=end[1],
                    z_pos=set_depth,
                    i_pos=(center[0] - last[0]),
                    j_pos=(center[1] - last[1]),
                )
                last = end

                break

        post.arc_ccw(
            x_pos=point[0],
            y_pos=point[1],
            z_pos=set_depth,
            i_pos=(center[0] - last[0]),
            j_pos=(center[1] - last[1]),
        )

    elif bulge < 0.0:
        (
            center,
            start_angle,
            end_angle,
            radius,
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)

        for tab in tabs.get("data", ()):
            inters = lines_intersect(
                (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
            )
            if inters:
                half_angle = start_angle + (end_angle - start_angle) / 4 * 3
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                post.arc_cw(
                    x_pos=end[0],
                    y_pos=end[1],
                    z_pos=set_depth,
                    i_pos=(center[0] - last[0]),
                    j_pos=(center[1] - last[1]),
                )
                last = end

                half_angle = start_angle + (end_angle - start_angle) / 2
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                post.arc_cw(
                    x_pos=end[0],
                    y_pos=end[1],
                    z_pos=tabs_depth,
                    i_pos=(center[0] - last[0]),
                    j_pos=(center[1] - last[1]),
                )
                last = end

                half_angle = start_angle + (end_angle - start_angle) / 4
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                post.arc_cw(
                    x_pos=end[0],
                    y_pos=end[1],
                    z_pos=set_depth,
                    i_pos=(center[0] - last[0]),
                    j_pos=(center[1] - last[1]),
                )
                last = end

                break

        post.arc_cw(
            x_pos=point[0],
            y_pos=point[1],
            z_pos=set_depth,
            i_pos=(center[0] - last[0]),
            j_pos=(center[1] - last[1]),
        )
    else:

        tab_list = {}
        for tab in tabs.get("data", ()):
            inters = lines_intersect(
                (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
            )
            if inters:
                dist = calc_distance((last[0], last[1]), inters)
                tab_list[dist] = inters

        if tab_list:
            for tab_dist in sorted(tab_list.keys()):
                angle = (
                    angle_of_line((last[0], last[1]), tab_list[tab_dist]) + math.pi / 2
                )

                tab_start_x = last[0] + (tab_dist - (tab_width / 2)) * math.sin(angle)
                tab_start_y = last[1] - (tab_dist - (tab_width / 2)) * math.cos(angle)
                tab_end_x = last[0] + (tab_dist + (tab_width / 2)) * math.sin(angle)
                tab_end_y = last[1] - (tab_dist + (tab_width / 2)) * math.cos(angle)

                post.linear(x_pos=tab_start_x, y_pos=tab_start_y, z_pos=set_depth)
                post.linear(
                    x_pos=tab_list[tab_dist][0],
                    y_pos=tab_list[tab_dist][1],
                    z_pos=tabs_depth,
                )
                post.linear(x_pos=tab_end_x, y_pos=tab_end_y, z_pos=set_depth)

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
            and offset.setup["mill"]["active"]
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


def polylines2machine_cmd(project: dict, post: PostProcessor) -> list[str]:
    """generates machine_cmd from polilines"""
    milling: dict = {}
    last_pos: list = [0, 0]
    polylines = project["offsets"]
    machine_cmd_begin(project, post)
    tabs = project.get("tabs", {})

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
                max_depth = polyline.setup["mill"]["depth"]

                if polyline.setup["tabs"]["active"]:
                    polyline.setup["tabs"]["data"] = tabs["data"]
                else:
                    polyline.setup["tabs"]["data"] = []

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

                helix_mode = polyline.setup["mill"]["helix_mode"]

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
                if not project["setup"]["maschine"]["laser"] and "Z" in project["axis"]:
                    post.comment(
                        f"Depth: {polyline.setup['mill']['depth']}mm / {polyline.setup['mill']['step']}mm"
                    )
                post.comment(f"Tool-Diameter: {project['setup']['tool']['diameter']}mm")
                if polyline.tool_offset:
                    post.comment(
                        f"Tool-Offset: {project['setup']['tool']['diameter'] / 2.0}mm {polyline.tool_offset}"
                    )
                post.comment("--------------------------------------------------")

                if is_closed:
                    if (
                        not project["setup"]["maschine"]["laser"]
                        and "Z" in project["axis"]
                    ):
                        post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
                    post.move(x_pos=points[0][0], y_pos=points[0][1])

                depth = polyline.setup["mill"]["step"]
                if project["setup"]["maschine"]["laser"] or "Z" not in project["axis"]:
                    depth = 0.0
                    post.spindel_cw(project["setup"]["tool"]["speed"], pause=0)

                last_depth = 0.0
                while True:
                    if depth < polyline.setup["mill"]["depth"]:
                        depth = polyline.setup["mill"]["depth"]

                    if (
                        not project["setup"]["maschine"]["laser"]
                        and "Z" in project["axis"]
                    ):
                        post.comment(f"- Depth: {depth}mm -")

                    if not is_closed:
                        if (
                            not project["setup"]["maschine"]["laser"]
                            and "Z" in project["axis"]
                        ):
                            post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
                        post.move(x_pos=points[0][0], y_pos=points[0][1])

                    if (
                        not project["setup"]["maschine"]["laser"]
                        and "Z" in project["axis"]
                    ):
                        post.feedrate(project["setup"]["tool"]["rate_v"])
                        if helix_mode:
                            post.linear(z_pos=last_depth)
                        else:
                            post.linear(z_pos=depth)
                        post.feedrate(project["setup"]["tool"]["rate_h"])

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
                        segment2machine_cmd(
                            post,
                            last,
                            point,
                            set_depth,
                            max_depth,
                            polyline.setup["tabs"],
                        )
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
                        segment2machine_cmd(
                            post,
                            last,
                            point,
                            set_depth,
                            max_depth,
                            polyline.setup["tabs"],
                        )

                    last_depth = depth

                    if depth <= polyline.setup["mill"]["depth"]:
                        if helix_mode:
                            helix_mode = False
                            continue
                        break
                    depth += polyline.setup["mill"]["step"]

                    if (
                        project["setup"]["maschine"]["laser"]
                        or "Z" not in project["axis"]
                    ):
                        break

                if not project["setup"]["maschine"]["laser"]:
                    post.move(z_pos=project["setup"]["mill"]["fast_move_z"])
                else:
                    post.spindel_off()

                if is_closed:
                    last_pos = points[0]
                else:
                    last_pos = points[-1]
                order += 1
            else:
                break

    machine_cmd_end(project, post)
    return post.get()
