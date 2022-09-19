"""generates machine commands"""
import math
from typing import Union

import ezdxf

from .calc import (
    angle_of_line,
    calc_distance,
    found_next_offset_point,
    lines_intersect,
    rotate_list,
    vertex2points,
    vertex_data_cache,
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

    def tool_offsets(self, offset="none") -> None:
        pass

    def machine_offsets(
        self, offsets: tuple[float, float, float] = (0.0, 0.0, 0.0), soft: bool = True
    ) -> None:
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

    def spindle_off(self) -> None:
        pass

    def spindle_cw(self, speed: int, pause: int = 1) -> None:
        pass

    def spindle_ccw(self, speed: int, pause: int = 1) -> None:
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

    def get(self) -> str:
        return ""


def machine_cmd_begin(project: dict, post: PostProcessor) -> None:
    """machine_cmd-header"""
    unit = project["setup"]["machine"]["unit"]
    fast_move_z = project["setup"]["mill"]["fast_move_z"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        fast_move_z *= unitscale

    if project["setup"]["machine"]["comments"]:
        post.comment("--------------------------------------------------")
        post.comment("Generator: viaConstructor")
        post.comment(f"Filename: {project['filename_draw']}")
        post.comment(f"Tool-Mode: {project['setup']['machine']['mode']}")
        if (
            project["setup"]["workpiece"]["offset_x"] != 0.0
            or project["setup"]["workpiece"]["offset_y"] != 0.0
            or project["setup"]["workpiece"]["offset_z"] != 0.0
        ):
            post.comment(
                f"Offsets: {project['setup']['workpiece']['offset_x']}, {project['setup']['workpiece']['offset_y']}, {project['setup']['workpiece']['offset_z']}"
            )
        post.comment("--------------------------------------------------")
    post.separation()

    post.program_start()

    post.unit(project["setup"]["machine"]["unit"])
    post.tool_offsets("none")

    post.machine_offsets(
        offsets=(
            project["setup"]["workpiece"]["offset_x"],
            project["setup"]["workpiece"]["offset_y"],
            project["setup"]["workpiece"]["offset_z"],
        ),
        soft=not project["setup"]["machine"]["g54"],
    )

    post.absolute(True)
    if project["setup"]["machine"]["mode"] == "mill" and "Z" in project["axis"]:
        if project["setup"]["mill"]["G64"] > 0.0:
            post.g64(project["setup"]["mill"]["G64"])
        post.spindle_off()
        post.tool(project["setup"]["tool"]["number"])
        post.spindle_cw(project["setup"]["tool"]["speed"])
        post.feedrate(project["setup"]["tool"]["rate_v"])
        post.move(z_pos=fast_move_z)
    elif project["setup"]["machine"]["mode"] == "laser_z" and "Z" in project["axis"]:
        post.spindle_off()
        post.feedrate(project["setup"]["tool"]["rate_v"])
        post.move(z_pos=fast_move_z)
    else:
        post.spindle_off()
        post.feedrate(project["setup"]["tool"]["rate_h"])
    post.separation()


def machine_cmd_end(project: dict, post: PostProcessor) -> None:
    """machine_cmd-footer"""
    unit = project["setup"]["machine"]["unit"]
    fast_move_z = project["setup"]["mill"]["fast_move_z"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        fast_move_z *= unitscale

    post.separation()
    if project["setup"]["machine"]["comments"]:
        post.comment("- end -")
    if project["setup"]["machine"]["mode"] != "laser" and "Z" in project["axis"]:
        post.move(z_pos=fast_move_z)
        post.spindle_off()
    if project["setup"]["mill"]["back_home"]:
        post.move(x_pos=0.0, y_pos=0.0)
    post.program_end()
    post.separation()


def segment2machine_cmd(
    project: dict,
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
    tabs_type = tabs.get("type", "rectangle")

    if bulge > 0.0:
        (
            center,
            start_angle,  # pylint: disable=W0612
            end_angle,  # pylint: disable=W0612
            radius,  # pylint: disable=W0612
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)
        circumference = 2 * radius * math.pi
        arc_lenght = (end_angle - start_angle) * circumference / (math.pi * 2)
        tab_width = min(tab_width, arc_lenght)
        tab_angle = (math.pi * 2) / (circumference / tab_width)

        for tab in tabs.get("data", ()):
            inters = lines_intersect(
                (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
            )
            if inters:
                half_angle = (
                    start_angle + (end_angle - start_angle) / 2 - (tab_angle / 2)
                )
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

                if (
                    project["setup"]["machine"]["mode"] != "mill"
                    or "Z" not in project["axis"]
                ):
                    post.spindle_off()

                if tabs_type == "rectangle":
                    post.linear(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=tabs_depth,
                    )
                else:
                    half_angle = start_angle + (end_angle - start_angle) / 2
                    (
                        start,
                        end,
                        bulge,
                    ) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
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

                half_angle = (
                    start_angle + (end_angle - start_angle) / 2 + (tab_angle / 2)
                )
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                if tabs_type == "rectangle":
                    post.arc_ccw(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=tabs_depth,
                        i_pos=(center[0] - last[0]),
                        j_pos=(center[1] - last[1]),
                    )
                    post.linear(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=set_depth,
                    )
                else:
                    post.arc_ccw(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=set_depth,
                        i_pos=(center[0] - last[0]),
                        j_pos=(center[1] - last[1]),
                    )
                last = end
                if (
                    project["setup"]["machine"]["mode"] != "mill"
                    or "Z" not in project["axis"]
                ):
                    post.spindle_cw(project["setup"]["tool"]["speed"], pause=0)
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
        circumference = 2 * radius * math.pi
        arc_lenght = (end_angle - start_angle) * circumference / (math.pi * 2)
        tab_width = min(tab_width, arc_lenght)
        tab_angle = (math.pi * 2) / (circumference / tab_width)

        for tab in tabs.get("data", ()):
            inters = lines_intersect(
                (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
            )
            if inters:
                half_angle = (
                    start_angle + (end_angle - start_angle) / 2 + (tab_angle / 2)
                )
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

                if (
                    project["setup"]["machine"]["mode"] != "mill"
                    or "Z" not in project["axis"]
                ):
                    post.spindle_off()

                if tabs_type == "rectangle":
                    post.linear(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=tabs_depth,
                    )
                else:
                    half_angle = start_angle + (end_angle - start_angle) / 2
                    (
                        start,
                        end,
                        bulge,
                    ) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
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

                half_angle = (
                    start_angle + (end_angle - start_angle) / 2 - (tab_angle / 2)
                )
                (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
                    center,
                    start_angle,
                    half_angle,
                    radius,
                )
                if tabs_type == "rectangle":
                    post.arc_cw(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=tabs_depth,
                        i_pos=(center[0] - last[0]),
                        j_pos=(center[1] - last[1]),
                    )
                    post.linear(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=set_depth,
                    )
                else:
                    post.arc_cw(
                        x_pos=end[0],
                        y_pos=end[1],
                        z_pos=set_depth,
                        i_pos=(center[0] - last[0]),
                        j_pos=(center[1] - last[1]),
                    )

                last = end
                if (
                    project["setup"]["machine"]["mode"] != "mill"
                    or "Z" not in project["axis"]
                ):
                    post.spindle_cw(project["setup"]["tool"]["speed"], pause=0)
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
                if (
                    project["setup"]["machine"]["mode"] != "mill"
                    or "Z" not in project["axis"]
                ):
                    post.spindle_off()

                if tabs_type == "rectangle":
                    post.linear(x_pos=tab_start_x, y_pos=tab_start_y, z_pos=tabs_depth)
                else:
                    post.linear(
                        x_pos=tab_list[tab_dist][0],
                        y_pos=tab_list[tab_dist][1],
                        z_pos=tabs_depth,
                    )

                if tabs_type == "rectangle":
                    post.linear(x_pos=tab_end_x, y_pos=tab_end_y, z_pos=tabs_depth)

                post.linear(x_pos=tab_end_x, y_pos=tab_end_y, z_pos=set_depth)

                if (
                    project["setup"]["machine"]["mode"] != "mill"
                    or "Z" not in project["axis"]
                ):
                    post.spindle_cw(project["setup"]["tool"]["speed"], pause=0)

        post.linear(x_pos=point[0], y_pos=point[1], z_pos=set_depth)


def get_nearest_free_object(
    polylines,
    level: int,
    last_pos: list,
    milling: set,
    is_pocket: bool,
    next_filter: str,
) -> tuple:
    found: bool = False
    nearest_dist: Union[None, float] = None
    nearest_idx: int = 0
    nearest_point = 0
    for offset_num, offset in polylines.items():
        if offset_num not in milling and (  # pylint: disable=R0916
            (
                next_filter == ""
                and offset.level == level
                and (offset.is_pocket != 0) == is_pocket
                and offset.setup["mill"]["active"]
            )
            or next_filter == offset_num
        ):
            if offset.is_pocket == 1 and offset.setup["pockets"]["insideout"]:
                pocket_filter = None
                offset_num_pre = offset_num.split(".")[0]
                for pocket_offset_num in polylines:
                    if (
                        pocket_offset_num not in milling
                        and pocket_offset_num.startswith(f"{offset_num_pre}.")
                    ):
                        pocket_filter = pocket_offset_num
                if offset_num != pocket_filter:
                    continue

            vertex_data = vertex_data_cache(offset)
            if offset.is_closed():
                if offset.start:
                    point_num = found_next_offset_point(
                        (offset.start[0], offset.start[1]), offset
                    )
                    if point_num:
                        point_num = point_num[2]
                        pos_x = vertex_data[0][point_num]
                        pos_y = vertex_data[1][point_num]
                        dist = calc_distance(last_pos, (pos_x, pos_y))
                        if nearest_dist is None or dist < nearest_dist:
                            nearest_dist = dist
                            nearest_idx = offset_num
                            nearest_point = point_num
                            found = True
                else:
                    point_num = 0
                    for pos_x, pos_y in zip(vertex_data[0], vertex_data[1]):
                        dist = calc_distance(last_pos, (pos_x, pos_y))
                        if nearest_dist is None or dist < nearest_dist:
                            nearest_dist = dist
                            nearest_idx = offset_num
                            nearest_point = point_num
                            found = True
                        point_num += 1
            else:
                # on open objects, test first and last point
                if len(vertex_data) > 0 and len(vertex_data[0]) > 0:
                    dist = calc_distance(
                        last_pos, (vertex_data[0][0], vertex_data[1][0])
                    )
                    if nearest_dist is None or dist < nearest_dist:
                        nearest_dist = dist
                        nearest_idx = offset_num
                        nearest_point = 0
                        found = True
                    if not offset.fixed_direction:
                        dist = calc_distance(
                            last_pos, (vertex_data[0][-1], vertex_data[1][-1])
                        )
                        if nearest_dist is None or dist < nearest_dist:
                            nearest_dist = dist
                            nearest_idx = offset_num
                            nearest_point = len(vertex_data[0]) - 1
                            found = True

    return (found, nearest_idx, nearest_point, nearest_dist)


def polylines2machine_cmd(project: dict, post: PostProcessor) -> str:
    """generates machine_cmd from polilines"""
    milling: set = set()
    last_pos: list = [0, 0]
    polylines = project["offsets"]
    machine_cmd_begin(project, post)
    tabs = project.get("tabs", {})

    unit = project["setup"]["machine"]["unit"]
    fast_move_z = project["setup"]["mill"]["fast_move_z"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        fast_move_z *= unitscale

    next_filter = ""
    order = 0
    was_pocket = False
    for level in range(project["maxOuter"], -1, -1):
        for is_pocket in (True, False):
            while True:
                (
                    found,
                    nearest_idx,
                    nearest_point,
                    nearest_dist,
                ) = get_nearest_free_object(
                    polylines, level, last_pos, milling, is_pocket, next_filter
                )
                next_filter = ""
                if found:
                    if "." in nearest_idx and nearest_idx.split(".")[-1] == "1":
                        # get parent after last pocket line
                        next_filter = f"{nearest_idx.split('.')[0]}.0"
                        if next_filter in milling:
                            next_filter = ""

                    milling.add(nearest_idx)
                    polyline = polylines[nearest_idx]
                    vertex_data = vertex_data_cache(polyline)
                    is_closed = polyline.is_closed()

                    max_depth = polyline.setup["mill"]["depth"]
                    step = polyline.setup["mill"]["step"]
                    if step >= -0.01:
                        step = -0.01
                    if unit == "inch":
                        unitscale = 25.4
                        max_depth *= unitscale
                        step *= unitscale

                    if polyline.setup["tabs"]["active"]:
                        polyline.setup["tabs"]["data"] = tabs["data"]
                    else:
                        polyline.setup["tabs"]["data"] = []

                    if is_closed:
                        points = rotate_list(vertex2points(vertex_data), nearest_point)
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
                    else:
                        points = vertex2points(vertex_data)

                    helix_mode = polyline.setup["mill"]["helix_mode"]

                    # get object distance
                    obj_distance = 0
                    last = points[0]
                    for point in points:
                        obj_distance += calc_distance(point, last)
                        last = point
                    if is_closed:
                        obj_distance += calc_distance(point, points[0])

                    if project["setup"]["machine"]["comments"]:
                        post.separation()
                        post.comment(
                            "--------------------------------------------------"
                        )
                        post.comment(f"Level: {level}")
                        post.comment(f"Order: {order}")
                        post.comment(f"Object: {nearest_idx}")
                        post.comment(
                            f"Distance: {round(obj_distance * unitscale, 4)}{unit}"
                        )
                        post.comment(f"Closed: {is_closed}")
                        post.comment(f"isPocket: {polyline.is_pocket != 0}")
                        if (
                            project["setup"]["machine"]["mode"] != "laser"
                            and "Z" in project["axis"]
                        ):
                            post.comment(
                                f"Depth: {polyline.setup['mill']['depth']}{unit} / {polyline.setup['mill']['step']}{unit}"
                            )
                        post.comment(
                            f"Tool-Diameter: {project['setup']['tool']['diameter']}{unit}"
                        )
                        if polyline.tool_offset:
                            post.comment(
                                f"Tool-Offset: {project['setup']['tool']['diameter'] / 2.0}{unit} {polyline.tool_offset}"
                            )
                        post.comment(
                            "--------------------------------------------------"
                        )

                    depth = step
                    depth = max(depth, max_depth)

                    if (
                        project["setup"]["machine"]["mode"] == "mill"
                        and "Z" in project["axis"]
                    ):
                        if not (
                            was_pocket
                            and is_pocket
                            and nearest_dist < project["setup"]["tool"]["diameter"]
                        ):
                            post.move(z_pos=fast_move_z)
                        elif helix_mode:
                            post.move(z_pos=0.0)
                        else:
                            post.move(z_pos=depth)

                    if (
                        project["setup"]["machine"]["mode"] != "mill"
                        or "Z" not in project["axis"]
                    ):
                        depth = 0.0
                        post.move(z_pos=depth)

                    post.move(x_pos=points[0][0], y_pos=points[0][1])

                    last_depth = 0.0
                    while True:
                        depth = max(depth, max_depth)

                        if (
                            project["setup"]["machine"]["mode"] != "laser"
                            and "Z" in project["axis"]
                        ):
                            if project["setup"]["machine"]["comments"]:
                                post.comment(f"- Depth: {depth}{unit} -")

                        if not is_closed:
                            if (
                                project["setup"]["machine"]["mode"] == "mill"
                                and "Z" in project["axis"]
                            ):
                                post.move(z_pos=fast_move_z)
                            post.move(x_pos=points[0][0], y_pos=points[0][1])

                        if (
                            project["setup"]["machine"]["mode"] != "laser"
                            and "Z" in project["axis"]
                        ):
                            post.feedrate(project["setup"]["tool"]["rate_v"])
                            if helix_mode:
                                post.linear(z_pos=last_depth)
                            else:
                                post.linear(z_pos=depth)
                            post.feedrate(project["setup"]["tool"]["rate_h"])

                        if (
                            project["setup"]["machine"]["mode"] != "mill"
                            or "Z" not in project["axis"]
                        ):
                            post.spindle_cw(project["setup"]["tool"]["speed"], pause=0)

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
                                project,
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
                                project,
                                post,
                                last,
                                point,
                                set_depth,
                                max_depth,
                                polyline.setup["tabs"],
                            )

                        last_depth = depth

                        zoffset = 0.0
                        if project["setup"]["machine"]["mode"] == "laser_z":
                            zoffset = step
                        if depth <= max_depth - zoffset:
                            if helix_mode:
                                helix_mode = False
                                continue
                            break
                        depth += step

                        if (
                            project["setup"]["machine"]["mode"] == "laser"
                            or "Z" not in project["axis"]
                        ):
                            break

                    # if project["setup"]["machine"]["mode"] != "laser":
                    #    post.move(z_pos=fast_move_z)

                    if project["setup"]["machine"]["mode"] != "mill":
                        post.spindle_off()

                    if is_closed:
                        last_pos = points[0]
                    else:
                        last_pos = points[-1]
                    order += 1
                else:
                    break

                was_pocket = is_pocket

    machine_cmd_end(project, post)
    return post.get()
