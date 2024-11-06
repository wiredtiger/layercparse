from dataclasses import dataclass
from copy import deepcopy
import itertools
import regex
from .ctoken import *
from .statement import clean_tokens_decl, scan_defn_ctype
from .workspace import scope, Scope

def get_base_type(clean_tokens: TokenList) -> str:
    type = TokenList((filter(lambda x:
                x.value not in c_type_keywords and x.value != "*", clean_tokens)))
    return type[-1].value if type else ""

def get_base_type_str(clean_txt: str, **kwargs) -> str:
    return get_base_type(TokenList(TokenList.xxFilterCode(TokenList.xFromText(
                clean_txt, base_offset=0, **kwargs))))

@dataclass
class Variable:
    name: Token
    typename: TokenList
    preComment: Token | None = None
    postComment: Token | None = None
    end: str | None = None
    scope: Scope = field(default_factory=Scope.empty, repr=False)

    def __post_init__(self):
        self.scope = scope()

    def short_repr(self) -> str:
        return f"Variable({self.name} : {self.typename})"

    def kind(self) -> str:
        return "variable"

    def update(self, other: 'Variable') -> list[str]:
        errors = []
        if self.name != other.name:
            errors.append(f"variable name mismatch for '{self.name.value}': "
                          f"'{self.name.value}' != '{other.name.value}'")
        if self.typename != other.typename:
            errors.append(f"variable type mismatch for '{self.name.value}': "
                          f"'{self.typename}' != '{other.typename}'")
        if self.preComment is None:
            self.preComment = other.preComment
        if self.postComment is None:
            self.postComment = other.postComment
        return errors

    # Get the variable name and type from C declaration.
    @staticmethod
    def fromVarDef(vardef: TokenList) -> 'Variable | None':
        """Get the variable name and type from C declaration."""
        clean_tokens = vardef.filterCode()
        for i in range(1, len(clean_tokens)-1):
            if clean_tokens[i].value == "=":
                clean_tokens = TokenList(clean_tokens[:i])
                break
        if not clean_tokens or (len(clean_tokens) == 1 and
                                clean_tokens[0].value in ["...", "void"]):
            return None
        # find some words, skip standalone []s and *s
        while clean_tokens and clean_tokens[-1].value.startswith(("*", "[")):
            clean_tokens.pop()
        # skip function arguments
        is_func_ptr = False
        if clean_tokens and clean_tokens[-1].value[0].startswith("("):
            clean_tokens.pop()
            is_func_ptr = True
        # find some words, skip standalone []s and *s
        while clean_tokens and clean_tokens[-1].value.startswith(("*", "[")):
            clean_tokens.pop()

        # The last token contains the arg name
        if not clean_tokens:
            return None

        name = deepcopy(clean_tokens.pop())
        name.value = regex.sub(r"\W+", "", name.value)
        # if clean_tokens[-1].getKind() == "(": # Function pointer
        #     # TODO: Work-around this:
        #     # uint32_t (*wiredtiger_crc32c_func(void))(const void *, size_t)
        #     # where it reads as:
        #     # wiredtiger_crc32c_func is function
        #     #   taking no arguments
        #     #   returning a pointer to a function
        #     #     taking const void *, size_t
        #     #     returning uint32_t
        #     if inner := Variable.fromVarDef(TokenList.fromText(clean_tokens[-1].value[1:-1],
        #                                                    base_offset=clean_tokens[-1].range[0])):
        #         name = inner.name
        #     clean_tokens.pop()
        # else:
        #     name = deepcopy(clean_tokens.pop())
        #     name.value = regex.sub(r"\W+", "", name.value)

        # Remove C keywords from type
        type = TokenList((filter(lambda x:
                    x.value not in c_type_keywords and x.value != "*", clean_tokens)))

        end = None
        for token in reversed(vardef):
            if token.getKind() in [" ", "/"]:
                continue
            end = token.value if token.value in [",", ";"] else None
            break

        return Variable(name, type, get_pre_comment(vardef)[0], get_post_comment(vardef), end)

    # Get the variable name and type from function argument list.
    @staticmethod
    def fromFuncArg(vardef: TokenList) -> 'Variable | None':
        """Get the variable name and type from C declaration."""

        clean_tokens = clean_tokens_decl(vardef.filterCode())

        type, i, token = scan_defn_ctype(clean_tokens)

        if i >= len(clean_tokens):
            return Variable(Token.empty(), type) if type else None
        if token:
            return Variable(token, type)

        # Now we are at something that is not a word
        # Should be either * or [] or ()

        for i in range(i, len(clean_tokens)):
            token = clean_tokens[i]
            if token.value == "*":
                continue
            if token.getKind() == "w":
                return Variable(token, type)
            if token.getKind() == "(":
                for token in reversed(
                        clean_tokens_decl(
                            TokenList(TokenList.xxFilterCode(
                                TokenList.xFromText(
                                    token.value[1:-1], base_offset=token.range[0]))))):
                    if token.getKind() == "w":
                        return Variable(token, type)
                break
            break

        # Fallback
        return Variable(Token.empty(), type) if type else None


# Variants of variable declarations:
#
# typedef int A;
# typedef char B;
#
# static A a;
#
# static A(b); // wrong
# static A b;  // right
#
# static A(bb)(void); // wrong
# static A bb(void);  // right
#
# static A(*c); // wrong
# static A *c;  // right
#
# static A fn1(B);
#
# static A (*fn2)(B);
#
# static A (*fn3(void))(B);



