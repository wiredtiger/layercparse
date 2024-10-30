#!/usr/bin/env python3

""" Source scan script.

This script scans WiredTiger.

"""

import sys, os, enum
import argparse
from dataclasses import dataclass, field, is_dataclass, fields

import regex
from layercparse import *


_globals: Codebase
_args: argparse.Namespace

@dataclass
class AccessDst:
    mod:     dict[str, int] | None = None                                           # module
    file:    dict[tuple[str, str], int] | None = None                               # module, file
    full:   dict[tuple[str, str, tuple[int, int], str, str], int] | None = None  # module, file, linecol, name, kind

@dataclass
class AccessSrc:
    mod:   dict[str, AccessDst] | None = None                                           # module
    file:  dict[tuple[str, str], AccessDst] | None = None                               # module, file
    full: dict[tuple[str, str, tuple[int, int], str, str], AccessDst] | None = None  # module, file, linecol, name, kind

def access_mod_to_str(mod: str):
    return (f"[{mod}]", )

def access_file_to_str(file: tuple[str, str]):
    return (f"[{file[0]}]", f"{file[1]}")

def access_thing_to_str(full: tuple[str, str, tuple[int, int], str, str]):
    return (f"[{full[0]}]", f"{full[1]}:{full[2][0]}:{full[2][1]}:", f"{full[4]}", f"{full[3]}")

# Format output by columns
def format_by_columns(rows: list[tuple]) -> list[str]:
    str_rows = [[str(cell) for cell in row] for row in rows]
    format_str = " ".join(["{:<" + str(max(len(cell) for cell in col)) + "}" for col in zip(*str_rows)])
    return ["  " + format_str.format(*row).strip() for row in str_rows]

def print_by_columns(rows: list[tuple]):
    print(*format_by_columns(rows), sep="\n")

detailsFunc = {"mod": access_mod_to_str, "file": access_file_to_str, "full": access_thing_to_str}

access_stats: AccessSrc
access_stats_r: AccessSrc

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
    lineCol: tuple[int, int]
    kind: str
    name: str
    parentname: str | None = None

    def getName(self):
        return self.name if not self.parentname else f"{self.parentname}.{self.name}"

    @staticmethod
    def fromDefn(defn: Definition):
        return LocationId(mod=defn.module,
                          file=defn.scope.file.name,
                          lineCol=defn.scope.file.offsetToLinePos(defn.offset),
                          name=defn.name,
                          kind=defn.kind)
    @staticmethod
    def fromField(defntype: Definition, defnfield: Definition):
        return LocationId(mod=defntype.module,
                          file=defntype.scope.file.name,
                          lineCol=defntype.scope.file.offsetToLinePos(defnfield.offset),
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
        locSrc = LocationId.fromDefn(defnSrc)
        for dst in exps:
            ret.append(Access(AccessType.MACRO,
                              locSrc,
                              LocationId.fromDefn(_globals.macros[dst])))
    return filter_access_list(ret)

def on_global_name(arg: AccessGlobalName) -> list[Access] | None:
    return filter_access_list([Access(AccessType.CALL,
                   LocationId.fromDefn(arg.src),
                   LocationId.fromDefn(_globals.names[arg.dst]))])

# def on_field_chain(arg: AccessFieldChain) -> list[Access]:
#     return f"{locationStr(arg.src)} Field chain {arg.chain}\n"

def on_field_access(arg: AccessField) -> list[Access] | None:
    if arg.typename not in _globals.fields or arg.field not in _globals.fields[arg.typename]:
        return None
    return filter_access_list([Access(AccessType.FIELD,
                   LocationId.fromDefn(arg.src),
                   LocationId.fromField(_globals.types[arg.typename], _globals.fields[arg.typename][arg.field]))])

def match_str_or_regex(filter: str, value: str) -> bool:
    if not filter:
        return True
    if filter[0] == "/" and filter[-1] == "/":
        return bool(regex.match(filter[1:-1], value))
    return value == filter

def match_str_or_regex_type(filter: str, value: str) -> bool:
    if not filter:
        return True
    if filter[0] == "/" and filter[-1] == "/":
        return bool(regex.match(filter[1:-1], value))
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
    if "/" not in filter:
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
    if filter in workspace.moduleSrcNames:
        return filter == loc.mod
    if filter[0] == "(" and loc.kind == "field":
        if filter[-1] == ")":
            return loc.parentname == filter[1:-1]
        type, field = _split_type_field(filter)
        return loc.name == field and loc.parentname == type
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

def filter_access_list(access_list: list[Access]) -> list[Access] | None:
    ret: list[Access] = list(filter(filter_access, access_list))
    return ret if ret else None

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
    if filter in workspace.moduleSrcNames:
        return filter == defn.module
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

    group = argparser.add_argument_group(title="Level of detail selection (access report mode)")
    group.add_argument("-d", "--detail", choices=["mod", "file", "full"],
                       help="Specify the level of detail for access report")
    group.add_argument("--detail-from", "--df", choices=["mod", "file", "full"],
                       default="mod",
                       help="Specify the level of detail for access report for outgoing access")
    group.add_argument("--detail-to", "--dt", choices=["mod", "file", "full"],
                       default="mod",
                       help="Specify the level of detail for access report for incoming access")

    global _args
    _args = argparser.parse_args()

    return _args

def scan_sources_main(extraFiles: list[str], modules: list[Module], extraMacros: list[dict]) -> int:
    global access_stats, access_stats_r, _globals, _args

    commandline()

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

    if _args.list_modules:
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
        print_by_columns(output)
        return 0

    access_stats = AccessSrc()
    access_stats_r = AccessSrc()

    setLogLevel(_args.logLevel)

    rootPath = os.path.realpath(_args.home)
    setRootPath(rootPath)
    setModules(modules)

    files = get_files()  # list of all source files
    for file in extraFiles:
        files.insert(0, os.path.join(os.path.realpath(rootPath), file))

    _globals = Codebase()
    for macro in extraMacros:
        _globals.addMacro(**macro)
    _globals.scanFiles(files)

    if _args.list is not None:
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
        return 0

    for res in AccessCheck(_globals).xscan(
                want_scan=want_scan if _args.from_ is not None or not _args.unmod else None,
                on_macro_expand=on_macro_expand if _args.macros else None,
                on_global_name=on_global_name if _args.calls else None,
                # on_field_chain=on_field_chain,
                on_field_access=on_field_access if _args.fields else None):
        if _args.debug:
            print(*res, sep="\n")
        for access in res:
            stats_from = [("mod", access.src.mod),
                          ("file", (access.src.mod, access.src.file)),
                          ("full", (access.src.mod, access.src.file, access.src.lineCol, access.src.getName(), access.src.kind))]
            stats_to = [("mod", access.dst.mod),
                        ("file", (access.dst.mod, access.dst.file)),
                        ("full", (access.dst.mod, access.dst.file, access.dst.lineCol, access.dst.getName(), access.dst.kind))]
            for stat_from in stats_from:
                for stat_to in stats_to:
                    update_stats(access_stats, *stat_from, *stat_to, 1)
                    update_stats(access_stats_r, *stat_to, *stat_from, 1)

    stats, src, dst, detail_src, detail_dst, dir_indicator = \
        (access_stats, _args.from_, _args.to, _args.detail_from, _args.detail_to, "->") if not _args.reverse else \
        (access_stats_r, _args.to, _args.from_, _args.detail_to, _args.detail_from, "<-")
    SrcDetails, DstDetails = detailsFunc[detail_src], detailsFunc[detail_dst]

    if getattr(stats, detail_src):
        for key, val in sorted(getattr(stats, detail_src).items()):
            print(*SrcDetails(key), dir_indicator) # type: ignore[operator] # Cannot call function of unknown type
            print_by_columns([(*DstDetails(key2), ":", val2) for key2, val2 in sorted(getattr(val, detail_dst).items())]) # type: ignore[operator] # Cannot call function of unknown type
            # for key2, val2 in sorted(getattr(val, detail_dst).items()):
            #     print(f"  {DstDetails(key2)} : {val2}")

    return not workspace.errors
