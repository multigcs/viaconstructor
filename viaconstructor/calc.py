"""viaconstructor calculation functions."""

import hashlib
import math
import os
import platform
import shutil
from copy import deepcopy
from pathlib import Path

import ezdxf

try:
    import pyclipper

    HAVE_PYCLIPPER = True
except Exception:  # pylint: disable=W0703
    HAVE_PYCLIPPER = False

from .ext.cavaliercontours import cavaliercontours as cavc
from .vc_types import VcObject

TWO_PI = math.pi * 2


# ########## helper Functions ###########
def external_command(cmd: str):
    known_paths = {
        "camotics": [
            "/Applications/CAMotics.app/Contents/MacOS/camotics",
        ],
        "camotics.exe": [
            "c:\\Program Files\\CAMotics\\camotics.exe",
            "c:\\Program Files (x86)\\CAMotics\\camotics.exe",
        ],
        "openscad.exe": [
            "c:\\Program Files\\OpenSCAD\\openscad.exe",
            "c:\\Program Files (x86)\\OpenSCAD\\openscad.exe",
        ],
    }
    if platform.system().lower() == "windows":
        cmd = f"{cmd}.exe"
    path = shutil.which(cmd)
    if path is None:
        if cmd in known_paths:
            for known_path in known_paths[cmd]:
                if os.path.isfile(known_path):
                    path = known_path
                    break
    return path


def get_tmp_prefix() -> str:
    if platform.system().lower() == "windows":
        return str(os.path.join(Path.home())) + "\\"
    return "/tmp/"


# ########## Misc Functions ###########
def rotate_list(rlist, idx):
    """rotating a list of values."""
    return rlist[idx:] + rlist[:idx]


# ########## Line Functions ###########
def get_next_line(end_point, lines):
    selected = -1
    nearest = 1000000
    reverse = 0
    for idx, line in enumerate(lines):
        dist = calc_distance(end_point, line[0])
        if dist < nearest:
            selected = idx
            nearest = dist
            reverse = 0

        dist = calc_distance(end_point, line[1])
        if dist < nearest:
            selected = idx
            nearest = dist
            reverse = 1

    if selected != -1:
        line = lines.pop(selected)
        if reverse:
            line = (line[1], line[0])
        return (nearest, line)
    return None


def lines_to_path(lines, max_vdist, max_dist):
    # optimize / adding bridges
    lines = lines[0:]
    output_lines = []
    if not lines:
        return []

    last_line = lines.pop(0)
    output_lines.append((last_line[0], last_line[1]))
    while True:
        check = get_next_line(last_line[1], lines)
        if check is None:
            break
        dist = check[0]
        next_line = check[1]
        vdist = abs(last_line[0][1] - next_line[0][1])
        if vdist <= max_vdist:
            if dist <= max_dist:
                output_lines.append((last_line[1], next_line[0]))
            elif last_line[0][0] <= next_line[0][0] <= last_line[1][0]:
                output_lines.append((last_line[1], next_line[0]))
            elif last_line[1][0] <= next_line[0][0] <= last_line[0][0]:
                output_lines.append((last_line[1], next_line[0]))
            elif next_line[0][0] <= last_line[1][0] <= next_line[1][0]:
                output_lines.append((last_line[1], next_line[0]))
            elif next_line[1][0] <= last_line[1][0] <= next_line[0][0]:
                output_lines.append((last_line[1], next_line[0]))
        output_lines.append((next_line[0], next_line[1]))
        last_line = next_line
    return output_lines


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
    return math.atan2(p_2[1] - p_1[1], p_2[0] - p_1[0])


def fuzy_match(p_1, p_2):
    """checks if  two points are matching / rounded."""
    return math.hypot(p_1[0] - p_2[0], p_1[1] - p_2[1]) < 0.01


def get_nearest_line(check, lines):
    """gets the lowest distance between a point and a list of lines in 2D."""
    nearest = None
    nline = None
    for line in lines:
        dist = calc_distance_to_line(check, line)
        if nearest is None or nearest > dist:
            nearest = dist
            nline = line
            if nearest == 0.0:
                break
    return (nearest, nline)


def calc_distance_to_line(check, line):
    """gets the lowest distance between a point and a line in 2D."""
    x_1 = line[0][0]
    y_1 = line[0][1]
    x_2 = line[1][0]
    y_2 = line[1][1]
    x_3 = check[0]
    y_3 = check[1]
    p_x = x_2 - x_1
    p_y = y_2 - y_1
    norm = p_x * p_x + p_y * p_y
    u_t = ((x_3 - x_1) * p_x + (y_3 - y_1) * p_y) / float(norm)
    if u_t > 1:
        u_t = 1
    elif u_t < 0:
        u_t = 0
    x_p = x_1 + u_t * p_x
    y_p = y_1 + u_t * p_y
    d_x = x_p - x_3
    d_y = y_p - y_3
    dist = (d_x * d_x + d_y * d_y) ** 0.5
    return dist


def calc_distance(p_1, p_2):
    """gets the distance between two points in 2D."""
    # return math.hypot(p_1[0] - p_2[0], p_1[1] - p_2[1])
    return math.dist(p_1[0:2], p_2[0:2])


def calc_distance3d(p_1, p_2):
    """gets the distance between two points in 3D."""
    return math.hypot(p_1[0] - p_2[0], p_1[1] - p_2[1], p_1[2] - p_2[2])


def is_between(p_1, p_2, p_3):
    """checks if a point is between 2 other points."""
    return round(math.hypot(p_1[0] - p_3[0], p_1[1] - p_3[1]), 2) + round(
        math.hypot(p_1[0] - p_2[0], p_1[1] - p_2[1]), 2
    ) == round(math.hypot(p_2[0] - p_3[0], p_2[1] - p_3[1]), 2)


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
    """gets the face of a line in 2D."""
    angle = angle_of_line(p_1, p_2) + math.pi
    center_x = (p_1[0] + p_2[0]) / 2
    center_y = (p_1[1] + p_2[1]) / 2
    bcenter_x = center_x - 0.01 * math.sin(angle)
    bcenter_y = center_y + 0.01 * math.cos(angle)
    return (bcenter_x, bcenter_y)


def angle_2d(p_1, p_2):
    """gets the angle of a single line (2nd version)."""
    theta1 = math.atan2(p_1[1], p_1[0])
    theta2 = math.atan2(p_2[1], p_2[0])
    dtheta = theta2 - theta1
    while dtheta > math.pi:
        dtheta -= TWO_PI
    while dtheta < -math.pi:
        dtheta += TWO_PI
    return dtheta


def quadratic_bezier(curv_pos, points):
    curve_x = (1 - curv_pos) * (
        (1 - curv_pos) * points[0][0] + curv_pos * points[1][0]
    ) + curv_pos * ((1 - curv_pos) * points[1][0] + curv_pos * points[2][0])
    curve_y = (1 - curv_pos) * (
        (1 - curv_pos) * points[0][1] + curv_pos * points[1][1]
    ) + curv_pos * ((1 - curv_pos) * points[1][1] + curv_pos * points[2][1])
    return curve_x, curve_y


def point_of_line(p_1, p_2, line_pos):
    return [
        p_1[0] + (p_2[0] - p_1[0]) * line_pos,
        p_1[1] + (p_2[1] - p_1[1]) * line_pos,
    ]


def point_of_line3d(p_1, p_2, line_pos):
    return [
        p_1[0] + (p_2[0] - p_1[0]) * line_pos,
        p_1[1] + (p_2[1] - p_1[1]) * line_pos,
        p_1[2] + (p_2[2] - p_1[2]) * line_pos,
    ]


def points_to_boundingbox(points):
    min_x = points[0][0]
    min_y = points[0][1]
    max_x = points[0][0]
    max_y = points[0][1]
    for point in points:
        min_x = min(min_x, point[0])
        min_y = min(min_y, point[1])
        max_x = max(max_x, point[0])
        max_y = max(max_y, point[1])
    return (min_x, min_y, max_x, max_y)


def points_to_center(points):
    bounding_box = points_to_boundingbox(points)
    center_x = bounding_box[0] + (bounding_box[2] - bounding_box[0]) / 2.0
    center_y = bounding_box[1] + (bounding_box[3] - bounding_box[1]) / 2.0
    return (center_x, center_y)


# ########## Object & Segments Functions ###########


def get_half_bulge_point(last: tuple, point: tuple, bulge: float) -> tuple:
    (
        center,
        start_angle,  # pylint: disable=W0612
        end_angle,  # pylint: disable=W0612
        radius,  # pylint: disable=W0612
    ) = ezdxf.math.bulge_to_arc(last, point, bulge)
    while start_angle > end_angle:
        start_angle -= math.pi
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
        min_x = round(min(segment1.start[0], segment1.end[0]), 4)
        min_y = round(min(segment1.start[1], segment1.end[1]), 4)
        max_x = round(max(segment1.start[0], segment1.end[0]), 4)
        max_y = round(max(segment1.start[1], segment1.end[1]), 4)
        bulge = round(segment1.bulge, 4) or 0.0
        key = f"{min_x},{min_y},{max_x},{max_y},{bulge},{segment1.layer}"
        cleaned[key] = segment1
    return list(cleaned.values())


def is_inside_polygon(obj, point):
    """checks if a point is inside an polygon."""
    angle = 0.0
    point_0 = point[0]
    point_1 = point[1]
    for segment in obj.segments:
        angle += angle_2d(
            (segment.start[0] - point_0, segment.start[1] - point_1),
            (segment.end[0] - point_0, segment.end[1] - point_1),
        )
    return bool(abs(angle) >= math.pi)


def reverse_object(obj):
    """reverse the direction of an object."""
    obj.segments.reverse()
    for segment in obj.segments:
        end = segment.end
        segment.end = segment.start
        segment.start = end
        segment.bulge = -segment.bulge
    return obj


# ########## Objects Functions ###########
def find_outer_objects(objects, point, exclude=None):
    """gets a list of closed objects where the point is inside."""
    if not exclude:
        exclude = []
    outer = []
    for obj_idx, obj in objects.items():
        if obj.closed and obj_idx not in exclude:
            inside = is_inside_polygon(obj, point)
            if inside:
                outer.append(obj_idx)
    return outer


def find_tool_offsets(objects):
    """check if object is inside an other closed  objects."""

    part_l = len(objects)
    part_n = 0
    max_outer = 0
    for obj in objects.values():
        obj["inner_objects"] = []

    for obj_idx, obj in objects.items():
        print(f"set offsets: {round((part_n + 1) * 100 / part_l, 1)}%", end="\r")
        part_n += 1

        outer = find_outer_objects(objects, obj.segments[0].start, [obj_idx])
        obj.outer_objects = outer
        if obj.closed:

            if obj.setup["mill"]["offset"] == "auto":
                obj.tool_offset = "outside" if len(outer) % 2 == 0 else "inside"
            else:
                obj.tool_offset = obj.setup["mill"]["offset"]
        if max_outer < len(outer):
            max_outer = len(outer)

        if obj.layer.startswith("BREAKS:") or obj.layer.startswith("_TABS"):
            continue

        for outer_idx in outer:
            objects[outer_idx]["inner_objects"].append(obj_idx)
    print("")

    return max_outer


def num_unused_segments(segments):
    part_l = 0
    for segment in segments:
        if segment.object is None:
            part_l += 1
    return part_l


def segments2objects(segments):
    """merge single segments to objects."""
    test_segments = deepcopy(segments)
    objects = {}
    obj_idx = 0

    part_l = num_unused_segments(segments)
    last_percent = -1
    while True:
        found = False
        last = None

        part_n = part_l - num_unused_segments(test_segments)
        percent = round((part_n + 1) * 100 / part_l, 1)
        if int(percent) != int(last_percent):
            print(f"combining segments: {percent}%", end="\r")
        last_percent = int(percent)

        # create new object
        obj = VcObject(
            {
                "segments": [],
                "closed": False,
                "tool_offset": "none",
                "overwrite_offset": None,
                "outer_objects": [],
                "inner_objects": [],
                "layer": "",
                "color": 256,
            }
        )

        # add first unused segment from segments
        for seg_idx, segment in enumerate(test_segments):
            if segment.object is None:
                segment.object = obj_idx
                obj.segments.append(segment)
                obj.layer = segment.layer
                obj.color = segment.color
                last = segment
                found = True
                test_segments.pop(seg_idx)
                break

        # find matching unused segments
        if last:
            rev = 0
            while True:
                found_next = False
                for seg_idx, segment in enumerate(test_segments):
                    if segment["object"] is None and obj.layer == segment.layer:
                        # add matching segment
                        if fuzy_match(last.end, segment.start):
                            segment.object = obj_idx
                            obj.segments.append(segment)
                            last = segment
                            found_next = True
                            rev += 1
                            test_segments.pop(seg_idx)
                            break
                        if fuzy_match(last.end, segment.end):
                            # reverse segment direction
                            end = segment.end
                            segment.end = segment.start
                            segment.start = end
                            segment.bulge = -segment.bulge
                            segment["object"] = obj_idx
                            obj.segments.append(segment)
                            last = segment
                            found_next = True
                            rev += 1
                            test_segments.pop(seg_idx)
                            break

                if not found_next:
                    obj.closed = fuzy_match(obj.segments[0].start, obj.segments[-1].end)
                    if obj.closed:
                        break

                    if rev > 0:
                        reverse_object(obj)
                        last = obj.segments[-1]
                        rev = 0
                    else:
                        break

        if obj.segments:
            if obj.closed:
                # set direction on closed objects
                point = calc_face(obj.segments[0].start, obj.segments[0].end)
                inside = is_inside_polygon(obj, point)
                if inside:
                    reverse_object(obj)

            min_x = obj.segments[0].start[0]
            min_y = obj.segments[0].start[1]
            max_x = obj.segments[0].start[0]
            max_y = obj.segments[0].start[1]
            for segment in obj.segments:
                min_x = min(min_x, segment.start[0], segment.end[0])
                min_y = min(min_y, segment.start[1], segment.end[1])
                max_x = max(max_x, segment.start[0], segment.end[0])
                max_y = max(max_y, segment.start[1], segment.end[1])
            uid = hashlib.md5(
                f"{int(min_x * 100)}_{int(min_y * 100)}_{int(max_x * 100)}_{int(max_y * 100)}".encode(
                    "utf-8"
                )
            ).hexdigest()
            obj_uid = f"{obj_idx}:{uid}"

            objects[obj_uid] = obj
            obj_idx += 1
            last = None

        if not found:
            break
    print("")
    return objects


# ########## Vertex Functions ###########
def vertex_data_cache(offset):
    """Caching the very slow vertex_data() function."""
    if hasattr(offset, "cache"):
        vertex_data = offset.cache
    else:
        vertex_data = offset.vertex_data()
        offset.cache = vertex_data
    return vertex_data


def inside_vertex(vertex_data, point):
    """checks if a point is inside an polygon in vertex format."""
    angle = 0.0
    start_x = vertex_data[0][-1]
    start_y = vertex_data[1][-1]
    point_0 = point[0]
    point_1 = point[1]
    for end_x, end_y in zip(vertex_data[0], vertex_data[1]):
        angle += angle_2d(
            (start_x - point_0, start_y - point_1), (end_x - point_0, end_y - point_1)
        )
        start_x = end_x
        start_y = end_y
    return bool(abs(angle) >= math.pi)


def bulge_points(start, end, bulge, parts=10):
    points = []
    (
        center,
        start_angle,  # pylint: disable=W0612
        end_angle,  # pylint: disable=W0612
        radius,  # pylint: disable=W0612
    ) = ezdxf.math.bulge_to_arc(start, end, bulge)
    while start_angle > end_angle:
        start_angle -= math.pi
    steps = abs(start_angle - end_angle) / parts
    angle = start_angle + steps
    if start_angle < end_angle:
        while angle < end_angle:
            ap_x = center[0] + radius * math.sin(angle + math.pi / 2)
            ap_y = center[1] - radius * math.cos(angle + math.pi / 2)
            points.append((ap_x, ap_y))
            angle += steps
    return points


def vertex2points(vertex_data, no_bulge=False, scale=1.0, interpolate=0):
    """converts an vertex to a list of points"""
    points = []

    if no_bulge:
        if interpolate > 0:
            last_x = vertex_data[0][-1]
            last_y = vertex_data[1][-1]
            last_b = vertex_data[2][-1]
            for pos_x, pos_y, bulge in zip(
                vertex_data[0], vertex_data[1], vertex_data[2]
            ):
                if last_b > 0.0:
                    points += bulge_points(
                        (last_x * scale, last_y * scale),
                        (pos_x * scale, pos_y * scale),
                        last_b,
                        interpolate,
                    )
                    points.append((pos_x * scale, pos_y * scale))
                elif last_b < 0.0:
                    new_points = bulge_points(
                        (last_x * scale, last_y * scale),
                        (pos_x * scale, pos_y * scale),
                        last_b,
                        interpolate,
                    )
                    new_points.reverse()
                    points += new_points
                    points.append((pos_x * scale, pos_y * scale))
                else:
                    points.append((pos_x * scale, pos_y * scale))
                last_x = pos_x
                last_y = pos_y
                last_b = bulge

        else:
            for pos_x, pos_y in zip(vertex_data[0], vertex_data[1]):
                points.append((pos_x * scale, pos_y * scale))
    else:
        for pos_x, pos_y, bulge in zip(vertex_data[0], vertex_data[1], vertex_data[2]):
            points.append((pos_x * scale, pos_y * scale, bulge))

    return points


def points2vertex(points, scale=1.0):
    """converts a list of points to vertex"""
    xdata = []
    ydata = []
    bdata = []
    for point in points:
        pos_x = point[0] * scale
        pos_y = point[1] * scale
        if len(point) > 2:
            bulge = point[2]
        else:
            bulge = 0.0
        xdata.append(pos_x)
        ydata.append(pos_y)
        bdata.append(bulge)
    return (xdata, ydata, bdata)


def object2vertex(obj):
    """converts an object to vertex points"""
    xdata = []
    ydata = []
    bdata = []
    segment = {}
    for segment in obj.segments:
        pos_x = segment.start[0]
        pos_y = segment.start[1]
        bulge = segment.bulge
        bulge = min(bulge, 1.0)
        bulge = max(bulge, -1.0)
        xdata.append(pos_x)
        ydata.append(pos_y)
        bdata.append(bulge)

    if segment and not obj.closed:
        xdata.append(segment.end[0])
        ydata.append(segment.end[1])
        bdata.append(0)
    return (xdata, ydata, bdata)


def object2points(obj):
    """converts an object to list of points"""
    points = []
    for segment in obj.segments:
        points.append(segment.start)
    if obj.closed:
        points.append(obj.segments[0].start)
    return points


# ########## Polyline Functions ###########


def found_next_point_on_segment(mpos, objects):
    for obj_idx, obj in objects.items():
        for segment_idx, segment in enumerate(obj.segments):
            last_x = segment.start[0]
            last_y = segment.start[1]
            pos_x = segment.end[0]
            pos_y = segment.end[1]
            bulge = segment.bulge
            for check in (
                ((mpos[0] - 5, mpos[1] - 5), (mpos[0] + 5, mpos[1] + 5)),
                ((mpos[0] + 5, mpos[1] - 5), (mpos[0] - 5, mpos[1] + 5)),
                # ((mpos[0] - 5, mpos[1]), (mpos[0] + 5, mpos[1])),
            ):
                inter = lines_intersect(check[0], check[1], segment.start, segment.end)
                if inter:
                    length = calc_distance(segment.start, segment.end)
                    if length > 0.0:
                        if bulge != 0.0:

                            inter = get_half_bulge_point(
                                (last_x, last_y), (pos_x, pos_y), bulge
                            )

                        return (obj_idx, segment_idx, inter)
    return ()


def found_next_segment_point(mpos, objects):
    nearest = ()
    min_dist = None
    for obj_idx, obj in objects.items():
        for segment in obj.segments:
            pos_x = segment.end[0]
            pos_y = segment.end[1]
            dist = calc_distance(mpos, (pos_x, pos_y))
            if min_dist is None or dist < min_dist:
                min_dist = dist
                nearest = (pos_x, pos_y, obj_idx)
            pos_x = segment.start[0]
            pos_y = segment.start[1]
            dist = calc_distance(mpos, (pos_x, pos_y))
            if min_dist is None or dist < min_dist:
                min_dist = dist
                nearest = (pos_x, pos_y, obj_idx)

    return nearest


def found_next_open_segment_point(mpos, objects, max_dist=None, exclude=None):
    nearest = ()
    min_dist = None
    for obj_idx, obj in objects.items():
        if not obj.closed:
            for segmentd_idx in (0, -1):
                if exclude and exclude[0] == obj_idx and exclude[1] == segmentd_idx:
                    continue
                if segmentd_idx == 0:
                    pos_x = obj.segments[segmentd_idx].start[0]
                    pos_y = obj.segments[segmentd_idx].start[1]
                else:
                    pos_x = obj.segments[segmentd_idx].end[0]
                    pos_y = obj.segments[segmentd_idx].end[1]
                dist = calc_distance(mpos, (pos_x, pos_y))
                if max_dist and dist > max_dist:
                    continue
                if min_dist is None or dist < min_dist:
                    min_dist = dist
                    nearest = (pos_x, pos_y, obj_idx, segmentd_idx)
    return nearest


def found_next_offset_point(mpos, offset):
    nearest = ()
    min_dist = None
    vertex_data = vertex_data_cache(offset)
    point_num = 0
    for pos_x, pos_y in zip(vertex_data[0], vertex_data[1]):
        dist = calc_distance(mpos, (pos_x, pos_y))
        if min_dist is None or dist < min_dist:
            min_dist = dist
            nearest = (pos_x, pos_y, point_num)
        point_num += 1
    return nearest


def found_next_tab_point(mpos, offsets):
    for offset in offsets.values():
        vertex_data = vertex_data_cache(offset)
        if offset.is_closed():
            last_x = vertex_data[0][-1]
            last_y = vertex_data[1][-1]
            last_bulge = vertex_data[2][-1]
        else:
            last_x = None
            last_y = None
            last_bulge = None
        for pos_x, pos_y, next_bulge in zip(
            vertex_data[0], vertex_data[1], vertex_data[2]
        ):
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


def points2offsets(
    obj,
    points,
    polyline_offsets,
    offset_idx,
    pocket_idx,
    tool_offset,
    scale=1.0,
    is_closed=True,
    is_pocket=0,
    parent_id="0",
):
    vertex_data = points2vertex(points, scale=scale)
    polyline_offset = cavc.Polyline(vertex_data, is_closed=is_closed)
    polyline_offset.level = len(obj.outer_objects)
    polyline_offset.tool_offset = tool_offset
    polyline_offset.layer = obj.layer
    polyline_offset.color = obj.color
    polyline_offset.setup = obj.setup
    polyline_offset.obj_idx = parent_id
    polyline_offset.outer_objects = obj.outer_objects
    polyline_offset.start = obj.start
    polyline_offset.is_pocket = is_pocket
    polyline_offset.fixed_direction = False
    polyline_offsets[f"{parent_id}.{offset_idx}.{pocket_idx}"] = polyline_offset
    offset_idx += 1
    return offset_idx


def do_pockets(  # pylint: disable=R0913
    polyline,
    obj,
    obj_idx,
    tool_offset,
    tool_radius,
    polyline_offsets,
    offset_idx,
    vertex_data_org,  # pylint: disable=W0613
    parent_id,
):
    """calculates multiple offset lines of an polyline"""
    interpolate = 6
    abs_tool_radius = abs(tool_radius)
    pocket_idx = 0
    if obj.setup["pockets"]["zigzag"]:
        vertex_data = vertex_data_cache(polyline)
        points = vertex2points(vertex_data, no_bulge=True, interpolate=interpolate)
        lines = []

        points_check = [points]
        if obj.inner_objects and obj.setup["pockets"]["islands"]:
            for idx in obj.inner_objects:
                polyline_offset = polyline_offsets.get(f"{idx}.0")
                if polyline_offset is not None:
                    vertex_data = vertex_data_cache(polyline_offset)
                    points_check.append(
                        vertex2points(
                            vertex_data, no_bulge=True, interpolate=interpolate
                        )
                    )

        # get bounding box
        bounding = points_to_boundingbox(points)
        y_pos = bounding[1] + abs_tool_radius
        bounding_ydiff = bounding[3] - bounding[1]
        steps_y = int(bounding_ydiff / abs_tool_radius) - 1
        abs_tool_radius = bounding_ydiff / steps_y
        while y_pos <= bounding[3] - abs_tool_radius:
            intersects = set()
            for points in points_check:
                last = points[-1]
                for point in points:
                    intersect = lines_intersect(
                        (bounding[0] - 1, y_pos), (bounding[2] + 1, y_pos), last, point
                    )
                    if intersect is not None:
                        intersects.add(intersect[0])
                    last = point
            if len(intersects) > 1:
                sortet_list = sorted(intersects, key=float)
                point_inter = iter(sortet_list)
                for point_x1, point_x2 in zip(point_inter, point_inter):
                    lines.append(
                        (
                            (point_x1 + abs_tool_radius * 0.6, y_pos),
                            (point_x2 - abs_tool_radius * 0.6, y_pos),
                        )
                    )
            y_pos += abs_tool_radius

        output_lines = lines_to_path(
            lines, max_vdist=abs_tool_radius * 2, max_dist=abs_tool_radius * 2
        )
        if output_lines:
            last = output_lines[0]
            polyline = []
            polyline.append(last[0])
            polyline.append(last[1])
            for line in output_lines[1:]:
                if last[1] != line[0]:
                    offset_idx = points2offsets(
                        obj,
                        polyline,
                        polyline_offsets,
                        offset_idx,
                        pocket_idx,
                        tool_offset,
                        is_closed=False,
                        is_pocket=1,
                        parent_id=parent_id,
                    )
                    pocket_idx += 1
                    polyline = []
                    polyline.append(line[0])
                    polyline.append(line[1])
                else:
                    polyline.append(line[1])
                last = line
            offset_idx = points2offsets(
                obj,
                polyline,
                polyline_offsets,
                offset_idx,
                pocket_idx,
                tool_offset,
                is_closed=False,
                is_pocket=2,
                parent_id=parent_id,
            )
            pocket_idx += 1
    elif HAVE_PYCLIPPER and obj.inner_objects and obj.setup["pockets"]["islands"]:
        subjs = []
        vertex_data = vertex_data_cache(polyline)
        points = vertex2points(
            vertex_data, no_bulge=True, scale=1000.0, interpolate=interpolate
        )
        pco = pyclipper.PyclipperOffset()  # pylint: disable=E1101
        pco.AddPath(
            points,
            pyclipper.JT_ROUND,  # pylint: disable=E1101
            pyclipper.ET_CLOSEDPOLYGON,  # pylint: disable=E1101
        )
        level = len(obj.outer_objects)
        for idx in obj.inner_objects:
            polyline_offset = polyline_offsets.get(f"{idx}.0")
            if polyline_offset and polyline_offset.level == level + 1:
                vertex_data = vertex_data_cache(polyline_offset)
                points = vertex2points(
                    vertex_data, no_bulge=True, scale=1000.0, interpolate=interpolate
                )
                pco.AddPath(
                    points,
                    pyclipper.JT_ROUND,  # pylint: disable=E1101
                    pyclipper.ET_CLOSEDPOLYGON,  # pylint: disable=E1101
                )
        subjs = pco.Execute(-abs_tool_radius * 1000)

        for points in subjs:
            offset_idx = points2offsets(
                obj,
                points,
                polyline_offsets,
                offset_idx,
                pocket_idx,
                tool_offset,
                scale=0.001,
                is_closed=obj.closed,
                is_pocket=2,
                parent_id=parent_id,
            )
            pocket_idx += 1

        while True:
            pco = pyclipper.PyclipperOffset()  # pylint: disable=E1101
            for subj in subjs:
                pco.AddPath(
                    subj,
                    pyclipper.JT_ROUND,  # pylint: disable=E1101
                    pyclipper.ET_CLOSEDPOLYGON,  # pylint: disable=E1101
                )
            subjs = pco.Execute(-abs_tool_radius * 1000)  # pylint: disable=E1101
            if not subjs:
                break
            for points in subjs:
                offset_idx = points2offsets(
                    obj,
                    points,
                    polyline_offsets,
                    offset_idx,
                    pocket_idx,
                    tool_offset,
                    scale=0.001,
                    is_closed=obj.closed,
                    is_pocket=2,
                    parent_id=parent_id,
                )
                pocket_idx += 1

    elif obj.segments[0]["type"] == "CIRCLE" and "center" in obj.segments[0]:
        start = obj.segments[0].start
        center = obj.segments[0].center
        radius = calc_distance(start, center)
        points = []
        rad = 0
        while True:
            rad += abs_tool_radius / 2
            if rad > radius - abs_tool_radius:
                break
            points.append((center[0] - rad, center[1] + 0.01, 1.0))
            rad += abs_tool_radius / 2
            if rad > radius - abs_tool_radius:
                break
            points.append((center[0] + rad, center[1] - 0.01, 1.0))
        vertex_data = points2vertex(points)
        polyline_offset = cavc.Polyline(vertex_data, is_closed=False)
        polyline_offset.level = len(obj.outer_objects)
        polyline_offset.tool_offset = tool_offset
        polyline_offset.layer = obj.layer
        polyline_offset.color = obj.color
        polyline_offset.setup = obj.setup
        polyline_offset.obj_idx = obj_idx
        polyline_offset.outer_objects = obj.outer_objects
        polyline_offset.start = obj.start
        polyline_offset.is_pocket = 1
        polyline_offset.fixed_direction = True
        polyline_offsets[f"{obj_idx}.{offset_idx}"] = polyline_offset
        offset_idx += 1

    else:
        offsets = polyline.parallel_offset(delta=tool_radius, check_self_intersect=True)
        for polyline_offset in offsets:
            if polyline_offset:
                # workaround for bad offsets
                vertex_data = vertex_data_cache(polyline_offset)
                point = (vertex_data[0][0], vertex_data[1][0], vertex_data[2][0])
                if not inside_vertex(vertex_data_org, point):
                    continue
                polyline_offset.level = len(obj.outer_objects)
                polyline_offset.tool_offset = tool_offset
                polyline_offset.layer = obj.layer
                polyline_offset.color = obj.color
                polyline_offset.setup = obj.setup
                polyline_offset.obj_idx = parent_id
                polyline_offset.outer_objects = obj.outer_objects
                polyline_offset.start = obj.start
                polyline_offset.is_pocket = 1
                polyline_offset.fixed_direction = False

                parent_id = f"{parent_id}.{pocket_idx}"
                polyline_offsets[parent_id] = polyline_offset
                pocket_idx += 1
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
                        parent_id,
                    )
    return offset_idx


def object2polyline_offsets(
    diameter, obj, obj_idx, max_outer, polyline_offsets, small_circles=False
):
    """calculates the offset line(s) of one object"""

    new_polyline_offsets = {}

    def overcut() -> None:
        quarter_pi = math.pi / 4
        radius_3 = abs(tool_radius * 3)
        for offset_idx, polyline in enumerate(list(new_polyline_offsets.values())):
            points = vertex2points(vertex_data_cache(polyline))
            xdata = []
            ydata = []
            bdata = []
            last = points[-1]
            last_angle = None
            for point in points:
                angle = angle_of_line(point, last)
                if last_angle is not None and last[2] == 0.0:
                    if angle > last_angle:
                        angle = angle + TWO_PI
                    adiff = angle - last_angle
                    if adiff < -TWO_PI:
                        adiff += TWO_PI

                    if abs(adiff) >= quarter_pi:
                        c_angle = last_angle + adiff / 2.0 + math.pi
                        over_x = last[0] - radius_3 * math.sin(c_angle)
                        over_y = last[1] + radius_3 * math.cos(c_angle)
                        for segment in obj.segments:
                            is_b = is_between(
                                (segment.start[0], segment.start[1]),
                                (last[0], last[1]),
                                (over_x, over_y),
                            )
                            if is_b:
                                dist = calc_distance(
                                    (segment.start[0], segment.start[1]),
                                    (last[0], last[1]),
                                )
                                over_dist = dist - abs(tool_radius)
                                over_x = last[0] - (over_dist) * math.sin(c_angle)
                                over_y = last[1] + (over_dist) * math.cos(c_angle)
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
                    angle = angle + TWO_PI
                adiff = angle - last_angle
                if adiff < -TWO_PI:
                    adiff += TWO_PI

                if abs(adiff) >= quarter_pi:
                    c_angle = last_angle + adiff / 2.0 + math.pi
                    over_x = last[0] - radius_3 * math.sin(c_angle)
                    over_y = last[1] + radius_3 * math.cos(c_angle)
                    for segment in obj.segments:
                        is_b = is_between(
                            (segment.start[0], segment.start[1]),
                            (last[0], last[1]),
                            (over_x, over_y),
                        )
                        if is_b:
                            dist = calc_distance(
                                (segment.start[0], segment.start[1]),
                                (last[0], last[1]),
                            )
                            over_dist = dist - abs(tool_radius)
                            over_x = last[0] - over_dist * math.sin(c_angle)
                            over_y = last[1] + over_dist * math.cos(c_angle)
                            xdata.append(over_x)
                            ydata.append(over_y)
                            bdata.append(0.0)
                            xdata.append(last[0])
                            ydata.append(last[1])
                            bdata.append(0.0)
                            break

            over_polyline = cavc.Polyline((xdata, ydata, bdata), is_closed=True)
            over_polyline.level = len(obj.outer_objects)
            over_polyline.start = obj.start
            over_polyline.setup = obj.setup
            over_polyline.obj_idx = obj_idx
            over_polyline.outer_objects = obj.outer_objects
            over_polyline.layer = obj.layer
            over_polyline.color = obj.color
            over_polyline.is_pocket = 0
            over_polyline.fixed_direction = False
            over_polyline.tool_offset = tool_offset
            new_polyline_offsets[f"{obj_idx}.{offset_idx}"] = over_polyline

    tool_offset = obj.tool_offset
    if obj.overwrite_offset is not None:
        tool_radius = obj.overwrite_offset
    else:
        tool_radius = diameter / 2.0

    if obj.setup["mill"]["reverse"]:
        tool_radius = -tool_radius

    is_circle = bool(obj.segments[0].type == "CIRCLE")

    vertex_data = object2vertex(obj)
    polyline = cavc.Polyline(vertex_data, is_closed=obj.closed)
    polyline.cache = vertex_data

    offset_idx = 0
    if polyline.is_closed() and tool_offset != "none":
        polyline_offset_list = polyline.parallel_offset(
            delta=tool_radius, check_self_intersect=True
        )
        if polyline_offset_list:
            for polyline_offset in polyline_offset_list:
                vertex_data = polyline_offset.vertex_data()
                polyline_offset.cache = vertex_data
                polyline_offset.level = len(obj.outer_objects)
                polyline_offset.start = obj.start
                polyline_offset.tool_offset = tool_offset
                polyline_offset.setup = obj.setup
                polyline_offset.obj_idx = obj_idx
                polyline_offset.outer_objects = obj.outer_objects
                polyline_offset.layer = obj.layer
                polyline_offset.color = obj.color
                polyline_offset.is_pocket = 0
                polyline_offset.fixed_direction = False
                polyline_offset.is_circle = is_circle
                parent_id = f"{obj_idx}.{offset_idx}"
                new_polyline_offsets[parent_id] = polyline_offset
                offset_idx += 1
                if tool_offset == "inside" and obj.setup["pockets"]["active"]:
                    if polyline_offset.is_closed():
                        offset_idx = do_pockets(
                            polyline_offset,
                            obj,
                            obj_idx,
                            tool_offset,
                            tool_radius,
                            polyline_offsets,
                            offset_idx,
                            vertex_data,
                            parent_id,
                        )

        elif is_circle and small_circles:
            # adding holes that smaler as the tool
            center_x = obj.segments[0].center[0]
            center_y = obj.segments[0].center[1]
            vertex_data = ((center_x,), (center_y,), (0,))
            polyline_offset = cavc.Polyline(vertex_data, is_closed=False)
            polyline_offset.cache = polyline_offset.vertex_data()
            polyline_offset.level = len(obj.outer_objects)
            polyline_offset.start = obj.start
            polyline_offset.tool_offset = tool_offset
            polyline_offset.setup = obj.setup
            polyline_offset.obj_idx = obj_idx
            polyline_offset.outer_objects = obj.outer_objects
            polyline_offset.layer = obj.layer
            polyline_offset.color = obj.color
            polyline_offset.is_pocket = 0
            polyline_offset.fixed_direction = False
            polyline_offset.is_circle = True
            new_polyline_offsets[f"{obj_idx}.{offset_idx}.x"] = polyline_offset
            offset_idx += 1

        if obj.setup["mill"]["overcut"]:
            overcut()

    else:
        polyline.level = max_outer
        polyline.setup = obj.setup
        polyline.obj_idx = obj_idx
        polyline.outer_objects = obj.outer_objects
        polyline.tool_offset = tool_offset
        polyline.start = obj.start
        polyline.layer = obj.layer
        polyline.color = obj.color
        polyline.is_pocket = 0
        polyline.fixed_direction = False
        polyline.is_circle = False
        new_polyline_offsets[f"{obj_idx}.{offset_idx}"] = polyline
        offset_idx += 1

    polyline_offsets.update(new_polyline_offsets)

    return polyline_offsets


def objects2polyline_offsets(setup, objects, max_outer):
    """calculates the offset line(s) of all objects"""
    polyline_offsets = {}

    unit = setup["machine"]["unit"]
    small_circles = setup["mill"]["small_circles"]

    part_l = len(objects)
    part_n = 0
    last_percent = -1
    for level in range(max_outer, -1, -1):
        for obj_idx, obj in objects.items():
            if not obj.setup["mill"]["active"]:
                continue
            if len(obj.outer_objects) != level:
                continue
            percent = round((part_n + 1) * 100 / part_l, 1)
            if int(percent) != int(last_percent):
                print(f"calc offset path: {percent}%", end="\r")
            last_percent = int(percent)
            part_n += 1

            diameter = None
            for entry in setup["tool"]["tooltable"]:
                if obj.setup["tool"]["number"] == entry["number"]:
                    diameter = entry["diameter"]
            if diameter is None:
                print("ERROR: TOOL not found")
                break

            if unit == "inch":
                diameter *= 25.4

            obj_copy = deepcopy(obj)
            do_reverse = 0
            if obj_copy.tool_offset == "outside":
                do_reverse = 1 - do_reverse

            if obj_copy["setup"]["mill"]["reverse"]:
                do_reverse = 1 - do_reverse

            if do_reverse:
                reverse_object(obj_copy)

            object2polyline_offsets(
                diameter, obj_copy, obj_idx, max_outer, polyline_offsets, small_circles
            )

    print("")
    return polyline_offsets


# analyze size
def objects2minmax(objects):
    """find the min/max values of objects"""
    if len(objects.keys()) == 0:
        return (0, 0, 0, 0)
    fist_key = list(objects.keys())[0]
    min_x = objects[fist_key]["segments"][0].start[0]
    min_y = objects[fist_key]["segments"][0].start[1]
    max_x = objects[fist_key]["segments"][0].start[0]
    max_y = objects[fist_key]["segments"][0].start[1]
    for obj in objects.values():
        if obj.layer.startswith("BREAKS:") or obj.layer.startswith("_TABS"):
            continue
        for segment in obj.segments:
            min_x = min(min_x, segment.start[0])
            min_x = min(min_x, segment.end[0])
            min_y = min(min_y, segment.start[1])
            min_y = min(min_y, segment.end[1])
            max_x = max(max_x, segment.start[0])
            max_x = max(max_x, segment.end[0])
            max_y = max(max_y, segment.start[1])
            max_y = max(max_y, segment.end[1])
    return (min_x, min_y, max_x, max_y)


def rotate_point(
    origin_x: float, origin_y: float, point_x: float, point_y: float, angle: float
) -> tuple:
    new_x = (
        origin_x
        + math.cos(angle) * (point_x - origin_x)
        - math.sin(angle) * (point_y - origin_y)
    )
    new_y = (
        origin_y
        + math.sin(angle) * (point_x - origin_x)
        + math.cos(angle) * (point_y - origin_y)
    )
    return (new_x, new_y)


def rotate_object(
    obj: VcObject, origin_x: float, origin_y: float, angle: float
) -> None:
    """rotates an object"""
    for segment in obj.segments:
        for ptype in ("start", "end", "center"):
            if ptype in segment:
                segment[ptype] = rotate_point(
                    origin_x, origin_y, segment[ptype][0], segment[ptype][1], angle
                )


def move_object(obj: VcObject, xoff: float, yoff: float) -> None:
    """moves an object"""
    for segment in obj.segments:
        for ptype in ("start", "end", "center"):
            if ptype in segment:
                segment[ptype] = (
                    segment[ptype][0] + xoff,
                    segment[ptype][1] + yoff,
                )


def move_objects(objects: dict, xoff: float, yoff: float) -> None:
    """moves an object"""
    for obj in objects.values():
        move_object(obj, xoff, yoff)


def mirror_objects(
    objects: dict,
    min_max: list[float],
    vertical: bool = False,
    horizontal: bool = False,
) -> None:
    """mirrors an object"""
    if vertical or horizontal:
        for obj in objects.values():
            for segment in obj.segments:
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
                    segment.bulge = -segment.bulge

            if vertical != horizontal:
                reverse_object(obj)


def rotate_objects(objects: dict, min_max: list[float]) -> None:
    """rotates all object"""
    for obj in objects.values():
        for segment in obj.segments:
            for ptype in ("start", "end", "center"):
                if ptype in segment:
                    segment[ptype] = (segment[ptype][1], segment[ptype][0])

            segment.bulge = -segment.bulge
        reverse_object(obj)
    mirror_objects(objects, min_max, horizontal=True)


def scale_object(obj: VcObject, scale: float) -> None:
    """scale an object"""
    for segment in obj.segments:
        for ptype in ("start", "end", "center"):
            if ptype in segment:
                segment[ptype] = (
                    segment[ptype][0] * scale,
                    segment[ptype][1] * scale,
                )


def scale_objects(objects: dict, scale: float) -> None:
    """scale all object"""
    for obj in objects.values():
        for segment in obj.segments:
            for ptype in ("start", "end", "center"):
                if ptype in segment:
                    segment[ptype] = (
                        segment[ptype][0] * scale,
                        segment[ptype][1] * scale,
                    )
