import regex
from dataclasses import dataclass, field
from typing import Iterable, Any

from .common import *
from .record import *
from .function import *

@dataclass
class Definition:
    name: str
    kind: str
    file: File
    offset: int
    module: str
    is_private: bool | None = None
    details: FunctionParts | RecordParts | Variable | None = None
    preComments: list[Token] = field(default_factory=list)
    postComments: list[Token] = field(default_factory=list)

    def short_repr(self) -> str:
        return f"{self.name} ({self.kind}) {self.file.name}:{self.offset} {self.module} {'private' if self.is_private else 'public'} {self.details.short_repr() if self.details else ''}"

    def get_priority(self) -> int:
        ret = int(bool(self.is_private)) * 10 + get_file_priority(self.file.name)
        if isinstance(self.details, FunctionParts) or isinstance(self.details, RecordParts):
            ret += int(self.details.body is not None) * 100
        return ret

    def update(self, other: 'Definition', check_riority: bool = True) -> None:
        if check_riority and self.get_priority() < other.get_priority():
            return other.update(self, check_riority=False)
        if get_file_priority(self.file.name) < get_file_priority(other.file.name):
            self.file = other.file
            self.offset = other.offset
        if self.kind != other.kind:
            print(f"ERROR: type mismatch for {self.name}: {self.kind} != {other.kind}\n{self.short_repr()}\n{other.short_repr()}")
        if self.module != other.module:
            print(f"ERROR: module mismatch for {self.kind} {self.name}: {self.module} != {other.module}\n{self.short_repr()}\n{other.short_repr()}")
        if other.is_private:
            self.is_private = True
        if type(self.details).__name__ != type(other.details).__name__:
            print(f"ERROR: details type mismatch for '{self.name}: {type(self.details)} != {type(other.details)}\n{self.short_repr()}\n{other.short_repr()}")
        else:
            if isinstance(self.details, FunctionParts) or isinstance(self.details, RecordParts) or isinstance(self.details, Variable):
                errors = self.details.update(other.details)  # type: ignore
                if errors:
                    print(f"ERROR: for {self.name}:\n{self.short_repr()}\n{other.short_repr()}")
                    print("\n".join(errors))
        self.preComments += other.preComments
        self.postComments += other.postComments


def _dict_upsert_def(d: dict[str, Definition], other: Definition) -> None:
    if other.name in d:
        d[other.name].update(other)
    else:
        d[other.name] = other


# private: None -> not defined -> public
def _get_is_private(thing: FunctionParts | RecordParts | Variable, default_private: bool | None = None, defaule_module: str = "") -> tuple[bool | None, str]:
    if thing.name.value.startswith("__wti_"):
        if match := regex.match(r"^__wti_([a-zA-Z0-9]++)", thing.name.value, flags=re_flags): # no underscore
            return (True, match.group(1))
        return (True, defaule_module)
    if thing.name.value.startswith("__wt_"):
        if match := regex.match(r"^__wt_([a-zA-Z0-9]++)", thing.name.value, flags=re_flags): # no underscore
            return (False, match.group(1))
        return (False, defaule_module)
    if thing.preComment is not None:
        if thing.preComment.value.find("#private") >= 0:
            if match := regex.search(r"\#private\((\w++)\)", thing.preComment.value, flags=re_flags):
                return (True, match.group(1))
            return (True, defaule_module)
        if thing.preComment.value.find("#public") >= 0:
            if match := regex.search(r"\#public\((\w++)\)", thing.preComment.value, flags=re_flags):
                return (False, match.group(1))
            return (False, defaule_module)
    if thing.postComment is not None:
        if thing.postComment.value.find("#private") >= 0:
            if match := regex.search(r"\#private\((\w++)\)", thing.postComment.value, flags=re_flags):
                return (True, match.group(1))
            return (True, defaule_module)
        if thing.postComment.value.find("#public") >= 0:
            if match := regex.search(r"\#public\((\w++)\)", thing.postComment.value, flags=re_flags):
                return (False, match.group(1))
            return (False, defaule_module)
    return (default_private, defaule_module)


@dataclass
class Codebase:
    # Records: structs, unions, enums
    types: dict[str, Definition] = field(default_factory=dict)
    types_restricted: dict[str, Definition] = field(default_factory=dict)
    fields: dict[str, dict[str, Definition]] = field(default_factory=dict)  # record_name -> {field_name -> GlobalDefn}
    # Functions, variables, other identifiers
    names: dict[str, Definition] = field(default_factory=dict)
    names_restricted: dict[str, Definition] = field(default_factory=dict)
    # Typedefs
    typedefs: dict[str, str] = field(default_factory=dict)

    def untypedef(self, name: str) -> str:
        name1, name2 = "", ""
        while name in self.typedefs:
            if name in self.types:
                name1 = self.typedefs[name]
            if name in self.fields:
                name2 = self.typedefs[name]
            name = self.typedefs[name]
        return name2 if name2 else name1 if name1 else name

    def _add_record(self, record: RecordParts):
        record.getMembers()
        is_private_record, local_module = _get_is_private(record, defaule_module=scope_module())
        # TODO: check the parent record's access
        _dict_upsert_def(self.types, Definition(
            name=record.name.value,
            kind="record",
            file=scope_file(),
            offset=record.name.range[0],
            module=local_module,
            is_private=is_private_record,
            details=record))
        if is_private_record:
            self.types_restricted[record.name.value] = self.types[record.name.value]
        if record.members:
            for member in record.members:
                is_private_field, local_module = _get_is_private(record, defaule_module=scope_module())
                if record.name.value not in self.fields:
                    self.fields[record.name.value] = {}
                _dict_upsert_def(self.fields[record.name.value], Definition(
                    name=member.name.value,
                    kind="field",
                    file=scope_file(),
                    offset=member.name.range[0],
                    module=local_module,
                    is_private=is_private_field,
                    details=member))
        if record.typedefs:
            for typedef in record.typedefs:
                self.typedefs[typedef.name.value] = record.name.value
        if record.vardefs:
            pass # TODO
        if record.nested:
            for rec in record.nested:
                self._add_record(rec)

    def updateFromText(self, txt: str, offset: int = 0) -> None:
        with ScopePush(offset=offset):
            saved_type: Any = None
            for st in StatementList.fromText(txt):
                st.getKind()
                if saved_type is not None or (st.getKind().is_typedef and not st.getKind().is_record):
                    var = Variable.fromVarDef(st.tokens)
                    if var:
                        if not var.typename:
                            var.typename = saved_type
                        self.typedefs[var.name.value] = get_base_type(var.typename)
                        saved_type = var.typename if var.end == "," else None
                else:
                    saved_type = None
                    if st.getKind().is_function_def:
                        func = FunctionParts.fromStatement(st)
                        if func and func.body:
                            is_private, local_module = _get_is_private(func, defaule_module=scope_module())
                            _dict_upsert_def(self.names, Definition(
                                name=func.name.value,
                                kind="function",
                                file=scope_file(),
                                offset=func.name.range[0],
                                module=local_module,
                                is_private=is_private,
                                details=func))
                            if is_private:
                                self.names_restricted[func.name.value] = self.names[func.name.value]
                    elif st.getKind().is_record:
                        record = RecordParts.fromStatement(st)
                        if record:
                            self._add_record(record)
                        # TODO: add global variables from struct definitions
                    elif st.getKind().is_decl:
                        pass # TODO: global function and variable declarations
                    elif st.getKind().is_extern_c:
                        body = next((t for t in st.tokens if t.value[0] == "{"), None)
                        if body:
                            self.updateFromText(body.value[1:-1], offset=body.range[0]+1)

    def updateFromFile(self, fname: str) -> None:
        with ScopePush(file=File(fname)):
            txt = file_content(fname)
            self.updateFromText(txt)


@dataclass
class AccessCheck:
    _globals: Codebase
    _perModuleInvisibleNamesRe: dict[str, Any] = field(default_factory=dict)

    def getInvisibleNamesForModule(self, module: str) -> Any:
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
                reg_name =  r"(?<!(?:->|\.)\s*+)\b(" + "|".join(retSet) + r")\b"
                self._perModuleInvisibleNamesRe[module] = regex.compile(reg_name, re_flags)
        return self._perModuleInvisibleNamesRe[module]

    def _check_function(self, defn: Definition) -> Iterable[str]:
        if defn.kind != "function" or \
                not defn.details or \
                not isinstance(defn.details, FunctionParts) or \
                not defn.details.body:
            return
        body_clean = clean_text_sz(defn.details.body.value)
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
        from pprint import pprint
        pprint(localvars)

        def _get_type_of_name(name: str) -> str:
            nonlocal self, localvars
            if name in self._globals.names:
                return \
                    self._globals.untypedef(get_base_type(cast(FunctionParts | RecordParts | Variable, self._globals.names[name].details).typename)) \
                    if self._globals.names[name].details else \
                    ""
            if name in localvars:
                return self._globals.untypedef(get_base_type(cast(FunctionParts | RecordParts | Variable, localvars[name].details).typename)) if localvars[name].details else ""
            return ""

        # If locals_dict is present, checking local names. Otherwise, checking global names.
        def _check_names_re(reg_name: Any, locals_dict: dict[str, Definition] | None) -> Iterable[str]:
            if not reg_name:
                return
            nonlocal self, body_clean, module
            for match in reg_name.finditer(body_clean):  # it's ok is some expressions overla: x1(x2->zz)->yy
                name = match.group()
                if not locals_dict:
                    # Check access to a global name
                    print(f"INFO: Expression (initial) {match.span()}: {name}")
                    if name in self._globals.names_restricted:
                        defn = self._globals.names_restricted[name]
                        if defn.is_private and defn.module and defn.module != module:
                            yield f"ERROR: Access to private {defn.kind} '{name}' from module '{module}'" # TODO: improve error details

                # Check struct member access
                prev_type = _get_type_of_name(name)
                # if prev_type and prev_type in globals.fields:
                #     pass # TODO: check access to the type
                (begin, end) = match.span()
                did_expand = True
                while did_expand:
                    tmp = body_clean[begin:end]
                    print(f"INFO: Expression [{begin}:{end}]: {body_clean[begin:end]} : {prev_type}")
                    # yield f"INFO: Expression [{begin}:{end}]: {body_clean[begin:end]} : {prev_type}" # TODO: improve error details

                    did_expand = False

                    def expand_right():
                        # Go right and find the end of the expression
                        nonlocal end, tmp, match
                        ret = False
                        while match := reg_token.match(body_clean, pos=end):
                            ret = True
                            end = match.span()[1]
                            tmp = body_clean[begin:end]
                            if match.group()[0] not in ["[", "(", "{", " ", "\t", "\n"]:
                                break
                        return ret

                    def expand_left():
                        # Go left and find the start of the expression
                        nonlocal begin, tmp, match
                        ret = False
                        while match := reg_token_r.match(body_clean, endpos=begin):
                            ret = True
                            begin = match.span()[0]
                            tmp = body_clean[begin:end]
                            if match.group()[0] not in ["[", "{", " ", "\t", "\n"]:
                                break
                        return ret

                    def read_next():
                        # Go right and find the end of the expression
                        nonlocal end, tmp, match
                        ret = False
                        while match := reg_token.match(body_clean, pos=end):
                            ret = True
                            end = match.span()[1]
                            tmp = body_clean[begin:end]
                            if match.group()[0] not in [" ", "\t", "\n"]:
                                break
                        return ret

                    if expand_right():
                        if match and match[0][0] in [";", ","]:
                            break
                        did_expand = True
                        if match and match[0][0] in c_operators_no_dash:
                            while expand_right():
                                pass # Expand to the end of the expression to try to get up a level
                        elif match := regex.match(r"^\.|->", body_clean, pos=end-1):
                            end = match.span()[1]
                            if read_next():
                                name = match.group() # should be a word
                                if not name or not prev_type or prev_type not in self._globals.fields or name not in self._globals.fields[prev_type]:
                                    # no info about this member
                                    while expand_right():
                                        pass
                                    end = match.span()[1] if match else len(body_clean)
                                    continue
                                defn = self._globals.fields[prev_type][name]
                                if defn.is_private and defn.module and defn.module != module:
                                    yield f"Access to private member {prev_type}.{name} from module '{module}' ({body_clean[begin:end]})"  # TODO: improve error details
                                if not defn.details or not defn.details.typename:
                                    # no type info
                                    while expand_right():
                                        pass
                                    end = match.span()[1] if match else len(body_clean)
                                    continue
                                prev_type = self._globals.untypedef(get_base_type(defn.details.typename))
                    elif expand_left():
                        if match and match[0][0] in [";", ","]:
                            break
                        did_expand = True
                        if match and match[0][0] == "(":
                            # type cast
                            type_txt = match[0][1:-1]
                            type_end = len(type_txt)
                            while match := reg_token_r.match(type_txt, endpos=type_end):
                                if match.group()[0] not in ["[", "(", "{", " ", "\t", "\n", "*"]:
                                    break
                                type_end = match.span()[0]
                            if match:
                                # should be a word
                                prev_type = self._globals.untypedef(match.group())
                            # TODO: check access to the type

                    if not did_expand:
                        # check if bounded by ( ) on both sides
                        if begin > 0 and end < len(body_clean) and body_clean[begin-1] == "(" and body_clean[end] == ")":
                            begin -= 1
                            end += 1
                            # Check for function call
                            if begin > 0 and regex.match(r"\w", body_clean[begin-1]): # a word is adjacent to the left
                                break
                            did_expand = True

                    tmp = body_clean[begin:end]

        # Check global names
        reg_name = self.getInvisibleNamesForModule(module)
        yield from _check_names_re(reg_name, {})
        # reg_name = regex.compile(r"\b(" + "|".join((v for v in localvars)) + r")\s*+(?:->|\.|\()", re_flags)
        reg_name = regex.compile(r"(?<!(?:->|\.)\s*+)\b(" + "|".join((v for v in localvars)) + r")\b", re_flags)
        yield from _check_names_re(reg_name, localvars)

    # Go through function bodies. Check calls and struct member accesses.
    def checkAccess(self) -> Iterable[str]:
        for defn in self._globals.names.values():
            print(" === Checking", defn.short_repr())
            yield from self._check_function(defn)

