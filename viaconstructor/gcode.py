"""generates gcode"""
from typing import Union

import ezdxf

from .calc import calc_distance, rotate_list, vertex2points


def gcode_begin(project: dict) -> list[str]:
    """gcode-header"""
    gcode: list[str] = []

    gcode.append("(--------------------------------------------------)")
    gcode.append("(Generator: viaConstructor)")
    gcode.append(f"(Filename: {project['filename_dxf']})")
    gcode.append("(--------------------------------------------------)")
    gcode.append("")

    gcode.append("G21 (Metric/mm)")
    gcode.append("G40 (No Offsets)")
    gcode.append("G90 (Absolute-Mode)")
    gcode.append(f"F{project['setup']['mill']['rate_v']}")
    if project["setup"]["mill"]["G64"] > 0.0:
        gcode.append(f"G64 P{project['setup']['mill']['G64']}")
    gcode.append("M05 (Spindle off)")
    gcode.append(f"M06 T{project['setup']['tool']['number']}")
    gcode.append(f"M03 S{project['setup']['tool']['speed']} (Spindle on / CW)")
    gcode.append("G04 P1 (pause in sec)")
    gcode.append(f"G00 Z{round(project['setup']['mill']['fast_move_z'], 6)}")
    gcode.append("G00 X0.0 Y0.0")
    gcode.append("")
    return gcode


def gcode_end(project: dict) -> list[str]:
    """gcode-footer"""
    gcode: list[str] = []
    gcode.append("")
    gcode.append("(- end -)")
    gcode.append(f"G00 Z{round(project['setup']['mill']['fast_move_z'], 6)}")
    gcode.append("M05 (Spindle off)")
    if project["setup"]["mill"]["back_home"]:
        gcode.append("G00 X0.0 Y0.0")
    gcode.append("M02")
    gcode.append("")
    return gcode


def segment2gcode(
    project: dict, last: list, point: list, set_depth: float
) -> list[str]:
    gcode: list[str] = []
    bulge = last[2]
    if last[0] == point[0] and last[1] == point[1] and last[2] == point[2]:
        return gcode

    if bulge > 0.0:
        (
            center,
            start_angle,  # pylint: disable=W0612
            end_angle,  # pylint: disable=W0612
            radius,
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)
        if project["setup"]["gcode"]["arc_r"]:
            gcode.append(
                f"G03 X{round(point[0], 6)} Y{round(point[1], 6)} Z{round(set_depth, 6)} R{round(radius, 6)}"
            )
        else:
            i = center[0] - last[0]
            j = center[1] - last[1]
            gcode.append(
                f"G03 X{round(point[0], 6)} Y{round(point[1], 6)} Z{round(set_depth, 6)} I{round(i, 6)} J{round(j, 6)}"
            )
    elif bulge < 0.0:
        (
            center,
            start_angle,
            end_angle,
            radius,
        ) = ezdxf.math.bulge_to_arc(last, point, bulge)
        if project["setup"]["gcode"]["arc_r"]:
            gcode.append(
                f"G02 X{round(point[0], 6)} Y{round(point[1], 6)} Z{round(set_depth, 6)} R{round(radius, 6)}"
            )
        else:
            i = center[0] - last[0]
            j = center[1] - last[1]
            gcode.append(
                f"G02 X{round(point[0], 6)} Y{round(point[1], 6)} Z{round(set_depth, 6)} I{round(i, 6)} J{round(j, 6)}"
            )
    else:
        gcode.append(
            f"G01 X{round(point[0], 6)} Y{round(point[1], 6)} Z{round(set_depth, 6)}"
        )

    return gcode


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
            if offset.is_closed():
                vertex_data = offset.vertex_data()
                for point_num, point in enumerate(vertex2points(vertex_data)):
                    dist = calc_distance(last_pos, point)
                    if nearest_dist is None or dist < nearest_dist:
                        nearest_dist = dist
                        nearest_idx = offset_num
                        nearest_point = point_num
                        found = True
            else:
                # on open obejcts, test first and last point
                vertex_data = offset.vertex_data()
                points = vertex2points(vertex_data)
                dist = calc_distance(last_pos, points[0])
                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = offset_num
                    nearest_point = 0
                    found = True

                dist = calc_distance(last_pos, points[-1])
                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = offset_num
                    nearest_point = len(points) - 1
                    found = True

    return (found, nearest_idx, nearest_point)


def polylines2gcode(project: dict) -> list[str]:
    """generates gcode from polilines"""
    # found milling order (nearest obj next)
    milling: dict = {}
    last_pos: list = [0, 0]
    polylines = project["offsets"]
    gcode: list[str] = []
    gcode += gcode_begin(project)

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

                gcode.append("")
                gcode.append("(--------------------------------------------------)")
                gcode.append(f"(Level: {level})")
                gcode.append(f"(Order: {order})")
                gcode.append(f"(Object: {nearest_idx})")
                gcode.append(f"(Distance: {obj_distance}mm)")
                gcode.append(f"(Closed: {is_closed})")
                gcode.append(f"(isPocket: {polyline.is_pocket})")
                gcode.append(
                    f"(Depth: {polyline.mill['depth']}mm / {polyline.mill['step']}mm)"
                )
                gcode.append(
                    f"(Tool-Diameter: {project['setup']['tool']['diameter']}mm)"
                )
                if polyline.tool_offset:
                    gcode.append(
                        f"(Tool-Offset: {project['setup']['tool']['diameter'] / 2.0}mm {polyline.tool_offset})"
                    )
                gcode.append("(--------------------------------------------------)")

                if is_closed:
                    gcode.append(
                        f"G00 Z{round(project['setup']['mill']['fast_move_z'], 6)}"
                    )
                    gcode.append(f"G00 X{points[0][0]} Y{points[0][1]}")

                depth = polyline.mill["step"]

                last_depth = 0.0
                while True:
                    if depth < polyline.mill["depth"]:
                        depth = polyline.mill["depth"]

                    gcode.append(f"(- Depth: {depth}mm -)")

                    if not is_closed:
                        gcode.append(
                            f"G00 Z{round(project['setup']['mill']['fast_move_z'], 6)}"
                        )
                        gcode.append(f"G00 X{points[0][0]} Y{points[0][1]}")

                    gcode.append(f"F{project['setup']['mill']['rate_v']}")

                    if helix_mode:
                        gcode.append(f"G01 Z{last_depth}")
                    else:
                        gcode.append(f"G01 Z{depth}")
                    gcode.append(f"F{project['setup']['mill']['rate_h']}")

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
                        gcode += segment2gcode(project, last, point, set_depth)
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
                        gcode += segment2gcode(project, last, point, set_depth)

                    last_depth = depth

                    if depth <= polyline.mill["depth"]:
                        if helix_mode:
                            helix_mode = False
                            continue
                        break
                    depth += polyline.mill["step"]

                gcode.append(
                    f"G00 Z{round(project['setup']['mill']['fast_move_z'], 6)}"
                )

                if is_closed:
                    last_pos = points[0]
                else:
                    last_pos = points[-1]
                order += 1
            else:
                break

    gcode += gcode_end(project)
    return gcode
