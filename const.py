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
    css='''
.card {
  font-family: arial;
  font-size: 20px;
  text-align: center;
  color: black;
  background-color: white;
}
.context {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
}
.filepath {
  font-family: monospace;
  color: #888;
}
.context {
  margin-top: 5px;
}
.front, .back {
  text-align: left;
}
'''
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
    css='''
.card {
  font-family: arial;
  font-size: 20px;
  text-align: center;
  color: black;
  background-color: white;
}
.context {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
}
.filepath {
  font-family: monospace;
  color: #888;
}
.context {
  margin-top: 5px;
}
.front, .back {
  text-align: left;
}
'''
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
<div class="cloze">{{cloze:Text}}</div>
''',
            'afmt': '''
<div class="context">
{{#FilePath}}<div class="filepath">{{FilePath}}</div>{{/FilePath}}
{{#Context}}<div class="context">{{Context}}</div>{{/Context}}
</div>
<div class="cloze">{{cloze:Text}}</div>
''',
        },
    ],
    css='''
.card {
  font-family: arial;
  font-size: 20px;
  text-align: center;
  color: black;
  background-color: white;
}
.context {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
  padding-bottom: 5px;
}
.filepath {
  font-family: monospace;
  color: #888;
}
.context {
  margin-top: 5px;
}
.cloze {
  text-align: left;
}
.cloze .cloze-inactive {
  color: #0066cc;
}
'''
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
