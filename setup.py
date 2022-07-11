#!/usr/bin/env python3
#
#

import os
from setuptools import setup

required=[]
with open('requirements-install.txt') as f:
    for line in f.read().splitlines():
        if line.strip() and "#" not in line:
            required.append(line)

setup(
    name='viaconstructor',
    version='0.1.0',
    author='Oliver Dippel',
    author_email='o.dippel@gmx.de',
    packages=['viaconstructor', 'gcodepreview', 'dxfpreview'],
    scripts=['bin/viaconstructor','bin/gcodepreview','bin/dxfpreview'],
    url='http://pypi.python.org/pypi/viaconstructor/',
    license='LICENSE',
    description='python based cam-tool to convert dxf into gcode',
    long_description=open('README.md').read(),
    install_requires=required,
    include_package_data=True,
    data_files = [ ('data', ['data/exit.png', 'data/filesave.png', 'data/flip-x.png', 'data/flip-y.png', 'data/load-setup-gcode.png', 'data/load-setup.png', 'data/rotate.png', 'data/save-gcode.png', 'data/save-setup-as.png', 'data/save-setup.png', 'data/view-2d.png', 'data/view-reset.png']) ]
)

