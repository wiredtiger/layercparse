from dataclasses import dataclass
from typing import Iterable

from .common import *

@dataclass
class Token:
    """One token in the source code"""
    idx: int       # Index in the original stream of tokens
    range: Range   # Character range in the original text
    value: str     # Text value

class TokenList(list[Token]):
    """List of tokens"""
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

