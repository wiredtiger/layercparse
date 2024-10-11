from dataclasses import dataclass

from .macro import *

def c_string_escape(txt: str) -> str:
    return txt.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\"", "\\\"")

@dataclass
class Macros:
    macros: dict[str, MacroParts] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if "__attribute__" not in self.macros:
            self.macros["__attribute__"] = MacroParts(name=Token(0, (0, 0), "__attribute__"), args=[Token(0, (0, 0), "arg")])

    def add(self, macro: MacroParts) -> None:
        self.macros[macro.name.value] = macro

    def addFromStatement(self, statement: Statement) -> None:
        if macro := MacroParts.fromStatement(statement):
            self.add(macro)

    def upsert(self, other: MacroParts) -> list[tuple[str | Callable[[], str] | int | None, str]]:
        if other.name.value in self.macros:
            errors = self.macros[other.name.value].update(other)
            if not errors:
                return []
            return [
                (scope().locationStr(other.name.range[0]), f"Conflicting update for macro '{other.name.value}':"),
                # (scope().locationStr(self.macros[other.name.value].name.range[0]), f"conflict here:"),
                *(((None, err) for err in errors))
            ]
        else:
            self.add(other)
            return []

    # Macro expansion.
    #  - https://en.wikipedia.org/wiki/C_preprocessor#Order_of_expansion
    #  - https://stackoverflow.com/questions/45375238/c-preprocessor-macro-expansion
    #  - https://gcc.gnu.org/onlinedocs/cpp/Argument-Prescan.html
    def expand(self, txt: str, expand_const: bool = False) -> str:
        # TODO(later): Optimise: compose the result as a list of strings, then join at the end

        self.insert_list: list[tuple[int, int]] = []  # (offset, delta)
        self.errors = []

        if not self.macros:
            return txt

        names_re_a = [
            r"""(?> (?: \# | \/\/ ) (?: [^\\\n] | \\. )*+ \n)""",
            r"""(?> \/\* (?: [^*] | \*[^\/] )*+ \*\/ )""",
            r"""(?> " (?> [^\\"] | \\. )* " )""",
            r"""(?> ' (?> [^\\'] | \\. )* ' )""",
        ]
        kwargs = {}
        self._has_obj_like_names, self._has_fn_like_names = False, False
        if names := [k for k, v in self.macros.items() if v.args is None]:
            if not expand_const:
                names = [k for k in names if not self.macros[k].is_const]
            if names:
                kwargs["names_obj"] = names
                names_re_a.append(r"""(?P<name> \b(?:\L<names_obj>)\b )""")
                self._has_obj_like_names = True
        if names := [k for k, v in self.macros.items() if v.args is not None]:
            if not expand_const:
                names = [k for k in names if not self.macros[k].is_const]
            if names:
                kwargs["names_func"] = names
                names_re_a.append(r"""(?P<name> \b(?:\L<names_func>)\b )(?P<args>(?P<spc>\s*+)\((?P<list>(?&TOKEN)*+)\))""" + re_token)
                self._has_fn_like_names = True

        if not self._has_obj_like_names and not self._has_fn_like_names:
            return txt

        self._names_reg = regex.compile(" | ".join(names_re_a), re_flags, **kwargs)  # type: ignore # **kwargs
        self._in_use: set[str] = set()
        self._in_use_stack: list[str] = []

        return self._expand_fragment(txt)

    def __update_insert_list(self, replacement: str, match: regex.Match, base_offset) -> str:
        if self._in_use:
            return replacement
        self.insert_list.append((match.start() + base_offset, len(replacement) - len(match[0])))
        return replacement

    def _expand_fragment(self, txt: str, base_offset: int = 0) -> str:
        return self._names_reg.sub(
            lambda match: self._expand_fn_like(match, base_offset + base_offset) if self._has_fn_like_names and match["args"] else \
                          self._expand_obj_like(match, base_offset + base_offset) if self._has_obj_like_names and match["name"] else \
                          match[0],
            txt)

    def _expand_obj_like(self, match: regex.Match, base_offset: int = 0) -> str:
        name = match["name"]
        if name in self._in_use:
            return self.__update_insert_list(match[0], match, base_offset)
        if not self.macros[name].body:
            return self.__update_insert_list("", match, base_offset)

        self._in_use.add(name)
        self._in_use_stack.append(name)
        # TODO: embed file and line number
        replacement = self._expand_fragment(self.macros[name].body.value, base_offset)  # type: ignore # match is not None
        self._in_use_stack.pop()
        self._in_use.remove(name)

        return self.__update_insert_list(replacement, match, base_offset)

    def _expand_fn_like(self, match: regex.Match, base_offset: int = 0) -> str:
        name = match["name"]
        if name in self._in_use:
            return self.__update_insert_list(match[0], match, base_offset)
        macro = self.macros[name]
        if not macro.body:
            return self.__update_insert_list("", match, base_offset)

        # Parse args
        args_val: list[TokenList] = [TokenList([])]
        for token_arg in TokenList.xFromText(match["list"], base_offset=base_offset + match.start("list")):
            # if token_arg.getKind() in ["/", "#"]:
            #     continue
            if token_arg.value == ",":
                if len(args_val) < len(macro.args):  # type: ignore # macro has args
                    args_val.append(TokenList([]))
                    continue
                # Reached the required number of arguments
                if not macro.is_va_args:
                    break
                # if va_args, continue appending to the last list
            args_val[-1].append(token_arg)
        if len(args_val) < len(macro.args):  # type: ignore # macro has args
            self.errors.append(f"macro {name}: got only {len(args_val)} arguments, expected {len(macro.args)}")   # type: ignore # macro has args
            return self.__update_insert_list(match[0], match, base_offset)

        replacement = macro.body.value  # type: ignore # match is not None

        if macro.args:  # Can be an empty list
            args_dict = {k.value: Token(0, v.range(), "".join(v.strings()).strip()) for k, v in zip(macro.args, args_val)}

            # Calculate expanded arguments
            args_dict_expanded = {k: Token(0, v.range, self._expand_fragment(v.value, base_offset+v.range[0])) \
                    for k, v in args_dict.items()}

            # Replace operators # and ## and arguments
            reg_macro_subst = regex.compile(r"""
                (?P<h> \#\s*+ (?P<n>\w++) ) |
                (?P<hh> (?P<n>\w++)(?>\s*+(\#\#)\s*+(?P<n>\w++))++) |
                (?P<n>\b(?:\L<names>)\b)
            """, re_flags, names=args_dict.keys())

            def _concat_hh(match: regex.Match) -> str:
                return "".join(((args_dict[name].value if name in args_dict else name) for name in match.capturesdict()["n"]))
            def _arg_c_escape(name: str) -> str:
                return '"'+c_string_escape(args_dict[name].value)+'"' if name in args_dict else '""'

            replacement = reg_macro_subst.sub(
                lambda match: _arg_c_escape(match["n"]) if match["h"] else \
                              _concat_hh(match) if match["hh"] else \
                              args_dict_expanded[match["n"]].value,
                replacement)

        # Another round of global replacement
        self._in_use.add(name)
        self._in_use_stack.append(name)
        replacement = self._expand_fragment(replacement, base_offset+match.start())
        self._in_use_stack.pop()
        self._in_use.remove(name)

        return self.__update_insert_list(replacement, match, base_offset)
