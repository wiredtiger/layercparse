#!/usr/bin/env python3

from semanticc import *
import sys
from pprint import pprint, pformat

from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable

def file_content(fname: str) -> str:
    with open(fname) as file:
        return file.read()

def print_statement_from_text(txt: str, offset: int = 0):
    with ScopePush(offset=offset):
        for st in StatementList.fromText(txt):
            st.getKind()
            pprint(st, width=120)
            if st.getKind().is_function_def:
                func = FunctionParts.fromStatement(st)
                if func:
                    print("Function:")
                    pprint(func, width=120)
                    print("Args:")
                    pprint(func.getArgs(), width=120)
                    if func.body:
                        print("Vars:")
                        pprint(func.getLocalVars(), width=120)
            elif st.getKind().is_record:
                record = RecordParts.fromStatement(st)
                if record:
                    members = record.getMembers()
                    print("Record:")
                    pprint(record, width=120)
            elif st.getKind().is_extern_c:
                body = next((t for t in st.tokens if t.value[0] == "{"), None)
                if body:
                    print_statement_from_text(body.value[1:-1], offset=body.range[0]+1)

for fname in get_files(sys.argv[1]):
    print(f" === File: {fname}")
    with ScopePush(file=File(fname)):
        print_statement_from_text(file_content(fname))
