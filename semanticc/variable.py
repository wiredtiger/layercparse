from dataclasses import dataclass
from copy import deepcopy
import itertools
import regex
from .ctoken import *

def get_base_type(clean_tokens: TokenList) -> str:
    type = TokenList((filter(lambda x: x.value not in c_type_keywords and x.value != "*", clean_tokens)))
    return type[-1].value if type else ""

@dataclass
class Variable:
    name: Token
    typename: TokenList
    preComment: Token | None = None
    postComment: Token | None = None
    end: str | None = None

    def short_repr(self) -> str:
        return f"Variable({self.name} : {self.typename})"

    def update(self, other: 'Variable') -> list[str]:
        errors = []
        if self.name != other.name:
            errors.append(f"ERROR: variable name mismatch for {self.name.value}: {self.name.value} != {other.name.value}")
        if self.typename != other.typename:
            errors.append(f"ERROR: variable type mismatch for {self.name.value}: {self.typename} != {other.typename}")
        if self.preComment is None:
            self.preComment = other.preComment
        if self.postComment is None:
            self.postComment = other.postComment
        return errors

    # Get the variable name and type from C declaration or argument list. TODO: do proper parsing
    @staticmethod
    def fromVarDef(vardef: TokenList) -> 'Variable | None':
        """Get the variable name from C declaration."""
        clean_tokens = list(itertools.takewhile(
            lambda x: x.value[0] not in ["=", "+", "-", "/", "%", ">", "<", "!", "&", "|", "^", "~", "?", ":", ",", ";"],
            vardef.xFilterCode()))
        if len(clean_tokens) == 1 and clean_tokens[0].value in ["...", "void"]:
            return None
        # find some words, skip standalone []s and *s
        while clean_tokens and clean_tokens[-1].value[0] in ["*", "["]:
            clean_tokens.pop()
        # skip function arguments
        if clean_tokens and clean_tokens[-1].value[0].startswith("("):
            clean_tokens.pop()
        # find some words, skip standalone []s and *s
        while clean_tokens and clean_tokens[-1].value[0] in ["*", "["]:
            clean_tokens.pop()

        # The last token contains the arg name
        if not clean_tokens:
            return None
        name = deepcopy(clean_tokens.pop())
        name.value = regex.sub(r"\W+", "", name.value)

        # Remove C keywords from type
        type = TokenList((filter(lambda x: x.value not in c_type_keywords and x.value != "*", clean_tokens)))

        end = None
        for token in reversed(vardef):
            if token.value[0] in [" ", "\t", "\n", "/"]:
                continue
            end = token.value if token.value in [",", ";"] else None
            break

        return Variable(name, type, get_pre_comment(vardef)[0], get_post_comment(vardef), end)

