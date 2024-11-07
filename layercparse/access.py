import regex
import multiprocessing, signal
import itertools
from dataclasses import dataclass, field
from typing import Iterable, Any
from pprint import pformat

from .common import *
from .record import *
from .function import *
from .codebase import *
from .workspace import *

_reg_member_access_chain = regex.compile(r"""
    (?>
        # (1) variable or function call or array index
        (?>
            ( [a-zA-Z_] \w*+ )
            (?>
                (?> \( (?&TOKEN)*+ \) ) |
                (?> \[ (?&TOKEN)*+ \] )
            )*+
        ) |
        # (2) expression
        ( \( (?&TOKEN)++ \) )
    )
    # (3) member access chain via -> or .
    (?>
        (?> -> | \. )
        (?>
            ( [a-zA-Z_] \w*+ )
            (?>
                (?> \( (?&TOKEN)*+ \) ) |
                (?> \[ (?&TOKEN)*+ \] )
            )*+
        )
    )++
""" + re_token, re_flags)

_reg_member_access_chain_fast = regex.compile(r"""
    (?>
        (?> -> | \. )
        (?>
            ( [a-zA-Z_] \w*+ )
            (
                (?> \( (?&TOKEN)*+ \) ) |
                (?> \[ (?&TOKEN)*+ \] )
            )*+
        )
    )++
""" + re_token, re_flags)

@dataclass
class AccessChain:
    name: str
    members: list[tuple[str, Range]]
    range: Range

    def __str__(self) -> str:
        return self.name.replace("\n", " ") + f"->{'.'.join(f for f, _ in self.members)}"

def member_access_chains(txt: str, offset_in_parent: int = 0) -> Iterable[AccessChain]:
    for match in _reg_member_access_chain.finditer(txt):
        offset = match.start() + offset_in_parent
        if match[1]:
            yield AccessChain(match[1],
                              list(zip(match.allcaptures()[3], match.allspans()[3])), # type: ignore[misc] # Tuple index out of range
                              (offset, offset_in_parent + match.end()))
        elif match[2]:
            yield AccessChain(match[2],
                              list(zip(match.allcaptures()[3], match.allspans()[3])), # type: ignore[misc] # Tuple index out of range
                              (offset, offset_in_parent + match.end()))
            yield from member_access_chains(match[2][1:-1], offset_in_parent + match.start(2) + 1)

def member_access_chains_fast(txt: str, offset_in_parent: int = 0) -> Iterable[AccessChain]:
    for match in _reg_member_access_chain_fast.finditer(txt):
        endpos = match.start()
        offset = offset_in_parent + match.start()

        # Find previous token which should be a variable or function call or expression
        while True:
            prev_match = reg_token_r.match(txt, endpos=endpos)
            if not prev_match:
                break  # TODO: report error?
            endpos = prev_match.start()
            prev_token = Token.fromMatch(prev_match, base_offset=offset_in_parent)
            if prev_token.getKind() in [" ", "/", "#", "[", "{"]:
                continue
            if prev_token.getKind() == "w":
                break
            if prev_token.getKind() == "(":
                # If it's a function call, find the function name
                while True:
                    prevprev_match = reg_token_r.match(txt, endpos=endpos)
                    if not prevprev_match:
                        break
                    endpos = prevprev_match.start()
                    prevprev_token = Token.fromMatch(prevprev_match, base_offset=offset_in_parent)
                    if prevprev_token.getKind() in [" ", "/", "#", "["]:
                        continue
                    if prevprev_token.getKind() == "w":
                        prev_match = prevprev_match
                        prev_token = prevprev_token
                        break
                    break
                else: # not break
                    pass # TODO: report error?
                break
            prev_match = None
            break  # TODO: report error?

        if not prev_match:
            continue

        offset = offset_in_parent + prev_match.start()

        yield AccessChain(prev_token.value,
                          list(zip(match.allcaptures()[1], match.allspans()[1])), # type: ignore[misc] # Tuple index out of range
                          (offset, offset_in_parent + match.end()))

        if prev_token.getKind() == "(":
            yield from member_access_chains_fast(prev_token.value[1:-1], offset + 1)

        if (match2 := match.allcaptures()[2]): # type: ignore[misc] # Tuple index out of range
            for i in range(0, len(match2)):
                yield from member_access_chains_fast(match2[i][1:-1], offset_in_parent + match.allspans()[2][i][0] + 1) # type: ignore[misc] # Tuple index out of range

def _funcId(module: str, func: str, colon: str = ":") -> str:
    return (f"[{module}] " if module else "") + f"'{func}'{colon}"

@dataclass
class AccessEventBase:
    src: Definition

@dataclass
class AccessMacroExpand(AccessEventBase):
    "Report pacro expansion in a function body"
    exps: Expansions

@dataclass
class AccessGlobalName(AccessEventBase):
    "Report access to a global name in a function body - mostly, a function call"
    range: Range
    dst: str

@dataclass
class AccessFieldChain(AccessEventBase):
    "Report access to a field chain like 'a->b.c'"
    chain: AccessChain

@dataclass
class AccessField(AccessEventBase):
    "Report access to a field '(type of X)->a'"
    typename: str
    field: str
    range: Range

AccessEvent: TypeAlias = AccessMacroExpand | AccessGlobalName | AccessFieldChain | AccessField

def _yield_if_not_none(val: Any) -> Iterable[Any]:
    if val is not None:
        yield val

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
                reg_name =  r"(?<!(?:->|\.)\s*+)(?:\L<names>)\b"
                self._perModuleInvisibleNamesRe[module] = regex.compile(reg_name, re_flags, names=retSet)
        return self._perModuleInvisibleNamesRe[module]

    def _get_all_global_names_for_module(self) -> regex.Pattern | None:
        if "" not in self._perModuleInvisibleNamesRe:
            if not self._globals.names:
                self._perModuleInvisibleNamesRe[""] = None
            else:
                reg_name =  r"(?<!(?:->|\.)\s*+)(?:\L<names>)\b"
                self._perModuleInvisibleNamesRe[""] = regex.compile(reg_name, re_flags, names=list(self._globals.names))
        return self._perModuleInvisibleNamesRe[""]

    def __check_macro_expansions_access(self, defn: Definition,
                                        on_macro_expand: Callable[[AccessMacroExpand], Any] | None = None) -> Iterable[Any]:
        module = defn.module
        for exps in defn.scope.file.expansions(
                cast(Token, cast(FunctionParts, defn.details).body).range):
            if on_macro_expand:
                yield from _yield_if_not_none(on_macro_expand(AccessMacroExpand(defn, exps)))
            r, explist = exps.range, exps.expansions
            for callerMacro in sorted(explist.keys()):
                if callerMacro and callerMacro in self._globals.macros:
                    callerDef = self._globals.macros[callerMacro]
                    callerMod = callerDef.module
                else:
                    callerMod = module
                for calleeMacro in explist[callerMacro]:
                    if (calleeMacro in self._globals.macros and
                            (calleeDef := self._globals.macros[calleeMacro]) and
                            calleeDef.is_private and
                            (calleeMod := calleeDef.module) and
                            calleeMod != callerMod):
                        if not callerMacro:
                            Log.access_macro(defn.scope.file.locationStr(r[0]), _funcId(module, defn.name),
                                f"Invalid access to private macro [{calleeMod}] '{calleeMacro}'")
                        else:
                            if "" not in explist or len(explist[""]) != 1:
                                rootName = "a macro"
                            else:
                                rootName = list(explist[''])[0]
                                rootName = f"macro " + _funcId(
                                    (self._globals.macros[rootName].module
                                        if rootName in self._globals.macros
                                        else ""),
                                    rootName, colon="")
                            Log.access_macro(defn.scope.file.locationStr(r[0]), _funcId(module, defn.name),
                                f"Expansion of {rootName} leads to invalid private macro access:")
                            Log.access_macro(callerDef.scope.file.locationStr(
                                        cast(MacroParts, callerDef.details).name.range[0]),
                                "...",
                                _funcId(callerMod, callerMacro),
                                f"Invalid access to private macro [{calleeMod}] '{calleeMacro}'")
                            Log.access_macro(calleeDef.scope.file.locationStr(
                                        cast(MacroParts, calleeDef.details).name.range[0]),
                                "...",
                                _funcId(calleeMod, calleeMacro),
                                f"Defined here")

    def _scan_function(self, defn: Definition,
                       optimize_for_errors: bool = False,
                       on_macro_expand: Callable[[AccessMacroExpand], Any] | None = None,
                       on_global_name: Callable[[AccessGlobalName], Any] | None = None,
                       on_field_chain: Callable[[AccessFieldChain], Any] | None = None,
                       on_field_access: Callable[[AccessField], Any] | None = None) -> Iterable[Any]:
        DEBUG3(defn.scope.locationStr(defn.offset), f"Checking {defn.short_repr()}") or \
        DEBUG(defn.scope.locationStr(defn.offset),
              f"Checking {defn.kind} [{defn.module}] {defn.name}")
        if defn.kind != "function" or \
                not defn.details or \
                not isinstance(defn.details, FunctionParts) or \
                not defn.details.body:
            return
        body_clean = clean_text_more_sz(defn.details.body.value)

        def _locationStr(offset: int) -> str:
            return (defn.scope.locationStr(defn.details.body.range[0] + offset) + # type: ignore[union-attr]
                    " " + _funcId(module, defn.name))

        def _LOC(offset: int) -> Callable[[], str]:
            return lambda: _locationStr(offset)

        module = defn.module
        filename = defn.scope.file.name

        DEBUG5(_LOC(0), f"=== body:\n{body_clean}\n===")

        yield from self.__check_macro_expansions_access(defn, on_macro_expand=on_macro_expand)

        # Check local names
        localvars: dict[str, Definition] = {} # name -> type
        with ScopePush(file=defn.scope.file, offset=0):
            for var in defn.details.getArgs() + defn.details.getLocalVars(self._globals):
                if var.typename:
                    localvars[var.name.value] = Definition(
                        name=var.name.value,
                        kind="variable",
                        scope=defn.scope,
                        offset=var.name.range[0],
                        module="",
                        is_private=False,
                        details=var)
                else:
                    Log.parse_localvar(_LOC(var.name.range[0]),
                            f"Missing type for local variable '{var.name.value}'")

        if localvars:
            DEBUG4(_LOC(0), f"locals vars:\n{pformat(localvars, width=120, compact=False)}") or \
            DEBUG2(_LOC(0), f"locals vars:\n" + "\n".join(
                       f"    {name}: {cast(Details, d.details).typename.short_repr()}"
                       for name, d in localvars.items()))

        def _get_type_of_name(name: str) -> str:
            # Consider scopes in order: local, static, global
            if name in localvars:
                details = localvars[name].details
            elif filename in self._globals.static_names and \
                     name in self._globals.static_names[filename]:
                details = self._globals.static_names[filename][name].details
            elif name in self._globals.names:
                details = self._globals.names[name].details
            else:
                return ""
            return self._globals.untypedef(
                get_base_type(cast(Details, details).typename)) if details else ""

        def _get_type_of_expr(tokens: TokenList, root_offset: int = 0) -> str:
            while tokens and tokens[0].getKind() == "+":  # remove any prefix ops
                tokens.pop(0)
            if not tokens:
                return ""

            for i in range(len(tokens)):
                # it's a "?:" operator - find the type of the 2nd and/or 3rd expressions
                if tokens[i].value == "?":
                    # find the :
                    for j in range(i+1, len(tokens)):
                        if tokens[j].value == ":":
                            break
                    if ret := _get_type_of_expr(
                            TokenList(tokens[i+1:j]), root_offset + tokens[i].range[0]):
                        return ret
                    return (_get_type_of_expr(TokenList(tokens[j+1:]),
                                              root_offset + tokens[j+1].range[0])
                            if j < len(tokens) else "")

            # Not a ternary - the type is the type of the first token
            token = tokens[0]
            if token.getKind() == "(": # expression or type cast
                if (len(tokens) > 1 and (tokens[1].getKind() in ["w", "(", "{"] or
                                         tokens[1].value in ["&", "*"])):  # type cast
                    return self._globals.untypedef(get_base_type_str(token.value[1:-1]))
                else:
                    token_type = _get_type_of_expr_str(
                            token.value[1:-1], root_offset + token.range[0] + 1)  # expression
            elif reg_word_char.match(token.value):
                token_type = _get_type_of_name(token.value)
            else: # Something weird
                Log.parse_expression(_LOC(root_offset + token.range[0]),
                        f"Unexpected token in expression: {token.value}")
                return ""

            # Check for member access chain, return the type of the last member
            i = 1
            while token_type and i < len(tokens):
                if tokens[i].getKind() in ["(", "["]:
                    i += 1
                    if i >= len(tokens):
                        break
                if tokens[i].value not in [".", "->"]:
                    break
                i += 1
                if i >= len(tokens):
                    Log.parse_expression(_LOC(root_offset + tokens[-1].range[1]),
                            f"Unexpected end of expression: '{tokens.short_repr()}'")
                    break  # syntax error - stop the chain
                token_type = self._globals.get_field_type(token_type, tokens[i].value)
                i += 1

            return token_type

        def _get_type_of_expr_str(clean_txt: str, root_offset: int = 0) -> str:
            return self._globals.untypedef(_get_type_of_expr(TokenList(
                        TokenList.xxFilterCode(TokenList.xFromText(clean_txt, 0))), root_offset))

        def _check_access_to_defn(defn2: Definition, offset: int, prefix: str = "") -> None:
            if defn2.is_private and defn2.module and defn2.module != module:
                Log.access_member(_locationStr(offset),
                      f"Invalid access to private {defn2.kind} "
                      f"[{defn2.module}] '{prefix}{defn2.name}'")

        def _check_access_to_type(type: str, offset: int) -> None:
            if type in self._globals.types_restricted:
                _check_access_to_defn(self._globals.types_restricted[type], offset)

        def _check_access_to_global_name(name: str, offset: int) -> None:
            DEBUG3(_locationStr(0), f"Access global name: {name}")
            if name in self._globals.names_restricted:
                _check_access_to_defn(self._globals.names_restricted[name], offset)

        def _check_access_to_field(rec_type: str, field: str, offset: int) -> None:
            if rec_type in self._globals.fields and field in self._globals.fields[rec_type]:
                _check_access_to_defn(
                    self._globals.fields[rec_type][field], offset, prefix=f"{rec_type}.")

        if optimize_for_errors:
            if invisible_names := self._get_invisible_global_names_for_module(module):
                for match in invisible_names.finditer(body_clean):
                    name = match[0]
                    Log.access_global(_locationStr(match.start()),
                        f"Invalid access to private name [{self._globals.names_restricted[name].module}] '{name}' ")
                    if on_global_name:
                        yield from _yield_if_not_none(on_global_name(AccessGlobalName(defn, (match.start(), match.end()), name)))
        else:
            if global_names := self._get_all_global_names_for_module():
                for match in global_names.finditer(body_clean):
                    name = match[0]
                    dst_module = self._globals.names[name].module
                    DEBUG3(_LOC(match.start()), f"Function call: [{dst_module}] '{name}'")
                    if dst_module and dst_module != module:
                        Log.access_global(_locationStr(match.start()),
                            f"Invalid access to private name [{dst_module}] '{name}'")
                    if on_global_name:
                        yield from _yield_if_not_none(on_global_name(AccessGlobalName(defn, (match.start(), match.end()), name)))

        for chain in member_access_chains_fast(body_clean):
            DEBUG2(_LOC(chain.range[0]), f"Access chain: {chain}")
            if on_field_chain:
                yield from _yield_if_not_none(on_field_chain(AccessFieldChain(defn, chain)))
            expr_type = _get_type_of_expr_str(chain.name, chain.range[0])
            if expr_type:
                DEBUG3(_LOC(chain.range[0]), f"Access type: {expr_type}")
                _check_access_to_type(expr_type, chain.range[0])
                DEBUG3(_LOC(chain.range[0]), f"Field access chain: {chain}")
                for field, field_range in chain.members:
                    if on_field_access:
                        yield from _yield_if_not_none(on_field_access(AccessField(defn, expr_type, field, field_range)))
                    DEBUG3(_LOC(field_range[0]), f"Field access: {expr_type}->{field}")
                    _check_access_to_field(expr_type, field, field_range[0])
                    if not (expr_type := self._globals.get_field_type(expr_type, field)):
                        Log.type_deduce_member(_LOC(field_range[0]),
                                f"Can't deduce type of member '{field}' in {chain}")
                        break  # error
            else:
                Log.type_deduce_expr(_locationStr(chain.range[0]), f"Can't deduce type of expression {chain}")

    # Go through function bodies. Check calls and struct member accesses.
    def checkAccess(self, multithread = True) -> None:
        self.scan(multithread, optimize_for_errors=True)

    # Go through function bodies. Check calls and struct member accesses.
    def scan(self, multithread = True, *args, **kwargs) -> None:
        for _ in self.xscan(multithread, *args, **kwargs):
            pass

    # Go through function bodies. Check calls and struct member accesses.
    def xscan(self,
              multithread = True,
              want_scan: Callable[[Definition], bool] | None = None,
              *args, **kwargs) -> Iterable[Any]:
        if not multithread:
            for defn in itertools.chain(
                        self._globals.names.values(),
                        *(namedict.values() for namedict in self._globals.static_names.values())):
                if not want_scan or want_scan(defn):
                    yield from self._scan_function(defn, *args, **kwargs)
        else:
            init_multithreading()
            with multiprocessing.Pool(processes=multiprocessing.cpu_count(),
                                      initializer=signal.signal,
                                      initargs=(signal.SIGINT, signal.SIG_IGN)) as pool:
                for res in pool.starmap(
                        AccessCheck._check_function_name_for_multiproc,
                        itertools.chain(
                            ((self, n, True,  want_scan, args, kwargs) for n in self._globals.static_names.keys()),
                            ((self, n, False, want_scan, args, kwargs) for n in self._globals.names.keys()))):
                    print(res[0], end='')
                    yield from res[1]

    @staticmethod
    def _check_function_name_for_multiproc(self: 'AccessCheck',
                                           name: str,
                                           file: bool,
                                           want_scan: Callable[[Definition], bool] | None = None,
                                           args: list[Any] = [],
                                           kwargs = dict[Any, Any]) -> tuple[str, list[Any]]:
        ret: list[Any] = []
        with LogToStringScope():
            if not file:
                if not want_scan or want_scan(self._globals.names[name]):
                    for res in self._scan_function(self._globals.names[name], *args, **kwargs):
                        ret.append(res)
            else:
                for defn in self._globals.static_names[name].values():
                    if not want_scan or want_scan(defn):
                        for res in self._scan_function(defn, *args, **kwargs):
                            ret.append(res)
            return (workspace.logStream.getvalue(), # type: ignore # logStream is a StringIO
                    ret)
