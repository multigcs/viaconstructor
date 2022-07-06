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
        ((200.001, 200), (100, 100), (300, 300), False),
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
    ),
)
def test_clean_segments(segments, expected):
    assert calc.clean_segments(segments) == expected
