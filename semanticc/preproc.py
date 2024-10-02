from typing import Iterable, Any
from dataclasses import dataclass

from .internal import *
from .ctoken import *
from .statement import *
from .variable import *

@dataclass
class PreprocParts:
    is_define: bool = False

    @staticmethod
    def fromStatement(statement: Statement) -> 'PreprocParts':
        for token in statement.tokens:
            if token.getKind() in [" ", "/"]:
                continue
            if token.value.startswith("#define ") or token.value.startswith("#define\t"):
                return PreprocParts(is_define=True)
            break
        return PreprocParts()


@dataclass
class DefineParts:
    name: Token
    args: Token | None = None
    body: str | None = None
    preComment: Token | None = None
    # postComment: Token | None = None

    @staticmethod
    def fromStatement(statement: Statement) -> 'DefineParts | None':
        preComment = None
        for token in statement.tokens:
            if not preComment and token.getKind() == "/":
                preComment = token
                continue
            if token.getKind() in [" ", "/"]:
                continue
            if token.value.startswith("#define ") or token.value.startswith("#define\t"):
                break
            return None

        ret = None
        txt = token.value[8:].replace("\\\n", "\n")

        # Find name
        i = 0
        for token in TokenList.xFromText(txt):
            if token.getKind() == " ":
                continue
            if reg_identifier.match(token.value):
                ret = DefineParts(name=token, preComment=preComment)
                i = token.range[1]
                break
            return None
        else:
            # not finished by break
            return None
        txt = txt[i:]

        # Next: args or body
        token = next(TokenList.xFromText(txt), None)
        if token is None:
            return ret

        if token.getKind() == "(":
            ret.args = token
            txt = txt[token.range[1]:]

        ret.body = txt

        return ret
