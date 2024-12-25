#!/usr/bin/env python3

from setuptools import setup
import re

with open("README.md", "r") as f:
    long_description = f.read()

with open("requirements.txt") as f:
    requirements = f.read().split()

with open("layercparse/__init__.py") as f:
    version = re.search(r'LAYERCPARSE_VERSION\s*=\s*"([^"]+)"', f.read()).group(1)

setup(
    name="layercparse",
    version=version,
    author="Yury Ershov",
    license="GPL3",
    description="Layered C parser",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wiredtiger/layercparse",
    # scripts=["bin/..."],
    packages=["layercparse"],
    install_requires = requirements,
    zip_safe=False)
