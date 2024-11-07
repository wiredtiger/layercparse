#!/usr/bin/env python3

""" Source scan script.

This script scans WiredTiger.

"""

import sys, os, enum
import pickle, hashlib
import argparse
from glob import glob
from dataclasses import dataclass, field, is_dataclass, fields

import regex
from layercparse import *
from layercparse import cache

_globals: Codebase
_args: argparse.Namespace

_color: bool = False

class Color(enum.Enum):
    NORM = ""
    BRIGHT = "1"
    DIM = "2"
    UNDERSCORE = "4"
    INV = "7"
    RED = "31"
    GREEN = "32"
    YELLOW = "33"
    BLUE = "34"
    MAGENTA = "35"
    CYAN = "36"
    BG_GREY = "40"
    BG_RED = "41"
    BG_GREEN = "42"
    BG_YELLOW = "43"
    BG_BLUE = "44"
    _BG_MAGENTA = "45"
    _BG_CYAN = "46"

    def __call__(self, reset: bool = True, mod: 'Color | None' = None) -> str:
        if not _color:
            return ""
        reset_str = "0;" if reset else ""
        mod_str = f"{mod.value};" if mod is not None else ""
        return f"\x1b[{reset_str}{mod_str}{self.value}m" if _color else ""

@dataclass
class AccessDst:
    mod:  dict[str, int] | None = None                                         # module
    file: dict[tuple[str, str], int] | None = None                             # module, file
    defn: dict[tuple[str, str, tuple[int, int], str, str], int] | None = None  # module, file, linecol, name, kind
    full: dict[tuple[str, str, tuple[int, int], str, str, str, tuple[int, int] | None], int] | None = None  # module, file, linecol, name, kind, snippet, range

@dataclass
class AccessSrc:
    mod:  dict[str, AccessDst] | None = None                                         # module
    file: dict[tuple[str, str], AccessDst] | None = None                             # module, file
    defn: dict[tuple[str, str, tuple[int, int], str, str], AccessDst] | None = None  # module, file, linecol, name, kind
    full: dict[tuple[str, str, tuple[int, int], str, str, str, tuple[int, int] | None], AccessDst] | None = None  # module, file, linecol, name, kind, snippet, range

def access_mod_to_str(mod: str):
    return (f"[{mod}]", )

def access_file_to_str(file: tuple[str, str]):
    return (f"[{file[0]}]", f"{file[1]}")

def access_defn_to_str(full: tuple[str, str, tuple[int, int], str, str]):
    return (f"[{full[0]}]", f"{full[1]}:{full[2][0]}:{full[2][1]}:", f"{full[4]}", f"{full[3]}")

# Returns the entire line at the given offset
def lines_at_range(txt: str, range_: tuple[int, int] | None) -> tuple[str, tuple[int, int] | None]:
    if range_ is None or range_[0] >= len(txt):
        return ("", None)
    begin = txt.rfind("\n", 0, range_[0]) + 1
    end = txt.find("\n", range_[1])
    if end == -1:
        end = len(txt)
    return (txt[begin:end], (range_[0] - begin, range_[1] - begin), )

def access_full_to_str(full: tuple[str, str, tuple[int, int], str, str, str, tuple[int, int] | None]):
    ret1 = (f"[{full[0]}]", f"{full[1]}:{full[2][0]}:{full[2][1]}:", f"{full[4]}", f"{full[3]}",)
    txt = full[5]
    if not txt:
        return ret1 + ("",)
    range_ = full[6]
    if not _color:
        return ret1 + (f"\n{txt}",)
    if not range_:
        return ret1 + (Color.DIM() + f"\n{txt}" + Color.NORM(),)
    highlighted_txt = (
        Color.DIM() +
        txt[:range_[0]] +
        Color.YELLOW() +
        txt[range_[0]:range_[1]] +
        Color.DIM() +
        txt[range_[1]:] +
        Color.NORM())
    return ret1 + (f"\n{highlighted_txt}",)

# Format output by columns
def format_columns(rows: list[tuple]) -> list[str]:
    str_rows = [[str(cell) for cell in row] for row in rows]
    format_str = " ".join(["{:<" + str(max(len(cell) for cell in col)) + "}" for col in zip(*str_rows)])
    return ["  " + format_str.format(*row).strip() for row in str_rows]

def print_columns(rows: list[tuple]):
    print(*format_columns(rows), sep="\n")

detailsFunc = {"mod": access_mod_to_str, "file": access_file_to_str,
               "defn": access_defn_to_str, "full": access_full_to_str}

def is_addable_type(type) -> bool:
    return type in (int, float, str, list)

def update(val, other):
    assert type(val) is type(other)
    if isinstance(val, dict):
        for k, v in other.items():
            if k in val:
                assert type(val[k]) is type(v)
                if is_addable_type(type(v)):
                    val[k] += v
                elif not isinstance(v, Definition):
                    update(val[k], v)
            else:
                val[k] = v
    elif is_dataclass(val):
        for f in fields(val):
            if is_addable_type(f.type):
                setattr(val, f.name, getattr(val, f.name) + getattr(other, f.name))
            elif not isinstance(v, Definition):
                update(getattr(val, f.name), getattr(other, f.name))
    else:
        raise ValueError(f"Unsupported type {type(val)}")

def update_stats(stats, from_what: str, access_from, to_what, access_to, val):
    if not (obj := getattr(stats, from_what)):
        setattr(stats, from_what, obj := {})
    if access_from not in obj:
        obj[access_from] = AccessDst()
    obj = obj[access_from]
    if not (obj2 := getattr(obj, to_what)):
        setattr(obj, to_what, obj2 := {})
    if access_to not in obj2:
        obj2[access_to] = val
    else:
        if is_addable_type(type(val)):
            obj2[access_to] += val
        # else:
        #     update(obj2[access_to], val)


@dataclass
class LocationId:
    mod: str
    file: str
    lineColDefn: tuple[int, int]
    lineColUse: tuple[int, int]
    kind: str
    name: str
    snippet: str = ""
    range: tuple[int, int] | None = None
    parentname: str | None = None

    def getName(self):
        return self.name if not self.parentname else f"{self.parentname}.{self.name}"

    @staticmethod
    def fromDefn(defn: Definition, useOffset: int | None = None, snippet = "", range: tuple[int, int] | None = None):
        lineColDefn = defn.scope.offsetToLinePos(defn.offset)
        lineColUse = defn.scope.offsetToLinePos(useOffset) if useOffset is not None else lineColDefn
        return LocationId(mod=defn.module,
                          file=defn.scope.file.name,
                          lineColDefn=lineColDefn,
                          lineColUse=lineColUse,
                          name=defn.name,
                          kind=defn.kind,
                          snippet=snippet,
                          range=range)
    @staticmethod
    def fromField(defntype: Definition, defnfield: Definition):
        lineColDefn = defnfield.scope.offsetToLinePos(defnfield.offset)
        return LocationId(mod=defntype.module,
                          file=defntype.scope.file.name,
                          lineColDefn=lineColDefn,
                          lineColUse=lineColDefn,
                          name=defnfield.name,
                          parentname=defntype.name,
                          kind="field")

class AccessType(enum.IntEnum):
    MACRO = 0
    CALL = 1
    CHAIN = 2
    FIELD = 3

@dataclass
class Access:
    type: AccessType
    src: LocationId
    dst: LocationId

def on_macro_expand(arg: AccessMacroExpand) -> list[Access] | None:
    ret: list[Access] = []
    for src, exps in arg.exps.expansions.items():
        defnSrc = _globals.macros[src] if src else arg.src
        locSrc = LocationId.fromDefn(defnSrc, arg.exps.range[0])
        for dst in exps:
            ret.append(Access(AccessType.MACRO,
                              locSrc,
                              LocationId.fromDefn(_globals.macros[dst])))
    return ret

def on_global_name(arg: AccessGlobalName) -> list[Access] | None:
    return [Access(AccessType.CALL,
                   LocationId.fromDefn(arg.src, arg.src.offset + arg.range[0],
                                       *lines_at_range(arg.src.details.body.value, arg.range)),
                   LocationId.fromDefn(_globals.names[arg.dst]))]

# def on_field_chain(arg: AccessFieldChain) -> list[Access]:
#     return f"{locationStr(arg.src)} Field chain {arg.chain}\n"

def on_field_access(arg: AccessField) -> list[Access] | None:
    if arg.typename not in _globals.fields or arg.field not in _globals.fields[arg.typename]:
        return None
    return [Access(AccessType.FIELD,
                   LocationId.fromDefn(arg.src, arg.src.offset + arg.range[0],
                                       *lines_at_range(arg.src.details.body.value, arg.range)),
                   LocationId.fromField(_globals.types[arg.typename], _globals.fields[arg.typename][arg.field]))]

def match_str_or_regex(filter: str, value: str) -> bool:
    if not filter:
        return True
    if filter[0] == "/" and filter[-1] == "/":
        return bool(regex.search(filter[1:-1], value))
    return value == filter

def match_str_or_regex_type(filter: str, value: str) -> bool:
    if not filter:
        return True
    if filter[0] == "/" and filter[-1] == "/":
        return bool(regex.search(filter[1:-1], value))
    return value == _globals.untypedef(filter)

# Fuction to check whether a to/from filter matches a definition. Variants are:
#  "module"         - module name if it's in module list
#  "[module]"       - module name
#  "[/module/]"     - module regex
#  "filename"       - file name or its tail
#  "(type)"         - type name
#  "(/type/)"       - type name regex
#  "(type).field"   - type's field name
#  "(type)./field/" - type's field name regex
#  "name"           - any entity name (if it doesn't match a module name)
#  "*name"          - any entity name
#  "/regex/"        - entity name regex

def _unparentype(filter: str) -> str:
    if ":" not in filter:
        while filter and filter[0] == "(" and filter[-1] == ")":
            filter = filter[1:-1]
    else:
        while len(filter) > 1 and filter[0] == "(" and filter[1] == "(" and filter[-1] == ")":
            filter = filter[1:-1]
    return filter

def _split_type_field(filter: str) -> tuple[str, str]:
    if filter[-1] == ")":
        return _unparentype(filter), ""
    # Find the last dot
    if (i := filter.rfind(".")) == -1:
        return _unparentype(filter), ""
    return _unparentype(filter[:i]), filter[i+1:]

def filter_matches_location(filter: str, loc: LocationId) -> bool:
    if not filter:
        return True
    if filter[0] == "[" and filter[-1] == "]":
        return loc.mod == filter[1:-1]
    if filter in workspace.modules:
        return filter == loc.mod
    if filter in workspace.moduleAliasesSrc:
        return workspace.moduleAliasesSrc[filter] == loc.mod
    if filter[0] == "(" and loc.kind == "field":
        if filter[-1] == ")":
            return bool(loc.parentname and match_str_or_regex_type(filter[1:-1], loc.parentname))
        type, field = _split_type_field(filter)
        return bool(loc.parentname and match_str_or_regex(field, loc.name) and match_str_or_regex_type(type, loc.parentname))
    if filter[0] == "*":
        return match_str_or_regex(filter[1:], loc.name)
    if "/" in filter or "." in filter: # file name
        return bool(loc.file and loc.file.endswith(filter))
    # may be a file name or a function name
    if loc.file and loc.file.endswith(filter):
        return True
    return match_str_or_regex(filter, loc.name)

def filter_access(access: Access) -> bool:
    if ((not _args.unmod and (not access.src.mod or not access.dst.mod)) or
        (not _args.macros and access.type == AccessType.MACRO) or
        (not _args.calls and access.type == AccessType.CALL) or
        (not _args.fields and access.type == AccessType.FIELD)):
        return False
    if _args.from_:
        for filter in _args.from_:
            if filter_matches_location(filter, access.src):
                break
        else: # not break
            return False
    if _args.to:
        for filter in _args.to:
            if filter_matches_location(filter, access.dst):
                break
        else: # not break
            return False
    if (not _args.self and
            # access.src.mod and access.dst.mod and
            access.src.mod == access.dst.mod):
        return False
    return True

def filter_access_list(access_list: Iterable[Access]) -> Iterable[Access]:
    return filter(filter_access, access_list)

_in_record = ""

def filter_matches_definition(filter: str, defn: Definition) -> bool:
    global _in_record
    if defn.kind == "record":
        _in_record = defn.name
    elif defn.kind != "field":
        _in_record = ""

    if not filter:
        return True
    if filter[0] == "[" and filter[-1] == "]":
        return match_str_or_regex(filter[1:-1], defn.module)
    if filter in workspace.modules:
        return filter == defn.module
    if filter in workspace.moduleAliasesSrc:
        return workspace.moduleAliasesSrc[filter] == defn.module
    if filter[0] == "(":
        if filter[-1] == ")":
            return defn.kind == "record" and match_str_or_regex_type(filter[1:-1], defn.name)
        if defn.kind != "field" or not _in_record:
            return False
        type, field = _split_type_field(filter)
        return match_str_or_regex(field, defn.name) and match_str_or_regex_type(type, _in_record)
    if filter[0] == "*":
        return match_str_or_regex(filter[1:], defn.name)
    if defn.scope.file.name.endswith(filter):
        return True
    return match_str_or_regex(filter, defn.name)

def want_scan(defn: Definition) -> bool:
    if not _args.unmod and not defn.module:
        return False
    if not _args.from_:
        return True
    for filter in _args.from_:
        if filter_matches_definition(filter, defn):
            return True
    return False

def want_list(defn: Definition) -> bool:
    if not defn.module:
        if not _args.list and _args.unmod:
            return True
        return False
    if _args.list:
        if not _args.unmod and not defn.module:
            return False
        for filter in _args.list:
            if filter_matches_definition(filter, defn):
                return True
        return False
    return True

def EnumFromStr(type, val: str) -> type:
    try:
        return type[val]
    except KeyError:
        print(f"Invalid value: '{val}'. Should be one of: {', '.join(e.name for e in type)}")
        sys.exit(1)

def script_files_list() -> list[str]:
    p = os.path
    return glob(p.realpath(p.join(p.dirname(p.realpath(__file__)), "..", "**/*.py")), recursive=True)

class MyFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, *args, **kwargs):
        super().__init__(max_help_position=26, *args, **kwargs)

def commandline() -> argparse.Namespace:
    argparser = argparse.ArgumentParser(formatter_class=MyFormatter,
        description=f"Source scanner version {LAYERCPARSE_VERSION}.",
        epilog=f"""
To/from filters notation for "TO", "FROM" and "LIST" options:
  module                  module name if it's in the list
  [module]                module name
  [/module/]              module regex
  filename                file name or its tail
  (type)                  type name
  (/type/)                type name regex
  (type).field            type's field name
  (type)./field/          type's field name regex
  (/type/)./field/        type and field regex
  name                    any entity name (if it doesn't match a module name)
  *name                   any entity name
  /regex/                 entity name regex
""")
    argparser.add_argument('--version',
                           action='version', version=f"%(prog)s {LAYERCPARSE_VERSION}")
    argparser.add_argument("home",
                           help="Home directory of the source tree")
    argparser.add_argument("-v", # choices=[e.name for e in LogLevel],
                           dest="logLevel",
                           default=LogLevel.QUIET,
                           type=lambda x: EnumFromStr(LogLevel, x),
                           help="Set verbosity level: " + ", ".join(e.name for e in LogLevel))

    group = argparser.add_argument_group(title="List modules mode")
    group.add_argument("-m", "--modules", dest="list_modules", action="store_true",
                       help="List modules")

    group = argparser.add_argument_group(title="Module content mode")
    group.add_argument("-l", "--list", action="extend", nargs="*",
                       help="List what belongs to a module or file")

    group = argparser.add_argument_group(title="Access report mode (default)")
    group.add_argument("-f", "--from", dest="from_", metavar="FROM", action="extend", nargs=1,
                       help="Find access from module, file, function, type or field")
    group.add_argument("-t", "--to", action="extend", nargs=1,
                       help="Find access to module, file, function, type or field")
    # group.add_argument("-x", "--exclude", action="extend", nargs="*")
    group.add_argument("-r", "--reverse", action=argparse.BooleanOptionalAction,
                       help="Reverse access report: what accesses the target")

    group = argparser.add_argument_group(title="What to report (all modes)")
    group.add_argument(      "--unmod", action=argparse.BooleanOptionalAction,
                       default=False,
                       help="Include unmodular things (default: no)")
    group.add_argument(      "--self", action=argparse.BooleanOptionalAction,
                       default=False,
                       help="Include internal uses within the module (default: no)")
    group.add_argument(      "--calls", action=argparse.BooleanOptionalAction,
                       default=True,
                       help="Include function calls (default: yes)")
    group.add_argument(      "--fields", action=argparse.BooleanOptionalAction,
                       default=True,
                       help="Include struct/union fields (default: yes)")
    group.add_argument(      "--macros", action=argparse.BooleanOptionalAction,
                       default=True,
                       help="Include macros (default: yes)")
    group.add_argument(      "--calls-only", action="store_true",
                       help="Include function calls only")
    group.add_argument(      "--fields-only", action="store_true",
                       help="Include struct/union fields only")
    group.add_argument(      "--macros-only", action="store_true",
                       help="Include macros only")
    group.add_argument(      "--debug", action=argparse.BooleanOptionalAction,
                       help=argparse.SUPPRESS) # help="Debug output")

    group = argparser.add_argument_group(title="Level of detail selection (access report mode)",
        description="""
mod:  module
file: module, file
defn: module, file, definition's line, name, kind
full: module, file, exact location's line, name, kind, code snippet (experimental)
        """.strip())
    group.add_argument("-d", "--detail", choices=["mod", "file", "defn", "full"],
                       help="Specify the level of detail for access report")
    group.add_argument("--detail-from", "--df", choices=["mod", "file", "defn", "full"],
                       default="mod",
                       help="Specify the level of detail for access report for outgoing access")
    group.add_argument("--detail-to", "--dt", choices=["mod", "file", "defn", "full"],
                       default="mod",
                       help="Specify the level of detail for access report for incoming access")

    group = argparser.add_argument_group(title="Output mode")
    group.add_argument(      "--color", action=argparse.BooleanOptionalAction,
                       default=False,
                       help="Enable ANSI color output (default: no)")

    group = argparser.add_argument_group(title="Cache control")
    group.add_argument(      "--cache", action=argparse.BooleanOptionalAction,
                       default=True,
                       help="Use cache for operations (default: yes)")
    group.add_argument(      "--clear-cache", action="store_true",
                       help="Clear cache before doing anything")

    global _args
    _args = argparser.parse_args()

    return _args

def list_modules(modules: list[Module]) -> None:
    print("Modules:")
    output = []
    for mod in sorted(modules, key=lambda m: m.name):
        desc = []
        if mod.dirname != mod.name:
            desc.append(f"dirname: {mod.dirname}")
        if mod.sourceAliases:
            desc.append(f"sourceAliases: {mod.sourceAliases}")
        if mod.fileAliases:
            desc.append(f"fileAliases: {mod.fileAliases}")
        output.append((f"{mod.name}:", ",   ".join(desc)))
    print_columns(output)

def list_contents() -> None:
    if _args.macros:
        print("  == Macros:")
        for _, defn in _globals.macros.items():
            if not defn.offset or not want_list(defn):
                continue
            print(f"{defn.locationStr()} {'private' if defn.is_private else 'public'}")
    if _args.calls:
        print("  == Functions:")
        for _, defn in _globals.names.items():
            if not want_list(defn):
                continue
            print(f"{defn.locationStr()} {'private' if defn.is_private else 'public'}")
    if _args.fields:
        print("  == Fields:")
        for recname, recdefn in _globals.fields.items():
            defn = _globals.types[recname]
            r: str | None = f"{defn.locationStr()} {'private' if defn.is_private else 'public'}:"
            if want_list(defn):
                print(r)
                r = None
            for fieldname, defn in recdefn.items():
                if not want_list(defn):
                    continue
                if r:
                    print(r)
                    r = None
                # print(f"{defn.locationStr()} ..... {'private' if defn.is_private else 'public'} {fieldname}")
                print(f"    {fieldname} [{defn.module}] {'private' if defn.is_private else 'public'}")

_script_files = script_files_list()
_version_hash = hashlib.sha1(pickle.dumps((_script_files, LAYERCPARSE_VERSION))).digest()

def _hashstr(obj: Any, sz: int = 8) -> str:
    return hashlib.sha1(pickle.dumps((obj, _version_hash))).hexdigest()[:sz]

@cache.cached(file=lambda files, *args, **kwargs: f"globals.{LAYERCPARSE_VERSION}." + _hashstr(files),
              deps=lambda files, *args, **kwargs: files + _script_files)
def load_globals(files: list[str], extraMacros: list[dict]) -> Codebase:
    ret = Codebase()
    for macro in extraMacros:
        ret.addMacro(**macro)
    ret.scanFiles(files)
    return ret

@cache.cached(file=lambda files, *args, **kwargs: f"access.{LAYERCPARSE_VERSION}." + _hashstr(files),
              deps=lambda files: files + _script_files)
def load_access(files: list[str]) -> list[Access]:
    ret = []
    for res in AccessCheck(_globals).xscan(
                # want_scan=want_scan if _args.from_ is not None or not _args.unmod else None,
                on_macro_expand=on_macro_expand if _args.macros else None,
                on_global_name=on_global_name if _args.calls else None,
                # on_field_chain=on_field_chain,
                on_field_access=on_field_access if _args.fields else None):
        if _args.debug:
            print(*res, sep="\n")
        for access in res:
            ret.append(access)
    return ret

@cache.cached(file=lambda files, *args, **kwargs: f"stats.{LAYERCPARSE_VERSION}." + _hashstr(files),
              deps=lambda files: files + _script_files,
              suffix=lambda _: "." + _hashstr(_args, 16))
def load_stats(files: list[str]) -> tuple[AccessSrc, AccessSrc]:
    access_stats = AccessSrc()
    access_stats_r = AccessSrc()

    for access in filter_access_list(load_access(files)):
        stats_from = [("mod", access.src.mod),
                        ("file", (access.src.mod, access.src.file)),
                        ("defn", (access.src.mod, access.src.file, access.src.lineColDefn, access.src.getName(), access.src.kind)),
                        ("full", (access.src.mod, access.src.file, access.src.lineColUse, access.src.getName(), access.src.kind, access.src.snippet, access.src.range))]
        stats_to = [("mod", access.dst.mod),
                    ("file", (access.dst.mod, access.dst.file)),
                    ("defn", (access.dst.mod, access.dst.file, access.dst.lineColDefn, access.dst.getName(), access.dst.kind)),
                    ("full", (access.dst.mod, access.dst.file, access.dst.lineColUse, access.dst.getName(), access.dst.kind, access.dst.snippet, access.dst.range))]
        for stat_from in stats_from:
            for stat_to in stats_to:
                update_stats(access_stats, *stat_from, *stat_to, 1)
                update_stats(access_stats_r, *stat_to, *stat_from, 1)

    return access_stats, access_stats_r

def scan_sources_main(extraFiles: list[str], modules: list[Module], extraMacros: list[dict]) -> int:
    global _globals, _args, _color

    commandline()

    if _args.color:
        _color = True
    _args.color = None  # Clear for proper cache key

    if _args.detail:
        _args.detail_from = _args.detail_to = _args.detail

    match int(bool(_args.calls_only)) + int(bool(_args.fields_only)) + int(bool(_args.macros_only)):
        case 0:
            pass
        case 1:
            if _args.calls_only:
                _args.calls, _args.fields, _args.macros = True, False, False
            elif _args.fields_only:
                _args.calls, _args.fields, _args.macros = False, True, False
            else:
                _args.calls, _args.fields, _args.macros = False, False, True
        case _:
            print(f"Error: Cannot specify more than one of --calls-only, --fields-only, --macros-only")
            return 1
    _args.calls_only = _args.fields_only = _args.macros_only = None  # Clear for proper cache key

    if _args.list_modules:
        list_modules(modules)
        return 0

    setLogLevel(_args.logLevel)

    rootPath = os.path.realpath(_args.home)
    setRootPath(rootPath)
    setModules(modules)

    files = get_files()  # list of all source files
    for file in extraFiles:
        files.insert(0, os.path.join(os.path.realpath(rootPath), file))

    if _args.clear_cache:
        cache.clearcache()
    cache.use_cache = _args.cache
    _args.cache = _args.clear_cache = None  # Clear for proper cache key

    _globals = load_globals(files, extraMacros)

    if _args.list is not None:
        list_contents()
        return 0

    access_stats, access_stats_r = load_stats(files)

    stats, src, dst, detail_src, detail_dst, dir_indicator = \
        (access_stats, _args.from_, _args.to, _args.detail_from, _args.detail_to, "->") if not _args.reverse else \
        (access_stats_r, _args.to, _args.from_, _args.detail_to, _args.detail_from, "<-")
    SrcDetails, DstDetails = detailsFunc[detail_src], detailsFunc[detail_dst]

    if getattr(stats, detail_src):
        for key, val in sorted(getattr(stats, detail_src).items()):
            print(*SrcDetails(key), dir_indicator) # type: ignore[operator] # Cannot call function of unknown type
            print_columns([(*DstDetails(key2), ":" if val2 > 1 else "", val2 if val2 > 1 else "") for key2, val2 in sorted(getattr(val, detail_dst).items())]) # type: ignore[operator] # Cannot call function of unknown type
            # for key2, val2 in sorted(getattr(val, detail_dst).items()):
            #     print(f"  {DstDetails(key2)} : {val2}")

    return not workspace.errors
