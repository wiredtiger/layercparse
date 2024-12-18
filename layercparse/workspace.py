import enum
import regex
from dataclasses import dataclass, field
from typing import Callable, IO
import itertools
from glob import glob
from os import path
from bisect import bisect_left
from io import StringIO

from .internal import *
from .common import *
from . import workspace

def load_wt_defs(rootPath) -> dict[str, list]:
    content = file_content(path.join(rootPath, 'dist', 'modularity', 'wt_defs.py'))
    wt_defs = regex.sub(r"(?m)^\s*(import|from\s+\S+\s+import).*?$", "", content)
    return eval(wt_defs)

FileKind: TypeAlias = Literal[
    "",   # undefined
    "c",  # .c file
    "i",  # _inline.h
    "h",  # .h but not inline
]

def get_file_kind(fname: str) -> FileKind:
    return "c" if fname.endswith(".c") else \
           "i" if fname.endswith("_inline.h") else \
           "h" if fname.endswith(".h") else \
           ""

def get_file_priority(fname: str) -> int:
    return 4 if fname.endswith(".c") else \
           3 if fname.endswith("_inline.h") else \
           2 if fname.endswith(".h") else \
           1 if fname else \
           0

rootPath = ""

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

def setModules(mods: Iterable[Module]):
    global modules, moduleDirs, moduleAliasesFile, moduleAliasesSrc, moduleSrcNames
    modules, moduleDirs, moduleAliasesFile, moduleAliasesSrc, moduleSrcNames = {}, {}, {}, {}, set()
    for module in mods:
        name = module.name
        if not name:
            # make fatal error?
            raise ValueError(f"Module doesn't have a name: {module}")
        if name in modules:
            # make fatal error?
            raise ValueError(f"Module {name} already exists")
        modules[name] = module
        if module.dirname in moduleDirs:
            # make fatal error?
            raise ValueError(f"Module directory {module.dirname} "
                             f"conflicts with [{moduleDirs[module.dirname]}]")
        moduleDirs[module.dirname] = name
        for alias in module.fileAliases:
            if alias in moduleAliasesFile:
                # make fatal error?
                raise ValueError(f"Module file alias {alias} for [{name}] "
                                 f"conflicts with [{moduleAliasesFile[alias]}]")
            moduleAliasesFile[alias] = name
        for alias in module.sourceAliases:
            if alias in moduleAliasesSrc:
                # make fatal error?
                raise ValueError(f"Module source alias {alias} for [{name}] "
                                 f"conflicts with [{moduleAliasesSrc[alias]}]")
            moduleAliasesSrc[alias] = name
    moduleSrcNames = set(modules.keys()).union(set(moduleAliasesSrc.keys()))

# Read module description from a file
# src/<name>/README.md
# <!-- MODULE: {
#   "name": "name",
#   "dirname": "dirname",
#   "fileAliases": ["alias1", "alias2"],
#   "sourceAliases": ["alias3", "alias4"]
# } -->
def read_module_desc(name: str = "", fname = "", **kwargs) -> Iterable[Module]:
    import json
    if not fname and name:
        if name:
            fname = f"src/{name}/README.md"
        else:
            return
    with open(fname) as file:
        txt = file.read()
    for match in regex.finditer(r"<!--\s*+MODULE:\s*+((?&TOKEN))\s*+-->"+re_token,
                                txt, flags=re_flags):
        try:
            desc = {"name": name, **kwargs, **json.loads(clean_text(match[1]))}
        except json.JSONDecodeError as e:
            FATAL(None, f"{fname}:{lineno(txt, match.start(1))}",
                  f"Error parsing module description: {e}\n", txt[match.start(1):match.end(1)])
            continue
        module = Module(**desc)
        DEBUG3(None, f"Add module: {module}")
        yield module

def read_modules(rootPath: str) -> Iterable[Module]:
    for fname in glob(path.join(rootPath, "src/*/README.md"), recursive=False):
        yield from read_module_desc(name=path.basename(path.dirname(fname)), fname=fname)

def setRootPath(p: str):
    global rootPath
    rootPath = path.realpath(p)
    setModules(read_modules(rootPath))

# First go headers, then inlines, then sources
def get_files() -> list[str]:
    return sorted(glob(path.join(rootPath, "src/**/*.[ch]"), recursive=True),
                  key=lambda x: ("3" if x.endswith(".c") else
                                 "2" if x.endswith("_inline.h") else
                                 "1")+x)

# Get all headers, excluding inlines
def get_h_files() -> list[str]:
    return sorted((f
                   for f in glob(path.join(rootPath, "src/**/*.h"), recursive=True)
                   if not f.endswith("_inline.h")))

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
    module: str = ""
    is_private: bool | None = field(default=None, repr=False)
    # txt: str = ""
    lineOffsets: list[int] | None = field(default=None, repr=False)
    expandList: list[Expansions] = field(default_factory=list, repr=False)
    fileKind: FileKind = field(default="", repr=False)
    relpath: str = field(default="", repr=False)
    # Mapping from expanded offset to original offset
    _offsetMapIdx: list[int] = field(default_factory=list, repr=False)
    _offsetMapOffset: list[int] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.relpath:
            # self.relpath = path.relpath(self.name, workspace.rootPath) if workspace.rootPath and self.name else self.name
            self.relpath = self.name
        if not self.module:
            self.module = fname_to_module(self.name)
        if "_private" in self.name:
            self.is_private = True
        if not self.fileKind:
            self.fileKind = get_file_kind(self.name)

    # Create a mapping from offset to line number
    def fillLineInfo(self, txt: str) -> list[int]:
        if self.lineOffsets is None:
            self.lineOffsets = []
            for match in regex.finditer(r"\n", txt):
                self.lineOffsets.append(match.start())
        return self.lineOffsets

    def updateLineInfoWithInsertList(self, insertList: InsertList) -> None:
        self._offsetMapIdx = [0]
        self._offsetMapOffset = [0]
        if not insertList:
            return

        cur_delta = 0
        for ins in insertList:
            offset, delta = ins.range_new[0], ins.delta
            cur_delta += delta
            self._offsetMapIdx.append(offset)
            self._offsetMapOffset.append(cur_delta)

    def offsetToLinePos(self, offset: int) -> tuple[int, int]:
        offset = self.getOrigOffset(offset)
        if not self.lineOffsets:
            return (0, offset)
        line = bisect_left(self.lineOffsets, offset)
        return (line + 1,
                offset - self.lineOffsets[line-1] if line > 0 else offset)

    def offsetToLinePosStr(self, offset: int) -> str:
        line, pos = self.offsetToLinePos(offset)
        return f"{line}:{pos}"

    def locationStr(self, offset: int) -> str:
        return f"{self.relpath}:{self.offsetToLinePosStr(offset)}:"

    def read(self) -> str:
        txt = file_content(self.name)
        self.fillLineInfo(txt)
        return txt

    def expansions(self, range: Range) -> Iterable[Expansions]:
        if not self.expandList:
            return
        idx = bisect_left(self.expandList, range[0], key=lambda x: x.at.range_new[0])
        while idx < len(self.expandList) and self.expandList[idx].at.range_new[0] < range[1]:
            yield self.expandList[idx]
            idx += 1

    # Get original file offset before macro expansion
    def getOrigOffset(self, offset: int) -> int:
        if not self._offsetMapIdx:
            return offset
        idx = bisect_left(self._offsetMapIdx, offset)
        return offset - self._offsetMapOffset[idx - 1]

@dataclass
class Scope:
    file: File
    offset: int  # offset in file
    # txt: str | None = None

    def offsetToLinePos(self, offset: int) -> tuple[int, int]:
        return self.file.offsetToLinePos(self.offset + offset)
    def offsetToLinePosStr(self, offset: int) -> str:
        return self.file.offsetToLinePosStr(self.offset + offset)
    def locationStr(self, offset: int) -> str:
        return self.file.locationStr(self.offset + offset)

    @staticmethod
    def create(file: File | None, offset: int) -> 'Scope':
        if file is not None:
            return Scope(file, offset=offset)
        else:
            f = scope_file()
            if not scope_stack.stack:
                return Scope(f, offset=offset)
            return Scope(f, scope_stack.stack[-1].offset + offset)

    @staticmethod
    def empty() -> 'Scope':
        return Scope(File(""), 0)

@dataclass
class _ScopeStack:
    stack: list[Scope]

    def push(self, scope: Scope):
        self.stack.append(scope)

    def pop(self) -> Scope:
        return self.stack.pop()


scope_stack = _ScopeStack([])

def scope() -> Scope:
    return scope_stack.stack[-1] if scope_stack.stack else Scope.empty()

def scope_file() -> File:
    return scope_stack.stack[-1].file if scope_stack.stack else File("")

def scope_push_s(sc: Scope) -> None:
    scope_stack.push(sc)

def scope_push(file: File | None, offset: int) -> None:
    scope_stack.push(Scope.create(file, offset))

def scope_pop() -> None:
    scope_stack.pop()

def scope_filename() -> str:
    return scope_stack.stack[-1].file.name if scope_stack.stack else ""

def scope_offset() -> int:
    return scope_stack.stack[-1].offset if scope_stack.stack else 0

def scope_module() -> str:
    return scope_stack.stack[-1].file.module if scope_stack.stack else ""

def locationStr(offset: int) -> str:
    return scope_stack.stack[-1].locationStr(offset) if scope_stack.stack else f"-:0:{offset}:"

class ScopePush:
    def __init__(self, file: File | str | None = None, offset: int = 0):
        self.file, self.offset = ((File(file) if isinstance(file, str) else file), offset)

    def __enter__(self):
        scope_push(self.file, self.offset)

    def __exit__(self, exc_type, exc_value, traceback):
        scope_pop()

import enum
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

from dataclasses import dataclass, field
from typing import Any
@dataclass
class LogCategory:
    name: str
    level: LogLevel
    enabled: bool

    def __call__(self, *args, **kwargs) -> bool:
        return LOG(self, *args, **kwargs)

class Log: # Log Categories
    none                 = LogCategory("none",                 LogLevel.QUIET,   True)
    misc                 = LogCategory("misc",                 LogLevel.QUIET,   True)
    macro_expand         = LogCategory("macro_expand",         LogLevel.DEBUG3,  True)
    module_name_mismatch = LogCategory("module_name_mismatch", LogLevel.ERROR,   True)
    module_foreign_def   = LogCategory("module_foreign_def",   LogLevel.ERROR,   True)
    access_macro         = LogCategory("access_macro",         LogLevel.ERROR,   True)
    access_global        = LogCategory("access_global",        LogLevel.ERROR,   True)
    access_member        = LogCategory("access_member",        LogLevel.ERROR,   True)
    defn_conflict        = LogCategory("defn_conflict",        LogLevel.WARNING, True)
    defn_conflict_macro  = LogCategory("defn_conflict_macro",  LogLevel.WARNING, True)
    parse_typedef        = LogCategory("parse_typedef",        LogLevel.WARNING, True)
    parse_localvar       = LogCategory("parse_localvar",       LogLevel.WARNING, True)
    parse_expression     = LogCategory("parse_expression",     LogLevel.WARNING, True)
    type_deduce_member   = LogCategory("type_deduce_member",   LogLevel.WARNING, True)
    type_deduce_expr     = LogCategory("type_deduce_expr",     LogLevel.WARNING, True)
    ignored_global       = LogCategory("ignored_global",       LogLevel.INFO,    True)

logLevel = LogLevel.DEFAULT
logStream: IO | None = None
errors: int = 0

class LogToStringScope:
    def __init__(self):
        self.oldStream = logStream

    def __enter__(self):
        global logStream
        logStream = StringIO()

    def __exit__(self, exc_type, exc_value, traceback):
        global logStream
        logStream = self.oldStream

def setLogLevel(level: LogLevel):
    global logLevel
    logLevel = level

def LOG(what: LogLevel | LogCategory,
        location: str | Callable[[], str] | int | None,
        *args, **kwargs) -> bool:
    level, enabled, catname = ((what.level, what.enabled, (f"{{{what.name}}}", ))
                               if isinstance(what, LogCategory) else
                               (what, True, ()))
    if level <= LogLevel.ERROR:
        global errors
        errors += 1
    if level > logLevel or not enabled:
        return False
    if isinstance(location, int):
        location = locationStr(location)
    elif callable(location):
        location = location()
    elif location is None:
        location = "    "
    for i in range(len(args)):
        if callable(args[i]):
            args = [arg() if callable(arg) else arg for arg in args] # type: ignore[assignment] # incompatible type
            break
    print(location, f"{level.name.lower()}:", *args, *catname, **kwargs, file=logStream)
    return True

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
