import enum
from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable, Callable, NamedTuple, TypedDict
from dataclasses import dataclass
from copy import deepcopy
import regex
from glob import glob
from os import path

from .internal import *

# Calculate line number from position
def lineno(txt: str, pos: int | None = None) -> int:
    return txt.count("\n", 0, pos) + 1

# Calculate column number from position
def linepos(txt: str, pos: int | None = None) -> int:
    off = txt.rfind("\n", 0, pos)
    if pos is None:
        pos = len(txt)
    return pos - off + 1 if off >= 0 else pos + 1

# Remove comments and preprocessor directives, preserving newlines and text size
def clean_text_sz(txt: str):
    return reg_clean.sub(
        lambda match: reg_cr.sub(" ", match[0]) if match[0][0] in ["#", "/"] else match[0],
        txt)

# Remove comments and preprocessor directives
def clean_text(txt: str):
    return reg_clean.sub(lambda match: " " if match[0][0] in ["#", "/"] else match[0], txt)

parsing_file = "-"

def set_file(fname: str):
    global parsing_file
    parsing_file = fname

# First go headers, then inlines, then sources
def get_files(root: str) -> list[str]:
    return sorted(glob(path.join(root, "src/**/*.[ch]"), recursive=True),
                  key=lambda x: ("3" if x.endswith(".c") else
                                 "2" if x.endswith("_inline.h") else
                                 "1")+x)
