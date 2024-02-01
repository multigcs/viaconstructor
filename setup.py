#!/usr/bin/env python3
#
# ls data/* | awk '{print "\""$1"\""}' | tr "\n" ","
#

import os
from setuptools import setup


setup(
    name='viaconstructor',
    version='0.6.5',
    author='Oliver Dippel',
    author_email='o.dippel@gmx.de',
    packages=['viaconstructor', 'viaconstructor.ext.cavaliercontours', 'viaconstructor.ext.HersheyFonts', 'viaconstructor.ext.meshcut', 'viaconstructor.ext.stl', 'viaconstructor.ext.svgpathtools', 'viaconstructor.input_plugins', 'viaconstructor.output_plugins', 'viaconstructor.preview_plugins', 'viaconstructor.tools', 'gcodepreview', 'dxfpreview'],
    package_data={'viaconstructor.ext.cavaliercontours': ['lib/libCavalierContours.x86_64-linux.so'], 'viaconstructor/ext/nest2D': ['nest2D.cpython-39-x86_64-linux-gnu.so']},
    scripts=['bin/viaconstructor','bin/gcodepreview','bin/dxfpreview'],
    url='https://github.com/multigcs/viaconstructor',
    license='LICENSE',
    description='python based cam-tool to convert dxf into gcode',
    long_description=open('README.md').read(),
    install_requires=["PyQt5", "ezdxf", "PyOpenGL", "Pillow", "pygame", "pyclipper", "setproctitle", "freetype-py", "python-utils", "svgwrite", "matplotlib", "numpy"],
    include_package_data=True,
)

