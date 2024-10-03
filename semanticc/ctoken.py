import enum
import regex
from dataclasses import dataclass, field
from typing import Iterable

from . import common
from .internal import *

@dataclass
class Token:
    """One token in the source code"""
    idx: int = field(compare=False)     # Index in the original stream of tokens
    range: Range = field(compare=False) # Character range in the original text
    value: str                          # Text value
    kind: TokenKind | None = field(default=None, repr=False)

    def getKind(self) -> TokenKind:
        if self.kind is not None:
            return self.kind
        self.kind = getTokenKind(self.value)
        return self.kind

    @staticmethod
    def fromMatch(match: regex.Match, base_offset: int = 0, match_group: int = 0, idx: int = 0, kind: TokenKind | None = None) -> 'Token':
        return Token(idx, rangeShift(match.span(match_group), base_offset), match[match_group], kind)

class TokenList(list[Token]):
    """List of tokens"""
    def range(self) -> Range:
        return (self[0].range[0], self[-1].range[1]) if len(self) > 0 else (0, 0)

    def short_repr(self) -> str:
        return " ".join([t.value for t in self])

    @staticmethod
    def xFromMatches(matches: Iterable[regex.Match], base_offset: int = 0, match_group: int = 0, kind: TokenKind | None = None) -> Iterable[Token]:
        i = 0
        for match in matches:
            yield Token.fromMatch(match, base_offset, match_group, idx=i, kind=kind)
            i += 1
    @staticmethod
    def xFromText(txt: str) -> Iterable[Token]:
        i = 0
        for match in reg_token.finditer(txt):
            yield Token(i, match.span(), match[0])
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
            if t.getKind() not in [" ", "#", "/", ";"]:
                yield t
    def xFilterCode(self) -> Iterable[Token]:
        return TokenList.xxFilterCode(self)
    def filterCode(self) -> 'TokenList':
        return TokenList(self.xFilterCode())

    def xFilterCode_r(self) -> Iterable[Token]:
        for t in reversed(self):
            if t.getKind() not in [" ", "#", "/", ";"]:
                yield t
    def filterCode_r(self) -> 'TokenList':
        return TokenList(self.xFilterCode_r())


def get_pre_comment(tokens: TokenList) -> tuple[Token | None, int]:
    for i in range(len(tokens)):
        token = tokens[i]
        if token.getKind() == " ":
            continue
        if token.getKind() == "/":
            return (token, i+1)
        return (None, i)
    return (None, i+1)


def get_post_comment(tokens: TokenList) -> Token | None:
    for token in reversed(tokens):
        if token.getKind() == " ":
            continue
        if token.getKind() == "/":
            return token
        return None
    return None

