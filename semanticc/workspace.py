import enum
import regex
from dataclasses import dataclass, field
from typing import Callable, IO
import itertools
from glob import glob
from os import path
from bisect import bisect_left

from .internal import *

###### TODO::
# 1. split preprocessor from everything else
# 2. load preprocessor
# 3. load everything else, expanding macros
# No need to remove preprocessor - it's ignored anyway

def get_file_priority(fname: str) -> int:
    return 3 if fname.endswith(".c") else \
           2 if fname.endswith("_inline.h") else \
           1 if fname else \
           0

rootPath = ""

def setRootPath(path: str):
    global rootPath
    rootPath = path

@dataclass
class Module:
    name: str
    dirname: str = ""
    fileAliases: list[str] = field(default_factory=list)
    sourceAliases: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.dirname:
            self.dirname = self.name

modules: dict[str, Module] = {}
moduleDirs: dict[str, str] = {}
moduleAliasesFile: dict[str, str] = {}
moduleAliasesSrc: dict[str, str] = {}
moduleSrcNames: set[str] = set()

def setModules(mods: list[Module]):
    global modules, moduleDirs, moduleAliasesFile, moduleAliasesSrc, moduleSrcNames
    for module in mods:
        name = module.name
        if name in modules:
            # TODO: make fatal error?
            raise ValueError(f"Module {name} already exists")
        modules[name] = module
        if module.dirname in moduleDirs:
            # TODO: make fatal error?
            raise ValueError(f"Module directory {module.dirname} conflicts with [{moduleDirs[module.dirname]}]")
        moduleDirs[module.dirname] = name
        for alias in module.fileAliases:
            if alias in moduleAliasesFile:
                # TODO: make fatal error?
                raise ValueError(f"Module file alias {alias} for [{name}] conflicts with [{moduleAliasesFile[alias]}]")
            moduleAliasesFile[alias] = name
        for alias in module.sourceAliases:
            if alias in moduleAliasesSrc:
                # TODO: make fatal error?
                raise ValueError(f"Module source alias {alias} for [{name}] conflicts with [{moduleAliasesSrc[alias]}]")
            moduleAliasesSrc[alias] = name
    moduleSrcNames = set(modules.keys()).union(set(moduleAliasesSrc.keys()))

# First go headers, then inlines, then sources
def get_files() -> list[str]:
    return sorted(glob(path.join(rootPath, "src/**/*.[ch]"), recursive=True),
                  key=lambda x: ("3" if x.endswith(".c") else
                                 "2" if x.endswith("_inline.h") else
                                 "1")+x)

# Get all headers, excluding inlines
def get_h_files() -> list[str]:
    return sorted((f for f in glob(path.join(rootPath, "src/**/*.h"), recursive=True) if not f.endswith("_inline.h")))

# Get all inline headers
def get_h_inline_files() -> list[str]:
    return sorted(glob(path.join(rootPath, "src/**/*_inline.h"), recursive=True))

# Get all .c sources
def get_c_files() -> list[str]:
    return sorted(glob(path.join(rootPath, "src/**/*.[c]"), recursive=True))

def _fname_to_module_raw(fname: str) -> str:
    prefix = path.join(rootPath, "src/")
    if not fname.startswith(prefix):
        return ""
    fname = fname[len(prefix):]
    if not fname.startswith("include/"):
        i = fname.find("/")
        if i >= 0:
            fname = fname[:i]
        return fname
    # A header in include/ directory
    fname = fname[8:]
    ret = path.splitext(path.basename(fname))[0]
    if ret.endswith("_inline"):
        ret = ret[:-7]
    elif ret.endswith("_private"):
        ret = ret[:-8]
    return ret if ret not in ["wt_internal", "extern"] else ""

def fname_to_module(fname: str) -> str:
    ret = _fname_to_module_raw(fname)
    if not ret:
        return ""
    if ret in moduleAliasesFile:
        ret = moduleAliasesFile[ret]
    if ret in modules:
        return ret
    return ""


@dataclass
class File:
    name: str
    module: str | None = None
    # txt: str = ""
    lineOffsets: list[int] | None = field(default=None, repr=False)

    def getModule(self) -> str:
        if self.module is None:
            self.module = fname_to_module(self.name)
        return self.module

    # Create a mapping from offset to line number
    def lineNumbers(self, txt: str) -> list[int]:
        if self.lineOffsets is None:
            self.lineOffsets = []
            for match in regex.finditer(r"\n", txt):
                self.lineOffsets.append(match.start())
        return self.lineOffsets

    def offsetToLinePos(self, offset: int) -> tuple[int, int]:
        if not self.lineOffsets:
            return (0, offset)
        line = bisect_left(self.lineOffsets, offset)
        return (line + 1,
                offset - self.lineOffsets[line-1] if line > 0 else offset)

    def offsetToLinePosStr(self, offset: int) -> str:
        line, pos = self.offsetToLinePos(offset)
        return f"{line}:{pos}"

    def locationStr(self, offset: int) -> str:
        return f"{self.name}:{self.offsetToLinePosStr(offset)}:"

@dataclass
class _Scope:
    file: File
    offset: int  # Offset in the file
    # txt: str | None = None

    def offsetToLinePos(self, offset: int) -> tuple[int, int]:
        return self.file.offsetToLinePos(self.offset + offset)
    def offsetToLinePosStr(self, offset: int) -> str:
        return self.file.offsetToLinePosStr(self.offset + offset)
    def locationStr(self, offset: int) -> str:
        return self.file.locationStr(self.offset + offset)

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

def locationStr(offset: int) -> str:
    return stack.stack[-1].locationStr(offset) if stack.stack else f"-:0:{offset}:"

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

class LogLevel(enum.IntEnum):
    QUIET   = 0
    FATAL   = 1
    ERROR   = DEFAULT = 2
    WARNING = 3
    INFO    = 4
    DEBUG   = DEBUG1 = 5
    DEBUG2  = 6
    DEBUG3  = 7
    DEBUG4  = 8
    DEBUG5  = 9

logLevel = LogLevel.DEFAULT
logStream: IO | None = None
errors: int = 0

def setLogLevel(level: LogLevel):
    global logLevel
    logLevel = level

def LOG(level: LogLevel, location: str | Callable[[], str] | int, *args, **kwargs) -> bool:
    if level <= LogLevel.ERROR:
        global errors
        errors += 1
    if level <= logLevel:
        if isinstance(location, int):
            location = locationStr(location)
        elif callable(location):
            location = location()
        for i in range(len(args)):
            if callable(args[i]):
                args[i] = args[i]()  # type: ignore # Unsupported target for indexed assignment ("tuple[Any, ...]")  [index]
        print(location, *args, **kwargs, file=logStream)
        return True
    return False

def FATAL(*args, **kwargs): LOG(LogLevel.FATAL, *args, **kwargs)
def ERROR(*args, **kwargs): LOG(LogLevel.ERROR, *args, **kwargs)
def WARNING(*args, **kwargs): LOG(LogLevel.WARNING, *args, **kwargs)
def INFO(*args, **kwargs): LOG(LogLevel.INFO, *args, **kwargs)
def DEBUG(*args, **kwargs): LOG(LogLevel.DEBUG, *args, **kwargs)
def DEBUG1(*args, **kwargs): LOG(LogLevel.DEBUG1, *args, **kwargs)
def DEBUG2(*args, **kwargs): LOG(LogLevel.DEBUG2, *args, **kwargs)
def DEBUG3(*args, **kwargs): LOG(LogLevel.DEBUG3, *args, **kwargs)
def DEBUG4(*args, **kwargs): LOG(LogLevel.DEBUG4, *args, **kwargs)
def DEBUG5(*args, **kwargs): LOG(LogLevel.DEBUG5, *args, **kwargs)
