#!/bin/bash
mypy check_sources.py scan_sources.py scan_sources_all.py refactor.py test/*.py "$@"
