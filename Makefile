
all: isort black lint pytest pdoc help_gen gettext docindex

check: isort_check black_check lint pytest_check

format: isort black

pdoc: pyvenv
	rm -rf docs/pdoc
	pyvenv/bin/pdoc -o docs/pdoc viaconstructor/ dxfpreview/ gcodepreview/

help_gen: pyvenv
	mkdir -p docs/help
	pyvenv/bin/pdoc help_gen.py

docindex: pyvenv
	pyvenv/bin/markdown_py README.md | sed "s|https://raw.githubusercontent.com/multigcs/viaconstructor/main/docs/|./|g" > docs/readme.html

pyvenv-update: pyvenv
	pyvenv/bin/python -m pip install -r requirements-dev.txt
	pyvenv/bin/python -m pip install -r requirements.txt

pyvenv:
	python3 -m venv pyvenv
	pyvenv/bin/python -m pip install -r requirements-dev.txt
	pyvenv/bin/python -m pip install -r requirements.txt
	@echo "# for testing: pyvenv/bin/python -m viaconstructor tests/data/simple.dxf"
	@echo "# for testing: pyvenv/bin/python -m gcodepreview tests/data/simple.ngc"

pip-compile: pyvenv
	pyvenv/bin/pip-compile requirements-dev.in
	pyvenv/bin/pip-compile requirements.in

isort: pyvenv
	pyvenv/bin/python -m isort --profile black */*py viaconstructor/*/*.py

isort_check: pyvenv
	pyvenv/bin/python -m isort --check --profile black */*py viaconstructor/*/*.py

black: pyvenv
	pyvenv/bin/python -m black */*py viaconstructor/*/*.py

black_check: pyvenv
	pyvenv/bin/python -m black --check */*py viaconstructor/*/*.py

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
	rm -rf dist/
	rm -rf build/
	rm -rf viaconstructor.egg-info/

dist-clean: clean
	rm -rf pyvenv
	rm -rf docs/pdoc
	rm -rf docs/help

run: run-viaconstructor

run-viaconstructor: pyvenv
	pyvenv/bin/python -m viaconstructor tests/data/simple.dxf

run-gcodepreview: pyvenv
	pyvenv/bin/python -m gcodepreview tests/data/simple.ngc

install:
	python3 setup.py install

docker-build:
	docker build -t viaconstructor .

docker-run:
	docker rm viaconstructor || true
	#macOS: -e DISPLAY=docker.for.mac.host.internal:0
	#Windows: -e DISPLAY=host.docker.internal:0
	docker run --net=host -e DISPLAY=:0  --privileged --name viaconstructor -t -i viaconstructor

gettext:
	/usr/bin/pygettext3 -d base -o locales/base.pot viaconstructor/viaconstructor.py viaconstructor/setupdefaults.py
	@for lang in de ; do \
		echo "updating lang $$lang" ; \
		msgmerge --update locales/$$lang/LC_MESSAGES/base.po locales/base.pot ; \
		msgfmt -o locales/$$lang/LC_MESSAGES/base.mo locales/$$lang/LC_MESSAGES/base ; \
	done

dist:
	rm -rf dist/*
	python3 setup.py sdist
	twine upload -u meister23 --verbose dist/viaconstructor*
