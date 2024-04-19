import filecmp

from examples.simple_sample import main

from . import here


def test_simple_sample():
    output_svg = here("../out.svg")
    expected_svg = here("resources/expected_output.svg")

    main()
    assert filecmp.cmp(output_svg, expected_svg), "svg output not as expected!"
