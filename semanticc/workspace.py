from dataclasses import dataclass
from typing import Iterable
import itertools
from glob import glob
from os import path


# First go headers, then inlines, then sources
def get_files(root: str) -> list[str]:
    return sorted(glob(path.join(root, "src/**/*.[ch]"), recursive=True),
                  key=lambda x: ("3" if x.endswith(".c") else
                                 "2" if x.endswith("_inline.h") else
                                 "1")+x)


@dataclass
class File:
    name: str
    # text: str | None = None


@dataclass
class _Scope:
    file: File
    offset: int
    # text: str | None = None


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
