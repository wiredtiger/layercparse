#!/bin/bash

set -ueo pipefail

[[ -f .venv/bin/activate ]] || virtualenv -q -p python3 .venv
chmod 755 .venv/bin/activate

. .venv/bin/activate
pip3 -q --disable-pip-version-check install -r requirements.txt

# set up development environment
pip3 --disable-pip-version-check install mypy types-regex

