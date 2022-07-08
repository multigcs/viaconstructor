import pytest

from viaconstructor import calc


@pytest.mark.parametrize(
    "rlist, idx, expected",
    (
        ([1, 2, 3, 4], 2, [3, 4, 1, 2]),
        ([1, 2, 3, 4], 3, [4, 1, 2, 3]),
    ),
)
def test_rotate_list(rlist, idx, expected):
    result = calc.rotate_list(rlist, idx)
    assert result == expected


@pytest.mark.parametrize(
    "p1, p2, expected",
    (
        ((123, 345), (678, 890), 0.7763075047323885),
        ((678, 890), (123, 345), -2.3652851488574047),
    ),
)
def test_angle_of_line(p1, p2, expected):
    result = calc.angle_of_line(p1, p2)
    assert result == expected


@pytest.mark.parametrize(
    "p1, p2, expected",
    (
        ((123.001, 345.002), (123.002, 345.001), True),
        ((123.009, 345.002), (123.002, 345.001), False),
        ((123.001, 345.009), (123.002, 345.001), False),
    ),
)
def test_fuzy_match(p1, p2, expected):
    assert calc.fuzy_match(p1, p2) == expected


@pytest.mark.parametrize(
    "p1, p2, expected",
    (
        ((123, 345), (678, 890), 777.8495998584816),
        ((678, 890), (123, 345), 777.8495998584816),
    ),
)
def test_calc_distance(p1, p2, expected):
    assert round(calc.calc_distance(p1, p2), 5) == round(expected, 5)


@pytest.mark.parametrize(
    "p1, p2, p3, expected",
    (
        ((200, 200), (100, 100), (300, 300), True),
        ((200.01, 200), (100, 100), (300, 300), False),
    ),
)
def test_is_between(p1, p2, p3, expected):
    assert calc.is_between(p1, p2, p3) == expected


@pytest.mark.parametrize(
    "p1, p2, expected",
    (
        ((100, 100, 0), (200, 200, 0), (150, 150, 0)),
        ((210, 200, 0), (100, 100, 100), (155, 150, 50)),
    ),
)
def test_line_center_3d(p1, p2, expected):
    assert calc.line_center_3d(p1, p2) == expected


@pytest.mark.parametrize(
    "p1, p2, expected",
    (
        ((100, 100, 0), (200, 200, 0), (151.06066017177983, 148.93933982822017)),
        ((210, 200, 0), (100, 100, 100), (153.99099080900552, 151.10991011009392)),
    ),
)
def test_calc_face(p1, p2, expected):
    assert calc.calc_face(p1, p2) == expected


@pytest.mark.parametrize(
    "p1, p2, expected",
    (
        ((123, 345), (678, 890), -0.30853603576416455),
        ((678, 890), (123, 345), 0.30853603576416455),
    ),
)
def test_angle_2d(p1, p2, expected):
    assert calc.angle_2d(p1, p2) == expected


@pytest.mark.parametrize(
    "segments, expected",
    (
        (
            [
                {
                    "start": (100, 100),
                    "end": (200, 200),
                    "bulge": 0.0,
                },
                {
                    "start": (0, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                },
            ],
            [
                {
                    "start": (0, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                }
            ],
        ),
        (
            [
                {
                    "start": (100, 100),
                    "end": (200, 200),
                    "bulge": 0.0,
                },
                {
                    "start": (20, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                },
            ],
            [
                {
                    "start": (100, 100),
                    "end": (200, 200),
                    "bulge": 0.0,
                },
                {
                    "start": (20, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                },
            ],
        ),
        (
            [
                {
                    "start": (100, 100),
                    "end": (200, 200),
                    "bulge": 0.0,
                },
                {
                    "start": (20, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                },
                {
                    "start": (20, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                },
            ],
            [
                {
                    "start": (100, 100),
                    "end": (200, 200),
                    "bulge": 0.0,
                },
                {
                    "start": (20, 0),
                    "end": (300, 300),
                    "bulge": 0.0,
                },
            ],
        ),
    ),
)
def test_clean_segments(segments, expected):
    assert calc.clean_segments(segments) == expected


@pytest.mark.parametrize(
    "obj, point, expected",
    (
        (
            {
                "segments": [
                    {
                        "start": (10.0, 90.0, 0.0),
                        "end": (0.0, 0.0, 0.0),
                    },
                    {
                        "start": (0.0, 0.0, 0.0),
                        "end": (110.0, -10.0, 0.0),
                    },
                    {
                        "start": (110.0, -10.0, 0.0),
                        "end": (120.0, 80.0, 0.0),
                    },
                    {
                        "start": (120.0, 80.0, 0.0),
                        "end": (10.0, 90.0, 0.0),
                    },
                ],
            },
            (20.0, 70.0, 0.0),
            True,
        ),
        (
            {
                "segments": [
                    {
                        "start": (20.0, 70.0, 0.0),
                        "end": (20.0, 10.0, 0.0),
                    },
                    {
                        "start": (20.0, 10.0, 0.0),
                        "end": (80.0, 70.0, 0.0),
                    },
                    {
                        "start": (80.0, 70.0, 0.0),
                        "end": (20.0, 70.0, 0.0),
                    },
                ],
            },
            (10.0, 90.0, 0.0),
            False,
        ),
    ),
)
def test_is_inside_polygon(obj, point, expected):
    assert calc.is_inside_polygon(obj, point) == expected


@pytest.mark.parametrize(
    "obj, expected",
    (
        (
            {
                "segments": [
                    {
                        "start": (10.0, 90.0, 0.0),
                        "end": (0.0, 0.0, 0.0),
                        "bulge": 0.0,
                    },
                    {
                        "start": (0.0, 0.0, 0.0),
                        "end": (110.0, -10.0, 0.0),
                        "bulge": 0.0,
                    },
                    {
                        "start": (110.0, -10.0, 0.0),
                        "end": (120.0, 80.0, 0.0),
                        "bulge": 1.0,
                    },
                    {
                        "start": (120.0, 80.0, 0.0),
                        "end": (10.0, 90.0, 0.0),
                        "bulge": 0.0,
                    },
                ],
            },
            {
                "segments": [
                    {
                        "start": (10.0, 90.0, 0.0),
                        "end": (120.0, 80.0, 0.0),
                        "bulge": -0.0,
                    },
                    {
                        "start": (120.0, 80.0, 0.0),
                        "end": (110.0, -10.0, 0.0),
                        "bulge": -1.0,
                    },
                    {
                        "start": (110.0, -10.0, 0.0),
                        "end": (0.0, 0.0, 0.0),
                        "bulge": -0.0,
                    },
                    {"start": (0.0, 0.0, 0.0), "end": (10.0, 90.0, 0.0), "bulge": -0.0},
                ]
            },
        ),
    ),
)
def test_reverse_object(obj, expected):
    assert calc.reverse_object(obj) == expected


@pytest.mark.parametrize(
    "objects, point, exclude, expected",
    (
        (
            {
                0: {
                    "segments": [
                        {
                            "start": (20.0, 70.0, 0.0),
                            "end": (20.0, 10.0, 0.0),
                        },
                        {
                            "start": (20.0, 10.0, 0.0),
                            "end": (80.0, 70.0, 0.0),
                        },
                        {
                            "start": (80.0, 70.0, 0.0),
                            "end": (20.0, 70.0, 0.0),
                        },
                    ],
                    "closed": True,
                },
                1: {
                    "segments": [
                        {
                            "start": (10.0, 90.0, 0.0),
                            "end": (0.0, 0.0, 0.0),
                        },
                        {
                            "start": (0.0, 0.0, 0.0),
                            "end": (110.0, -10.0, 0.0),
                        },
                        {
                            "start": (110.0, -10.0, 0.0),
                            "end": (120.0, 80.0, 0.0),
                        },
                        {
                            "start": (120.0, 80.0, 0.0),
                            "end": (10.0, 90.0, 0.0),
                        },
                    ],
                    "closed": True,
                },
            },
            (20.0, 70.0, 0.0),
            [0],
            [1],
        ),
    ),
)
def test_find_outer_objects(objects, point, exclude, expected):
    assert calc.find_outer_objects(objects, point, exclude) == expected


@pytest.mark.parametrize(
    "objects, expected",
    (
        (
            {
                0: {
                    "segments": [
                        {
                            "start": (20.0, 70.0, 0.0),
                            "end": (20.0, 10.0, 0.0),
                        },
                        {
                            "start": (20.0, 10.0, 0.0),
                            "end": (80.0, 70.0, 0.0),
                        },
                        {
                            "start": (80.0, 70.0, 0.0),
                            "end": (20.0, 70.0, 0.0),
                        },
                    ],
                    "closed": True,
                    "tool_offset": "inside",
                    "overwrite_offset": None,
                    "outer_objects": [1],
                    "inner_objects": [],
                },
                1: {
                    "segments": [
                        {
                            "start": (10.0, 90.0, 0.0),
                            "end": (0.0, 0.0, 0.0),
                        },
                        {
                            "start": (0.0, 0.0, 0.0),
                            "end": (110.0, -10.0, 0.0),
                        },
                        {
                            "start": (110.0, -10.0, 0.0),
                            "end": (120.0, 80.0, 0.0),
                        },
                        {
                            "start": (120.0, 80.0, 0.0),
                            "end": (10.0, 90.0, 0.0),
                        },
                    ],
                    "closed": True,
                    "tool_offset": "outside",
                    "overwrite_offset": None,
                    "outer_objects": [],
                    "inner_objects": [0],
                },
            },
            1,
        ),
    ),
)
def test_find_tool_offsets(objects, expected):
    assert calc.find_tool_offsets(objects) == expected


@pytest.mark.parametrize(
    "objects, expected",
    (
        (
            [
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (20.0, 70.0, 0.0),
                    "end": (80.0, 70.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (80.0, 70.0, 0.0),
                    "end": (20.0, 10.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (20.0, 70.0, 0.0),
                    "end": (20.0, 10.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (10.0, 90.0, 0.0),
                    "end": (120.0, 80.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (120.0, 80.0, 0.0),
                    "end": (110.0, -10.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (110.0, -10.0, 0.0),
                    "end": (0.0, 0.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "layer": "0",
                    "start": (0.0, 0.0, 0.0),
                    "end": (10.0, 90.0, 0.0),
                    "bulge": 0.0,
                },
            ],
            {
                0: {
                    "segments": [
                        {
                            "type": "LINE",
                            "object": 0,
                            "layer": "0",
                            "start": (20.0, 70.0, 0.0),
                            "end": (20.0, 10.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 0,
                            "layer": "0",
                            "start": (20.0, 10.0, 0.0),
                            "end": (80.0, 70.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 0,
                            "layer": "0",
                            "start": (80.0, 70.0, 0.0),
                            "end": (20.0, 70.0, 0.0),
                            "bulge": -0.0,
                        },
                    ],
                    "closed": True,
                    "tool_offset": "none",
                    "overwrite_offset": None,
                    "outer_objects": [],
                    "inner_objects": [],
                },
                1: {
                    "segments": [
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (10.0, 90.0, 0.0),
                            "end": (0.0, 0.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (0.0, 0.0, 0.0),
                            "end": (110.0, -10.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (110.0, -10.0, 0.0),
                            "end": (120.0, 80.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (120.0, 80.0, 0.0),
                            "end": (10.0, 90.0, 0.0),
                            "bulge": -0.0,
                        },
                    ],
                    "closed": True,
                    "tool_offset": "none",
                    "overwrite_offset": None,
                    "outer_objects": [],
                    "inner_objects": [],
                },
            },
        ),
    ),
)
def test_segments2objects(objects, expected):
    assert calc.segments2objects(objects) == expected


@pytest.mark.parametrize(
    "vertex_data, point, expected",
    (
        (
            [[40.0, 60.0, 60.0, 40.0], [30.0, 30.0, 10.0, 10.0], [0.0, 0.0, 0.0, 0.0]],
            (49.199999999999996, 20.800000000000004, 0.0),
            True,
        ),
    ),
)
def test_inside_vertex(vertex_data, point, expected):
    assert calc.inside_vertex(vertex_data, point) == expected


@pytest.mark.parametrize(
    "obj, expected, expected_minmax",
    (
        (
            {
                "segments": [
                    {
                        "type": "LINE",
                        "object": 5,
                        "layer": "0",
                        "start": (40.0, 30.0, 0.0),
                        "end": (40.0, 10.0, 0.0),
                        "bulge": -0.0,
                    },
                    {
                        "type": "LINE",
                        "object": 5,
                        "layer": "0",
                        "start": (40.0, 10.0, 0.0),
                        "end": (60.0, 10.0, 0.0),
                        "bulge": -0.0,
                    },
                    {
                        "type": "LINE",
                        "object": 5,
                        "layer": "0",
                        "start": (60.0, 10.0, 0.0),
                        "end": (60.0, 30.0, 0.0),
                        "bulge": -0.0,
                    },
                    {
                        "type": "LINE",
                        "object": 5,
                        "layer": "0",
                        "start": (60.0, 30.0, 0.0),
                        "end": (40.0, 30.0, 0.0),
                        "bulge": -0.0,
                    },
                ],
                "closed": True,
                "tool_offset": "inside",
                "overwrite_offset": None,
                "outer_objects": [4],
                "inner_objects": [6],
                "mill": {
                    "rate_h": 1000,
                    "rate_v": 100,
                    "fast_move_z": 5.0,
                    "G64": 0.05,
                    "depth": -9.0,
                    "step": -9.0,
                    "active": True,
                    "helix_mode": False,
                    "reverse": False,
                    "pocket": False,
                    "back_home": True,
                    "small_circles": True,
                    "zero": "original",
                    "overcut": False,
                },
                "tool": {"number": 1, "diameter": 4.0, "speed": 10000},
            },
            (
                [40.0, 40.0, 60.0, 60.0],
                [30.0, 10.0, 10.0, 30.0],
                [-0.0, -0.0, -0.0, -0.0],
            ),
            (40.0, 10.0, 60.0, 30.0),
        ),
    ),
)
def test_object2vertex(obj, expected, expected_minmax):
    assert calc.object2vertex(obj) == expected
    assert calc.objects2minmax({0: obj}) == expected_minmax


@pytest.mark.parametrize(
    "diameter, objects, max_outer, small_circles, expected",
    (
        (
            4.0,
            {
                0: {
                    "segments": [
                        {
                            "type": "LINE",
                            "object": 0,
                            "layer": "0",
                            "start": (20.0, 70.0, 0.0),
                            "end": (20.0, 10.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 0,
                            "layer": "0",
                            "start": (20.0, 10.0, 0.0),
                            "end": (80.0, 70.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 0,
                            "layer": "0",
                            "start": (80.0, 70.0, 0.0),
                            "end": (20.0, 70.0, 0.0),
                            "bulge": -0.0,
                        },
                    ],
                    "closed": True,
                    "tool_offset": "inside",
                    "overwrite_offset": None,
                    "outer_objects": [1],
                    "inner_objects": [],
                    "mill": {
                        "rate_h": 1000,
                        "rate_v": 100,
                        "fast_move_z": 5.0,
                        "G64": 0.05,
                        "depth": -9.0,
                        "step": -9.0,
                        "active": True,
                        "helix_mode": False,
                        "reverse": False,
                        "pocket": False,
                        "back_home": True,
                        "small_circles": True,
                        "zero": "original",
                        "overcut": False,
                    },
                    "tool": {"number": 1, "diameter": 4.0, "speed": 10000},
                },
                1: {
                    "segments": [
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (10.0, 90.0, 0.0),
                            "end": (0.0, 0.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (0.0, 0.0, 0.0),
                            "end": (110.0, -10.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (110.0, -10.0, 0.0),
                            "end": (120.0, 80.0, 0.0),
                            "bulge": -0.0,
                        },
                        {
                            "type": "LINE",
                            "object": 1,
                            "layer": "0",
                            "start": (120.0, 80.0, 0.0),
                            "end": (10.0, 90.0, 0.0),
                            "bulge": -0.0,
                        },
                    ],
                    "closed": True,
                    "tool_offset": "outside",
                    "overwrite_offset": None,
                    "outer_objects": [],
                    "inner_objects": [0],
                    "mill": {
                        "rate_h": 1000,
                        "rate_v": 100,
                        "fast_move_z": 5.0,
                        "G64": 0.05,
                        "depth": -9.0,
                        "step": -9.0,
                        "active": True,
                        "helix_mode": False,
                        "reverse": False,
                        "pocket": False,
                        "back_home": True,
                        "small_circles": True,
                        "zero": "original",
                        "overcut": False,
                    },
                    "tool": {"number": 1, "diameter": 4.0, "speed": 10000},
                },
            },
            1,
            True,
            [
                22.0,
                75.171573,
                22.0,
                68.0,
                68.0,
                14.828427,
                0.0,
                0.0,
                0.0,
                8.012233,
                -1.987767,
                -0.181071,
                109.818929,
                111.987767,
                121.987767,
                120.181071,
                10.181071,
                90.220863,
                0.220863,
                -1.991786,
                -11.991786,
                -10.220863,
                79.779137,
                81.991786,
                91.991786,
                -0.0,
                0.420083,
                0.0,
                0.408369,
                0.0,
                0.420083,
                0.0,
                0.408369,
            ],
        ),
    ),
)
def test_objects2polyline_offsets(
    diameter, objects, max_outer, small_circles, expected
):
    result = []
    for idx, line in calc.objects2polyline_offsets(
        diameter, objects, max_outer, small_circles
    ).items():
        for axis in line.vertex_data().tolist():
            for value in axis:
                result.append(round(value, 6))
    assert result == expected
