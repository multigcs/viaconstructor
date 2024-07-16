#!/bin/bash
#
#

set -e

sudo rm -rf dist/ deb_dist/
sudo apt-get -y install python3-stdeb dh-python || true

VERSION=`grep "version=" setup.py | cut -d"'" -f2`
CNAME=`lsb_release -a | grep "^Codename:" | awk '{print $2}'`
ARCH=`uname -m`



SETUPTOOLS_USE_DISTUTILS=stdlib python3 setup.py --command-packages=stdeb.command sdist_dsc
(
    cd deb_dist/viaconstructor-*/
    sed -i 's|Depends: |Depends: python3-pyqt5.qtopengl, |g' debian/control
    dpkg-buildpackage -rfakeroot -uc -us
)

mkdir -p debian-packages/
cp deb_dist/*.deb debian-packages/python3-viaconstructor_${VERSION}-${CNAME}_${ARCH}.deb
sudo rm -rf dist/ deb_dist/
ls debian-packages/*deb
