#!/bin/bash
mypy check_sources.py scan_sources.py scan_sources_all.py test/*.py "$@"
