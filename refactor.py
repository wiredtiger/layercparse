#!/usr/bin/env python3

""" Access checker script.

This script checks that WiredTiger sources comply with modularity rules
described in MODULARITY.md.

"""

import sys, os
import glob
import itertools
from dataclasses import dataclass, field

# layercparse is a library written and maintained by the WiredTiger team.
import regex
from layercparse import *

home_dir = os.path.expanduser("~")
pattern = os.path.join(home_dir, '**', 'dist', 'access_check')
wt_defs_path = next(glob.iglob(pattern, recursive=True), None)

if wt_defs_path:
    sys.path.insert(0, os.path.abspath(wt_defs_path))
    import wt_defs
else:
    print("Error: 'wt_defs.py' not found.")
    sys.exit(1)

_globals: Codebase

class Patcher:
    txt = ""
    patch_list: list[tuple[tuple[int, int], int, str]]
    idx = 0  # this is used to order the patches for the same range

    def __init__(self, txt: str):
        self.txt = txt
        self.patch_list = []

    @staticmethod
    def fromFile(fname: str) -> 'Patcher':
        return Patcher(file_content(fname))

    def replace(self, range_: tuple[int, int], txt: str) -> None:
        self.idx += 1
        self.patch_list.append((range_, self.idx, txt))

    def __bool__(self) -> bool:
        return bool(self.patch_list)

    def get_patched(self) -> str:
        ret: list[str] = []
        self.patch_list.sort()
        pos = 0
        for patch in self.patch_list:
            if patch[0][0] > pos:
                ret.append(self.txt[pos:patch[0][0]])
            ret.append(patch[2])
            pos = patch[0][1]
        ret.append(self.txt[pos:])
        return "".join(ret)

_patchers: dict[str, Patcher]  # file -> Patcher

def _get_patcher_for_file(fname: str) -> Patcher:
    if fname not in _patchers:  # type: ignore[attr-defined]
        _patchers[fname] = Patcher.fromFile(fname)  # type: ignore[attr-defined]
    return _patchers[fname]  # type: ignore[attr-defined]

def renameFields(renames: dict[str, dict[str, str]]) -> None:
    access_chain: AccessChain

    def on_field_chain(arg: AccessFieldChain):
        nonlocal access_chain
        access_chain = arg.chain

    def on_field_access(arg: AccessField):
        t = _globals.untypedef(arg.typename)
        if t not in renames or arg.field not in renames[t]:
            return
        body = cast(Token, arg.src.details.body)  # type: ignore[union-attr] # arg.src.details.body
        rng = rangeShift(arg.range, body.range[0])
        fname = arg.src.scope.file.name
        patcher = _get_patcher_for_file(fname)
        txt = patcher.txt
        if body.value[arg.range[0]:arg.range[1]] != arg.field or arg.field != txt[rng[0]:rng[1]]:
            LOG(LogLevel.QUIET, lambda:arg.src.scope.locationStr(rng[0]), f"Field access mismatch in {arg.src.name}: <{arg.field}> == <{body.value[arg.range[0]:arg.range[1]]}> == <{txt[rng[0]:rng[1]]}>")
            return None
        print(f"{arg.src.scope.locationStr(rng[0])} Field access in {arg.src.name}: {access_chain}: {t}:{arg.field} -> {renames[t][arg.field]}")
        patcher.replace(rng, renames[t][arg.field])
        return None

    access = AccessCheck(_globals)
    fields_re = regex.compile(r"\b(?:\L<names>)\b", re_flags, names=[v for vv in renames.values() for v in vv.keys()])
    for defn in itertools.chain(_globals.names.values(),
                                (v for vv in _globals.static_names.values() for v in vv.values())):
        if (not defn.details or
                not (body := getattr(defn.details, "body", None)) or
                not body.value or
                not fields_re.search(body.value)
                ):
            continue
        list(access.scan_function(defn, on_field_access=on_field_access, on_field_chain=on_field_chain))

def applyPatches() -> None:
    if not _patchers:
        print("No patches to apply.")
        return
    print("Applying patches:")
    total = 0
    for fname, patcher in _patchers.items():
        if patcher:
            total += len(patcher.patch_list)
            print(f"{fname}: Applying {len(patcher.patch_list)} patches.")
            with open(fname, "w") as f:
                f.write(patcher.get_patched())
    print(f"Total patches applied: {total}")

def main():
    global _globals, _patchers
    _patchers = {}

    if len(sys.argv) < 3:
        print("Usage: refactor.py <path> <script>")
        return 1

    print(f"Loading wt_defs.py from: {wt_defs_path}")

    refactor_prog = file_content(sys.argv[2])

    setLogLevel(LogLevel.FATAL)
    Log.module_name_mismatch.enabled = False

    rootPath = os.path.realpath(sys.argv[1])
    setRootPath(rootPath)
    setModules(wt_defs.modules)

    files = get_files()  # list of all source files
    for file in wt_defs.extraFiles:
        files.insert(0, os.path.join(os.path.realpath(rootPath), file))

    _globals = Codebase()
    # print(" ===== Scan")
    for macro in wt_defs.extraMacros:
        _globals.addMacro(**macro)
    _globals.scanFiles(files, twopass=False)

    # Pretend that typed macros are functions
    for macrodef in _globals.macros.values():
        macro = cast(MacroParts, macrodef.details)
        if macro.get_has_rettype() and macro.name.value not in _globals.names:
            _globals.names[macro.name.value] = macrodef

    exec(refactor_prog)
    applyPatches()

    return not workspace.errors

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, BrokenPipeError):
        print("\nInterrupted")
        sys.exit(1)
    except OSError as e:
        print(f"\n{e.strerror}: {e.filename}")
        sys.exit(1)

