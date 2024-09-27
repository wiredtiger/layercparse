#!/usr/bin/env python3

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.dirname(__file__))

import unittest
from unittest.util import _common_shorten_repr

from semanticc import *
from pprint import pprint, pformat

import difflib


def file_content(fname: str) -> str:
    with open(fname) as file:
        return file.read()


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

    def parseDetailsFromFile(self, fname: str) -> str:
        a = []
        for st in StatementList.fromFile(fname):
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
        return "\n".join(a)


class TestRegex(TestCaseLocal):
    def test_regex(self):
        self.assertListEqual(reg.match("qwe").captures(),
            ["qwe"])
        self.assertListEqual(reg.findall("qwe"),
            ["qwe"])
        self.assertListEqual(reg.findall("qwe(asd)  {zxc} \n [wer]"),
            ["qwe", "(asd)", "  ", "{zxc}", " ", "\n", " ", "[wer]"])
        self.assertListEqual(reg.findall(r"""/* qwe(asd*/ "as\"d" {zxc} \n [wer]"""),
            ['/* qwe(asd*/', ' ', '"as\\"d"', ' ', '{zxc}', ' ', '\\n', ' ', '[wer]'])
        self.assertListEqual(reg.findall(r"""/* qwe(asd*/ "as\"d" {z/*xc} \n [wer]*/}"""),
            ['/* qwe(asd*/', ' ', '"as\\"d"', ' ', '{z/*xc} \\n [wer]*/}'])
        self.assertListEqual(reg.findall(r"""int main(int argc, char *argv[]) {\n  int a = 1;\n  return a;\n}"""),
            ['int', ' ', 'main', '(int argc, char *argv[])', ' ', '{\\n  int a = 1;\\n  return a;\\n}'])


class TestToken(TestCaseLocal):
    def test_token(self):
        self.checkObjAgainstFile(TokenList.fromFile("data/block.h"), "data/block.h.tokens")


class TestVariable(TestCaseLocal):
    def test_1(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int a;"))),
            r"""Variable(name=Token(idx=2, range=(4, 5), value='a'), type=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")
    def test_2(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int (*a)(void);"))),
            r"""Variable(name=Token(idx=2, range=(4, 8), value='a'), type=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")
    def test_3(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int a[10];"))),
            r"""Variable(name=Token(idx=2, range=(4, 5), value='a'), type=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")
    def test_4(self):
        self.assertMultiLineEqualDiff(repr(Variable.fromVarDef(TokenList.fromText("int *a[10];"))),
            r"""Variable(name=Token(idx=3, range=(5, 6), value='a'), type=[0:3] 〈int〉, preComment=None, postComment=None, end=';')""")


class TestStatement(TestCaseLocal):
    def test_statement(self):
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


# Enable to run as a standalone script
if __name__ == "__main__":
    unittest.TextTestRunner().run(unittest.TestLoader().discover(os.path.dirname(__file__)))
