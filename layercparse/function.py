from typing import Iterable, Any
from dataclasses import dataclass

from .internal import *
from .ctoken import *
from .statement import *
from .variable import *
from .record import *
from .workspace import scope, Scope

@dataclass
class FunctionParts:
    typename: TokenList
    name: Token
    args: Token
    body: Token | None = None
    preComment: Token | None = None
    postComment: Token | None = None
    is_type_const: bool = False
    is_type_static: bool = False
    scope: Scope = field(default_factory=Scope.empty, repr=False)

    def __post_init__(self):
        self.scope = scope()

    def short_repr(self) -> str:
        ret = f"Function({self.name} ({self.args})) : {self.typename}"
        if self.is_type_const:
            ret = ret + " const"
        if self.is_type_static:
            ret = ret + " static"
        return ret

    def kind(self) -> str:
        return "function"

    def update(self, other: 'FunctionParts') -> list[str]:
        errors = []
        if self.typename != other.typename:
            errors.append(f"function retType mismatch for '{self.name.value}': "
                          f"'{self.typename.short_repr()}' != '{other.typename.short_repr()}'")
        if self.name.value != other.name.value:
            errors.append(f"function name mismatch for '{self.name.value}': "
                          f"'{self.name.value}' != '{other.name.value}'")
        if self.args.value != other.args.value:
            errors.append(f"function args mismatch for '{self.name.value}': "
                          f"'{self.args.value}' != '{other.args.value}'")
        if self.body is not None and other.body is not None and self.body.value != other.body.value:
            errors.append(f"function redifinition: '{self.name.value}'")
        if self.preComment is None:
            self.preComment = other.preComment
        if self.postComment is None:
            self.postComment = other.postComment
        return errors

    @staticmethod
    def fromStatement(statement: Statement) -> 'FunctionParts | None':
        preComment, _ = get_pre_comment(statement.tokens)
        postComment = get_post_comment(statement.tokens)

        clean_tokens = clean_tokens_decl(statement.tokens.filterCode(), clean_static_const=False)

        retType, i, name = scan_defn_ctype(clean_tokens, ignore_static_const=False)
        if not retType or i >= len(clean_tokens) or name:  # having name means it's not a function
            return None

        # Now we are at something that is not a word
        # Should be either * or [] or ()

        # Skip stars and find the name
        for i in range(i, len(clean_tokens)):
            if clean_tokens[i].value == "*":
                continue
            break
        else:
            return None

        # It must be () and the last word of type is the function name
        token = clean_tokens[i]
        if token.getKind() == "w":
            name = token
            # Find a ()
            for i in range(i+1, len(clean_tokens)):
                token = clean_tokens[i]
                if token.getKind() == "(":
                    break
            else:
                return None
        elif token.getKind() != "(":
            return None

        # It's a ().
        # Now find out if it's an arguments list or a function pointer
        argsList = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])

        body: Token | None = None
        if not name:
            # If there are more ()s at this level, it's a function pointer and args are somewhere else
            for i in range(i+1, len(clean_tokens)):
                token = clean_tokens[i]
                if token.getKind() == "(":
                    # Found another (), so the first one was a function pointer and this is the args
                    for token in reversed(
                            clean_tokens_decl(
                                TokenList(TokenList.xxFilterCode(
                                    TokenList.xFromText(
                                        argsList.value, base_offset=argsList.range[0]))))):
                        if token.getKind() == "w":
                            name = token
                            break
                    else: # Not break
                        name = Token.empty()
                    argsList = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                    break
                if token.getKind() == "{":
                    body = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
            else: # not break
                # The name is the last word of the type
                name = retType.pop()

        # Finish scanning if there's no body
        if not body:
            for i in range(i+1, len(clean_tokens)):
                token = clean_tokens[i]
                if token.getKind() == "{":
                    body = Token(token.idx, (token.range[0]+1, token.range[1]-1), token.value[1:-1])
                    break

        is_type_const, is_type_static = False, False
        i = 0
        while i < len(retType):
            match retType[i].value:
                case "const":
                    is_type_const = True
                    retType.pop(i)
                case "static":
                    is_type_static = True
                    retType.pop(i)
                case _:
                    i += 1

        return FunctionParts(retType,
                             name, # type: ignore[arg-type] # name is guaranteed to be a Token
                             argsList,
                             body,
                             preComment=preComment,
                             postComment=postComment,
                             is_type_const=is_type_const, is_type_static=is_type_static)

    def xGetArgs(self) -> Iterable[Variable]:
        for stt in StatementList.xFromText(self.args.value, base_offset=self.args.range[0]):
            var = Variable.fromFuncArg(stt.tokens)
            if var:
                yield var
    def getArgs(self) -> list[Variable]:
        return list(self.xGetArgs())


    def xGetLocalVars(self, _globals: 'Codebase | None' = None) -> Iterable[Variable]: # type: ignore[name-defined] # error: Name "Codebase" is not defined (circular dependency)
        if not self.body:
            return
        saved_type: Any = None
        for st in StatementList.xFromText(self.body.value, base_offset=self.body.range[0]):
            t = st.getKind()
            if (not saved_type and not t.is_decl and (
                    t.is_statement or
                    (t.is_expression and not t.is_initialization))):
                break
            if saved_type or (t.is_decl and not t.is_function and not t.is_record):
                var = Variable.fromVarDef(st.tokens)
                if var:
                    if not var.typename:
                        var.typename = saved_type
                    yield var
                    saved_type = var.typename if var.end == "," else None
            else:
                saved_type = None
                if t.is_record:
                    with ScopePush(offset=self.body.range[0]):
                        record = RecordParts.fromStatement(st)
                    if record:
                        if _globals:
                            _globals.addRecordDesc(record, is_global_scope=False)
                        if record.vardefs:
                            yield from record.vardefs

    def getLocalVars(self, _globals: 'Codebase | None' = None) -> list[Variable]: # type: ignore[name-defined] # error: Name "Codebase" is not defined (circular dependency)
        return list(self.xGetLocalVars(_globals))
