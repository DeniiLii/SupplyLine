PY ?= python

.PHONY: dev demo seed test build screens install

install:
	$(PY) tasks.py install

dev:
	$(PY) tasks.py dev

demo:
	$(PY) tasks.py demo

seed:
	$(PY) tasks.py seed

test:
	$(PY) tasks.py test

build:
	$(PY) tasks.py build

screens:
	$(PY) tasks.py screens
