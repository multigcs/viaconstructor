"""viaconstructor calculation functions."""

import math
from copy import deepcopy

import cavaliercontours as cavc
import ezdxf


# ########## Misc Functions ###########
def rotate_list(rlist, idx):
    """rotating a list of values."""
    return rlist[idx:] + rlist[:idx]


# ########## Point Functions ###########
def lines_intersect(line1_start, line1_end, line2_start, line2_end):
    x_1, y_1 = line1_start
    x_2, y_2 = line1_end
    x_3, y_3 = line2_start
    x_4, y_4 = line2_end
    denom = (y_4 - y_3) * (x_2 - x_1) - (x_4 - x_3) * (y_2 - y_1)
    if denom == 0:
        return None
    u_a = ((x_4 - x_3) * (y_1 - y_3) - (y_4 - y_3) * (x_1 - x_3)) / denom
    if u_a < 0 or u_a > 1:
        return None
    u_b = ((x_2 - x_1) * (y_1 - y_3) - (y_2 - y_1) * (x_1 - x_3)) / denom
    if u_b < 0 or u_b > 1:
        return None
    x_inter = x_1 + u_a * (x_2 - x_1)
    y_inter = y_1 + u_a * (y_2 - y_1)
    return (x_inter, y_inter)


def angle_of_line(p_1, p_2):
    """gets the angle of a single line."""
    d_1 = p_2[0] - p_1[0]
    d_2 = p_2[1] - p_1[1]
    angle = math.atan2(d_2, d_1)
    return angle


def fuzy_match(p_1, p_2):
    """checks if  two points are matching / rounded."""
    return round(p_1[0], 2) == round(p_2[0], 2) and round(p_1[1], 2) == round(p_2[1], 2)


def calc_distance(p_1, p_2):
    """gets the distance between two points in 2D."""
    return math.hypot(p_1[0] - p_2[0], p_1[1] - p_2[1])


def is_between(p_1, p_2, p_3):
    """checks if a point is between 2 other points."""
    return round(calc_distance(p_1, p_3), 2) + round(
        calc_distance(p_1, p_2), 2
    ) == round(calc_distance(p_2, p_3), 2)


def line_center_2d(p_1, p_2):
    """gets the center point between 2 points in 2D."""
    center_x = (p_1[0] + p_2[0]) / 2
    center_y = (p_1[1] + p_2[1]) / 2
    return (center_x, center_y)


def line_center_3d(p_1, p_2):
    """gets the center point between 2 points in 3D."""
    center_x = (p_1[0] + p_2[0]) / 2
    center_y = (p_1[1] + p_2[1]) / 2
    center_z = (p_1[2] + p_2[2]) / 2
    return (center_x, center_y, center_z)


def calc_face(p_1, p_2):
    """gets the face og a line in 2D."""
    angle = angle_of_line(p_1, p_2)
    center_x = (p_1[0] + p_2[0]) / 2
    center_y = (p_1[1] + p_2[1]) / 2
    bcenter_x = center_x - 1.5 * math.sin(angle + math.pi)
    bcenter_y = center_y + 1.5 * math.cos(angle + math.pi)
    return (bcenter_x, bcenter_y)


def angle_2d(p_1, p_2):
    """gets the angle of a single line (2nd version)."""
    two_pi = math.pi * 2
    theta1 = math.atan2(p_1[1], p_1[0])
    theta2 = math.atan2(p_2[1], p_2[0])
    dtheta = theta2 - theta1
    while dtheta > math.pi:
        dtheta -= two_pi
    while dtheta < -math.pi:
        dtheta += two_pi
    return dtheta


# ########## Object & Segments Functions ###########


def get_half_bulge_point(last: tuple, point: tuple, bulge: float) -> tuple:
    (
        center,
        start_angle,  # pylint: disable=W0612
        end_angle,  # pylint: disable=W0612
        radius,  # pylint: disable=W0612
    ) = ezdxf.math.bulge_to_arc(last, point, bulge)
    half_angle = start_angle + (end_angle - start_angle) / 2
    (start, end, bulge) = ezdxf.math.arc_to_bulge(  # pylint: disable=W0612
        center,
        start_angle,
        half_angle,
        radius,
    )
    return (end[0], end[1])


def clean_segments(segments: list) -> list:
    """removing double and overlaying lines."""
    cleaned = {}
    for segment1 in segments:
        min_x = round(min(segment1["start"][0], segment1["end"][0]), 4)
        min_y = round(min(segment1["start"][1], segment1["end"][1]), 4)
        max_x = round(max(segment1["start"][0], segment1["end"][0]), 4)
        max_y = round(max(segment1["start"][1], segment1["end"][1]), 4)
        bulge = round(segment1["bulge"], 4) or 0.0
        key = f"{min_x},{min_y},{max_x},{max_y},{bulge},{segment1.get('layer', '')}"
        cleaned[key] = segment1
    return list(cleaned.values())


def is_inside_polygon(obj, point):
    """checks if a point is inside an polygon."""
    angle = 0.0
    p_1 = [0, 0]
    p_2 = [0, 0]
    for segment in obj["segments"]:
        start_x = segment["start"][0]
        start_y = segment["start"][1]
        end_x = segment["end"][0]
        end_y = segment["end"][1]
        p_1[0] = start_x - point[0]
        p_1[1] = start_y - point[1]
        p_2[0] = end_x - point[0]
        p_2[1] = end_y - point[1]
        angle += angle_2d(p_1, p_2)
    return bool(abs(angle) >= math.pi)


def reverse_object(obj):
    """reverse the direction of an object."""
    obj["segments"].reverse()
    for segment in obj["segments"]:
        end = segment["end"]
        segment["end"] = segment["start"]
        segment["start"] = end
        segment["bulge"] = -segment["bulge"]
    return obj


# ########## Objects Functions ###########
def find_outer_objects(objects, point, exclude=None):
    """gets a list of closed objects where the point is inside."""
    if not exclude:
        exclude = []
    outer = []
    for obj_idx, obj in objects.items():
        if obj["closed"] and obj_idx not in exclude:
            inside = is_inside_polygon(obj, point)
            if inside:
                outer.append(obj_idx)
    return outer


def find_tool_offsets(objects):
    """check if object is inside an other closed  objects."""
    max_outer = 0
    for obj_idx, obj in objects.items():
        outer = find_outer_objects(objects, obj["segments"][0]["start"], [obj_idx])
        obj["outer_objects"] = outer
        if obj["closed"]:
            obj["tool_offset"] = "outside" if len(outer) % 2 == 0 else "inside"
            # if obj["tool_offset"] == "inside":
            #    reverse_object(obj)

        if max_outer < len(outer):
            max_outer = len(outer)
        for outer_idx in outer:
            objects[outer_idx]["inner_objects"].append(obj_idx)
    return max_outer


def segments2objects(segments):
    """merge single segments to objects."""
    objects = {}
    obj_idx = 0
    while True:
        found = False
        last = None

        # create new object
        obj = {
            "segments": [],
            "closed": False,
            "tool_offset": "none",
            "overwrite_offset": None,
            "outer_objects": [],
            "inner_objects": [],
            "layer": "",
        }

        # add first unused segment from segments
        for segment in segments:
            if segment["object"] is None:
                segment["object"] = obj_idx
                obj["segments"].append(segment)
                obj["layer"] = segment["layer"]
                last = segment
                found = True
                break

        # find matching unused segments
        if last:
            rev = 0
            while True:
                found_next = False
                for segment in segments:
                    if segment["object"] is None and obj["layer"] == segment["layer"]:
                        # add matching segment
                        if fuzy_match(last["end"], segment["start"]):
                            segment["object"] = obj_idx
                            obj["segments"].append(segment)
                            last = segment
                            found_next = True
                            rev += 1
                        elif fuzy_match(last["end"], segment["end"]):
                            # reverse segment direction
                            end = segment["end"]
                            segment["end"] = segment["start"]
                            segment["start"] = end
                            segment["bulge"] = -segment["bulge"]
                            segment["object"] = obj_idx
                            obj["segments"].append(segment)
                            last = segment
                            found_next = True
                            rev += 1

                if not found_next:
                    obj["closed"] = fuzy_match(
                        obj["segments"][0]["start"], obj["segments"][-1]["end"]
                    )
                    if obj["closed"]:
                        break

                    if rev > 0:
                        reverse_object(obj)
                        last = obj["segments"][-1]
                        rev = 0
                    else:
                        break

        if obj["segments"]:
            if obj["closed"]:
                # set direction on closed objects
                point = calc_face(
                    obj["segments"][0]["start"], obj["segments"][0]["end"]
                )
                inside = is_inside_polygon(obj, point)
                if inside:
                    reverse_object(obj)

            objects[obj_idx] = obj
            obj_idx += 1
            last = None

        if not found:
            break

    return objects


# ########## Vertex Functions ###########
def inside_vertex(vertex_data, point):
    """checks if a point is inside an polygon in vertex format."""
    angle = 0.0
    p_1 = [0, 0]
    p_2 = [0, 0]
    start_x = vertex_data[0][-1]
    start_y = vertex_data[1][-1]
    for pos, end_x in enumerate(vertex_data[0]):
        end_y = vertex_data[1][pos]
        p_1[0] = start_x - point[0]
        p_1[1] = start_y - point[1]
        p_2[0] = end_x - point[0]
        p_2[1] = end_y - point[1]
        start_x = end_x
        start_y = end_y
        angle += angle_2d(p_1, p_2)
    return bool(abs(angle) >= math.pi)


def vertex2points(vertex_data, limit=None):
    """converts an vertex to a list of points"""
    points = []
    for pos, pos_x in enumerate(vertex_data[0]):
        pos_y = vertex_data[1][pos]
        bulge = vertex_data[2][pos]
        points.append((pos_x, pos_y, bulge))
        if limit and pos >= limit - 1:
            break
    return points


def object2vertex(obj):
    """converts an object to vertex points"""
    xdata = []
    ydata = []
    bdata = []
    segment = {}

    # last_x = None
    # last_y = None
    # last_bulge = None

    for segment in obj["segments"]:
        pos_x = segment["start"][0]
        pos_y = segment["start"][1]

        bulge = segment.get("bulge")
        bulge = min(bulge, 1.0)
        bulge = max(bulge, -1.0)

        xdata.append(pos_x)
        ydata.append(pos_y)
        bdata.append(bulge)

        # last_x = pos_x
        # last_y = pos_y
        # last_bulge = bulge

    if segment and not obj["closed"]:
        xdata.append(segment["end"][0])
        ydata.append(segment["end"][1])
        bdata.append(0)
    return (xdata, ydata, bdata)


# ########## Polyline Functions ###########
def found_next_tab_point(mpos, offsets):
    for offset in offsets.values():
        vertex_data = offset.vertex_data()
        if offset.is_closed():
            last_x = vertex_data[0][-1]
            last_y = vertex_data[1][-1]
            last_bulge = vertex_data[2][-1]
        else:
            last_x = None
            last_y = None
            last_bulge = None
        for point_num, pos_x in enumerate(vertex_data[0]):
            pos_y = vertex_data[1][point_num]
            next_bulge = vertex_data[2][point_num]
            if last_x is not None:
                line_start = (last_x, last_y)
                line_end = (pos_x, pos_y)
                for check in (
                    ((mpos[0] - 5, mpos[1] - 5), (mpos[0] + 5, mpos[1] + 5)),
                    ((mpos[0] + 5, mpos[1] - 5), (mpos[0] - 5, mpos[1] + 5)),
                    ((mpos[0] - 5, mpos[1]), (mpos[0] + 5, mpos[1])),
                ):
                    inter = lines_intersect(check[0], check[1], line_start, line_end)
                    if inter:
                        length = calc_distance(line_start, line_end)
                        if length > offset.setup["tabs"]["width"]:
                            angle = angle_of_line((last_x, last_y), (pos_x, pos_y))
                            if last_bulge != 0.0:
                                inter = get_half_bulge_point(
                                    (last_x, last_y), (pos_x, pos_y), last_bulge
                                )

                            start_x = inter[0] + 3 * math.sin(angle)
                            start_y = inter[1] - 3 * math.cos(angle)
                            end_x = inter[0] - 3 * math.sin(angle)
                            end_y = inter[1] + 3 * math.cos(angle)
                            return (start_x, start_y), (end_x, end_y)

            last_x = pos_x
            last_y = pos_y
            last_bulge = next_bulge
    return ()


def do_pockets(  # pylint: disable=R0913
    polyline,
    obj,
    obj_idx,
    tool_offset,
    tool_radius,
    polyline_offsets,
    offset_idx,
    vertex_data_org,
):
    """calculates multiple offset lines of an polyline"""
    offsets = polyline.parallel_offset(delta=-tool_radius, check_self_intersect=True)
    for polyline_offset in offsets:
        if polyline_offset:
            # workaround for bad offsets
            vertex_data = polyline_offset.vertex_data()
            point = (vertex_data[0][0], vertex_data[1][0], vertex_data[2][0])
            if not inside_vertex(vertex_data_org, point):
                continue

            polyline_offset.level = len(obj.get("outer_objects", []))
            polyline_offset.tool_offset = tool_offset
            polyline_offset.layer = obj["layer"]
            polyline_offset.setup = obj["setup"]
            polyline_offset.is_pocket = True
            polyline_offsets[f"{obj_idx}.{offset_idx}"] = polyline_offset
            offset_idx += 1
            if polyline_offset.is_closed():
                offset_idx = do_pockets(
                    polyline_offset,
                    obj,
                    obj_idx,
                    tool_offset,
                    tool_radius,
                    polyline_offsets,
                    offset_idx,
                    vertex_data_org,
                )

    return offset_idx


def object2polyline_offsets(diameter, obj, obj_idx, max_outer, small_circles=False):
    """calculates the offset line(s) of one object"""
    polyline_offsets = {}

    def overcut() -> None:
        radius_3 = abs(tool_radius * 3)
        for offset_idx, polyline in enumerate(list(polyline_offsets.values())):
            points = vertex2points(polyline.vertex_data())
            xdata = []
            ydata = []
            bdata = []
            last = points[-1]
            last_angle = None
            for point in points:
                angle = angle_of_line(point, last)
                if last_angle is not None and last[2] == 0.0:
                    if angle > last_angle:
                        angle = angle + math.pi * 2
                    adiff = angle - last_angle
                    if adiff < -math.pi * 2:
                        adiff += math.pi * 2

                    if abs(adiff) >= math.pi / 4:
                        over_x = last[0] - radius_3 * math.sin(
                            last_angle + adiff / 2.0 + math.pi
                        )
                        over_y = last[1] + radius_3 * math.cos(
                            last_angle + adiff / 2.0 + math.pi
                        )
                        for segment in obj["segments"]:
                            is_b = is_between(
                                (segment["start"][0], segment["start"][1]),
                                (last[0], last[1]),
                                (over_x, over_y),
                            )
                            if is_b:
                                dist = calc_distance(
                                    (segment["start"][0], segment["start"][1]),
                                    (last[0], last[1]),
                                )
                                over_dist = dist - abs(tool_radius)
                                over_x = last[0] - (over_dist) * math.sin(
                                    last_angle + adiff / 2.0 + math.pi
                                )
                                over_y = last[1] + (over_dist) * math.cos(
                                    last_angle + adiff / 2.0 + math.pi
                                )
                                xdata.append(over_x)
                                ydata.append(over_y)
                                bdata.append(0.0)
                                xdata.append(last[0])
                                ydata.append(last[1])
                                bdata.append(0.0)
                                break
                xdata.append(point[0])
                ydata.append(point[1])
                bdata.append(point[2])
                last_angle = angle
                last = point

            point = points[0]
            angle = angle_of_line(point, last)
            if last_angle is not None and last[2] == 0.0:
                if angle > last_angle:
                    angle = angle + math.pi * 2
                adiff = angle - last_angle
                if adiff < -math.pi * 2:
                    adiff += math.pi * 2

                if abs(adiff) >= math.pi / 4:
                    over_x = last[0] - radius_3 * math.sin(
                        last_angle + adiff / 2.0 + math.pi
                    )
                    over_y = last[1] + radius_3 * math.cos(
                        last_angle + adiff / 2.0 + math.pi
                    )
                    for segment in obj["segments"]:
                        is_b = is_between(
                            (segment["start"][0], segment["start"][1]),
                            (last[0], last[1]),
                            (over_x, over_y),
                        )
                        if is_b:
                            dist = calc_distance(
                                (segment["start"][0], segment["start"][1]),
                                (last[0], last[1]),
                            )
                            over_dist = dist - abs(tool_radius)
                            over_x = last[0] - over_dist * math.sin(
                                last_angle + adiff / 2.0 + math.pi
                            )
                            over_y = last[1] + over_dist * math.cos(
                                last_angle + adiff / 2.0 + math.pi
                            )
                            xdata.append(over_x)
                            ydata.append(over_y)
                            bdata.append(0.0)
                            xdata.append(last[0])
                            ydata.append(last[1])
                            bdata.append(0.0)
                            break

            over_polyline = cavc.Polyline((xdata, ydata, bdata), is_closed=True)
            over_polyline.level = len(obj.get("outer_objects", []))
            over_polyline.setup = obj.get("setup", {})
            over_polyline.layer = obj.get("layer", "")
            over_polyline.is_pocket = False
            over_polyline.tool_offset = tool_offset
            polyline_offsets[f"{obj_idx}.{offset_idx}"] = over_polyline

    tool_offset = obj["tool_offset"]
    if obj["overwrite_offset"] is not None:
        tool_radius = obj["overwrite_offset"]
    else:
        tool_radius = diameter / 2.0

    if obj["setup"]["mill"]["reverse"]:
        tool_radius = -tool_radius

    is_circle = bool(obj["segments"][0]["type"] == "CIRCLE")

    vertex_data = object2vertex(obj)
    polyline = cavc.Polyline(vertex_data, is_closed=obj["closed"])

    offset_idx = 0
    if polyline.is_closed() and tool_offset != "none":
        polyline_offset_list = polyline.parallel_offset(
            delta=-tool_radius, check_self_intersect=True
        )
        if polyline_offset_list:
            for polyline_offset in polyline_offset_list:
                polyline_offset.level = len(obj.get("outer_objects", []))
                polyline_offset.tool_offset = tool_offset
                polyline_offset.setup = obj["setup"]
                polyline_offset.layer = obj.get("layer", "")
                polyline_offset.is_pocket = False
                polyline_offset.is_circle = is_circle
                polyline_offsets[f"{obj_idx}.{offset_idx}"] = polyline_offset
                offset_idx += 1
                if tool_offset == "inside" and obj["setup"]["pockets"]["active"]:
                    if polyline_offset.is_closed():
                        offset_idx = do_pockets(
                            polyline_offset,
                            obj,
                            obj_idx,
                            tool_offset,
                            tool_radius * 1.2,
                            polyline_offsets,
                            offset_idx,
                            polyline.vertex_data(),
                        )
        elif is_circle and small_circles:
            # adding holes that smaler as the tool
            center_x = obj["segments"][0]["center"][0]
            center_y = obj["segments"][0]["center"][1]
            vertex_data = ((center_x,), (center_y,), (0,))
            polyline_offset = cavc.Polyline(vertex_data, is_closed=False)
            polyline_offset.level = len(obj.get("outer_objects", []))
            polyline_offset.tool_offset = tool_offset
            polyline_offset.setup = obj["setup"]
            polyline_offset.layer = obj.get("layer", "")
            polyline_offset.is_pocket = False
            polyline_offset.is_circle = True
            polyline_offsets[f"{obj_idx}.{offset_idx}.x"] = polyline_offset
            offset_idx += 1

        if obj["setup"]["mill"]["overcut"]:
            overcut()

    else:
        polyline.level = max_outer
        polyline.tool_offset = tool_offset
        polyline.setup = obj["setup"]
        polyline.layer = obj.get("layer", "")
        polyline.is_pocket = False
        polyline.is_circle = False
        polyline_offsets[f"{obj_idx}.{offset_idx}"] = polyline
        offset_idx += 1

    return polyline_offsets


def objects2polyline_offsets(diameter, objects, max_outer, small_circles=False):
    """calculates the offset line(s) of all objects"""
    polyline_offsets = {}
    for obj_idx, obj in objects.items():
        if not obj["setup"]["mill"]["active"]:
            continue

        obj_copy = deepcopy(obj)
        do_reverse = 0
        if obj_copy["tool_offset"] == "inside":
            do_reverse = 1 - do_reverse

        if obj_copy["setup"]["mill"]["reverse"]:
            do_reverse = 1 - do_reverse

        if do_reverse:
            reverse_object(obj_copy)

        polyline_offsets.update(
            object2polyline_offsets(
                diameter, obj_copy, obj_idx, max_outer, small_circles
            )
        )

    return polyline_offsets


# analyze size
def objects2minmax(objects):
    """find the min/max values of objects"""
    min_x = objects[0]["segments"][0]["start"][0]
    min_y = objects[0]["segments"][0]["start"][1]
    max_x = objects[0]["segments"][0]["start"][0]
    max_y = objects[0]["segments"][0]["start"][1]
    for obj in objects.values():
        if obj.get("layer", "").startswith("BREAKS:") or obj.get(
            "layer", ""
        ).startswith("_TABS"):
            continue
        for segment in obj["segments"]:
            min_x = min(min_x, segment["start"][0])
            min_x = min(min_x, segment["end"][0])
            min_y = min(min_y, segment["start"][1])
            min_y = min(min_y, segment["end"][1])
            max_x = max(max_x, segment["start"][0])
            max_x = max(max_x, segment["end"][0])
            max_y = max(max_y, segment["start"][1])
            max_y = max(max_y, segment["end"][1])
    return (min_x, min_y, max_x, max_y)


def move_objects(objects: dict, xoff: float, yoff: float) -> None:
    """moves an object"""
    for obj in objects.values():
        for segment in obj["segments"]:
            for ptype in ("start", "end", "center"):
                if ptype in segment:
                    segment[ptype] = (
                        segment[ptype][0] + xoff,
                        segment[ptype][1] + yoff,
                    )


def mirror_objects(
    objects: dict,
    min_max: list[float],
    vertical: bool = False,
    horizontal: bool = False,
) -> None:
    """mirrors an object"""
    if vertical or horizontal:
        for obj in objects.values():
            for segment in obj["segments"]:
                for ptype in ("start", "end", "center"):
                    if ptype in segment:
                        pos_x = segment[ptype][0]
                        pos_y = segment[ptype][1]
                        if vertical:
                            pos_x = min_max[0] - pos_x + min_max[2]
                        if horizontal:
                            pos_y = min_max[1] - pos_y + min_max[3]
                        segment[ptype] = (pos_x, pos_y)

                if vertical != horizontal:
                    segment["bulge"] = -segment["bulge"]

            if vertical != horizontal:
                reverse_object(obj)


def rotate_objects(objects: dict, min_max: list[float]) -> None:
    """rotates an object"""
    for obj in objects.values():
        for segment in obj["segments"]:
            for ptype in ("start", "end", "center"):
                if ptype in segment:
                    segment[ptype] = (segment[ptype][1], segment[ptype][0])

            segment["bulge"] = -segment["bulge"]
        reverse_object(obj)
    mirror_objects(objects, min_max, horizontal=True)
