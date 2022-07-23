#!/usr/bin/env python3
#
#

import os
from setuptools import setup


setup(
    name='viaconstructor',
    version='0.1.4',
    author='Oliver Dippel',
    author_email='o.dippel@gmx.de',
    packages=['viaconstructor', 'viaconstructor.output_plugins', 'gcodepreview', 'dxfpreview'],
    scripts=['bin/viaconstructor','bin/gcodepreview','bin/dxfpreview'],
    url='http://pypi.python.org/pypi/viaconstructor/',
    license='LICENSE',
    description='python based cam-tool to convert dxf into gcode',
    long_description=open('README.md').read(),
    install_requires=["PyQt5", "ezdxf", "cavaliercontours-python", "PyOpenGL", "Pillow", "pygame", "Hershey-Fonts", "svgpathtools"],
    include_package_data=True,
    data_files = [ ('data', ['data/exit.png', 'data/select.png', 'data/flip-x.png', 'data/flip-y.png', 'data/load-setup-gcode.png', 'data/load-setup.png', 'data/rotate.png', 'data/save-gcode.png', 'data/save-setup-as.png', 'data/save-setup.png', 'data/view-2d.png', 'data/view-reset.png']) ]
)

