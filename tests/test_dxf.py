import pytest

from viaconstructor.input_plugins import dxfread


@pytest.mark.parametrize(
    ("filename", "expected_minmax", "expected_size"),
    [
        (
            "tests/data/simple.dxf",
            [0.0, -10.0, 120.0, 90.0],
            [120.0, 100.0],
        ),
    ],
)
def test_DxfReader(filename, expected_minmax, expected_size):
    dxfreader = dxfread.DrawReader(filename)
    dxfreader.get_segments()
    assert dxfreader.get_minmax() == expected_minmax
    assert dxfreader.get_size() == expected_size
