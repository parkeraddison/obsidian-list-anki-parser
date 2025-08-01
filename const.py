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
.cloze, .cloze-inactive {
    background-color: hsl(var(--accent-hsl) / 0.1);
    border-radius: 4px;
    padding: 2px 4px;
}
.cloze {
    color: hsl(var(--accent-hsl));
}
ul {
    list-style: disc;
    position: relative;
    padding-left: 0;
    margin-left: 1.5em;
}
ul li {
    position: relative;
    margin-top: 0.25em;
}
ul li::marker {
    color: var(--tertiary);
}
ul li:has(li)::before {
    content: '';
    position: absolute;
    left: -14px;
    top: 20px;
    bottom: 0px;
    width: 1px;
    background: var(--tertiary);
}
.math {
    display: inline;
}
code {
    background: hsl(0 0% 0% / 0.3);
    border-radius: 4px;
    padding: 2px 4px;
}
.formatting {
    color: var(--tertiary);
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
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Front}}
<hr>
''',
            'afmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Front}}
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
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Front}}
<hr>
''',
            'afmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Front}}
<hr id="answer">
<div class="back">{{Back}}</div>
''',
        },
        {
            'name': 'Card 2',
            'qfmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Front}}
<hr>
''',
            'afmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Front}}
<hr id="answer">
<div class="back">{{Back}}</div>
''',
        },
        {
            'name': 'Card 2',
            'qfmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Back}}
<hr>
''',
            'afmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{Back}}
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
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
{{cloze:Text}}
''',
            'afmt': '''
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}{{Context}}{{/Context}}
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
