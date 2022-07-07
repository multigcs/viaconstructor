
all: format lint test

pdoc:
	pdoc -o docs/pdoc viaconstructor/ dxfpreview/ gcodepreview/

pyvenv-update:
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

format: pyvenv
	pyvenv/bin/python -m black viaconstructor/*py tests/*py

lint: flake8 pylint mypy

flake8: pyvenv
	pyvenv/bin/python -m flake8 viaconstructor/*.py tests/*.py

mypy: pyvenv
	pyvenv/bin/python -m mypy viaconstructor/*.py # tests/*.py

pylint: pyvenv
	pyvenv/bin/python -m pylint viaconstructor/*.py # tests/*.py

test: pyvenv
	PYTHONPATH=. pyvenv/bin/python -m pytest --cov=. --cov-report html --cov-report term -vv tests/

clean:
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf htmlcov/
	rm -rf tests/__pycache__
	rm -rf viaconstructor/__pycache__/
	rm -rf viaconstructor/htmlcov/
	rm -rf gcodepreview/__pycache__/
	rm -rf gcodepreview/htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf viaconstructor.egg-info/

dist-clean: clean
	rm -rf pyvenv

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

