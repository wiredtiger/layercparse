import enum
from dataclasses import dataclass
from typing import Iterable

from .common import *
from .ctoken import *

class StatementType(enum.Enum):
    UNDEF = 0
    COMMENT = enum.auto()
    PREPROC = enum.auto()
    TYPEDEF = enum.auto()
    RECORD = enum.auto()  # struct, union, enum
    FUNCTION_DEF = enum.auto()
    FUNCTION_DECL = enum.auto()
    FUNCTION_CALL = enum.auto()
    STATEMENT = enum.auto()
    VARDECL = enum.auto()
    EXPRESSION = enum.auto()
    #
    EXPRESSION_OR_VARDECL = enum.auto()
    EXPRESSION_OR_VARDECL_OR_FUNC = enum.auto()
    EXPRESSION_OR_VARDECL_OR_FUNC_OR_FUNCALL = enum.auto()
    FUNCTION_DEF_OR_DECL = enum.auto()

@dataclass
class Statement:
    type: StatementType
    tokens: TokenList

    def range(self) -> Range:
        return self.tokens.range()

    def xFilterCode(self) -> Iterable[Token]:
        return self.tokens.xFilterCode()
    def filterCode(self) -> 'Statement':
        return Statement(self.type, self.tokens.filterCode())

    def xFilterCode_r(self) -> Iterable[Token]:
        return self.tokens.xFilterCode_r()
    def filterCode_r(self) -> 'Statement':
        return Statement(self.type, self.tokens.filterCode_r())

# class StatementList: ...
class StatementList(list[Statement]):
    def range(self):
        return self[0].range[0], self[-1].range[1] if len(self) > 0 else (0, 0)

    @staticmethod
    def xFromFile(fname: str) -> Iterable[Statement]:
        return StatementList.xFromTokens(TokenList.fromFile(fname))
    @staticmethod
    def fromFile(fname: str) -> 'StatementList':
        return StatementList.fromTokens(TokenList.fromFile(fname))

    @staticmethod
    def xFromText(txt: str) -> Iterable[Statement]:
        return StatementList.xFromTokens(TokenList.fromText(txt))
    @staticmethod
    def fromText(txt: str) -> 'StatementList':
        return StatementList.fromTokens(TokenList.fromText(txt))

    @staticmethod
    def xFromTokens(tokens: TokenList) -> Iterable[Statement]:
        stype, cur, complete, statement_special, prev_thing, prev_word, prev_type, curly = StatementType.UNDEF, TokenList([]), False, 0, -10, False, False, False
        else_idx = -1

        def push_statement():
            nonlocal stype, cur, complete, statement_special, prev_thing, prev_word, prev_type, curly
            if stype in [StatementType.EXPRESSION_OR_VARDECL, StatementType.EXPRESSION_OR_VARDECL_OR_FUNC, StatementType.EXPRESSION_OR_VARDECL_OR_FUNC_OR_FUNCALL]:
                stype = StatementType.VARDECL
            elif stype == StatementType.FUNCTION_DEF_OR_DECL:
                stype = StatementType.FUNCTION_DECL
            elif stype == StatementType.RECORD and not curly:
                stype = StatementType.VARDECL
            elif stype == StatementType.TYPEDEF and curly:
                stype = StatementType.RECORD
            ret = Statement(stype, TokenList(cur))
            stype, cur, complete, statement_special, prev_thing, prev_word, prev_type, curly = StatementType.UNDEF, TokenList([]), False, 0, -10, False, False, False
            return ret

        for i in range(len(tokens)):
            def find_else():
                nonlocal else_idx, i
                if else_idx > i:
                    return tokens[else_idx].value == "else"
                for ii in range(i+1, len(tokens)):
                    if tokens[ii].value == "else":
                        else_idx = ii
                        return True
                    if tokens[ii].value[0] == ";" or tokens[ii].value[0] not in [" ", "\t", "\n", "#", "/"]:
                        else_idx = ii
                        return False

            token = tokens[i]
            if (complete and token.value[0] not in ["/", " ", "\t", "\n"]) or \
               (stype == StatementType.COMMENT and token.value[0] == "/"):
                    yield push_statement()

            is_thing = token.value[0] not in [" ", "\t", "\n", "#", "/"]
            is_word = is_thing and not not reg_identifier.match(token.value)
            is_type = is_thing and not not reg_type.match(token.value)

            if stype == StatementType.UNDEF:
                if token.value[0] == "/":
                    stype = StatementType.COMMENT
            if stype in [StatementType.UNDEF, StatementType.COMMENT]:
                if token.value[0] in [" ", "\t", "\n", "/"]:
                    pass
                elif token.value[0] == "#":
                    stype = StatementType.PREPROC
                elif token.value in ["struct", "union", "enum"]:
                    stype = StatementType.RECORD
                elif token.value in ["typedef"]:
                    stype = StatementType.TYPEDEF
                elif reg_statement_keyword.match(token.value):
                    stype = StatementType.STATEMENT
                # elif token.value[0] in ["("]:   # type conversion?
                #     stype = StatementType.EXPRESSION
                elif token.value[0] != "/" and reg_c_operators.search(token.value):  # invalid
                    stype = StatementType.EXPRESSION
                elif reg_identifier.match(token.value):    # something starging with an identifier name
                    stype = StatementType.EXPRESSION_OR_VARDECL_OR_FUNC_OR_FUNCALL
                elif reg_type.match(token.value):       # ???
                    stype = StatementType.EXPRESSION_OR_VARDECL_OR_FUNC_OR_FUNCALL
            elif stype == StatementType.EXPRESSION_OR_VARDECL_OR_FUNC_OR_FUNCALL:
                if token.value[0] == "(":   # For function call, ellipsis follow the identifier
                    stype = StatementType.FUNCTION_CALL
                else:
                    # it's a space or comment or preproc
                    stype = StatementType.EXPRESSION_OR_VARDECL_OR_FUNC
                # can to into the next statement
            if stype == StatementType.EXPRESSION_OR_VARDECL_OR_FUNC:
                if token.value[0] != "/" and reg_c_operators.search(token.value):
                    stype = StatementType.EXPRESSION
                elif token.value[0] == "(" and prev_thing == i-1 and prev_word:  # no space between the identifier and the (
                    stype = StatementType.FUNCTION_DEF_OR_DECL
            elif stype == StatementType.FUNCTION_DEF_OR_DECL:
                if token.value[0] == "{":
                    stype = StatementType.FUNCTION_DEF

            # print(f"i={i}, stype={stype}, token=<{token.value}>, is_thing={is_thing}, is_word={is_word}, is_type={is_type}")

            if is_thing:
                prev_thing, prev_word, prev_type = i, is_word, is_type

            if not statement_special:   # Constructs that don't end by ; or {}
                if token.value == "if": # if can continue with else after ;
                    statement_special = 1
                elif token.value in ["struct", "union", "enum", "do", "typedef"]:  # These end strictly with a ;
                    statement_special = 2
            cur.append(token)
            if (complete and token.value == "\n") or token.value[0] == "#":
                yield push_statement()
                continue

            if token.value[0] not in [";", ",", "{"]:  # Any statement ends with one of these
                continue

            if token.value[0] == "{":
                curly = True
            elif token.value[0] in [";", ","] and statement_special == 2:
                if stype == StatementType.RECORD and not curly:
                    stype = StatementType.VARDECL
                    statement_special = 0

            if statement_special == 1:
                if find_else():
                    continue
            elif statement_special == 2 and token.value[0] != ";":
                continue

            complete = True  # The statement is complete but may want to attach trailing \n or comment

        if cur:
            yield push_statement()
    @staticmethod
    def fromTokens(tokens: TokenList) -> 'StatementList':
        return StatementList(StatementList.xFromTokens(tokens))

    def xFilterCode(self) -> Iterable[Statement]:
        for st in self:
            yield st.filterCode()
    def filterCode(self) -> 'StatementList':
        return StatementList(self.xFilterCode())

    def xFilterCode_r(self) -> Iterable[Statement]:
        for st in self:
            yield st.filterCode_r()
    def filterCode_r(self) -> 'StatementList':
        return StatementList(self.xFilterCode_r())

