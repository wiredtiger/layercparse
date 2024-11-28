import regex
from dataclasses import dataclass

from .internal import *
from .common import *
from .ctoken import *
from .statement import *
from .variable import *
from .workspace import *

reg_define = regex.compile(
    r"^\#define\s++(?P<name>\w++)(?P<args>\((?P<args_in>[^)]*+)\))?\s*+(?P<body>.*)$", re_flags)
reg_whole_word = regex.compile(r"[\w\.]++", re_flags)

# The difference from re_token is that # and ## are operators rather than preprocessor directives
re_token_preproc = r'''(?(DEFINE)(?<TOKEN>
    (?> \/\/ (?: [^\\\n] | \\. )*+ \n) |
    (?> \/\* (?: [^*] | \*[^\/] )*+ \*\/ ) |
    (?> " (?> [^\\"] | \\. )* " ) |
    (?> ' (?> [^\\'] | \\. )* ' ) |
    (?> \{ (?&TOKEN)* \} ) |
    (?> \( (?&TOKEN)* \) ) |
    (?> \[ (?&TOKEN)* \] ) |
    (?>\n) |
    [\r\t ]++ |
    (?>\\.) |
    (?> , | ; | \? | : |
        ! | \~ |
        <<= | >>= |
        \#\# | \+\+ | \-\- | \-> | \+\+ | \-\- | << | >> | <= | >= | == | != |
        \&\& | \|\| | \+= | \-= | \*= | /= | %= | \&= | \^= | \|= |
        \# | \. | \+ | \- | \* | \& | / | % | \+ | \- | < | > |
        \& | \^ | \| | = |
        \@ # invalid charachter
    ) |
    \w++
))''' # /nxs;

reg_token_preproc = regex.compile(r"(?&TOKEN)"+re_token_preproc, re_flags)

def is_wellformed(txt: str) -> bool:
    offset = 0
    for match in reg_token_preproc.finditer(txt):
        if match.start() != offset:
            return False
        offset = match.end()
    return offset == len(txt)

def get_unbalanced(txt: str) -> list[str]:
    ret: list[str] = []
    offset = 0
    for match in reg_token_preproc.finditer(txt):
        if match.start() != offset:
            ret.append(txt[offset:match.start()])
        offset = match.end()
    if offset != len(txt):
        ret.append(txt[offset:])
    return ret

_re_clean_preproc = r'''(
    (?P<s>(?>(?> \/\/ (?:[^\\\n]|\\.)*+ \n) |
    (?> \/\* (?:[^*]|\*[^\/])*+ \*\/ ))++) |
    ((?> " (?>[^\\"]|\\.)* " ) |
    (?> ' (?>[^\\']|\\.)* ' ))
)''' # /nxs;
_reg_clean_preproc = regex.compile(_re_clean_preproc, re_flags)

# Remove comments for preprocessor
def _clean_text_preproc(txt: str):
    return _reg_clean_preproc.sub(lambda match: reg_cr.sub(" ", match[0]) if match["s"] else match[0], txt)

@dataclass
class MacroParts:
    name: Token
    args: list[Token] | None = None
    body: Token | None = None
    preComment: Token | None = None
    postComment: Token | None = field(default=None, repr=False) # for compatibility with all details
    is_va_args: bool = False
    # is_multiple_statements: bool = False

    is_const: bool | None = None
    is_wellformed: bool | None = True
    unbalanced: str | None = None
    has_rettype: bool | None = None
    typename: TokenList = field(default_factory=TokenList)

    # TODO(later): Parse body into a list of tokens.
    #              Use special token types for # and ## operators and replacements

    # def __post_init__(self):
    #     self.parseExtra()

    def get_is_const(self) -> bool | None:
        self.parseExtra()
        return self.is_const
    def get_is_wellformed(self) -> bool | None:
        self.parseExtra()
        return self.is_wellformed
    def get_unbalanced(self) -> str | None:
        self.parseExtra()
        return self.unbalanced
    def get_has_rettype(self) -> bool | None:
        self.parseExtra()
        return self.has_rettype
    def get_typename(self) -> TokenList:
        self.parseExtra()
        return self.typename

    def args_short_repr(self) -> str:
        return "(" + ", ".join([arg.value for arg in self.args]) + ")" if self.args is not None else ""
    def short_repr(self) -> str:
        return (f"Macro {self.name.value}{self.args_short_repr()} "
                f"is_wellformed={self.is_wellformed} is_const={self.is_const}")

    def kind(self) -> str:
        return "macro"

    def update(self, other: 'MacroParts') -> list[str]:
        errors = []
        if self.name.value != other.name.value:
            errors.append(f"macro name mismatch for '{self.name.value}': "
                          f"'{self.name.value}' != '{other.name.value}'")
        if ((self.args is None) != (other.args is None) or
                (self.args is not None and len(self.args) != len(other.args))): # type: ignore[arg-type] # args is not None
            errors.append(f"macro args mismatch for '{self.name.value}': "
                          f"{self.args_short_repr()} != {other.args_short_repr()}")
        if ((self.body is None) != (other.body is None) or
                (self.body is not None and self.body.value != other.body.value)): # type: ignore[union-attr] # body is not None
            errors.append(f"macro body redifinition: '{self.name.value}'")
        if self.preComment is None:
            self.preComment = other.preComment
        return errors

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
        else: # not break
            return None

        is_va_args = False
        offset = token.range[0]
        args = None
        if match["args"]:
            args = list(
            TokenList.xFromMatches(reg_whole_word.finditer(match["args_in"]),
                                   offset + match.start("args_in"), kind="w"))
            if args and args[-1].value == "...":
                args[-1].value = "__VA_ARGS__"
                is_va_args = True

        body = Token.fromMatch(match, offset, "body")
        # space to preserve byte offset
        body.value = _clean_text_preproc(body.value.replace("\\\n", " \n").strip())

        return MacroParts(preComment=preComment, args=args, is_va_args=is_va_args,
            name=Token.fromMatch(match, offset, "name", kind="w"), # type: ignore # match is not None; match is indexable
            body=body) # type: ignore # match is not None; match is indexable

    def parseExtra(self) -> None:
        """Do extra parsing of body: fill in is_wellformed, unbalanced, has_rettype, typename"""
        if self.is_const is not None:
            return
        if not self.body:
            self.is_wellformed = True
            self.is_const = True
            self.unbalanced = ""
            self.has_rettype = False
            return

        tokens = TokenList()
        unbalanced: list[str] = []
        offset = 0
        for match in reg_token_preproc.finditer(self.body.value):
            if match.start() != offset:
                unbalanced.append(self.body.value[offset:match.start()])
            offset = match.end()
            if not unbalanced:  # Only add tokens up to the first unbalanced token after which the expression is broken
                token = Token.fromMatch(match, self.body.range[0])
                if token.getKind() not in [" ", "/", ";"]:
                    tokens.append(token)
                    if self.is_const is None:
                        if (token.getKind() == "'" or
                                (token.getKind() == "w" and regex.match(r"^\d", token.value))):
                            self.is_const = True
                        elif token.getKind() == "+":
                            pass  # skip operators
                        else:
                            self.is_const = False
        if offset != len(self.body.value):
            unbalanced.append(self.body.value[offset:])

        self.is_wellformed = not unbalanced
        self.unbalanced = "".join(unbalanced)
        if not self.is_wellformed:
            self.is_const = False
        elif self.is_const is None:
            self.is_const = True

        self.typename = self._get_return_type_from_tokens(tokens, self.body.range[0])
        self.has_rettype = bool(self.typename)

    def _get_return_type_from_tokens(self, tokens: TokenList, base_offset: int) -> TokenList:
        if not tokens:
            return self.typename

        if len(tokens) == 1:
            if tokens[0].getKind() != "(":
                return self.typename
            base_offset += 1
            return self._get_return_type_from_tokens(
                self._get_preproc_tokens_from_text(
                    tokens[0].value[1:-1], base_offset), base_offset)

        # more than one token
        if tokens[0].getKind() != "(":
            return self.typename

        # fist token is something in (...)
        if tokens[1].getKind() not in ["w", "(", "{"] or (tokens[1].getKind() == "+" and tokens[1].value != "*"):
            return self.typename

        return self._get_preproc_tokens_from_text(tokens[0].value[1:-1], base_offset+1)

    def _get_preproc_tokens_from_text(self, txt: str, base_offset: int) -> TokenList:
        offset = 0
        tokens = TokenList()
        for match in reg_token_preproc.finditer(txt):
            if match.start() != offset:
                break
            offset = match.end()
            token = Token.fromMatch(match, self.body.range[0])  # type: ignore[union-attr] # we do have a body
            if token.getKind() not in [" ", "/", ";"]:
                tokens.append(token)
        return tokens

