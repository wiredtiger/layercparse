#!/usr/bin/env python3

""" Source scan script.

This script scans WiredTiger.

"""

import sys, os

# layercparse is a library written and maintained by the WiredTiger team.
import layercparse as lcp
from layercparse import Module

_globals: lcp.Codebase

def locationStr(defn: lcp.Definition):
    return f"{defn.locationStr()}"

def on_macro_expand(arg: lcp.AccessMacroExpand):
    ret: list[str] = []
    for src, exps in arg.exps.expansions.items():
        ret.extend((locationStr(arg.src),
            f" Macro expand: ",
            f"... [{_globals.macros[src].module}] {src} -> " if src else "",
            ", ".join(f"[{_globals.macros[exp].module}] {exp}" for exp in exps),
            "\n"))
    return "".join(ret)

def on_global_name(arg: lcp.AccessGlobalName):
    return f"{locationStr(arg.src)} Call [{_globals.names[arg.dst].module if arg.dst in _globals.names else '*'}] '{arg.dst}'\n"

def on_field_chain(arg: lcp.AccessFieldChain):
    return f"{locationStr(arg.src)} Field chain {arg.chain}\n"

def on_field_access(arg: lcp.AccessField):
    dstMod = defn.module if (defn := _globals.types.get(arg.typename, None)) else ""
    return f"{locationStr(arg.src)} Field access [{dstMod}] '{arg.typename}' -> '{arg.field}'" + "\n"

def main():
    lcp.setLogLevel(lcp.LogLevel.QUIET)
    lcp.Log.module_name_mismatch.enabled = False

    rootPath = os.path.realpath(sys.argv[1])
    lcp.setRootPath(rootPath)
    lcp.setModules([
        Module("block"),
        Module("block_cache", fileAliases=["block_chunkcache"], sourceAliases = ["blkcache", "bm"]),
        Module("bloom"),
        Module("btree", fileAliases=["btmem", "btree_cmp", "dhandle", "modify", "ref", "serial"]),
        Module("call_log"),
        # Module("checksum"),
        Module("conf", sourceAliases=["conf_keys"]),
        Module("config"),
        Module("conn", fileAliases=["connection"], sourceAliases=["connection"]),
        Module("cursor", sourceAliases=["cur", "btcur", "curbackup"]),
        Module("evict", fileAliases=["cache"]),
        Module("history", sourceAliases = ["hs"]),
        Module("log"),
        Module("lsm", sourceAliases=["clsm"]),
        Module("meta", sourceAliases=["metadata"]),
        Module("optrack"),
        # Module("os", fileAliases = ["os_common", "os_darwin", "os_linux", "os_posix", "os_win"]),
        Module("packing", sourceAliases=["pack"]),
        Module("reconcile", sourceAliases = ["rec"]),
        Module("rollback_to_stable", sourceAliases = ["rts"]),
        Module("schema"),
        Module("session"),
        # Module("support"),
        Module("tiered"),
        Module("txn", sourceAliases=["truncate"]),
        # Module("utilities"),

        Module("bitstring"),
        Module("cell"),
        Module("checkpoint", sourceAliases=["ckpt"]),
        Module("column", sourceAliases=["col"]),
        Module("compact"),
        Module("generation"),
        Module("pack", fileAliases=["intpack"]),
        Module("stat"),
    ])
    files = lcp.get_files()  # list of all source files
    files.insert(0, os.path.join(os.path.realpath(rootPath), "src/include/wiredtiger.in"))

    global _globals
    _globals = lcp.Codebase()
    # print(" ===== Scan")
    _globals.addMacro("__attribute__", 1)
    _globals.addMacro("WT_UNUSED", 1)
    _globals.addMacro("WT_ATTRIBUTE_LIBRARY_VISIBLE")
    _globals.addMacro("WT_INLINE")
    _globals.addMacro("inline")
    _globals.addMacro("WT_COMPILER_BARRIER", ("__VA_ARGS__"), body="WT_COMPILER_BARRIER", is_va_args=True)
    _globals.addMacro("WT_FULL_BARRIER",     ("__VA_ARGS__"), body="WT_FULL_BARRIER",     is_va_args=True)
    _globals.addMacro("WT_PAUSE",            ("__VA_ARGS__"), body="WT_PAUSE",            is_va_args=True)
    _globals.addMacro("WT_ACQUIRE_BARRIER",  ("__VA_ARGS__"), body="WT_ACQUIRE_BARRIER",  is_va_args=True)
    _globals.addMacro("WT_RELEASE_BARRIER",  ("__VA_ARGS__"), body="WT_RELEASE_BARRIER",  is_va_args=True)
    _globals.scanFiles(files)
    # _globals.scanFiles(files, twopass=True, multithread=False)
    # print(" ===== Globals:")
    # pprint(_globals, width=120, compact=False)
    # print(" =====")

    # print(" ===== Access check:")
    # print(" ===== Check")
    for res in lcp.AccessCheck(_globals).xscan(
                on_macro_expand=on_macro_expand,
                on_global_name=on_global_name,
                on_field_chain=on_field_chain,
                on_field_access=on_field_access
            ):
        print(res, end="")

    # import cProfile as p
    # pr = p.Profile()
    # pr.runctx('AccessCheck(_globals).checkAccess(multithread=False)', globals=globals(), locals=locals())
    # pr.create_stats()
    # pr.dump_stats("q")

    return not lcp.workspace.errors

if __name__ == "__main__":
    sys.exit(main())

