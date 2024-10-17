#!/usr/bin/env python3

from setuptools import setup
from layercparse import LAYERCPARSE_VERSION

with open("README.md", "r") as f:
    long_description = f.read()

with open("requirements.txt") as f:
    requirements = f.read().split()

setup(
    name="layercparse",
    version=LAYERCPARSE_VERSION,
    author="Yury Ershov",
    license="GPL3",
    description="Layered C parser",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ershov/layercparse",
    # scripts=["bin/..."],
    packages=["layercparse"],
    install_requires = requirements,
    zip_safe=False)
