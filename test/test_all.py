#!/usr/bin/env python3

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.dirname(__file__))

import unittest
from unittest.util import _common_shorten_repr
from copy import deepcopy

from semanticc import *
from pprint import pprint, pformat

import difflib


def pf(obj: Any) -> str:
    return pformat(obj, width=120, compact=False)


class TestCaseLocal(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxDiff = None

    def assertMultiLineEqualDiff(self, result, expected, msg=None):
        """Assert that two multi-line strings are equal."""
        self.assertIsInstance(result, str, 'First argument is not a string')
        self.assertIsInstance(expected, str, 'Second argument is not a string')

        if result.rstrip() != expected.rstrip():
            resultlines = result.splitlines(keepends=False)
            expectedlines = expected.splitlines(keepends=False)
            if len(resultlines) == 1 and result.strip('\r\n') == result:
                resultlines = [result + '\n']
                expectedlines = [expected + '\n']
            standardMsg = '%s != %s' % _common_shorten_repr(result, expected)
            diff = '\n' + '\n'.join(difflib.unified_diff(expectedlines, resultlines))
            standardMsg = self._truncateMessage(standardMsg, diff)
            self.fail(self._formatMessage(msg, standardMsg))

    def checkStrAgainstFile(self, result, fname):
        with open(f"{fname}.test", "w") as f:
            f.write(result)
        self.assertMultiLineEqualDiff(result, file_content(fname))

    def checkObjAgainstFile(self, result, fname):
        self.checkStrAgainstFile(pf(result), fname)

    def parseDetailsFromText(self, txt: str, offset: int = 0) -> str:
        a = []
        with ScopePush(offset=offset):
            for st in StatementList.fromText(txt):
                st.getKind()
                a.append(pf(st))
                # a.append(pf(StatementKind.fromTokens(st.tokens)))
                if st.getKind().is_function_def:
                    func = FunctionParts.fromStatement(st)
                    self.assertIsNotNone(func)
                    if func:
                        a.extend(["Function:", pf(func)])
                        a.extend(["Args:", pf(func.getArgs())])
                        if func.body:
                            a.extend(["Vars:", pf(func.getLocalVars())])
                elif st.getKind().is_record:
                    record = RecordParts.fromStatement(st)
                    self.assertIsNotNone(record)
                    if record:
                        members = record.getMembers()
                        a.extend(["Record:", pf(record)])
                        # a.extend(["Members:", pf(members)])
                elif st.getKind().is_extern_c:
                    body = next((t for t in st.tokens if t.value[0] == "{"), None)
                    self.assertIsNotNone(body)
                    if body:
                        a.append(self.parseDetailsFromText(body.value[1:-1], offset=body.range[0]+1))
                elif st.getKind().is_decl and not st.getKind().is_function and not st.getKind().is_record:
                    var = Variable.fromVarDef(st.tokens)
                    if var:
                        a.extend(["Variable:", pf(var)])
        return "\n".join(a)

    def parseDetailsFromFile(self, fname: str) -> str:
        with ScopePush(file=fname):
            return self.parseDetailsFromText(file_content(fname))


class TestRegex(TestCaseLocal):
    def test_regex(self):
        self.assertListEqual(reg_token.match("qwe").captures(),
            ["qwe"])
        self.assertListEqual(reg_token.findall("qwe"),
            ["qwe"])
        self.assertListEqual(reg_token.findall("qwe\\\nasd"),
            ['qwe', '\\\n', 'asd'])
        self.assertListEqual(reg_token.findall("qwe(asd)  {zxc} \n [wer]"),
            ["qwe", "(asd)", "  ", "{zxc}", " ", "\n", " ", "[wer]"])
        self.assertListEqual(reg_token.findall(r"""/* qwe(asd*/ "as\"d" {zxc} """+"\n [wer]"),
            ['/* qwe(asd*/', ' ', '"as\\"d"', ' ', '{zxc}', ' ', '\n', ' ', '[wer]'])
        self.assertListEqual(reg_token.findall(r"""/* qwe(asd*/ "as\"d" {z/*xc} """+"\n [wer]*/}"),
            ['/* qwe(asd*/', ' ', '"as\\"d"', ' ', '{z/*xc} \n [wer]*/}'])
        self.assertListEqual(reg_token.findall(r"""int main(int argc, char *argv[]) {\n  int a = 1;\n  return a;\n}"""),
            ['int', ' ', 'main', '(int argc, char *argv[])', ' ', '{\\n  int a = 1;\\n  return a;\\n}'])

    def test_regex_r(self):
        self.assertListEqual(reg_token_r.match("qwe").captures(),
            ["qwe"])
        self.assertListEqual(reg_token_r.findall("qwe"),
            ["qwe"])
        # self.assertListEqual(reg_token_r.findall("qwe\\\nasd"),
        #     list(reversed(['qwe', '\\\n', 'asd'])))
        self.assertListEqual(reg_token_r.findall("qwe(asd)  {zxc} \n [wer]"),
            list(reversed(["qwe", "(asd)", "  ", "{zxc}", " ", "\n", " ", "[wer]"])))
        self.assertListEqual(reg_token_r.findall(r"""/* qwe(asd*/ "as\"d" {zxc} """+"\n [wer]"),
            list(reversed(['/* qwe(asd*/', ' ', '"as\\"d"', ' ', '{zxc}', ' ', '\n', ' ', '[wer]'])))
        self.assertListEqual(reg_token_r.findall(r"""/* qwe(asd*/ "as\"d" {z/*xc} """+"\n [wer]*/}"),
            list(reversed(['/* qwe(asd*/', ' ', '"as\\"d"', ' ', '{z/*xc} \n [wer]*/}'])))
        self.assertListEqual(reg_token_r.findall(r"""int main(int argc, char *argv[]) {\n  int a = 1;\n  return a;\n}"""),
            list(reversed(['int', ' ', 'main', '(int argc, char *argv[])', ' ', '{\\n  int a = 1;\\n  return a;\\n}'])))

print("qwer"[:1])


class TestToken(TestCaseLocal):
    def test_token(self):
        self.checkObjAgainstFile(TokenList.fromFile("data/block.h"), "data/block.h.tokens")


class TestVariable(TestCaseLocal):
    def test_1(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int a;"))),
            r"""Variable(name=Token(idx=2, range=(4, 5), value='a'), typename=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")
    def test_2(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int (*a)(void);"))),
            r"""Variable(name=Token(idx=2, range=(4, 8), value='a'), typename=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")
    def test_3(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int a[10];"))),
            r"""Variable(name=Token(idx=2, range=(4, 5), value='a'), typename=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")
    def test_4(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int *a[10];"))),
            r"""Variable(name=Token(idx=3, range=(5, 6), value='a'), typename=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")


class TestStatement(TestCaseLocal):
    def test_statement(self):
        with ScopePush(file=File("data/block.h")):
            self.checkObjAgainstFile(StatementList.fromFile("data/block.h"), "data/block.h.statements")

    def test_statement_details(self):
        self.checkStrAgainstFile(self.parseDetailsFromFile("data/block.h"), "data/block.h.statements-details")


class TestStatementDetails(TestCaseLocal):
    def test_func(self):
        self.checkStrAgainstFile(self.parseDetailsFromFile("data/func_simple.c"), "data/func_simple.c.statements-details")

    def test_various(self):
        self.checkStrAgainstFile(self.parseDetailsFromFile("data/various.c"), "data/various.c.statements-details")

    def test_statement_types(self):
        self.checkStrAgainstFile(self.parseDetailsFromFile("data/statements.c"), "data/statements.c.statements-details")


class TestRecordAccess(TestCaseLocal):
    def test_record(self):
        _globals = Codebase()
        _globals.updateFromFile("data/record.c")
        errors = "\n".join(AccessCheck(_globals).checkAccess())
        self.checkStrAgainstFile(errors, "data/record.c.access")

    # def test_record2(self):
    #     _globals = Codebase()
    #     _globals.updateFromFile("data/record.c")
    #     pprint(_globals, width=120, compact=False)
    #     # self.checkStrAgainstFile("\n".join(AccessCheck(globals).checkAccess()), "data/record.c.access")

    #     defn = _globals.names["func"]
    #     body_clean = clean_text_sz(defn.details.body.value)
    #     module = defn.module
    #     locals = {} # : dict[str, str] = {}
    #     for var in defn.details.getArgs() + defn.details.getLocalVars():
    #         pprint(var)
    #         locals[var.name.value] = get_base_type(var.typename)

    #     import regex
    #     body_clean = r"((S2*)((S1*)((S2*)s2[10])->s)->x)->s;"
    #     reg_name =  r"(?<!->|\.)\s*+\b(s2)\b"
    #     pprint(body_clean)
    #     match = regex.search(reg_name, body_clean)
    #     pprint(match)

    #     # Check access to global name
    #     name = match.group()
    #     if name in _globals.names_restricted:
    #         defn = _globals.names_restricted[name]
    #         if defn.is_private and defn.module != module:
    #             print(f"Access to private member '{name}' from module '{module}'")

    #     # Check struct member access

    #     def get_type_of_name(name: str) -> str:
    #         nonlocal _globals, locals
    #         if name in _globals.names:
    #             return _globals.untypedef(get_base_type(_globals.names[name].details.recordKind))
    #         if name in locals:
    #             return _globals.untypedef(locals[name])
    #         return ""

    #     prev_type = get_type_of_name(name)
    #     # if prev_type and prev_type in globals.fields:
    #     #     pass # TODO: check access to the type

    #     (begin, end) = match.span()

    #     did_expand = True
    #     while did_expand:
    #         tmp = body_clean[begin:end]
    #         print(f"Expression [{begin}:{end}]: {body_clean[begin:end]} : {prev_type}")

    #         did_expand = False

    #         def expand_right():
    #             # Go right and find the end of the expression
    #             nonlocal end, tmp, match
    #             ret = False
    #             while match := reg_token.match(body_clean, pos=end):
    #                 ret = True
    #                 end = match.span()[1]
    #                 tmp = body_clean[begin:end]
    #                 if match.group()[0] not in ["[", "(", "{", " ", "\t", "\n"]:
    #                     break
    #             return ret

    #         def expand_left():
    #             # Go left and find the start of the expression
    #             nonlocal begin, tmp, match
    #             ret = False
    #             while match := reg_token_r.match(body_clean, endpos=begin):
    #                 ret = True
    #                 begin = match.span()[0]
    #                 tmp = body_clean[begin:end]
    #                 if match.group()[0] not in ["[", "{", " ", "\t", "\n"]:
    #                     break
    #             return ret

    #         def read_next():
    #             # Go right and find the end of the expression
    #             nonlocal end, tmp, match
    #             ret = False
    #             while match := reg_token.match(body_clean, pos=end):
    #                 ret = True
    #                 end = match.span()[1]
    #                 tmp = body_clean[begin:end]
    #                 if match.group()[0] not in [" ", "\t", "\n"]:
    #                     break
    #             return ret

    #         if expand_right():
    #             did_expand = True
    #             if match and match[0][0] in [";", ","]:
    #                 break
    #             if match := regex.match(r"^\.|->", body_clean, pos=end-1):
    #                 end = match.span()[1]
    #                 if read_next():
    #                     name = match.group() # should be a word
    #                     if not name or not prev_type or name not in _globals.fields[prev_type]:
    #                         # no info about this member
    #                         while expand_right():
    #                             pass
    #                         end = match.span()[1] if match else len(body_clean)
    #                         continue
    #                     defn = _globals.fields[prev_type][name]
    #                     if defn.is_private and defn.module != module:
    #                         print(f"Access to private member {prev_type}.{name} from module '{module}' ({body_clean[begin:end]})")
    #                     if not defn.details or not defn.details.recordKind:
    #                         # no type info
    #                         while expand_right():
    #                             pass
    #                         end = match.span()[1] if match else len(body_clean)
    #                         continue
    #                     prev_type = _globals.untypedef(get_base_type(defn.details.recordKind))
    #                 else:
    #                     pass # ignore error
    #             else:
    #                 pass # ignore error
    #         elif expand_left():
    #             did_expand = True
    #             if match[0][0] == "(":
    #                 # type cast
    #                 type_txt = match[0][1:-1]
    #                 type_end = len(type_txt)
    #                 while match := reg_token_r.match(type_txt, endpos=type_end):
    #                     if match.group()[0] not in ["[", "(", "{", " ", "\t", "\n", "*"]:
    #                         break
    #                     type_end = match.span()[0]
    #                 if match:
    #                     # should be a word
    #                     prev_type = _globals.untypedef(match.group())
    #                 # TODO: check access to the type

    #         if not did_expand:
    #             # check if bounded by ( ) on both sides
    #             if begin > 0 and end < len(body_clean) and body_clean[begin-1] == "(" and body_clean[end] == ")":
    #                 did_expand = True
    #                 begin -= 1
    #                 end += 1

    #         tmp = body_clean[begin:end]

# Enable to run as a standalone script
if __name__ == "__main__":
    unittest.TextTestRunner().run(unittest.TestLoader().discover(os.path.dirname(__file__)))
