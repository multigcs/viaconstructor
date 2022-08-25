#!/usr/bin/env python3
#
# ls data/* | awk '{print "\""$1"\""}' | tr "\n" ","
#

import os
from setuptools import setup


setup(
    name='viaconstructor',
    version='0.4.2',
    author='Oliver Dippel',
    author_email='o.dippel@gmx.de',
    packages=['viaconstructor', 'viaconstructor.ext.cavaliercontours', 'viaconstructor.ext.HersheyFonts', 'viaconstructor.ext.meshcut', 'viaconstructor.ext.stl', 'viaconstructor.ext.svgpathtools', 'viaconstructor.input_plugins', 'viaconstructor.output_plugins', 'viaconstructor.preview_plugins', 'gcodepreview', 'dxfpreview'],
    package_data={'viaconstructor.ext.cavaliercontours': ['lib/libCavalierContours.so']},
    scripts=['bin/viaconstructor','bin/gcodepreview','bin/dxfpreview'],
    url='https://github.com/multigcs/viaconstructor',
    license='LICENSE',
    description='python based cam-tool to convert dxf into gcode',
    long_description=open('README.md').read(),
    install_requires=["PyQt5", "ezdxf", "PyOpenGL", "Pillow", "pygame", "pyclipper", "setproctitle", "freetype-py", "python-utils", "svgwrite", "matplotlib"],
    include_package_data=True,
)

