"""
Constants and data models for the Anki card extraction system.
"""

import re
from enum import Enum
from typing import list

from markdown_it.token import Token
from pydantic import BaseModel


FILE_SPLIT_PATTERN = re.compile(r"---\n")
INLINE_SYMBOL = {
    "forward": "==>",
    "backward": "<==",
    "bidirectional": "<==>",
}


class SymbolDirection(str, Enum):
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"


class IndexCard(BaseModel):
    """ Represents a potential flashcard when scanning the document. """
    list_open_token_index: int
    inline_token_index: int
    symbol_child_index: int
    symbol_direction: SymbolDirection
    list_close_token_index: int


class IndexCloze(BaseModel):
    list_open_token_index: int
    inline_token_index: int
    clozed_tokens: list[Token]
