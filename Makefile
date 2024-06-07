
VERSION ?= $(shell grep "version=" setup.py | cut -d"'" -f2)
DOCKERBASE ?= debian12


all: ruff isort black lint pytest help_gen gettext docindex done

done:
	@echo "-------------------------"
	@echo "ALL RIGHT !"
	@echo "-------------------------"

check: ruff isort_check black_check lint pytest_check

format: isort black

pdoc: pyvenv
	rm -rf docs/pdoc
	pyvenv/bin/pdoc -o docs/pdoc viaconstructor/

help_gen: pyvenv
	mkdir -p docs/help
	pyvenv/bin/python help_gen.py

docindex: pyvenv
	pyvenv/bin/markdown_py README.md | sed "s|https://raw.githubusercontent.com/multigcs/viaconstructor/main/docs/|./|g" > docs/readme.html

pyvenv-update: pyvenv pip-compile
	pyvenv/bin/python -m pip install -r requirements-dev.txt
	pyvenv/bin/python -m pip install -r requirements.txt

pyvenv:
	python3 -m venv pyvenv
	pyvenv/bin/python -m pip install -r requirements-dev.txt
	pyvenv/bin/python -m pip install -r requirements.txt
	@echo "# for testing: pyvenv/bin/python -m viaconstructor tests/data/simple.dxf"

pip-compile: pyvenv requirements-dev.txt requirements.txt

requirements-dev.txt: requirements-dev.in
	pyvenv/bin/pip-compile --generate-hashes --allow-unsafe requirements-dev.in

requirements.txt: requirements.in
	pyvenv/bin/pip-compile --generate-hashes --allow-unsafe requirements.in

isort: pyvenv
	pyvenv/bin/python -m isort --profile black */*py viaconstructor/*/*.py

ruff: pyvenv
	pyvenv/bin/python -m ruff check viaconstructor/*.py viaconstructor/*/*.py tests/*.py

isort_check: pyvenv
	pyvenv/bin/python -m isort --check --profile black */*py viaconstructor/*/*.py

black: pyvenv
	pyvenv/bin/python -m black -l 200 */*py viaconstructor/*/*.py

black_check: pyvenv
	pyvenv/bin/python -m black -l 200 --check */*py viaconstructor/*/*.py

lint: flake8 pylint mypy

flake8: pyvenv
	pyvenv/bin/python -m flake8 viaconstructor/*.py viaconstructor/*/*.py tests/*.py

mypy: pyvenv
	pyvenv/bin/python -m mypy viaconstructor/*.py

pylint: pyvenv
	pyvenv/bin/python -m pylint viaconstructor/*.py viaconstructor/*/*.py

pytest: pyvenv
	PYTHONPATH=. pyvenv/bin/python -m pytest --cov=viaconstructor --cov-report html:docs/pytest --cov-report term tests/

pytest_check: pyvenv
	PYTHONPATH=. pyvenv/bin/python -m pytest -vv tests/

clean:
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf */__pycache__/
	rm -rf */*/__pycache__
	rm -rf */*/*/__pycache__
	rm -rf dist/
	rm -rf deb_dist/
	rm -rf build/
	rm -rf viaconstructor.egg-info/
	rm -rf deb_dist/
	rm -rf AppDir/
	rm -rf viaconstructor-*.AppImage
	rm -rf viaconstructor-*.tar.gz

dist-clean: clean
	rm -rf pyvenv
	rm -rf docs/pdoc
	rm -rf docs/help

run: run-viaconstructor

run-viaconstructor: pyvenv
	pyvenv/bin/python -m viaconstructor tests/data/simple.dxf

install:
	python3 setup.py install

docker-build:
	docker build -t viaconstructor -f dockerfiles/Dockerfile.${DOCKERBASE} .

docker-run-dist-check: dist
	docker rm viaconstructor || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --privileged --name viaconstructor -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor /bin/bash -c "cd /usr/src/viaconstructor; pip3 install dist/viaconstructor-*.tar.gz; cd ~ ; ln -sf /usr/src/viaconstructor/tests ./ ; viaconstructor tests/data/check.dxf -s tests/data/gcode-2x2mm-d2.cfg -o /tmp/out.ngc ; diff /tmp/out.ngc tests/data/check.dxf-gcode-2x2mm-d2.cfg.check"
	@echo "--- DISTCHECK OK ---"

docker-run-dist: dist
	docker rm viaconstructor || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --privileged --name viaconstructor -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor /bin/bash -c "cd /usr/src/viaconstructor; pip3 install dist/viaconstructor-*.tar.gz; cd ~ ; viaconstructor /usr/src/viaconstructor/tests/data/simple.dxf"

docker-run-deb:
	docker rm viaconstructor || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --privileged --name viaconstructor -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor /bin/bash -c "cd /usr/src/viaconstructor; apt-get install -y ./deb_dist/python3-viaconstructor_*.deb; cd ~ ; viaconstructor /usr/src/viaconstructor/tests/data/simple.dxf"

docker-run-pip-install:
	docker rm viaconstructor || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --privileged --name viaconstructor -v $(CURDIR)/tests/data:/usr/src -t -i viaconstructor /bin/bash -c "cd /usr/src; pip3 install viaconstructor; viaconstructor simple.dxf"

docker-run-dev:
	docker rm viaconstructor || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --privileged --name viaconstructor -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor /bin/bash -c "cd /usr/src/viaconstructor; bin/viaconstructor tests/data/simple.dxf"

docker-run-shell:
	docker rm viaconstructor || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --privileged --name viaconstructor -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor /bin/bash

docker-build-debian: docker-build-debian11_deb docker-build-debian12_deb
	ls debian-packages/*deb

docker-build-debian12_deb:
	sudo rm -rf dist/ deb_dist/
	docker build -t viaconstructor_build_debian12 -f dockerfiles/Dockerfile.debian12 .
	docker rm viaconstructor_build_debian12 || true
	docker run --net=host --name viaconstructor_build_debian12 -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor_build_debian12 /bin/bash -c "cd /usr/src/viaconstructor; SETUPTOOLS_USE_DISTUTILS=stdlib python3 setup.py --command-packages=stdeb.command sdist_dsc && cd deb_dist/viaconstructor-*/ && sed -i 's|Depends: |Depends: python3-pyqt5.qtopengl, |g' debian/control && dpkg-buildpackage -rfakeroot -uc -us"
	mkdir -p debian-packages/
	cp deb_dist/*.deb debian-packages/python3-viaconstructor_${VERSION}-bookworm_amd64.deb
	sudo rm -rf dist/ deb_dist/
	ls debian-packages/*deb

docker-run-debian12_deb:
	docker build -t viaconstructor_debian12 -f dockerfiles/Dockerfile.debian12-min .
	docker rm viaconstructor_debian12 || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --name viaconstructor_debian12 -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor_debian12 /bin/bash -c "cd /usr/src/viaconstructor; apt-get install --no-install-recommends -y ./debian-packages/python3-viaconstructor_*-bookworm_amd64.deb; cd ~ ; viaconstructor /usr/src/viaconstructor/tests/data/simple.dxf"


docker-build-debian11_deb:
	sudo rm -rf dist/ deb_dist/
	docker build -t viaconstructor_build_debian11 -f dockerfiles/Dockerfile.debian11 .
	docker rm viaconstructor_build_debian11 || true
	docker run --net=host --name viaconstructor_build_debian11 -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor_build_debian11 /bin/bash -c "cd /usr/src/viaconstructor; SETUPTOOLS_USE_DISTUTILS=stdlib python3 setup.py --command-packages=stdeb.command sdist_dsc && cd deb_dist/viaconstructor-*/ && sed -i 's|Depends: |Depends: python3-pyqt5.qtopengl, |g' debian/control && dpkg-buildpackage -rfakeroot -uc -us"
	mkdir -p debian-packages/
	cp deb_dist/*.deb debian-packages/python3-viaconstructor_${VERSION}-bullseye_amd64.deb
	sudo rm -rf dist/ deb_dist/
	ls debian-packages/*deb

docker-run-debian11_deb:
	docker build -t viaconstructor_debian11 -f dockerfiles/Dockerfile.debian11-min .
	docker rm viaconstructor_debian11 || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --name viaconstructor_debian11 -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor_debian11 /bin/bash -c "cd /usr/src/viaconstructor; apt-get install --no-install-recommends -y ./debian-packages/python3-viaconstructor_*-bullseye_amd64.deb; cd ~ ; viaconstructor /usr/src/viaconstructor/tests/data/simple.dxf"




docker-build-ubuntu22.04_deb:
	sudo rm -rf dist/ deb_dist/ deb_dist_ubuntu22.04/
	docker build -t viaconstructor_build_ubuntu22.04 -f dockerfiles/Dockerfile.ubuntu22.04 .
	docker rm viaconstructor_build_ubuntu22.04 || true
	docker run --net=host --name viaconstructor_build_ubuntu22.04 -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor_build_ubuntu22.04 /bin/bash -c "cd /usr/src/viaconstructor; SETUPTOOLS_USE_DISTUTILS=stdlib python3 setup.py --command-packages=stdeb.command sdist_dsc && cd deb_dist/viaconstructor-*/ && sed -i 's|Depends: |Depends: python3-pyqt5.qtopengl, |g' debian/control && dpkg-buildpackage -rfakeroot -uc -us || /bin/bash"
	mkdir -p debian-packages/
	cp deb_dist/*.deb debian-packages/python3-viaconstructor_${VERSION}-jammy_amd64.deb
	sudo rm -rf dist/ deb_dist/ deb_dist_ubuntu22.04/
	ls debian-packages/*deb

docker-run-ubuntu22.04_deb:
	docker build -t viaconstructor_ubuntu22.04 -f dockerfiles/Dockerfile.ubuntu22.04-min .
	docker rm viaconstructor_ubuntu22.04 || true
	docker run --net=host -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$$DISPLAY -v $$HOME/.Xauthority:/root/.Xauthority --name viaconstructor_ubuntu22.04 -v $(CURDIR):/usr/src/viaconstructor -t -i viaconstructor_ubuntu22.04 /bin/bash -c "cd /usr/src/viaconstructor; apt-get install --no-install-recommends -y ./debian-packages/python3-viaconstructor_*-jammy_amd64.deb; cd ~ ; viaconstructor /usr/src/viaconstructor/tests/data/simple.dxf"



gettext:
	/usr/bin/pygettext3 --no-location -d base -o viaconstructor/locales/base.pot viaconstructor/viaconstructor.py viaconstructor/setupdefaults.py
	@for lang in de ; do \
		echo "updating lang $$lang" ; \
		msgmerge --update viaconstructor/locales/$$lang/LC_MESSAGES/base.po viaconstructor/locales/base.pot ; \
		msgfmt -o viaconstructor/locales/$$lang/LC_MESSAGES/base.mo viaconstructor/locales/$$lang/LC_MESSAGES/base ; \
	done

dist:
	python3 setup.py sdist

pypi: dist
	twine upload --verbose dist/viaconstructor*

bdist_deb:
	SETUPTOOLS_USE_DISTUTILS=stdlib python3 setup.py --command-packages=stdeb.command bdist_deb
	ls -l deb_dist/*.deb

bdist_rpm:
	python setup.py bdist_rpm

appimage: bdist_deb
	rm -rf viaconstructor-.*.AppImage
	sed -i "s| version: .*| version: ${VERSION}|g" AppImageBuilder.yml
	appimage-builder || true
	chmod +x viaconstructor-*.AppImage
