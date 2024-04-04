import os

import pytest


@pytest.mark.parametrize(
    "cfg",
    [
        "gcode-2x2mm-d2.cfg",
        "gcode-laser-d02.cfg",
        "hpgl-d01.cfg",
    ],
)
@pytest.mark.parametrize(
    "filename",
    [
        "check.dxf",
        "check.svg",
        "check.hpgl",
        "check.stl",
    ],
)
def test_DxfReader(filename, cfg):
    os.system(f"pyvenv/bin/python -m viaconstructor -s tests/data/{cfg} tests/data/{filename} --dxfread-no-svg -o tests/data/{filename}-{cfg}.out")
    result = open(f"tests/data/{filename}-{cfg}.out", "r").read()
    if not os.path.isfile(f"tests/data/{filename}-{cfg}.check"):
        print("new check-file generated")
        os.system(f"cp tests/data/{filename}-{cfg}.out tests/data/{filename}-{cfg}.check")
        # assert False
    expected = open(f"tests/data/{filename}-{cfg}.check", "r").read()
    os.system(f"rm tests/data/{filename}-{cfg}.out")
    assert result == expected
