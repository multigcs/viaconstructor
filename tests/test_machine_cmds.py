import pytest

from viaconstructor import machine_cmd
from viaconstructor.output_plugins.gcode_linuxcnc import PostProcessorGcodeLinuxCNC


class fakeOffset:
    def __init__(self, data, closed, level, mill, tool_offset):
        self.level = level
        self.closed = closed
        self.setup = {"mill": mill, "tabs": {"active": False}}
        self.data = data
        self.tool_offset = tool_offset
        self.is_pocket = False

    def is_closed(self):
        return self.closed

    def vertex_data(self):
        return self.data


@pytest.mark.parametrize(
    "project, expected",
    (
        (
            {
                "filename_dxf": "/tmp/t.dxf",
                "filename_machine_cmd": "/tmp/t.ngc",
                "offsets": {
                    "0.0": fakeOffset(
                        [
                            ([22.0, 75.17157288, 22.0]),
                            ([78.0, 78.0, 24.82842712]),
                            ([0.0, 0.0, 0.0]),
                        ],
                        True,
                        1,
                        {
                            "G64": 0.05,
                            "active": True,
                            "back_home": True,
                            "depth": -7.0,
                            "fast_move_z": 20.0,
                            "pocket": False,
                            "reverse": False,
                            "step": -4.0,
                            "helix_mode": False,
                        },
                        "inside",
                    ),
                    "1.0": fakeOffset(
                        [
                            (
                                [
                                    8.01223253,
                                    -1.98776747,
                                    -0.18107149,
                                    109.81892851,
                                    111.98776747,
                                    121.98776747,
                                    120.18107149,
                                    10.18107149,
                                ]
                            ),
                            (
                                [
                                    100.22086305,
                                    10.22086305,
                                    8.00821359,
                                    -1.99178641,
                                    -0.22086305,
                                    89.77913695,
                                    91.99178641,
                                    101.99178641,
                                ]
                            ),
                            (
                                [
                                    -0.0,
                                    0.42008285,
                                    0.0,
                                    0.40836853,
                                    0.0,
                                    0.42008285,
                                    0.0,
                                    0.40836853,
                                ]
                            ),
                        ],
                        True,
                        0,
                        {
                            "G64": 0.05,
                            "active": True,
                            "back_home": True,
                            "depth": -7.0,
                            "fast_move_z": 20.0,
                            "pocket": False,
                            "reverse": False,
                            "step": -4.0,
                            "helix_mode": False,
                        },
                        "outside",
                    ),
                },
                "gllist": 2,
                "maxOuter": 1,
                "minMax": (0.0, 0.0, 120.0, 100.0),
                "table": [],
                "glwidget": "",
                "setup": {
                    "workpiece": {
                        "mirrorH": False,
                        "mirrorV": False,
                        "rotate": "0",
                        "zero": "bottomLeft",
                    },
                    "tool": {"diameter": 4.0, "number": 1, "speed": 10000},
                    "mill": {
                        "G64": 0.05,
                        "active": True,
                        "back_home": True,
                        "depth": -7.0,
                        "fast_move_z": 20.0,
                        "pocket": False,
                        "reverse": False,
                        "step": -4.0,
                        "rate_h": 10000,
                        "rate_v": 1000,
                        "helix_mode": False,
                        "laser": False,
                    },
                    "view": {"path": "simple"},
                },
                "tablewidget": "",
                "textwidget": "",
            },
            [
                "(--------------------------------------------------)",
                "(Generator: viaConstructor)",
                "(Filename: /tmp/t.dxf)",
                "(--------------------------------------------------)",
                "",
                "G21 (Metric/mm)",
                "G40 (No Offsets)",
                "G90 (Absolute-Mode)",
                "F1000",
                "G64 P0.05",
                "M05 (Spindle off)",
                "M06 T1",
                "M03 S10000 (Spindle on / CW)",
                "G04 P1 (pause in sec)",
                "G00 Z20.0",
                "",
                "",
                "(--------------------------------------------------)",
                "(Level: 1)",
                "(Order: 0)",
                "(Object: 0.0)",
                "(Distance: 181.53910525960544mm)",
                "(Closed: True)",
                "(isPocket: False)",
                "(Depth: -7.0mm / -4.0mm)",
                "(Tool-Diameter: 4.0mm)",
                "(Tool-Offset: 2.0mm inside)",
                "(--------------------------------------------------)",
                "G00 X22.0 Y24.828427",
                "(- Depth: -4.0mm -)",
                "F1000",
                "G01 Z-4.0",
                "F10000",
                "G01 Y78.0",
                "G01 X75.171573",
                "G01 X22.0 Y24.828427",
                "(- Depth: -7.0mm -)",
                "F1000",
                "G01 Z-7.0",
                "F10000",
                "G01 Y78.0",
                "G01 X75.171573",
                "G01 X22.0 Y24.828427",
                "G00 Z20.0",
                "",
                "(--------------------------------------------------)",
                "(Level: 0)",
                "(Order: 1)",
                "(Object: 1.0)",
                "(Distance: 413.3280660679408mm)",
                "(Closed: True)",
                "(isPocket: False)",
                "(Depth: -7.0mm / -4.0mm)",
                "(Tool-Diameter: 4.0mm)",
                "(Tool-Offset: 2.0mm outside)",
                "(--------------------------------------------------)",
                "G00 X-0.181071 Y8.008214",
                "(- Depth: -4.0mm -)",
                "F1000",
                "G01 Z-4.0",
                "F10000",
                "G01 X109.818929 Y-1.991786",
                "G03 X111.987767 Y-0.220863 I0.181071 J1.991786",
                "G01 X121.987767 Y89.779137",
                "G03 X120.181071 Y91.991786 I-1.987767 J0.220863",
                "G01 X10.181071 Y101.991786",
                "G03 X8.012233 Y100.220863 I-0.181071 J-1.991786",
                "G01 X-1.987767 Y10.220863",
                "G03 X-0.181071 Y8.008214 I1.987767 J-0.220863",
                "(- Depth: -7.0mm -)",
                "F1000",
                "G01 Z-7.0",
                "F10000",
                "G01 X109.818929 Y-1.991786",
                "G03 X111.987767 Y-0.220863 I0.181071 J1.991786",
                "G01 X121.987767 Y89.779137",
                "G03 X120.181071 Y91.991786 I-1.987767 J0.220863",
                "G01 X10.181071 Y101.991786",
                "G03 X8.012233 Y100.220863 I-0.181071 J-1.991786",
                "G01 X-1.987767 Y10.220863",
                "G03 X-0.181071 Y8.008214 I1.987767 J-0.220863",
                "G00 Z20.0",
                "",
                "(- end -)",
                "M05 (Spindle off)",
                "G00 X0.0 Y0.0",
                "M02",
                "",
            ],
        ),
    ),
)
def test_polylines2machine_cmd(project, expected):
    result = machine_cmd.polylines2machine_cmd(project, PostProcessorGcodeLinuxCNC())
    print(result)
    assert result == expected
