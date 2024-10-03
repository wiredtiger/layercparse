#!/usr/bin/env python3

from dataclasses import dataclass, field
from semanticc import *
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
    return "\n".join(a)

def print_statement_from_file(fname: str) -> str:
    a = []
    a.append(f" === File: {fname}")
    with ScopePush(file=File(fname)):
        txt = file_content(fname)
        a.append(print_statement_from_text(txt))
    return "\n".join(a)


def main():
    # setLogLevel(LogLevel.DEBUG5)

    # for fname in get_files(sys.argv[1]):
    #     print_statement_from_file(fname)

    # multiprocessing.set_start_method('fork')  # 'fork' is faster than 'spawn'
    # with multiprocessing.Pool() as pool:
    #     for res in pool.starmap(print_statement_from_file, ((f,) for f in get_files(sys.argv[1]))):
    #         print(res)

    globals = Codebase()
    for fname in get_files(sys.argv[1]):
        globals.updateFromFile(fname)

    # pprint(globals, width=120, compact=False)

    # print(" ===== Access check:")
    access = AccessCheck(globals)
    for err in access.checkAccess():
        print(err)

if __name__ == "__main__":
    main()
