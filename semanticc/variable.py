from dataclasses import dataclass
from copy import deepcopy

from .common import *
from .ctoken import *
from .statement import *

@dataclass
class Variable:
    name: Token
    type: TokenList
    preComment: Token | None = None
    postComment: Token | None = None
    end: str | None = None

    # Get the vatiable name and type from C declaration or argument list.
    @staticmethod
    def fromVarDef(vardef: TokenList) -> 'Variable | None':
        """Get the variable name from C declaration."""
        if vardef == 1 and vardef[0] in ["...", "void"]:
            return None
        tokens = vardef.filterCode()
        # find some words, skip standalone []s and *s
        while tokens and not regex.search(r"\w", tokens[-1].value):
            tokens.pop()
        # skip function arguments
        if tokens and tokens[-1].value[0].startswith("("):
            tokens.pop()
        # find some words, skip standalone []s and *s
        while tokens and not regex.search(r"\w", tokens[-1].value):
            tokens.pop()

        # The last token contains the arg name
        if not tokens:
            return None
        name = deepcopy(tokens.pop())
        name.value = regex.sub(r"\W+", "", name.value)

        # Remove C keywords from type
        type = TokenList((filter(lambda x: x.value not in c_type_keywords, tokens)))

        end = None
        for token in reversed(vardef):
            if token.value[0] in [" ", "\t", "\n", "/"]:
                continue
            end = token.value if token.value in [",", ";"] else None
            break

        return Variable(name, type, get_pre_comment(vardef)[0], get_post_comment(vardef), end)
