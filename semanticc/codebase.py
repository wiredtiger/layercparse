import regex
from dataclasses import dataclass, field
from typing import Iterable, Any

from .common import *
from .record import *
from .function import *
from .preproc import *

Details: TypeAlias = FunctionParts | RecordParts | Variable

@dataclass
class Definition:
    name: str
    kind: str
    file: File
    offset: int
    module: str
    is_private: bool | None = None
    details: Details | None = None
    preComments: list[Token] = field(default_factory=list)
    postComments: list[Token] = field(default_factory=list)

    def short_repr(self) -> str:
        return f"{self.name} ({self.kind}) {self.file.locationStr(self.offset)} {self.module} {'private' if self.is_private else 'public'} {self.details.short_repr() if self.details else ''}"

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
def _get_is_private(thing: Details, default_private: bool | None = None, default_module: str = "") -> tuple[bool | None, str]:
    if thing.preComment is not None:
        if match := regex.search(r"\#(?>(public)|(private))\b(?>\((\w++)\))?", thing.preComment.value, flags=re_flags):
            return (bool(match[2]), match[3] if match[3] else default_module)
    if thing.postComment is not None:
        if match := regex.search(r"\#(?>(public)|(private))\b(?>\((\w++)\))?", thing.postComment.value, flags=re_flags):
            return (bool(match[2]), match[3] if match[3] else default_module)

    if match := regex.match(r"^(?>(__wt_)|(__wti_|WT_))([a-zA-Z0-9]++)?", thing.name.value, flags=re_flags):
        return (bool(match[2]), match[3] if match[3] else default_module)

    return (default_private, default_module)


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
    # Macros
    macros: Macros = field(default_factory=Macros)

    def untypedef(self, name: str) -> str:
        name1, name2 = "", ""
        while name in self.typedefs:
            if name in self.types:
                name1 = self.typedefs[name]
            if name in self.fields:
                name2 = self.typedefs[name]
            name = self.typedefs[name]
        return name2 if name2 else name1 if name1 else name

    # Get the un-typedefed type of a field or ""
    def get_field_type(self, rec_type: str, field_name: str) -> str:
        if not rec_type in self.fields or \
                field_name not in self.fields[rec_type] or \
                not self.fields[rec_type][field_name] or \
                not self.fields[rec_type][field_name].details or \
                not cast(Details, self.fields[rec_type][field_name].details).typename:
            return ""  # unknown type
        return self.untypedef(get_base_type(
            cast(Details, self.fields[rec_type][field_name].details).typename))

    def _add_record(self, record: RecordParts):
        record.getMembers()
        is_private_record, local_module = _get_is_private(record, default_module=scope_module())
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
                is_private_field, local_module = _get_is_private(record, default_module=scope_module())
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
                            is_private, local_module = _get_is_private(func, default_module=scope_module())
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
                    elif st.getKind().is_preproc:
                        macro = MacroParts.fromStatement(st)
                        if macro:
                            self.macros.upsert(macro)
                    elif st.getKind().is_extern_c:
                        body = next((t for t in st.tokens if t.value.startswith("{")), None)
                        if body:
                            self.updateFromText(body.value[1:-1], offset=body.range[0]+1)

    def updateFromFile(self, fname: str) -> None:
        with ScopePush(file=File(fname)):
            txt = file_content(fname)
            scope_file().lineNumbers(txt)
            self.updateFromText(txt)
