from dataclasses import dataclass
from typing import Iterable
import itertools
from glob import glob
from os import path


def get_file_priority(fname: str) -> int:
    return 3 if fname.endswith(".c") else \
           2 if fname.endswith("_inline.h") else \
           1 if fname else \
           0

# First go headers, then inlines, then sources
def get_files(root: str) -> list[str]:
    return sorted(glob(path.join(root, "src/**/*.[ch]"), recursive=True),
                  key=lambda x: ("3" if x.endswith(".c") else
                                 "2" if x.endswith("_inline.h") else
                                 "1")+x)

# Get all headers, excluding inlines
def get_h_files(root: str) -> list[str]:
    return sorted((f for f in glob(path.join(root, "src/**/*.h"), recursive=True) if not f.endswith("_inline.h")))

# Get all inline headers
def get_h_inline_files(root: str) -> list[str]:
    return sorted(glob(path.join(root, "src/**/*_inline.h"), recursive=True))

# Get all .c sources
def get_c_files(root: str) -> list[str]:
    return sorted(glob(path.join(root, "src/**/*.[c]"), recursive=True))


def _fname_to_module_raw(fname: str) -> str:
    i = fname.rfind("/src/")
    if i >= 0:
        fname = fname[i+5:]
    if not fname.startswith("include/"):
        i = fname.find("/")
        if i >= 0:
            fname = fname[:i]
        return fname
    fname = fname[8:]
    ret = path.splitext(path.basename(fname))[0]
    if ret.endswith("_inline"):
        ret = ret[:-7]
    elif ret.endswith("_private"):
        ret = ret[:-8]
    return ret if ret not in ["wt_internal", "extern"] else ""

def fname_to_module(fname: str) -> str:
    ret = _fname_to_module_raw(fname)
    if ret.startswith("os_") or ret in ["gcc", "clang", "msvc"]:
        return "os"
    return ret


@dataclass
class File:
    name: str
    module: str | None = None
    # txt: str = ""

    def getModule(self) -> str:
        if self.module is None:
            self.module = fname_to_module(self.name)
        return self.module


@dataclass
class _Scope:
    file: File
    offset: int
    # txt: str | None = None


@dataclass
class _ScopeStack:
    stack: list[_Scope]

    def push(self, scope: _Scope):
        self.stack.append(scope)

    def pop(self) -> _Scope:
        return self.stack.pop()


stack = _ScopeStack([])

def scope_file() -> File:
    return stack.stack[-1].file if stack.stack else File("")

def scope_push(offset: int = 0, file: File | None = None) -> None:
    stack.push(_Scope(
        file if file is not None else scope_file(),
        offset if not stack.stack else stack.stack[-1].offset + offset))

def scope_pop() -> None:
    stack.pop()

def scope_filename() -> str:
    return stack.stack[-1].file.name if stack.stack else ""

def scope_offset() -> int:
    return stack.stack[-1].offset if stack.stack else 0

def scope_module() -> str:
    return stack.stack[-1].file.getModule() if stack.stack else ""

class ScopePush:
    def __init__(self, offset: int = 0, file: File | str | None = None, relative: bool = True):
        self.offset = offset if not relative else scope_offset() + offset
        self.file = scope_file() if file is None else \
            File(file) if isinstance(file, str) else \
            file

    def __enter__(self):
        scope_push(self.offset, self.file)

    def __exit__(self, exc_type, exc_value, traceback):
        scope_pop()
