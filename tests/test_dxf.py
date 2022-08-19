import pytest

from viaconstructor.input_plugins import dxfread
from viaconstructor.vc_types import VcSegment


@pytest.mark.parametrize(
    "filename, expected, expected_minmax, expected_size",
    (
        (
            "tests/data/simple.dxf",
            [
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (20.0, 70.0),
                        "end": (80.0, 70.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (80.0, 70.0),
                        "end": (20.0, 10.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (20.0, 10.0),
                        "end": (20.0, 70.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (10.0, 90.0),
                        "end": (120.0, 80.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (120.0, 80.0),
                        "end": (110.0, -10.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (110.0, -10.0),
                        "end": (0.0, 0.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (0.0, 0.0),
                        "end": (10.0, 90.0),
                        "bulge": 0.0,
                    }
                ),
            ],
            [0.0, -10.0, 120.0, 90.0],
            [120.0, 100.0],
        ),
        (
            "tests/data/all.dxf",
            [
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (10.0, 0.0),
                        "end": (7.0710678118654755, 7.071067811865475),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (7.0710678118654755, 7.071067811865475),
                        "end": (6.123233995736766e-16, 10.0),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (6.123233995736766e-16, 10.0),
                        "end": (-7.071067811865475, 7.0710678118654755),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-7.071067811865475, 7.0710678118654755),
                        "end": (-10.0, 1.2246467991473533e-15),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-10.0, 1.2246467991473533e-15),
                        "end": (-7.071067811865477, -7.071067811865475),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-7.071067811865477, -7.071067811865475),
                        "end": (-1.8369701987210296e-15, -10.0),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-1.8369701987210296e-15, -10.0),
                        "end": (7.071067811865474, -7.071067811865477),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (7.071067811865474, -7.071067811865477),
                        "end": (10.0, -2.4492935982947065e-15),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (20.0, 0.0),
                        "end": (14.142135623730951, 14.14213562373095),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (14.142135623730951, 14.14213562373095),
                        "end": (1.2246467991473533e-15, 20.0),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (1.2246467991473533e-15, 20.0),
                        "end": (-14.14213562373095, 14.142135623730951),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-14.14213562373095, 14.142135623730951),
                        "end": (-20.0, 2.4492935982947065e-15),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-20.0, 2.4492935982947065e-15),
                        "end": (-14.142135623730955, -14.14213562373095),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-14.142135623730955, -14.14213562373095),
                        "end": (-3.673940397442059e-15, -20.0),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-3.673940397442059e-15, -20.0),
                        "end": (14.142135623730947, -14.142135623730955),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "layer2",
                        "start": (14.142135623730947, -14.142135623730955),
                        "end": (20.0, -4.898587196589413e-15),
                        "bulge": 0.19891236737965798,
                        "center": (0.0, 0.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-20.0, 30.0),
                        "end": (20.0, 30.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (-20.0, 40.0),
                        "end": (20.0, 40.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (30.0, -20.0),
                        "end": (90.0, -20.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (40.0, 30.0),
                        "end": (60.0, 30.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (60.0, 30.0),
                        "end": (60.0, 10.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (60.0, 10.0),
                        "end": (40.0, 10.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (40.0, 10.0),
                        "end": (40.0, 30.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (56.0, 20.0),
                        "end": (54.242640687119284, 24.242640687119284),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (54.242640687119284, 24.242640687119284),
                        "end": (50.0, 26.0),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (50.0, 26.0),
                        "end": (45.757359312880716, 24.242640687119284),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (45.757359312880716, 24.242640687119284),
                        "end": (44.0, 20.0),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (44.0, 20.0),
                        "end": (45.757359312880716, 15.757359312880716),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (45.757359312880716, 15.757359312880716),
                        "end": (50.0, 14.0),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (50.0, 14.0),
                        "end": (54.242640687119284, 15.757359312880714),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "CIRCLE",
                        "object": None,
                        "layer": "0",
                        "start": (54.242640687119284, 15.757359312880714),
                        "end": (56.0, 20.0),
                        "bulge": 0.19891236737965798,
                        "center": (50.0, 20.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (30.0, 24.0),
                        "end": (30.0, -20.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (46.0, 40.0),
                        "end": (34.68629150101524, 35.31370849898476),
                        "bulge": 0.19891236737965798,
                        "center": (46.0, 24.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (34.68629150101524, 35.31370849898476),
                        "end": (30.0, 24.000000000000004),
                        "bulge": 0.19891236737965798,
                        "center": (46.0, 24.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (74.0, 40.0),
                        "end": (46.0, 40.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (90.0, -20.0),
                        "end": (90.0, 24.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (90.0, 24.0),
                        "end": (85.31370849898477, 35.31370849898476),
                        "bulge": 0.19891236737965798,
                        "center": (74.0, 24.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (85.31370849898477, 35.31370849898476),
                        "end": (74.0, 40.0),
                        "bulge": 0.19891236737965798,
                        "center": (74.0, 24.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (54.0, 0.0),
                        "end": (51.17157287525381, -1.1715728752538097),
                        "bulge": 0.19891236737965798,
                        "center": (54.0, -4.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (51.17157287525381, -1.1715728752538097),
                        "end": (50.0, -3.9999999999999996),
                        "bulge": 0.19891236737965798,
                        "center": (54.0, -4.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (50.0, -4.0),
                        "end": (50.0, -6.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (50.0, -5.999999999999999),
                        "end": (51.17157287525381, -8.82842712474619),
                        "bulge": 0.19891236737965798,
                        "center": (54.0, -6.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (51.17157287525381, -8.82842712474619),
                        "end": (54.0, -10.0),
                        "bulge": 0.19891236737965798,
                        "center": (54.0, -6.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (54.0, -10.0),
                        "end": (66.0, -10.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (66.0, -10.0),
                        "end": (68.82842712474618, -8.828427124746192),
                        "bulge": 0.19891236737965798,
                        "center": (66.0, -6.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (68.82842712474618, -8.828427124746192),
                        "end": (70.0, -6.000000000000001),
                        "bulge": 0.19891236737965798,
                        "center": (66.0, -6.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (54.0, 0.0),
                        "end": (66.0, 0.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "0",
                        "start": (70.0, -6.0),
                        "end": (70.0, -4.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (70.0, -4.0),
                        "end": (68.82842712474618, -1.1715728752538102),
                        "bulge": 0.19891236737965798,
                        "center": (66.0, -4.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "0",
                        "start": (68.82842712474618, -1.1715728752538102),
                        "end": (66.0, 0.0),
                        "bulge": 0.19891236737965798,
                        "center": (66.0, -4.0),
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (60.0, 60.0),
                        "end": (60.0, 90.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (60.0, 90.0),
                        "end": (0.0, 90.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (0.0, 90.0),
                        "end": (0.0, 60.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (0.0, 60.0),
                        "end": (60.0, 60.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (20.0, 70.0),
                        "end": (20.0, 74.42225278929824),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "LINE",
                        "object": None,
                        "layer": "layer2",
                        "start": (20.21456992734422, 75.53642481836056),
                        "end": (22.0, 80.0),
                        "bulge": 0.0,
                    }
                ),
                VcSegment(
                    {
                        "type": "ARC",
                        "object": None,
                        "layer": "layer2",
                        "start": (20.214569927344225, 75.53642481836056),
                        "end": (20.0, 74.42225278929824),
                        "bulge": 0.09541457239976009,
                        "center": (23.0, 74.42225278929824),
                    }
                ),
            ],
            [-20.0, -20.0, 90.0, 90.0],
            [110.0, 110.0],
        ),
    ),
)
def test_DxfReader(filename, expected, expected_minmax, expected_size):
    dxfreader = dxfread.DrawReader(filename)
    result = dxfreader.get_segments()
    assert str(result) == str(expected)
    assert dxfreader.get_minmax() == expected_minmax
    assert dxfreader.get_size() == expected_size
