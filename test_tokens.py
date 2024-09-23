#!/usr/bin/env python3

from semanticc import *
import sys
from pprint import pprint, pformat

from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable

# import regex


# pprint(regex.findall(r"(?&TOKEN)"+re_arg, "qwe", regex.RegexFlag.VERSION1 | regex.RegexFlag.DOTALL | regex.RegexFlag.VERBOSE | regex.RegexFlag.POSIX))
# for x in regex.finditer(r"(?&TOKEN)"+re_arg, "qwe", regex.RegexFlag.VERSION1 | regex.RegexFlag.DOTALL | regex.RegexFlag.VERBOSE | regex.RegexFlag.POSIX):
#     pprint(x)


# pprint(reg)
# pprint(reg.match("qwe"))

for f in sys.argv[1:]:
    # with open(f) as file:
    #     txt = file.read()
    #     for x in reg.finditer(txt):
    #         pprint(x)
    #         print(f"{x.span()[0]}...{x.span()[1]}: {x[0]}")

    # pprint(TokenList.fromFile(f))

    print(f" === File: {f}")
    for st in StatementList.xFromFile(f):
        # pprint(st)
        # pprint(st.filterCode())
        print(f"{st.type} {st.range()}: ", end="")
        if st.type in [StatementType.STRUCT, StatementType.UNION, StatementType.ENUM]:
            print("〈"+"⌇".join((t.value for t in st.tokens))+"〉")
        elif st.type == StatementType.FUNCTION_DEF:
            func = FunctionParts.fromStatement(st)
            pprint(func)
            if func:
                for var in func.xGetArgs():
                    print(f"=== Arg: <{var.name.value}> : {var.type}")
                if func.body:
                    for var in func.xGetLocalVars():
                        print(f"=== Local var: <{var.name.value}> : {var.type}")
                    # for stt in StatementList.xFromText(func.body.value):
                    #     print(f"{stt.type}: " + "〈"+"⌇".join((t.value for t in stt.tokens))+"〉")

            # print("〈", end="")
            # for t in st.tokens:
            #     if t.value[0] != "{":
            #         print("〈"+t.value+"〉", end="")
            #     else:
            #         # print("⌇".join((tt.value for tt in TokenList.fromText(clean_text_sz(t.value[1:-1])))))
            #         for stt in StatementList.xFromText(clean_text_sz(t.value[1:-1])):
            #             print("〈"+"⌇".join((tt.value for tt in stt.tokens))+"〉", end="")
            # print("〉")
        else:
            print("〈"+"⌇".join((t.value for t in st.tokens))+"〉")

        # for t in st.tokens:
        #     print("〈", end="")
        #     if t.value[0] not in ["{", "("]:
        #         print(t.value, end="")
        #     else:
        #         print("\n〈", end="")
        #         tt = TokenList.fromText(t.value[1:-1])
        #         for stt in StatementList.xFromTokens(tt):
        #             print("〈", end="")
        #             print("⌇".join((ttt.value for ttt in stt.tokens)), end="")
        #             print("〉")
        #         print("〉\n", end="")
        #     print("〉", end="")
        # print("")
