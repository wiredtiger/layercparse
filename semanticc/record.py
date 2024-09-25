import enum
from dataclasses import dataclass

from . import common
from .ctoken import *
from .statement import *
from .variable import *

class RecordType(enum.Enum):
    UNDEF = 0
    STRUCT = enum.auto()
    UNION = enum.auto()
    ENUM = enum.auto()

@dataclass
class RecordParts:
    type: RecordType
    name: Token | None = None
    body: Token | None = None
    members: list[Variable] | None = None
    typedefs: list[Variable] | None = None
    vardefs: list[Variable] | None = None
    preComment: Token | None = None
    postComment: Token | None = None
    nested: 'list[RecordParts] | None' = None
    parent: 'RecordParts | None' = None

    @staticmethod
    def fromStatement(st: Statement) -> 'RecordParts | None':
        tokens = st.tokens
        ret = RecordParts(RecordType.UNDEF)

        ret.preComment, i = get_pre_comment(tokens)

        for i in range(i, len(tokens)):
            token = tokens[i]
            if token.value == "typedef":
                ret.typedefs = []
            elif token.value == "struct":
                ret.type = RecordType.STRUCT
            elif token.value == "union":
                ret.type = RecordType.UNION
            elif token.value == "enum":
                ret.type = RecordType.ENUM
            elif token.value in c_type_keywords:
                pass
            elif reg_identifier.match(token.value):
                ret.name = token
            elif token.value[0] == "{":
                ret.body = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                break
            elif token.value[0] in [";", ","]:
                return None

        if not ret.body:
            return None

        # vars or types list
        names: list[Variable] = []
        if ret.name is None:
            ret.name = Token(ret.body.idx, ret.body.range, f"({common.parsing_file}:{ret.body.range[0]}-{ret.body.range[1]})")
        for stt in StatementList.xFromTokens(TokenList(tokens[i+1:])):
            var = Variable.fromVarDef(stt.tokens)
            if var:
                var.type = TokenList([ret.name])
                names.append(var)

        if ret.typedefs is not None:
            ret.typedefs = names
        else:
            ret.vardefs = names

        ret.postComment = get_post_comment(tokens)

        return ret

    def _xGetMembers(self) -> Iterable[Variable]:
        if not self.body:
            return
        saved_type: Any = None
        var: Variable | None
        for st in StatementList.xFromText(self.body.value):
            if st.type == StatementType.PREPROC:
                continue

            if st.type == StatementType.RECORD:
                record = RecordParts.fromStatement(st)
                if record:
                    if self.nested is None:
                        self.nested = []
                    self.nested.append(record)
                    record.parent = self
                    record.getMembers()
                    if record.vardefs:
                        for var in record.vardefs:
                            yield var
                continue

            var = Variable.fromVarDef(st.tokens)
            if var:
                if not var.type:
                    var.type = saved_type
                yield var
                saved_type = var.type if var.end == "," else None
            else:
                saved_type = None

    def getMembers(self) -> list[Variable]:
        if self.members is None:
            self.members = list(self._xGetMembers())
        return self.members

