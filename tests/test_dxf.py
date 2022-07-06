import pytest
from viaconstructor import dxfread


@pytest.mark.parametrize(
    "filename, expected",
    (
        (
            "tests/data/simple.dxf",
            [
                {
                    "type": "LINE",
                    "object": None,
                    "start": (20.0, 70.0, 0.0),
                    "end": (80.0, 70.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "start": (80.0, 70.0, 0.0),
                    "end": (20.0, 10.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "start": (20.0, 10.0, 0.0),
                    "end": (20.0, 70.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "start": (10.0, 90.0, 0.0),
                    "end": (120.0, 80.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "start": (120.0, 80.0, 0.0),
                    "end": (110.0, -10.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "start": (110.0, -10.0, 0.0),
                    "end": (0.0, 0.0, 0.0),
                    "bulge": 0.0,
                },
                {
                    "type": "LINE",
                    "object": None,
                    "start": (0.0, 0.0, 0.0),
                    "end": (10.0, 90.0, 0.0),
                    "bulge": 0.0,
                },
            ],
        ),
    ),
)
def test_DxfReader(filename, expected):
    dxfreader = dxfread.DxfReader(filename)
    result = dxfreader.get_segments()
    print(result)
    assert result == expected
