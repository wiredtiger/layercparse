import regex
from typing import Iterable, Any
from dataclasses import dataclass

from .internal import *
from .common import *
from .ctoken import *
from .statement import *
from .variable import *

reg_define = regex.compile(r"^\#define\s++(?P<name>\w++)\s*+(?P<args>\((?P<args_in>[^)]*+)\))?\s*+(?P<body>.*)$", re_flags)
reg_whole_word = regex.compile(r"[\w\.]++", re_flags)

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
    is_va_args: bool = False
    is_wellformed: bool = False
    # is_multiple_statements: bool = False

    def __post_init__(self):
        self.is_wellformed = is_wellformed(self.body.value) if self.body else True

    def update(self, other: 'MacroParts') -> None:
        if self.name != other.name:
            print(f"ERROR: macro name mismatch for {self.name.value}: {self.name.value} != {other.name.value}")
        if self.args != other.args:
            print(f"ERROR: macro args mismatch for {self.name.value}: {self.args} != {other.args}")
        if self.body != other.body:
            print(f"ERROR: macro redifinition: {self.name.value}")
        if self.preComment is None:
            self.preComment = other.preComment

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

        is_va_args = False
        offset = token.range[0]
        args = None
        if match["args"]:  # type: ignore # match is not None; match is indexable
            args = list(
            TokenList.xFromMatches(reg_whole_word.finditer(match["args_in"]), # type: ignore # match is not None; match is indexable
                                   offset + match.start("args_in"), kind="w")) # type: ignore # match is not None; match is indexable
            if args and args[-1].value == "...":
                args[-1].value = "__VA_ARGS__"
                is_va_args = True

        body = Token.fromMatch(match, offset, "body") # type: ignore # match is not None; match is indexable
        body.value = clean_text_sz(body.value.replace("\\\n", " \n").strip()) # space to preserve byte offset

        return MacroParts(preComment=preComment, args=args, is_va_args=is_va_args,
            name=Token.fromMatch(match, offset, "name", kind="w"), # type: ignore # match is not None; match is indexable
            body=body) # type: ignore # match is not None; match is indexable

re_expandable = r"""
    (?> (?: \# | \/\/ ) (?: [^\\\n] | \\. )*+ \n) |
    (?> \/\* (?: [^*] | \*[^\/] )*+ \*\/ ) |
    (?> " (?> [^\\"] | \\. )* " ) |
    (?> ' (?> [^\\'] | \\. )* ' ) |
    (?P<txt> (?>[^'"\#\/]|\/[^\/\*])++ )
"""
reg_expandable = regex.compile(re_expandable, re_flags)

reg_hash_subst = regex.compile(r"""(?P<h>\#\s*+(?P<n>\w++))|(?P<hh>(?P<n>\w++)(?>\s*+(\#\#)\s*+(?P<n>\w++))++)""", re_flags)

def c_string_escape(txt: str) -> str:
    return txt.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\"", "\\\"")

@dataclass
class Macros:
    macros: dict[str, MacroParts] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add(self, macro: MacroParts) -> None:
        self.macros[macro.name.value] = macro

    def addFromStatement(self, statement: Statement) -> None:
        if macro := MacroParts.fromStatement(statement):
            self.add(macro)

    def upsert(self, other: MacroParts) -> None:
        if other.name.value in self.macros:
            self.macros[other.name.value].update(other)
        else:
            self.add(other)

    # Simplified macro expansion.
    # TODO: make it properly:
    #  - https://en.wikipedia.org/wiki/C_preprocessor#Order_of_expansion
    #  - https://stackoverflow.com/questions/45375238/c-preprocessor-macro-expansion
    #  - https://gcc.gnu.org/onlinedocs/cpp/Argument-Prescan.html
    def expand(self, txt: str) -> str:
        # TODO: Optimise: compose the result as a list of strings, then join at the end
        names_re = regex.compile(r"\b(?>\L<names>)\b", flags=re_flags, names=self.macros.keys())
        in_use: set[str] = set()

        def _expand_fragment(txt: str, base_offset: int = 0) -> str:
            nonlocal names_re, in_use
            pos = 0
            while match := names_re.search(txt, pos=pos):
                name = match[0]
                macro = self.macros[name]  # must be in the dictionary
                if macro.name.value in in_use:
                    pos = match.end()
                    continue
                if macro.args is None:
                    in_use.add(name)
                    replacement = _expand_fragment(macro.body.value, base_offset+match.start()) if macro.body else ""
                    in_use.remove(name)
                    txt = txt[:match.start()] + replacement + txt[match.end():]
                    pos = match.start() + len(replacement)
                    continue

                # Find the arguments
                args_str = None
                token_args = None
                for token_args in TokenList.xFromText(txt, pos=match.end()):
                    if token_args.getKind() in [" ", "/", "#"]:
                        continue
                    if token_args.getKind() == "(":
                        args_str = token_args.value
                        break
                pos = token_args.range[1] if token_args else match.end()
                if args_str is None:
                    self.errors.append(f"error: macro {name} has arguments but none found")  # TODO: better error reporting
                    continue

                if not macro.body:
                    txt = txt[:match.start()] + txt[token_args.range[1]:]
                    pos = token_args.range[1]
                    continue

                # Parse args
                args_val: list[TokenList] = [TokenList([])]
                for token_arg in TokenList.xFromText(args_str, pos=1, endpos=len(args_str)-1):
                    if token_arg.getKind() in ["/", "#"]:
                        continue
                    if token_arg.value == ",":
                        if len(args_val) < len(macro.args):
                            args_val.append(TokenList([]))
                            continue
                        # Reached the required number of arguments
                        if not macro.is_va_args:
                            break
                        # if is va_args, continue appending to the last list
                    args_val[-1].append(token_arg)
                if len(args_val) < len(macro.args):
                    self.errors.append(f"error: macro {name}: got only {len(args_val)} arguments, expected {len(macro.args)}") # TODO: better error reporting
                    continue

                replacement = macro.body.value
                in_use.add(name)

                if macro.args:
                    args_dict = {k.value: Token(0, v.range(), "".join(v.strings()).strip()) for k, v in zip(macro.args, args_val)}

                    # Replace # and ## operators
                    replacement = reg_hash_subst.sub(
                        lambda match: \
                            f'"{match["n"]}"' if match["h"] else \
                            "".join(((args_dict[name].value if name in args_dict else name) for name in match.capturesdict()["n"])),
                        replacement)

                    # Expand and replace arguments

                    args_dict_expanded = {}
                    def get_expanded_arg(name: str) -> str:
                        nonlocal args_dict_expanded
                        if name not in args_dict_expanded:
                            token = args_dict[name]
                            args_dict_expanded[name] = Token(0, token.range, _expand_fragment(token.value, base_offset+token.range[0]))
                        return args_dict_expanded[name].value

                    replacement = regex.sub(r"\b(?:\L<names>)\b",
                        lambda match: get_expanded_arg(match[0]),
                        replacement,
                        flags=re_flags, names=args_dict.keys())

                # Another round of global replacement
                replacement = _expand_fragment(replacement, base_offset+match.start())

                in_use.remove(name)

                # Done
                txt = txt[:match.start()] + replacement + txt[token_args.range[1]:]
                pos = match.start() + len(replacement)

            return txt

        self.errors = []
        return reg_expandable.sub(
            lambda match: _expand_fragment(match[0], match.start()) if match["txt"] else match[0], txt)
