import enum
from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable, Callable, NamedTuple, TypedDict
from dataclasses import dataclass
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
def lineno(txt: str, pos: int | None = None) -> int:
    return txt.count("\n", 0, pos) + 1

# Calculate column number from position
def linepos(txt: str, pos: int | None = None) -> int:
    off = txt.rfind("\n", 0, pos)
    if pos is None:
        pos = len(txt)
    return pos - off + 1 if off >= 0 else pos + 1

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

parsing_file = "-"

def set_file(fname: str):
    global parsing_file
    parsing_file = fname
