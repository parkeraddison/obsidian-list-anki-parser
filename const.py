"""
Constants and data models for the Anki card extraction system.
"""

import re
from enum import Enum

import genanki
from markdown_it.token import Token
from pydantic import BaseModel


FILE_SPLIT_PATTERN = re.compile(r"---\n")
INLINE_SYMBOL = {
    "forward": "==>",
    "backward": "<==",
    "bidirectional": "<==>",
}


# Custom Anki Models with Context Fields
CARD_CSS = '''
.card {
  font-family: Inter, arial, sans-serif;
  font-size: 20px;
  color: black;
  background-color: white;
  text-align: left;
  --secondary: #444;
  --tertiary: #888;
  --accent-hsl: 210 100% 50%;
}
.card.nightMode  {
    --secondary: #bbb;
    --tertiary: #666;
    --accent-hsl: 210 100% 70%;
}
.filepath {
  font-family: monospace;
  font-size: 80%;
  color: var(--tertiary);
}
.context {
  /* color: var(--secondary); */
  padding-bottom: 5px;
}
.front ul, .front li {
    list-style-type: none;
}
.cloze {
    font-weight: bold;
    color: hsl(var(--accent));
}
.cloze-inactive {
    background-color: hsl(var(--accent-hsl), 0.1);
}
'''

# TODO: Make styling better, more similar to logseq-anki-sync where the content
# is basically all part of a list. Style the lists better, etc.
# https://github.com/debanjandhar12/logseq-anki-sync/blob/0dff5363f4f43267cc5ed417168823a0278355f8/src/templates/_logseq_anki_sync.scss


BASIC_CONTEXT_MODEL = genanki.Model(
    1874134123,  # Unique model ID
    'Basic with Context',
    fields=[
        {'name': 'FilePath'},
        {'name': 'Context'},
        {'name': 'Front'},
        {'name': 'Back'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="front">{{Front}}</div>
<hr>
''',
            'afmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="front">{{Front}}</div>
<hr id="answer">
<div class="back">{{Back}}</div>
''',
        },
    ],
    css=CARD_CSS
)

BASIC_AND_REVERSED_CONTEXT_MODEL = genanki.Model(
    1874134124,  # Unique model ID
    'Basic with Context (and reversed)',
    fields=[
        {'name': 'FilePath'},
        {'name': 'Context'},
        {'name': 'Front'},
        {'name': 'Back'},
    ],
    templates=[
        {
            'name': 'Card 1',
            'qfmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="front">{{Front}}</div>
<hr>
''',
            'afmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="front">{{Front}}</div>
<hr id="answer">
<div class="back">{{Back}}</div>
''',
        },
        {
            'name': 'Card 2',
            'qfmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="front">{{Back}}</div>
<hr>
''',
            'afmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="front">{{Back}}</div>
<hr id="answer">
<div class="back">{{Front}}</div>
''',
        },
    ],
    css=CARD_CSS
)

CLOZE_CONTEXT_MODEL = genanki.Model(
    1874134125,  # Unique model ID
    'Cloze with Context',
    fields=[
        {'name': 'FilePath'},
        {'name': 'Context'},
        {'name': 'Text'},
    ],
    templates=[
        {
            'name': 'Cloze',
            'qfmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
{{cloze:Text}}
''',
            'afmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
{{cloze:Text}}
''',
        },
    ],
    css=CARD_CSS
)


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
