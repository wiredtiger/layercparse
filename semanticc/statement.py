import enum
from itertools import islice
from dataclasses import dataclass
from typing import Iterable

from .ctoken import *


@dataclass
class StatementKind:
    is_comment: bool | None = None
    is_preproc: bool | None = None
    is_typedef: bool | None = None
    is_record: bool | None = None
    is_function: bool | None = None
    is_function_def: bool | None = None
    is_function_decl: bool | None = None
    is_statement: bool | None = None
    is_decl: bool | None = None
    is_expression: bool | None = None
    is_initialization: bool | None = None
    is_extern_c: bool | None = None
    end: str | None = None
    preComment: Token | None = None
    postComment: Token | None = None

    @staticmethod
    def fromTokens(tokens: TokenList) -> 'StatementKind':
        ret = StatementKind()
        if not tokens:
            return ret
        for token in tokens:
            if token.value[0] in [" ", "\t", "\n"]:
                continue
            if token.value[0] == "/":
                ret.is_comment = True
                ret.preComment = token
                continue
            if token.value[0] == "#":
                ret.is_preproc = True
                return ret
            if token.value in c_statement_keywords:
                ret.is_statement = True
                return ret
            if token.value[0] not in [" ", "\t", "\n", "#", "/"]:
                break
        else:
            # we get here if "break" was not executed
            return ret

        # Only get here if we have a non-empty token
        clean_tokens = tokens.filterCode()
        if not clean_tokens:
            return ret

        # From here the options are:
        # - typedef
        # - record
        # - function
        # - expression
        # - declaration
        # - declaration + initialization (expression)

        ret.postComment = get_post_comment(tokens)

        if len(clean_tokens) > 1 and clean_tokens[0].value == "extern" and clean_tokens[1].value == '"C"':
            ret.is_extern_c = True
            return ret

        curly = next((True for token in clean_tokens if token.value[0] == "{"), False)
        if clean_tokens[0].value == "typedef":
            ret.is_typedef = True
            clean_tokens.pop(0)
        if clean_tokens[0].value in ["struct", "union", "enum"]:
            if curly:
                ret.is_record = True
            else:
                if not ret.is_typedef:
                    ret.is_decl = True
            return ret
        if ret.is_typedef:
            return ret

        # Not a typedef or record

        first_is_type = bool(reg_type.match(clean_tokens[0].value))

        if len(clean_tokens) == 1:
            if first_is_type:
                # ret.is_decl = True
                ret.is_expression = True
            elif clean_tokens[0].value in ["(", "[", "{"] or clean_tokens[0].value in c_operators_all:
                ret.is_expression = True
            return ret

        # There are at least two tokens

        if first_is_type:
            next_word = next((token for token in islice(clean_tokens, 1, None) if token.value != "*"), None)
            if next_word:
                next_next_word = next((token for token in clean_tokens if token.idx > next_word.idx and token.value != "*"), None)
                if reg_type.match(next_word.value):
                    ret.is_decl = True
                elif next_word.value in ["(", "[", "{"] and next_next_word and reg_type.match(next_next_word.value):
                    ret.is_decl = True

        for i in range(1, len(clean_tokens)):
            token = clean_tokens[i]
            if token.value[0] == "(":
                if reg_identifier.match(clean_tokens[i-1].value):   # word followed by (
                    ret.is_function = True
                    if ret.is_decl:
                        ret.is_function_decl = True
                        if curly:                                   # has a body
                            ret.is_function_def = True
                break

        for i in range(1, len(clean_tokens)-1):
            token = clean_tokens[i]
            if token.value[0] == "=":
                ret.is_expression = True
                if ret.is_decl:
                    ret.is_initialization = True
                break
            elif token.value in c_operators_all:
                if token.value == "*" and clean_tokens[i+1].idx - token.idx == 1:
                    pass # pointer dereference
                else:
                    ret.is_expression = True
                    break

        return ret


@dataclass
class Statement:
    tokens: TokenList
    kind: StatementKind | None = None

    def range(self) -> Range:
        return self.tokens.range()

    def xFilterCode(self) -> Iterable[Token]:
        return self.tokens.xFilterCode()
    def filterCode(self) -> 'Statement':
        return Statement(self.tokens.filterCode(), self.kind)

    def xFilterCode_r(self) -> Iterable[Token]:
        return self.tokens.xFilterCode_r()
    def filterCode_r(self) -> 'Statement':
        return Statement(self.tokens.filterCode_r(), self.kind)

    def getKind(self) -> StatementKind:
        if not self.kind:
            self.kind = StatementKind.fromTokens(self.tokens)
        return self.kind


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
        cur, complete, statement_special, curly, comment_only, is_record, is_expr = TokenList([]), False, 0, False, None, False, False
        else_idx = -1

        def push_statement():
            nonlocal cur, complete, statement_special, curly, comment_only, is_record, is_expr
            ret = Statement(cur)
            cur, complete, statement_special, curly, comment_only, is_record, is_expr = TokenList([]), False, 0, False, None, False, False
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
               (comment_only and token.value[0] == "/"):
                    yield push_statement()

            if comment_only is None and token.value[0] == "/":
                comment_only = True
            elif comment_only is not False and token.value[0] not in ["/", " ", "\t", "\n"]:
                comment_only = False
            if not is_expr and token.value in c_operators_all and i < len(tokens)-1 and tokens[i+1].value in [" ", "\t", "\n"]:
                is_expr = True

            # print(f"i={i}, stype={stype}, token=<{token.value}>, is_thing={is_thing}, is_word={is_word}, is_type={is_type}")

            if not statement_special:   # Constructs that don't end by ; or {}
                if token.value == "if": # if can continue with else after ;
                    statement_special = 1
                elif token.value in ["struct", "union", "enum"]:  # These end strictly with a ;
                    statement_special = 2
                    is_record = True
                elif is_expr or token.value == "do":  # These end strictly with a ;
                    statement_special = 2

            cur.append(token)

            if (complete and token.value == "\n") or token.value[0] == "#": # preproc is always a single token
                yield push_statement()
                continue

            if token.value[0] not in [";", ",", "{"]:  # Any statement ends with one of these
                continue

            if token.value[0] == "{":
                curly = True
            elif token.value[0] in [";", ","] and statement_special == 2:
                if is_record and not curly:
                    is_record = False
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

