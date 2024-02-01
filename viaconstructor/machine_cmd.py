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

TWO_PI = math.pi * 2.0
HALF_PI = math.pi / 2.0


class PostProcessor:
    def separation(self) -> None:
        pass

    def raw(self, cmd) -> None:
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

    def coolant_mist(self) -> None:
        pass

    def coolant_flood(self) -> None:
        pass

    def coolant_off(self) -> None:
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

    def get(self, numbers=False) -> str:  # pylint: disable=W0613
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

        # post.tool(project["setup"]["tool"]["number"])
        # post.spindle_cw(
        #    project["setup"]["tool"]["speed"], project["setup"]["tool"]["pause"]
        # )

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
    tool: dict,
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
        if tabs.get("data"):
            circumference = 2 * radius * math.pi
            arc_lenght = (end_angle - start_angle) * circumference / (math.pi * 2)
            tab_width = min(tab_width, arc_lenght)
            if tab_width > 0.0 and circumference > 0.0:
                tab_angle = (math.pi * 2) / (circumference / tab_width)
            else:
                tab_angle = 0.1

            for tab in tabs.get("data", ()):
                inters = lines_intersect(
                    (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
                )
                if inters:
                    half_angle = (
                        start_angle + (end_angle - start_angle) / 2 - (tab_angle / 2)
                    )
                    (
                        start,  # pylint: disable=W0612
                        end,
                        bulge,
                    ) = ezdxf.math.arc_to_bulge(
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
                        post.spindle_cw(
                            tool["speed"],
                            tool["pause"],
                        )
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
        if tabs.get("data"):
            circumference = 2 * radius * math.pi
            arc_lenght = (end_angle - start_angle) * circumference / (math.pi * 2)
            tab_width = min(tab_width, arc_lenght)
            if tab_width > 0.0 and circumference > 0.0:
                tab_angle = (math.pi * 2) / (circumference / tab_width)
            else:
                tab_angle = 0.1

            for tab in tabs.get("data", ()):
                inters = lines_intersect(
                    (last[0], last[1]), (point[0], point[1]), tab[0], tab[1]
                )
                if inters:
                    half_angle = (
                        start_angle + (end_angle - start_angle) / 2 + (tab_angle / 2)
                    )
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
                        post.spindle_cw(
                            tool["speed"],
                            tool["pause"],
                        )
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
                angle = angle_of_line((last[0], last[1]), tab_list[tab_dist]) + HALF_PI

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
                    post.spindle_cw(
                        tool["speed"],
                        tool["pause"],
                    )

        post.linear(x_pos=point[0], y_pos=point[1], z_pos=set_depth)


def get_nearest_free_object(
    polylines,
    level: int,
    tool: int,
    last_pos: list,
    milling: set,
    objectorder: str,
    master_idx: str,
) -> tuple:
    found: bool = False
    nearest_dist: Union[None, float] = None
    nearest_idx: int = 0
    nearest_point = 0
    for offset_num, offset in polylines.items():
        if master_idx and master_idx not in offset.outer_objects and master_idx != offset.obj_idx:
            continue

        # no order
        if (
            objectorder == "unordered" and offset_num not in milling
        ):  # pylint: disable=R0916
            vertex_data = vertex_data_cache(offset)
            dist = calc_distance(last_pos, (vertex_data[0][0], vertex_data[1][0]))
            nearest_dist = dist
            nearest_idx = offset_num
            nearest_point = 0
            found = True
            break

        # find nearest
        if offset_num not in milling and (  # pylint: disable=R0916
            (
                (level == -1 or offset.level == level)
                and offset.setup["tool"]["number"] == tool
                and offset.setup["mill"]["active"]
            )
        ):

            if offset.setup["pockets"]["insideout"]:
                sub_found = False
                for pocket_offset_num, pocket_offset in polylines.items():
                    if (
                        pocket_offset.is_pocket != 0
                        and pocket_offset_num not in milling
                    ):
                        if pocket_offset_num.startswith(f"{offset_num}."):
                            sub_found = True
                            break
                # skip this offset while found a sub offset
                if sub_found:
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
    tabs = project.get("tabs", {})
    unit = project["setup"]["machine"]["unit"]
    fast_move_z = project["setup"]["mill"]["fast_move_z"]
    objectorder = project["setup"]["mill"]["objectorder"]
    unitscale = 1.0
    if unit == "inch":
        unitscale = 25.4
        fast_move_z *= unitscale

    machine_cmd_begin(project, post)

    tools = set()
    for polyline in polylines.values():
        if not polyline.setup["mill"]["active"]:
            continue
        tools.add(polyline.setup["tool"]["number"])

    order = 0
    was_pocket = False
    polylines_len = len(polylines.keys())
    polylines_n = 0
    last_percent = -1

    master_ids = []
    if objectorder == "per_object":
        # TODO: reorder master_ids (nearest)
        for obj_idx, obj_data in project["objects"].items():
            if not obj_data.outer_objects:
                master_ids.append(obj_idx)
    else:
        master_ids = [""]

    for master_idx in master_ids:
        levels = range(project["maxOuter"], -1, -1)
        # ignore levels
        #levels = [-1]
        for level in levels:
            for tool in tools:
                while True:
                    (
                        found,
                        nearest_idx,
                        nearest_point,
                        nearest_dist,
                    ) = get_nearest_free_object(
                        polylines,
                        level,
                        tool,
                        last_pos,
                        milling,
                        objectorder,
                        master_idx,
                    )
                    if found:
                        percent = round((polylines_n + 1) * 100 / polylines_len, 1)
                        if int(percent) != int(last_percent):
                            print(f"generating machine commands: {percent}%", end="\r")
                        last_percent = int(percent)
                        polylines_n += 1

                        milling.add(nearest_idx)
                        polyline = polylines[nearest_idx]
                        vertex_data = vertex_data_cache(polyline)
                        is_closed = polyline.is_closed()

                        coolant_mist = polyline.setup["tool"]["mist"]
                        coolant_flood = polyline.setup["tool"]["flood"]
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
                            for num, _point in enumerate(bulges):
                                bulges[num] = -bulges[num]
                            points = vertex2points((x_start, y_start, bulges))
                        else:
                            points = vertex2points(vertex_data)

                        helix_mode = polyline.setup["mill"]["helix_mode"]
                        if not is_closed:
                            helix_mode = False
                        # if polyline.is_pocket > 0:
                        #    helix_mode = False

                        # get object distance
                        obj_distance = 0
                        point = [0, 0]
                        last = points[0]
                        for point in points:
                            obj_distance += calc_distance(point, last)
                            last = point
                        if is_closed:
                            obj_distance += calc_distance(point, points[0])

                        diameter = None
                        for entry in project["setup"]["tool"]["tooltable"]:
                            if polyline.setup["tool"]["number"] == entry["number"]:
                                diameter = entry["diameter"]
                        if diameter is None:
                            print("ERROR: TOOL not found")
                            break

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
                            post.comment(f"Tool-Diameter: {diameter}{unit}")
                            if polyline.tool_offset:
                                post.comment(
                                    f"Tool-Offset: {diameter / 2.0}{unit} {polyline.tool_offset}"
                                )
                            post.comment(
                                "--------------------------------------------------"
                            )

                        # toolchange
                        if project["setup"]["machine"]["mode"] == "mill":
                            post.move(z_pos=fast_move_z)
                            if project["setup"]["machine"]["supports_toolchange"]:
                                post.tool(polyline.setup["tool"]["number"])
                            post.spindle_cw(
                                polyline.setup["tool"]["speed"],
                                polyline.setup["tool"]["pause"],
                            )

                        depth = step
                        depth = max(depth, max_depth)
                        min_depth = polyline.setup["mill"]["start_depth"]
                        depth = min(depth, min_depth)

                        if coolant_mist:
                            post.coolant_mist()
                        if coolant_flood:
                            post.coolant_flood()

                        if (
                            project["setup"]["machine"]["mode"] == "mill"
                            and "Z" in project["axis"]
                        ):
                            if not (was_pocket and nearest_dist < diameter):
                                post.move(z_pos=fast_move_z)
                            elif helix_mode:
                                post.move(z_pos=0.0)
                            else:
                                post.move(z_pos=depth)

                        was_pocket = polyline.is_pocket > 0

                        if (
                            project["setup"]["machine"]["mode"] != "mill"
                            or "Z" not in project["axis"]
                        ):
                            depth = 0.0
                            post.move(z_pos=depth)

                        lead_in_active = polyline.setup["leads"]["in"]
                        lead_out_active = polyline.setup["leads"]["out"]
                        if not is_closed:
                            # only on closed contours
                            lead_in_active = "off"
                            lead_out_active = "off"
                        if not polyline.start:
                            # only if a start point is set
                            lead_in_active = "off"
                            lead_out_active = "off"
                        if max_depth < step:
                            # lead-out only on single pathes
                            lead_out_active = "off"

                        if lead_in_active != "off":
                            lead_in_lenght = polyline.setup["leads"]["in_lenght"]
                            line_angle = angle_of_line(points[0], points[1])
                            if lead_in_active == "straight":
                                lead_in_x = points[0][0] - lead_in_lenght * math.sin(
                                    line_angle
                                )
                                lead_in_y = points[0][1] + lead_in_lenght * math.cos(
                                    line_angle
                                )
                            else:
                                lead_radius = lead_in_lenght * 2 / math.pi
                                if polyline.setup["mill"]["reverse"]:
                                    lead_in_center_x = points[0][
                                        0
                                    ] + lead_radius * math.sin(line_angle)
                                    lead_in_center_y = points[0][
                                        1
                                    ] - lead_radius * math.cos(line_angle)
                                    lead_in_x = lead_in_center_x + lead_radius * math.sin(
                                        line_angle - HALF_PI
                                    )
                                    lead_in_y = lead_in_center_y - lead_radius * math.cos(
                                        line_angle - HALF_PI
                                    )
                                else:
                                    line_angle = (
                                        angle_of_line(points[0], points[1]) + math.pi
                                    )
                                    lead_in_center_x = points[0][
                                        0
                                    ] + lead_radius * math.sin(line_angle)
                                    lead_in_center_y = points[0][
                                        1
                                    ] - lead_radius * math.cos(line_angle)
                                    lead_in_x = lead_in_center_x + lead_radius * math.sin(
                                        line_angle + HALF_PI
                                    )
                                    lead_in_y = lead_in_center_y - lead_radius * math.cos(
                                        line_angle + HALF_PI
                                    )
                            post.move(x_pos=lead_in_x, y_pos=lead_in_y)
                        else:
                            post.move(x_pos=points[0][0], y_pos=points[0][1])

                        if lead_out_active != "off":
                            lead_out_lenght = polyline.setup["leads"]["out_lenght"]
                            line_angle = angle_of_line(points[0], points[1])
                            if lead_out_active == "straight":
                                lead_out_x = points[0][0] - lead_out_lenght * math.sin(
                                    line_angle
                                )
                                lead_out_y = points[0][1] + lead_out_lenght * math.cos(
                                    line_angle
                                )
                            else:
                                lead_radius = lead_out_lenght * 2 / math.pi
                                if polyline.setup["mill"]["reverse"]:
                                    lead_out_center_x = points[0][
                                        0
                                    ] + lead_radius * math.sin(line_angle)
                                    lead_out_center_y = points[0][
                                        1
                                    ] - lead_radius * math.cos(line_angle)
                                    lead_out_x = lead_out_center_x + lead_radius * math.sin(
                                        line_angle + HALF_PI
                                    )
                                    lead_out_y = lead_out_center_y - lead_radius * math.cos(
                                        line_angle + HALF_PI
                                    )
                                else:
                                    line_angle = (
                                        angle_of_line(points[0], points[1]) + math.pi
                                    )
                                    lead_out_center_x = points[0][
                                        0
                                    ] + lead_radius * math.sin(line_angle)
                                    lead_out_center_y = points[0][
                                        1
                                    ] - lead_radius * math.cos(line_angle)
                                    lead_out_x = lead_out_center_x + lead_radius * math.sin(
                                        line_angle - HALF_PI
                                    )
                                    lead_out_y = lead_out_center_y - lead_radius * math.cos(
                                        line_angle - HALF_PI
                                    )

                        last_depth = 0.0
                        passes = 1
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
                                post.feedrate(polyline.setup["tool"]["rate_v"])
                                if helix_mode:
                                    post.linear(z_pos=last_depth)
                                else:
                                    post.linear(z_pos=depth)
                                post.feedrate(polyline.setup["tool"]["rate_h"])

                            if (
                                project["setup"]["machine"]["mode"] != "mill"
                                or "Z" not in project["axis"]
                            ):
                                post.spindle_cw(
                                    polyline.setup["tool"]["speed"],
                                    polyline.setup["tool"]["pause"],
                                )

                            if lead_in_active != "off":

                                if lead_in_active == "straight":
                                    post.linear(
                                        x_pos=points[0][0],
                                        y_pos=points[0][1],
                                    )
                                else:
                                    if polyline.setup["mill"]["reverse"]:
                                        post.arc_cw(
                                            x_pos=points[0][0],
                                            y_pos=points[0][1],
                                            i_pos=(lead_in_center_x - lead_in_x),
                                            j_pos=(lead_in_center_y - lead_in_y),
                                        )
                                    else:
                                        post.arc_ccw(
                                            x_pos=points[0][0],
                                            y_pos=points[0][1],
                                            i_pos=(lead_in_center_x - lead_in_x),
                                            j_pos=(lead_in_center_y - lead_in_y),
                                        )
                                lead_in_active = "off"

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
                                    polyline.setup["tool"],
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
                                    polyline.setup["tool"],
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
                                and polyline.setup["mill"]["passes"] == passes
                            ) or "Z" not in project["axis"]:
                                break

                            passes += 1

                        if lead_out_active != "off":
                            if lead_out_active == "straight":
                                post.linear(
                                    x_pos=lead_out_x,
                                    y_pos=lead_out_y,
                                )
                            else:
                                if polyline.setup["mill"]["reverse"]:
                                    post.arc_cw(
                                        x_pos=lead_out_x,
                                        y_pos=lead_out_y,
                                        i_pos=(lead_out_center_x - points[0][0]),
                                        j_pos=(lead_out_center_y - points[0][1]),
                                    )
                                else:
                                    post.arc_ccw(
                                        x_pos=lead_out_x,
                                        y_pos=lead_out_y,
                                        i_pos=(lead_out_center_x - points[0][0]),
                                        j_pos=(lead_out_center_y - points[0][1]),
                                    )
                            lead_out_active = "off"

                        if project["setup"]["machine"]["mode"] != "mill":
                            post.spindle_off()

                        if is_closed:
                            last_pos = points[0]
                        else:
                            last_pos = points[-1]
                        order += 1

                        if coolant_mist or coolant_flood:
                            post.coolant_off()

                    else:
                        break

    machine_cmd_end(project, post)
    print("")
    return post.get(numbers=project["setup"]["machine"].get("numbers", False))
