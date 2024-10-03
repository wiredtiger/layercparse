import regex
from dataclasses import dataclass, field
from typing import Iterable, Any
from pprint import pformat

from .common import *
from .record import *
from .function import *
from .codebase import *

_reg_member_access_chain = regex.compile(r"""
    # ((?<!\w)\((?&TOKEN)++\))*                        # Possible type conversions - not needed
    (?>
        (\w++)(?>\((?&TOKEN)*+\))? |  # (1) variable or function call
        (\((?&TOKEN)++\))             # (2) expression
    )
    (?>(?>->|\.)(\w++))++             # (3) member access chain via -> or .
"""+re_token, re_flags)

AccessChain: TypeAlias = tuple[str, list[str], int]  # name, chain of members, offset

def get_access_chains(txt: str, offset_in_parent: int = 0) -> Iterable[AccessChain]:
    for match in _reg_member_access_chain.finditer(txt):
        offset = match.start() + offset_in_parent
        if match[1]:
            yield (match[1], match.allcaptures()[3], offset)  # type: ignore[misc] # Tuple index out of range
        elif match[2]:
            yield (match[2], match.allcaptures()[3], offset)  # type: ignore[misc] # Tuple index out of range
            yield from get_access_chains(match[2][1:-1], offset_in_parent + match.start(2) + 1)


@dataclass
class AccessCheck:
    _globals: Codebase
    _perModuleInvisibleNamesRe: dict[str, regex.Pattern | None] = field(default_factory=dict)

    def _get_invisible_global_names_for_module(self, module: str) -> regex.Pattern | None:
        if module not in self._perModuleInvisibleNamesRe:
            retSet = set()
            for name in self._globals.names_restricted:
                if self._globals.names_restricted[name].module != module:
                    retSet.add(name)
            if not retSet:
                self._perModuleInvisibleNamesRe[module] = None
            else:
                # reg_name =  r"(?<!->|\.)\s*+\b(" + "|".join(retSet) + r")\s*+(?:->|\.|\()"
                # reg_name =  r"(?<!->|\.)\s*+\b(" + "|".join(retSet) + r")\b"
                reg_name =  r"(?<!(?:->|\.)\s*+)(?:" + "|".join(retSet) + r")\b"
                self._perModuleInvisibleNamesRe[module] = regex.compile(reg_name, re_flags)
        return self._perModuleInvisibleNamesRe[module]

    def _check_function(self, defn: Definition) -> Iterable[str]:
        if defn.kind != "function" or \
                not defn.details or \
                not isinstance(defn.details, FunctionParts) or \
                not defn.details.body:
            return
        body_clean = clean_text_sz(defn.details.body.value)

        def _locationStr(msgtype: str, offset: int) -> str:
            return (defn.file.locationStr(defn.details.body.range[0] + offset) + # type: ignore[union-attr]
                    f": {msgtype}: [{module}] {defn.name}")

        if common.logLevel >= LogLevel.DEBUG5:
            yield f"{_locationStr('debug5', 0)}: === body:\n{body_clean}\n==="

        module = defn.module

        # Check local names
        localvars: dict[str, Definition] = {} # name -> type
        for var in defn.details.getArgs() + defn.details.getLocalVars():
            if var.typename:
                localvars[var.name.value] = Definition(
                    name=var.name.value,
                    kind="variable",
                    file=defn.file,
                    offset=var.name.range[0],
                    module="",
                    is_private=False,
                    details=var)
            elif common.logLevel >= LogLevel.WARNING:
                yield f"{_locationStr('warning', var.name.range[0])}: Missing type for local variable '{var.name.value}'"

        if localvars and common.logLevel >= LogLevel.DEBUG2:
            if logLevel >= LogLevel.DEBUG4:
                yield _locationStr('debug4', 0) + ": locals vars:\n" + pformat(localvars, width=120, compact=False)
            else:
                yield _locationStr('debug2', 0) + ": locals vars:"
                for name, d in localvars.items():
                    yield f"    {name}: {cast(Details, d.details).typename.short_repr()}"

        def _get_type_of_name(name: str) -> str:
            if name in localvars:
                return self._globals.untypedef(get_base_type(cast(Details, localvars[name].details).typename)) if localvars[name].details else ""
            if name in self._globals.names:
                return \
                    self._globals.untypedef(get_base_type(cast(Details, self._globals.names[name].details).typename)) \
                    if self._globals.names[name].details else \
                    ""
            return ""

        errors: list[str] = []

        # Get the un-typedefed type of an expression
        def _get_type_of_expr(tokens: TokenList, root_offset: int = 0) -> str:
            while tokens and tokens[0].getKind() == "+":  # remove any prefix ops
                tokens.pop(0)
            if not tokens:
                return ""

            for i in range(len(tokens)):
                if tokens[i].value == "?":  # it's a "?:" operator - find the type of the 2nd and/or 3rd expression
                    # find the :
                    for j in range(i+1, len(tokens)):
                        if tokens[j].value == ":":
                            break
                    if ret := _get_type_of_expr(TokenList(tokens[i:j-1]), root_offset + tokens[i].range[0]):
                        return ret
                    return _get_type_of_expr(TokenList(tokens[j+1:]), root_offset + tokens[j+1].range[0]) if j < len(tokens) else ""

            # Not a ternary - the type is the type of the first token
            token = tokens[0]
            if token.getKind() == "(": # expression or type cast
                if len(tokens) > 1 and tokens[1].getKind() in ["w", "("]:  # type cast
                    token_type = self._globals.untypedef(get_base_type_str(token.value[1:-1]))
                else:
                    token_type = _get_type_of_expr_str(token.value[1:-1], root_offset + token.range[0] + 1)  # expression
            elif reg_word_char.match(token.value):
                token_type = _get_type_of_name(token.value)
            else: # Something weird
                if common.logLevel >= LogLevel.WARNING:
                    errors.append(f"{_locationStr('warning', root_offset + token.range[0])}: Unexpected token in expression: {token.value}")
                return ""

            # Check for member access chain, return the type of the last member
            i = 1
            while token_type and i < len(tokens):
                if tokens[i].value not in [".", "->"]:
                    break
                i += 1
                if i >= len(tokens):
                    if common.logLevel >= LogLevel.WARNING:
                        errors.append(f"{_locationStr('warning', root_offset + tokens[-1].range[0])}: Unexpected end of expression")
                    break  # syntax error - stop the chain
                token_type = self._globals.get_field_type(token_type, tokens[i].value)
                i += 1

            return token_type

        chain: AccessChain

        def _get_type_of_expr_str(clean_txt: str, root_offset: int = 0) -> str:
            return _get_type_of_expr(TokenList(TokenList.xxFilterCode(TokenList.xFromText(clean_txt))), root_offset)

        def _check_access_to_defn(defn2: Definition, prefix: str = "") -> Iterable[str]:
            if defn2.is_private and defn2.module and defn2.module != module:
                yield f"{_locationStr('error', chain[2])}: Invalid access to private {defn2.kind} '{prefix}{defn2.name}' of [{defn2.module}]"

        def _check_access_to_type(type: str) -> Iterable[str]:
            if common.logLevel >= LogLevel.DEBUG:
                yield f"{_locationStr('debug', 0)}: Access type: {type}"
            if type in self._globals.types_restricted:
                yield from _check_access_to_defn(self._globals.types_restricted[type])

        def _check_access_to_global_name(name: str) -> Iterable[str]:
            if common.logLevel >= LogLevel.DEBUG:
                yield f"{_locationStr('debug', 0)}: Access global name: {name}"
            if name in self._globals.names_restricted:
                yield from _check_access_to_defn(self._globals.names_restricted[name])

        def _check_access_to_field(rec_type: str, field: str) -> Iterable[str]:
            if common.logLevel >= LogLevel.DEBUG:
                yield f"{_locationStr('debug', 0)}: Access field: {rec_type}.{field}"
            if rec_type in self._globals.fields and field in self._globals.fields[rec_type]:
                yield from _check_access_to_defn(self._globals.fields[rec_type][field], prefix=f"{rec_type} :: ")

        if invisible_names := self._get_invisible_global_names_for_module(module):
            for match in invisible_names.finditer(body_clean):
                name = match[0]
                yield f"{_locationStr('error', match.start())}: Invalid access to private name '{name}' of [{self._globals.names_restricted[name].module}]"

        for chain in get_access_chains(body_clean):
            if common.logLevel >= LogLevel.DEBUG:
                yield f"{_locationStr('debug', 0)}: Access chain: {chain}"
            errors = []
            expr_type = _get_type_of_expr_str(chain[0], chain[2])
            for err in errors:
                yield err
            if expr_type:
                yield from _check_access_to_type(expr_type)
                for field in chain[1]:
                    yield from _check_access_to_field(expr_type, field)
                    if not (expr_type := self._globals.get_field_type(expr_type, field)):
                        break  # error

    # Go through function bodies. Check calls and struct member accesses.
    def checkAccess(self) -> Iterable[str]:
        for defn in self._globals.names.values():
            if common.logLevel >= LogLevel.DEBUG:
                if common.logLevel >= LogLevel.DEBUG3:
                    yield f"{defn.file.locationStr(0)}: debug3: Checking {defn.short_repr()}"
                else:
                    yield f"{defn.file.locationStr(0)}: debug: Checking {defn.kind} [{defn.module}] {defn.name}"
            yield from self._check_function(defn)

