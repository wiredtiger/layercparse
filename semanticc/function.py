from typing import Iterable, Any
from dataclasses import dataclass

from .internal import *
from .ctoken import *
from .statement import *
from .variable import *

@dataclass
class FunctionParts:
    retType: TokenList
    name: Token
    args: Token
    body: Token | None = None
    preComment: Token | None = None
    postComment: Token | None = None

    @staticmethod
    def fromStatement(statement: Statement) -> 'FunctionParts | None':
        i = 0
        tokens = statement.tokens

        preComment, i = get_pre_comment(tokens)

        # Return type, function name, function args
        retType = TokenList([])
        funcName = None
        argsList = None
        for i in range(i, len(tokens)):
            token = tokens[i]
            if token.value[0] == "(":
                if retType:
                    funcName = retType.pop()
                argsList = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                break
            if token.value[0] not in [" ", "\t", "\n", "#", "/"]:
                retType.append(token)
        if funcName is None or argsList is None:
            return None
        retType = TokenList((filter(lambda x: x.value not in c_type_keywords, retType)))

        # Function body
        funcBody = None
        for i in range(i+1, len(tokens)):
            token = tokens[i]
            if token.value[0] == "{":
                funcBody = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                break

        # Post-comment
        postComment = get_post_comment(tokens)

        return FunctionParts(retType, funcName, argsList, funcBody, preComment, postComment)

    def xGetArgs(self) -> Iterable[Variable]:
        for stt in StatementList.xFromText(self.args.value):
            var = Variable.fromVarDef(stt.tokens)
            if var:
                yield var
    def getArgs(self) -> list[Variable]:
        return list(self.xGetArgs())

    def xGetLocalVars(self) -> Iterable[Variable]:
        if not self.body:
            return
        saved_type: Any = None
        for st in StatementList.xFromText(self.body.value):
            t = st.getKind()
            if saved_type is None and (t.is_statement or (t.is_expression and not t.is_initialization)):
                break
            if saved_type is not None or t.is_decl:
                var = Variable.fromVarDef(st.tokens)
                if var:
                    if not var.type:
                        var.type = saved_type
                    yield var
                    saved_type = var.type if var.end == "," else None
            else:
                saved_type = None
    def getLocalVars(self) -> list[Variable]:
        return list(self.xGetLocalVars())
