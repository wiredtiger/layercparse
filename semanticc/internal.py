import enum
from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias, Generator, Iterable, Callable, NamedTuple, TypedDict
from dataclasses import dataclass
from copy import deepcopy
import regex
from glob import glob

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
