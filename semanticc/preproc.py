import regex
from typing import Iterable, Any
from dataclasses import dataclass

from .internal import *
from .ctoken import *
from .statement import *
from .variable import *

reg_define = regex.compile(r"^\#define\s++(\w++)\s*+(?>\(([^)]*+)\))?\s*+(.*)$", re_flags)
reg_whole_word = regex.compile(r"\w++", re_flags)

def is_wellformed(txt: str) -> bool:
    offset = 0
    for match in reg_token.finditer(txt):
        if match.start() != offset:
            return False
        offset = match.end()
    return offset == len(txt)

@dataclass
class MacroParts:
    name: Token
    args: list[Token] | None = None
    body: Token | None = None
    preComment: Token | None = None
    # postComment: Token | None = None
    is_wellformed: bool = False
    # is_multiple_statements: bool = False

    def __post_init__(self):
        self.is_wellformed = is_wellformed(self.body.value) if self.body else True

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

        body = Token.fromMatch(match, offset, 3) # type: ignore # match is not None; match is indexable
        body.value = body.value.replace("\\\n", " \n").strip() # space to preserve byte offset

        return MacroParts(preComment=preComment, args=args,
            name=Token.fromMatch(match, offset, 1, kind="w"), # type: ignore # match is not None; match is indexable
            body=body) # type: ignore # match is not None; match is indexable

@dataclass
class Macros:
    macros: dict[str, MacroParts] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add(self, macro: MacroParts) -> None:
        self.macros[macro.name.value] = macro

    def addFromStatement(self, statement: Statement) -> None:
        if macro := MacroParts.fromStatement(statement):
            self.add(macro)

    # Simple macro expansion.
    # TODO: make it properly:
    #  - https://en.wikipedia.org/wiki/C_preprocessor#Order_of_expansion
    #  - https://stackoverflow.com/questions/45375238/c-preprocessor-macro-expansion
    #  - https://gcc.gnu.org/onlinedocs/cpp/Argument-Prescan.html
    def expand(self, txt: str) -> str:
        # TODO: Optimise: compose the result as a list of strings, then join at the end
        names_re = regex.compile(r"\b(?:\L<macros>)\b", flags=re_flags, macros=self.macros.keys())
        in_use: set[str] = set()
        match: regex.Match | None = None
        match_args: regex.Match | None = None
        name: str
        macro: MacroParts

        def _expand_fragment(start: int, end: int):
            nonlocal txt, names_re, in_use, match, match_args, name, macro
            while match := names_re.search(txt, pos=start, endpos=end):
                name = match[0]
                macro = self.macros[name]
                if macro.name.value in in_use:
                    start = match.end()
                    continue
                if macro.args:
                    offset = match.end()
                    # while (reg_token
                    continue

        self.errors = []
        _expand_fragment(0, len(txt))
        return txt
