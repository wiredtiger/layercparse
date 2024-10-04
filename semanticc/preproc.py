import regex
from typing import Iterable, Any
from dataclasses import dataclass

from .internal import *
from .ctoken import *
from .statement import *
from .variable import *

reg_define = regex.compile(r"^\#define\s++(\w++)\s*+(?>\(([^)]*+)\))?\s*+(.*)$", re_flags)
reg_whole_word = regex.compile(r"\w++", re_flags)

@dataclass
class MacroParts:
    name: Token
    args: list[Token] | None = None
    body: Token | None = None
    preComment: Token | None = None
    # postComment: Token | None = None

    @staticmethod
    def fromStatement(statement: Statement) -> 'MacroParts | None':
        preComment = None
        for token in statement.tokens:
            if not preComment and token.getKind() == "/":
                preComment = token
                continue
            if token.getKind() in [" ", "/"]:
                continue
            if match := reg_define.match(token.value):
                break
            return None

        offset = token.range[0]
        args = None if not match[2] else list( # type: ignore # match is not None; match is indexable
            TokenList.xFromMatches(reg_whole_word.finditer(match[2]), # type: ignore # match is not None; match is indexable
                                   offset + match.start(2), kind="w")) # type: ignore # match is not None; match is indexable

        body = Token.fromMatch(match, offset, 3)
        body.value = body.value.replace("\\\n", " \n").strip() # space to preserve byte offset

        return MacroParts(preComment=preComment, args=args,
            name=Token.fromMatch(match, offset, 1, kind="w"), # type: ignore # match is not None; match is indexable
            body=body) # type: ignore # match is not None; match is indexable
