#!/bin/bash
mypy check_sources.py scan_sources.py test/*.py "$@"
