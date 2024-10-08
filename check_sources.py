#!/usr/bin/env python3

from dataclasses import dataclass, field
from layercparse import *
import sys, os
from pprint import pprint, pformat

from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable

import multiprocessing

def pf(obj: Any) -> str:
    return pformat(obj, width=120, compact=False)

def print_statement_from_text(txt: str, offset: int = 0) -> str:
    a = []
    with ScopePush(offset=offset):
        for st in StatementList.fromText(txt):
            st.getKind()
            a.append(pf(st))
            # a.append(pf(StatementKind.fromTokens(st.tokens)))
            if st.getKind().is_function_def:
                func = FunctionParts.fromStatement(st)
                if func:
                    a.extend(["Function:", pf(func)])
                    a.extend(["Args:", pf(func.getArgs())])
                    if func.body:
                        a.extend(["Vars:", pf(func.getLocalVars())])
            elif st.getKind().is_record:
                record = RecordParts.fromStatement(st)
                if record:
                    members = record.getMembers()
                    a.extend(["Record:", pf(record)])
                    # a.extend(["Members:", pf(members)])
            elif st.getKind().is_extern_c:
                body = next((t for t in st.tokens if t.value[0] == "{"), None)
                if body:
                    a.append(print_statement_from_text(body.value[1:-1], offset=body.range[0]+1))
            elif st.getKind().is_preproc:
                macro = MacroParts.fromStatement(st)
                if macro:
                    a.extend(["Macro:", pf(macro)])
    return "\n".join(a)

def print_statement_from_file(fname: str) -> str:
    a = []
    a.append(f" === File: {fname}")
    with ScopePush(file=File(fname)):
        txt = file_content(fname)
        a.append(print_statement_from_text(txt))
    return "\n".join(a)


def addModules():
    setModules([
        Module("block"),
        Module("block_cache", sourceAliases = ["blkcache", "bm"]),
        Module("bloom"),
        Module("btree"),
        Module("call_log"),
        # Module("checksum"),
        Module("conf"),
        Module("config"),
        Module("conn"),
        Module("cursor", sourceAliases=["cur"]),
        Module("evict"),
        Module("history", sourceAliases = ["hs"]),
        Module("log"),
        Module("lsm", sourceAliases=["clsm"]),
        Module("meta", sourceAliases=["metadata"]),
        Module("optrack"),
        # Module("os", fileAliases = ["os_common", "os_darwin", "os_linux", "os_posix", "os_win"]),
        Module("packing", sourceAliases=["pack", "struct"]),
        Module("reconcile", sourceAliases = ["rec"]),
        Module("rollback_to_stable", sourceAliases = ["rts"]),
        Module("schema"),
        Module("session"),
        # Module("support"),
        Module("tiered"),
        Module("txn"),
        # Module("utilities"),
    ])


def main():
    # setLogLevel(LogLevel.DEBUG4)

    rootPath = os.path.realpath(sys.argv[1])
    setRootPath(rootPath)
    addModules()
    files = get_files()
    files.insert(0, os.path.join(os.path.realpath(rootPath), "src/include/wiredtiger.in"))

    # for fname in get_files(rootPath):
    #     print_statement_from_file(fname)

    # multiprocessing.set_start_method('fork')  # 'fork' is faster than 'spawn'
    # with multiprocessing.Pool() as pool:
    #     for res in pool.starmap(print_statement_from_file, ((f,) for f in get_files())):
    #         print(res)

    _globals = Codebase()
    _globals.scanFiles(files)
    # for fname in files:
    #     _globals.updateFromFile(fname)

    # print(" ===== Globals:")
    # pprint(_globals, width=120, compact=False)
    # print(" =====")

    # print(" ===== Access check:")
    AccessCheck(_globals).checkAccess()

if __name__ == "__main__":
    main()
