# viaConstructor

OpenSource CAM-Tool to generate gCode from DXF,SVG,CDR,HPGL-Files and more

## Features:
 * running on Linux (incl. Raspberry PI 4), OS-X (Intel and ARM) and Windows
 * 3D-Preview
 * Tabs and Pockets with Islands
 * Headless-Support to generate gcode on the console
 * the preview of the milling path is generated by the original gcode data using a simple gcode-interpreter
 * the offsets are calculated internaly, no offset-support in the cnc controller is needed
 * automatic offset finder (inside/outside)
 * automatic order of multiple parts (nearest first)
 * nested parts will milled in the right order (inside parts first)
 * can read DXF, SVG, HPGL and STL (cross section)
 * can also convert and read (limited support) CDR, PDF, EPS and some raster-image's
 * Truetype-Fonts to generate simple Text
 * generates gCode and HPGL output
 * limited drag knife support

## Known Issues:
* SVG-Support is very bad, better using DXF
* &gt;= Python-3.9 (will not work with Debian-10 or lower)
* may be unstable on Windows
* problems with some OpenGL versions (black 3D-View)
* tabs on circles sometimes broken
* slow on very big files

## demo-video
[![Demo-Video](http://img.youtube.com/vi/4OBiqeqKDsk/0.jpg)](https://www.youtube.com/watch?v=4OBiqeqKDsk "Demo-Video")

## screenshot
![viaconstructor](docs/viaconstructor.png)

## quikstart

### for Debian11/12 and Ubuntu 22.04:
download the right package from:
https://multixmedia.org/debian-packages

and install with 
```
apt-get install python3-viaconstructor_*.deb
```

### install with pip
```
pip3 install viaconstructor
```

### running from sources
```
git clone https://github.com/multigcs/viaconstructor.git
cd viaconstructor
pip3 install -r requirements.txt
```

### start viaconstructor
```
./bin/viaconstructor tests/data/simple.dxf
```

### running on macos/osx
```
brew install python@3.10
git clone https://github.com/multigcs/viaconstructor.git
cd viaconstructor
/usr/local/bin/python3 -m pip install -r requirements-install.txt
/usr/local/bin/python3 -m viaconstructor tests/data/simple.dxf
```

### running on Windows10
you can simply extract this zip file to you disk and execute the start.bat:

 https://www.multixmedia.org/viaconstructor.zip

this zip-file includes python3.10.10 and all needed packages

or 

install python3.10.10 from: https://www.python.org/ftp/python/3.10.10/python-3.10.10-amd64.exe
install git from: https://github.com/git-for-windows/git/releases/download/v2.40.0.windows.1/Git-2.40.0-64-bit.exe
at the moment, you need also Visual Studio Community 2022 from: https://visualstudio.microsoft.com/vs/community/ (to install pyclipper / some dll's needed for CavalierContours)
```
git clone https://github.com/multigcs/viaconstructor.git
python3.exe -m pip install -r requirements-install.in
python3.exe -m viaconstructor tests/data/simple.dxf
```

## Screenshots

### Helix
![helix](docs/mill-helix_mode-true.png)

### Overcut
![overcut](docs/mill-overcut-true.png)

### Tabs
![tabs](docs/tabs-active-true.png)

### Pockets
![pockets](docs/pockets-active-true.png)

### Lead-In/Lead-Out
![leads](docs/leads-in-arc.png)

### OSX
![osx](docs/osx.png)

### Windows
![osx](docs/windows.png)
