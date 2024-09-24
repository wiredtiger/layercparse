#!/usr/bin/env python3

import enum
from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable, Callable, NamedTuple, TypedDict
from dataclasses import dataclass, field
from copy import deepcopy
import regex

re_arg = r'''(?(DEFINE)(?<TOKEN>
    (?>\n) |
    \s++ |
    [;]++ |
    (?>,) |           ########### Add : and ? here?
    (?> (?:\#|\/\/) (?:[^\\\n]|\\.)*+ \n) |
    (?> \/\* (?:[^*]|\*[^\/])*+ \*\/ ) |
    (?> " (?>[^\\"]|\\.)* " ) |
    (?> ' (?>[^\\']|\\.)* ' ) |
    (?> \{ (?&TOKEN)* \} ) |
    (?> \( (?&TOKEN)* \) ) |
    (?> \[ (?&TOKEN)* \] ) |
    (?>(?:[^\[\](){};,\#\s"'\/]|\/[^\/\*])++)
))''' # /nxs;

regex.DEFAULT_VERSION = regex.RegexFlag.VERSION1
re_flags = regex.RegexFlag.VERSION1 | regex.RegexFlag.DOTALL | regex.RegexFlag.VERBOSE # | regex.RegexFlag.POSIX

reg = regex.compile(r"(?&TOKEN)"+re_arg, re_flags)

# Calculate line number from position
def lineno(txt: str, pos: int) -> int:
    return txt.count("\n", 0, pos) + 1

# Calculate column number from position
def linepos(txt: str, pos: int) -> int:
    off = txt.rfind("\n", 0, pos)
    return pos - off if off >= 0 else pos + 1

Range: TypeAlias = tuple[int, int]

reg_identifier = regex.compile(r"^\w++$", re_flags)
reg_type = regex.compile(r"^[\w\[\]\(\)\*\, ]++$", re_flags)

c_type_keywords = ["const", "volatile", "restrict", "static", "extern", "auto", "register", "struct", "union", "enum"]
c_statement_keywords = [
    "case", "continue", "default", "do", "else", "enum", "for", "goto", "if",
    "return", "struct", "switch", "typedef", "union", "while",
]
reg_statement_keyword = regex.compile(r"^(?:" + "|".join(c_statement_keywords) + r")$", re_flags)

c_operators = ["=", "+", "-", "%", "&", "|", "^", "~", ".", "?", ":"] # , "*"
reg_c_operators = regex.compile(r"(?:" + "|".join([regex.escape(op) for op in c_operators]) + r")", re_flags)

re_clean = r'''(
    (?> (?:\#|\/\/) (?:[^\\\n]|\\.)*+ \n) |
    (?> \/\* (?:[^*]|\*[^\/])*+ \*\/ ) |
    (?> " (?>[^\\"]|\\.)* " ) |
    (?> ' (?>[^\\']|\\.)* ' )
)''' # /nxs;
reg_clean = regex.compile(re_clean, re_flags)
reg_cr = regex.compile(r"""[^\n]""", re_flags)

# Remove comments and preprocessor directives, preserving newlines and text size
def clean_text_sz(txt: str):
    return reg_clean.sub(
        lambda match: reg_cr.sub(" ", match[0]) if match[0][0] in ["#", "/"] else match[0],
        txt)

# Remove comments and preprocessor directives
def clean_text(txt: str):
    return reg_clean.sub(lambda match: " " if match[0][0] in ["#", "/"] else match[0], txt)

@dataclass
class Token:
    """One token in the source code"""
    idx: int       # Index in the original stream of tokens
    range: Range   # Character range in the original text
    value: str     # Text value

class TokenList(list[Token]):
    """List of tokens"""
    # trerate over filtered list of tokens
    # def filtered(self) -> list[Token]:
    #     yield from self.tokens # TODO: Implement
    # def filtered(self) -> Iterator[Token]:
    #     yield from self.tokens # TODO: Implement
    def range(self) -> Range:
        return (self[0].range[0], self[-1].range[1]) if len(self) > 0 else (0, 0)

    @staticmethod
    def xFromText(txt: str) -> Iterable[Token]:
        i = 0
        for x in reg.finditer(txt):
            yield Token(i, x.span(), x[0])
            i += 1
    @staticmethod
    def fromText(txt: str) -> 'TokenList':
        return TokenList(TokenList.xFromText(txt))

    @staticmethod
    def xFromFile(fname: str) -> Iterable[Token]:
        with open(fname) as file:
            return TokenList.xFromText(file.read())
    @staticmethod
    def fromFile(fname: str) -> 'TokenList':
        return TokenList(TokenList.xFromFile(fname))

    def __str__(self) -> str:
        return f"[{self.range()[0]}:{self.range()[1]}] 〈{'⌇'.join([t.value for t in self])}〉"
    def __repr__(self) -> str:
        return f"[{self.range()[0]}:{self.range()[1]}] 〈{'⌇'.join([t.value for t in self])}〉"

    @staticmethod
    def xxFilterCode(tokens: Iterable[Token]) -> Iterable[Token]:
        for t in tokens:
            if t.value[0] not in [" ", "\t", "\n", "#", "/", ",", ";"]:
                yield t
    def xFilterCode(self) -> Iterable[Token]:
        return TokenList.xxFilterCode(self)
    def filterCode(self) -> 'TokenList':
        return TokenList(self.xFilterCode())

    def xFilterCode_r(self) -> Iterable[Token]:
        for t in reversed(self):
            if t.value[0] not in [" ", "\t", "\n", "#", "/", ",", ";"]:
                yield t
    def filterCode_r(self) -> 'TokenList':
        return TokenList(self.xFilterCode_r())

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

@dataclass
class Variable:
    name: Token
    type: TokenList
    preComment: Token | None = None
    postComment: Token | None = None
    end: Token | None = None

    # Get the vatiable name and type from C declaration or argument list.
    @staticmethod
    def fromVarDef(vardef: TokenList) -> 'Variable | None':
        """Get the variable name from C declaration."""
        if vardef == 1 and vardef[0] in ["...", "void"]:
            return None
        tokens = vardef.filterCode()
        # find some words, skip standalone []s and *s
        while tokens and not regex.search(r"\w", tokens[-1].value):
            tokens.pop()
        # skip function arguments
        if tokens and tokens[-1].value[0].startswith("("):
            tokens.pop()
        # find some words, skip standalone []s and *s
        while tokens and not regex.search(r"\w", tokens[-1].value):
            tokens.pop()

        # The last token contains the arg name
        if not tokens:
            return None
        name = deepcopy(tokens.pop())
        name.value = regex.sub(r"\W+", "", name.value)

        # Remove C keywords from type
        type = TokenList((filter(lambda x: x.value not in c_type_keywords, tokens)))

        end = None
        for token in reversed(vardef):
            if token.value[0] in [" ", "\t", "\n", "/"]:
                continue
            end = token.value if token.value in [",", ";"] else None
            break

        return Variable(name, type, get_pre_comment(vardef)[0], get_post_comment(vardef), end)

def get_pre_comment(tokens: TokenList) -> tuple[Token | None, int]:
    for i in range(len(tokens)):
        token = tokens[i]
        if token.value[0] in [" ", "\t", "\n"]:
            continue
        if token.value[0] == "/":
            return (token, i)
        return (None, i)
    return (None, i)

def get_post_comment(tokens: TokenList) -> Token | None:
    for token in reversed(tokens):
        if token.value[0] in [" ", "\t", "\n"]:
            continue
        if token.value[0] == "/":
            return token
        return None
    return None

@dataclass
class FunctionParts:
    retType: TokenList
    name: Token
    args: Token
    body: Token | None = None
    preComment: Token | None = None
    postComment: Token | None = None

    @staticmethod
    def fromStatement(statement: Statement) -> 'FunctionParts | None':
        i = 0
        tokens = statement.tokens

        preComment, i = get_pre_comment(tokens)

        # Return type, function name, function args
        retType = TokenList([])
        funcName = None
        argsList = None
        for i in range(i+1, len(tokens)):
            token = tokens[i]
            if token.value[0] == "(":
                if retType:
                    funcName = retType.pop()
                argsList = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                break
            if token.value[0] not in [" ", "\t", "\n", "#", "/"]:
                retType.append(token)
        if funcName is None or argsList is None:
            return None
        retType = TokenList((filter(lambda x: x.value not in c_type_keywords, retType)))

        # Function body
        funcBody = None
        for i in range(i+1, len(tokens)):
            token = tokens[i]
            if token.value[0] == "{":
                funcBody = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                break

        # Post-comment
        postComment = get_post_comment(tokens)

        return FunctionParts(retType, funcName, argsList, funcBody, preComment, postComment)

    def xGetArgs(self) -> Iterable[Variable]:
        for stt in StatementList.xFromText(self.args.value):
            var = Variable.fromVarDef(stt.tokens)
            if var:
                yield var
    def getArgs(self) -> list[Variable]:
        return list(self.xGetArgs())

    def xGetLocalVars(self) -> Iterable[Variable]:
        if not self.body:
            return
        saved_type: Any = None
        for st in StatementList.xFromText(self.body.value):
            if st.type in [StatementType.EXPRESSION, StatementType.STATEMENT, StatementType.FUNCTION_CALL]:
                break
            if st.type == StatementType.VARDECL:
                var = Variable.fromVarDef(st.tokens)
                if var:
                    if not var.type:
                        var.type = saved_type
                    yield var
                    saved_type = var.type if var.end == "," else None
            else:
                saved_type = None
    def getLocalVars(self) -> list[Variable]:
        return list(self.xGetLocalVars())

class RecordType(enum.Enum):
    UNDEF = 0
    STRUCT = enum.auto()
    UNION = enum.auto()
    ENUM = enum.auto()

@dataclass
class RecordParts:
    type: RecordType
    name: Token | None = None
    body: Token | None = None
    members: list[Variable] | None = None
    typedefs: list[Variable] | None = None
    vardefs: list[Variable] | None = None
    preComment: Token | None = None
    postComment: Token | None = None

    @staticmethod
    def fromStatement(st: Statement) -> 'RecordParts | None':
        tokens = st.tokens
        ret = RecordParts(RecordType.UNDEF)

        ret.preComment, i = get_pre_comment(tokens)

        for i in range(i+1, len(tokens)):
            token = tokens[i]
            if token.value == "typedef":
                ret.typedefs = []
            elif token.value == "struct":
                ret.type = RecordType.STRUCT
            elif token.value == "union":
                ret.type = RecordType.UNION
            elif token.value == "enum":
                ret.type = RecordType.ENUM
            elif token.value == "enum":
                ret.type = RecordType.ENUM
            elif token.value in c_type_keywords:
                pass
            elif reg_identifier.match(token.value):
                ret.name = token
            elif token.value[0] == "{":
                ret.body = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                break
            elif token.value[0] in [";", ","]:
                return None

        if not ret.body:
            return None

        # vars or types list
        names: list[Variable] = []
        typename = ret.name if ret.name else Token(ret.body.idx, ret.body.range, "(anonymous)")
        for stt in StatementList.xFromTokens(TokenList(tokens[i+1:])):
            var = Variable.fromVarDef(stt.tokens)
            if var:
                var.type = TokenList([typename])
                names.append(var)

        if ret.typedefs is not None:
            ret.typedefs = names
        else:
            ret.vardefs = names

        ret.postComment = get_post_comment(tokens)

        return ret

    def xGetMembers(self) -> Iterable[Variable]:
        if not self.body:
            return
        saved_type: Any = None
        for st in StatementList.xFromText(self.body.value):
            if st.type == StatementType.PREPROC:
                continue
            var = Variable.fromVarDef(st.tokens)
            if var:
                if not var.type:
                    var.type = saved_type
                yield var
                saved_type = var.type if var.end == "," else None
            else:
                saved_type = None



