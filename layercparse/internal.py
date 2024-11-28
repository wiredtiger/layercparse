
# This is an umbrella import for all submodules.
from dataclasses import dataclass
from typing import Union, Any, Optional, TYPE_CHECKING, cast, Iterator, TypeAlias
from typing import Generator, Iterable, Callable, NamedTuple, TypedDict, Literal
import regex

# This regex parses C code into fat tokens.
# Fat token is a highlevel thing like a string, a comment, a block, etc.
re_token = r'''(?(DEFINE)(?<TOKEN>
    (?> (?: \# | \/\/ ) (?: [^\\\n] | \\. )*+ \n) |                     # //-comment or preprocessor directive
    (?> \/\* (?: [^*] | \*[^\/] )*+ \*\/ ) |                            # /*-comment
    (?> " (?> [^\\"] | \\. )* " ) |                                     # ""-string
    (?> ' (?> [^\\'] | \\. )* ' ) |                                     # ''-string
    (?> \{ (?&TOKEN)*+ \} ) |                                           # {}-block
    (?> \( (?&TOKEN)*+ \) ) |                                           # ()-block
    (?> \[ (?&TOKEN)*+ \] ) |                                           # []-block
    (?>\n) |                                                            # newline
    [\r\t ]++ |                                                         # whitespace
    (?>\\.) |                                                           # escaped char
    (?> , | ; | \? | : |                                                # C operators
        ! | \~ |
        <<= | >>= |
        \+\+ | \-\- | \-> | \+\+ | \-\- | << | >> | <= | >= | == | != |
        \&\& | \|\| | \+= | \-= | \*= | /= | %= | \&= | \^= | \|= |
        \. | \+ | \- | \* | \& | / | % | \+ | \- | < | > |
        \& | \^ | \| | = |
        \@ # invalid charachter
    ) |
    \w++                                                                # word
))''' # /nxs;

# VERSION1 enables all types of advanced regex features.
# DOTALL makes dot match newline.
# VERBOSE allows comments and whitespace in the regex.
regex.DEFAULT_VERSION = regex.RegexFlag.VERSION1
re_flags = regex.RegexFlag.VERSION1 | regex.RegexFlag.DOTALL | \
           regex.RegexFlag.VERBOSE | regex.RegexFlag.ASCII # | regex.RegexFlag.POSIX

# Precompiled regex.
reg_token = regex.compile(r"(?&TOKEN)"+re_token, re_flags)
# Same for reverse search.
reg_token_r = regex.compile(r"(?&TOKEN)"+re_token, re_flags | regex.RegexFlag.REVERSE)

# Range is for (start, end) pairs.
Range: TypeAlias = tuple[int, int]

# Shifts a range by an offset.
def rangeShift(rng: Range, offset: int) -> Range:
    return (rng[0]+offset, rng[1]+offset)

# Macro expansion insetion list for mappimg the original text to the expanded text.
@dataclass
class InsertPoint:
    """A point in the original text where an expansion took place."""
    range_orig: Range
    range_new: Range
    delta: int
InsertList: TypeAlias = list[InsertPoint]
# InsertList: TypeAlias = list[tuple[int, int]]  # (offset, delta)

@dataclass
class Expansions:
    """A list of macro expansions that took place at a location."""
    at: InsertPoint
    expansions: dict[str, set[str]]  # name: set[expansion]

# C identifier regex.
reg_identifier = regex.compile(r"^[a-zA-Z_]\w++$", re_flags)
# Regex to match a C type definition.
reg_type = regex.compile(r"^[\w\[\]\(\)\*\, ]++$", re_flags)

c_type_keywords = ["const", "volatile", "restrict", "static", "extern", "auto",
                   "register", "struct", "union", "enum"]
c_statement_keywords = ["case", "continue", "default", "do", "else", "for", "goto", "if",
                        "return", "switch", "while" ]
reg_statement_keyword = regex.compile(r"^(?:" + "|".join(c_statement_keywords) + r")$", re_flags)

c_types = ["void", "char", "short", "int", "long", "float", "double", "signed", "unsigned", "bool",
           "size_t", "ssize_t", "ptrdiff_t", "intptr_t", "uintptr_t", "int8_t", "int16_t",
           "int32_t", "int64_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t", "int_least8_t",
           "int_least16_t", "int_least32_t", "int_least64_t", "uint_least8_t", "uint_least16_t",
           "uint_least32_t", "uint_least64_t", "int_fast8_t", "int_fast16_t", "int_fast32_t",
           "int_fast64_t", "uint_fast8_t", "uint_fast16_t", "uint_fast32_t", "uint_fast64_t",
           "intmax_t", "uintmax_t", "wchar_t", "char16_t", "char32_t", "__int128", "__uint128",
           "__float80", "__float128", "__float16", "__float32", "__float64", "__float128",
           "__int64", "__uint64", "__int32", "__uint32", "__int16", "__uint16", "__int8",
           "__uint8",
           "timespec", "timeval", "tm", "FILE", "DIR", "pid_t", "uid_t", "gid_t", "mode_t",
           ]
ignore_type_keywords = [
    "inline", "restrict", "volatile", "auto", "register",
    "__attribute__", "__extension__", "__restrict__", "__restrict", "__inline__", "__inline",
    "__asm__", "__asm",
    "WT_GCC_FUNC_DECL_ATTRIBUTE", "WT_GCC_FUNC_ATTRIBUTE", "WT_INLINE",
    "WT_ATTRIBUTE_LIBRARY_VISIBLE", "wt_shared", "WT_STAT_COMPR_RATIO_READ_HIST_INCR_FUNC",
    "WT_STAT_COMPR_RATIO_WRITE_HIST_INCR_FUNC", "WT_STAT_USECS_HIST_INCR_FUNC",
    "WT_ATOMIC_CAS_FUNC", "WT_ATOMIC_FUNC", "WT_CURDUMP_PASS",
    "WT_STAT_MSECS_HIST_INCR_FUNC",
    ]

c_ops_all = (
    "<<=", ">>=",
    "++", "--", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||", "+=", "-=", "*=",
    "/=", "%=", "&=", "^=", "|=",
    ".", "+", "-", "!", "~", "*", "&", "*", "/", "%", "+", "-", "<", ">", "&", "^", "|", "?", ":",
    "=",
    ",", ";",
    #",", "sizeof", "_Alignof", "(",")", "[","]", "(type)", ";",
)

reg_member_access = regex.compile(r"^\.|->", re_flags)

def file_content(fname: str) -> str:
    with open(fname) as file:
        return file.read()


reg_word_char = regex.compile(r"\w", re_flags)

### Multithreading ###
# Because multithreading must be initialized once at most, we do it globally.

_multithreading_initialized = False

def init_multithreading():
    global _multithreading_initialized
    if _multithreading_initialized:
        return
    _multithreading_initialized = True
    import multiprocessing
    multiprocessing.set_start_method('fork')  # 'fork' is faster than 'spawn'

def transpose_list(l):  # https://stackoverflow.com/a/45323085
    import functools
    import operator
    return functools.reduce(operator.iconcat, l, [])
