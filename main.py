"""
This script parses (recursively) a directory of markdown files and extracts
flashcard formatted text from them, which are then converted to rendered Anki
cards.

## Core formats

Inline flashcards have the front and back separated by a separator, e.g. `==>`.
- There must be text following the separator to be considered a valid flashcard.
- If there are only tags (`#tag-content`) after the separator, it is considered
empty.
```
This is the front ==> this is the back          [VALID]
- List items are ==> also supported #and-tags   [VALID]
- This is considered empty ==>                  [INVALID]
- This is empty ==> #tag-content                [INVALID]
```

List flashcards have the front ending with the separator, then followed by a
list of back items, each on a new line.
- There must be no text after the separator (except for tags).
```
- This is the front ==> #tag-content
    - These are the back items
        - All children (and sub-children) are part of the back
    - This is another back item
```

File flashcards have the front and back separated by a newline-surrounded separator,
e.g. `\n---\n`.
- The file must contain a tag in the yaml front-matter to be considered a card.
```
---
tags: card
---

This is the front

All paragraphs
- and content.

---

This is the back.

All paragraphs
- and content.
```

Cloze flashcards are a line of text with the back wrapped by syntax, e.g.
`~~back~~`.
```
This is the front, with the ~~back~~ hidden in a cloze.
```

## Additional sugar

- The separator supports forward, backward, and bi-directional cards, using
symbols `==>`, `<==`, and `<==>`, respectively. These will determine the order
of front and back, or use the "Reversed" card type in Anki that creates a card
for both directions.
- If the tag `#incremental` is used in a list flashcard, all top-level back
items will get their own cloze card where all other items are shown.
    ```
    - This is the front ==> #incremental
        - This is the first back item
        - ~~Each back item gets its own cloze card~~
        - This is a third back item
    ```
- All heading levels are included in the card front as prefixed context.
- If the inline or list flashcard is itself part of a list, then all ancestors
  are also included in the card front after the heading context.
- If an inline or list flashcard is part of a file flashcard, all file front
  content is added as context to the card front.
- Math expressions (wrapped in `$...$` or `$$...$$`) are preserved without
  parsing for card separators.
- Markdown and latex formatting is rendered for the final Anki card.
"""

import re
from copy import copy, deepcopy
from typing import Annotated

import genanki
import rich
import yaml
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins import dollarmath, front_matter
from pydantic import BaseModel, BeforeValidator

from enum import Enum

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

md = (
    MarkdownIt("commonmark")
    .use(dollarmath.dollarmath_plugin, double_inline=True, allow_space=False)
    .use(front_matter.front_matter_plugin)
)


def read_file(file_path: str) -> tuple[str, list[Token], set[str]]:
    """
    Read a markdown file, return its text content, token stream, and list of
    tags from front matter if present.
    """

    with open(file_path, "r") as f:
        text = f.read()

    tokens = md.parse(text)
    tokens = [
        t for t in tokens
        if not (t.type in ('html_inline', 'html_block') and t.content.strip().startswith('<!--'))
    ]

    tags = set()
    if tokens[0].type == 'front_matter':
        front_matter = tokens.pop(0)
        tags = set(yaml.safe_load(front_matter.content).get('tags', []))

    # Add index to token metadata
    for i, token in enumerate(tokens):
        token.meta['index'] = i

    return text, tokens, tags


def render(list_of_tokens: list[Token]) -> str:
    r"""
    Render a list of markdown tokens into HTML, wrapping math spans with \( or
    \[ as needed based on their display class. Used for final Anki card
    rendering.
    """
    soup = BeautifulSoup(md.renderer.render(list_of_tokens, md.options, {}), "html.parser")
    # Wrap math spans with \( or \[ as needed based on class
    for math_elem in soup.find_all(['div', 'span'], class_="math"):
        if "block" in math_elem["class"]:
            math_elem.string = f"\\[ {math_elem.string} \\]"
        else:
            math_elem.string = f"\\( {math_elem.string} \\)"
    return f"\n{str(soup)}\n"


def field_dict_to_list(field_dict: dict, model: genanki.Model) -> list:
    """ Uses the field order from a model to convert a field dict to a list. """
    return [field_dict.get(field["name"], "") for field in model.fields]


def parse_regions_of_interest(
    tokens: list[Token],
) -> tuple[list[IndexCard], list[IndexCloze]]:
    """
    Parse a list of tokens to find token indices that represent potential
    flashcards. Used for downstream extraction of inline- and list- cards.
    """

    card_indices: list[IndexCard] = []
    cloze_indices: list[IndexCloze] = []

    for i, token in enumerate(tokens):
        if token.type == "list_item_open":
            # Find next first inline token
            for j in range(i + 1, len(tokens)):
                if (inline := tokens[j]).type == "inline":
                    # Check if any of the level 0 children contain the symbol
                    for k, child in enumerate(inline.children):
                        if child.type == "text" and child.level == 0:
                            if INLINE_SYMBOL["forward"] in child.content:
                                direction = SymbolDirection.FORWARD
                            elif INLINE_SYMBOL["backward"] in child.content:
                                direction = SymbolDirection.BACKWARD
                            elif INLINE_SYMBOL["bidirectional"] in child.content:
                                direction = SymbolDirection.BIDIRECTIONAL
                            else:
                                continue

                            # Found the symbol
                            # print("Found symbol in list item:", tokens[i:j+1])
                            # print("List item index:", i)
                            # print("Inline token index:", j)
                            # print("Symbol child index:", k)

                            # Find where the list item closes, must be at the same level
                            for l in range(j + 1, len(tokens)):
                                if tokens[l].type == "list_item_close" and tokens[l].level == tokens[i].level:
                                    # Reached the end of the list item
                                    # print("List item close token index:", l)
                                    break

                            card_indices.append(IndexCard(
                                list_open_token_index=i,
                                inline_token_index=j,
                                symbol_child_index=k,
                                symbol_direction=direction,
                                list_close_token_index=l
                            ))

                            break

                    # Check if we have a cloze within the inline token.
                    #
                    # TODO: For now, to support rich content within the cloze,
                    # we look at the entire un-rendered inline token context,
                    # but this could be improved for safety. Check for the cloze
                    # symbol
                    cloze_pattern = re.compile(r"~~(\S(?:.*?\S)?)~~")
                    if cloze_pattern.search(inline.content):
                        clozed_content = cloze_pattern.sub(r"{{c0:: \1 }}", inline.content)
                        # Replace the "c0" index with incrementing indices
                        m = 1
                        while (match := re.search(r"{{c(0)::", clozed_content)):
                            clozed_content = clozed_content[0:match.start(1)] + str(m) + clozed_content[match.end(1):]
                            m += 1

                        clozed_tokens = md.parseInline(clozed_content)
                        cloze_indices.append(IndexCloze(
                            list_open_token_index=i,
                            inline_token_index=j,
                            clozed_tokens=clozed_tokens
                        ))

                elif tokens[j].type in ["list_item_close", "bullet_list_open", "ordered_list_open"]:
                    # Reached the end of the list item without finding the symbol
                    break


    return card_indices, cloze_indices


def incrementalize(
    front_tokens: list[Token],
    back_tokens: list[Token],
    tags: set[str] = set(),
    context: str = '',
) -> genanki.Note:
    # We create cloze cards for each of the top-level list items in the back,
    # rather than a basic front/back card.
    #
    # A cloze card just wraps each of the top-level list items with
    # `{{c1:: ... }}`, where the index increments for each item.
    #
    # We'll loop through the tokens in the back.
    back_tokens = deepcopy(back_tokens)
    current_nesting = 0
    current_cloze_index = 1
    for j, token in enumerate(back_tokens):
        if token.type == "list_item_open":
            current_nesting += 1
        if current_nesting > 0:
            if token.type == 'inline':
                cloze_start = Token(type='text', content=r'{{' + f"c{current_cloze_index}:: ", tag='', nesting=0)
                cloze_end = Token(type='text', content=r' }}', tag='', nesting=0)
                token.children.insert(0, cloze_start)
                token.children.append(cloze_end)
        if token.type == "list_item_close":
            current_nesting -= 1
            if current_nesting == 0:
                # Increment the cloze index for the next top-level list item
                current_cloze_index += 1

    cloze_card = genanki.Note(
        model=genanki.CLOZE_MODEL,
        fields=field_dict_to_list({
            'Text': context + render(front_tokens + back_tokens),
        }, genanki.CLOZE_MODEL),
        tags=tags,
    )

    return cloze_card


def find_prior_context(
    tokens: list[Token],
    list_open_token_index: int,
) -> list[Token]:
    """
    Find the context tokens prior to the given list open token, consisting of
    headings and ancestors of the list item.
    """
    # Add context to the front tokens. If front token is in a list (level > 0),
    # then we go up the tokens until we find root level. We can iterate
    # backwards through the tokens, only adding tokens that have a lower level
    # than the minimum we've currently seen.
    context_tokens = []
    min_level = tokens[list_open_token_index].level
    list_search = True
    in_heading = False
    min_heading = 6
    for token in tokens[list_open_token_index-1:None:-1]:
        if list_search:
            # Only add tokens at a lower indent level than the last seen list
            # item.
            if token.level <= min_level:
                context_tokens.append(token)

            if token.type == "list_item_open":
                min_level = token.level

            if token.level == 0:
                list_search = False
        else:
            # Heading search
            if token.type == 'heading_close':
                heading_level = int(token.tag[1]) # e.g. 'h2' -> 2
                if heading_level < min_heading:
                    in_heading = True
                    min_heading = heading_level

            if in_heading:
                context_tokens.append(token)

            if token.type == 'heading_open':
                in_heading = False

    context_tokens.reverse()
    return context_tokens


def extract_cards(file_path: str) -> list[genanki.Note]:
    """
    Parse a markdown file and return a list of Anki notes.
    """

    notes = []

    text, tokens, tags = read_file(file_path)
    context_filepath: str = '' # TODO: Add filepath breadcrumbs to context. Needs to define the root folder.
    context = context_filepath

    # First, check for file flashcards
    if "card" in tags:
        # Split the text at the card split symbol
        front_text, back_text = re.split(FILE_SPLIT_PATTERN, text, maxsplit=3)[2:]

        front_tokens = md.parse(front_text)
        back_tokens = md.parse(back_text)

        # Incremental tags
        if 'incremental' in tags:
            notes.append(incrementalize(front_tokens, back_tokens, tags=tags - {'incremental'}, context=context))
        else:
            notes.append(genanki.Note(
                model=genanki.BASIC_MODEL,
                fields=field_dict_to_list({
                    'Front': context + render(front_tokens),
                    'Back': render(back_tokens),
                }, genanki.BASIC_MODEL),
                tags=tags,
            ))

        context_file_front = render(front_tokens)
        context += context_file_front

    # Now check for inline and list flashcards. First we'll parse the tokens for
    # regions of interest, then extract the cards and context from those
    # regions.
    card_indices, cloze_indices = parse_regions_of_interest(tokens)

    for region in card_indices:
        # Let's look at the inline token and see if it is an inline card or a list
        # card. Check for content after the symbol that isn't a tag.
        inline_token = tokens[region.inline_token_index]
        child = inline_token.children[region.symbol_child_index]
        left_text, right_text = (child.content).split(INLINE_SYMBOL[region.symbol_direction], 1)

        # Extract tags
        tag_pattern = r"#([\w/][\w/-]*\w)"
        tags = re.findall(tag_pattern, right_text)
        # Is there any content if the tags are removed?
        content_without_tags = re.sub(tag_pattern, '', inline_token.content.split(INLINE_SYMBOL[region.symbol_direction], 1)[1]).strip()
        # print(f"Right content after symbol: {right_text}")
        # print(f"Content without tags: {content_without_tags}")

        if (not content_without_tags):
            # This is a list card. Let's check for the nested bullet list. If there
            # is none before the list close token, then this is an invalid card and
            # is ignored.
            # print(f"List card found from {region.list_open_token_index} to {region.list_close_token_index}")

            for j in range(region.list_open_token_index + 1, region.list_close_token_index):
                if tokens[j].type == "bullet_list_open":
                    # Found a nested bullet list, this is a valid list card
                    # print("Nested bullet list found at index:", j)
                    break
            else:
                # No nested bullet list found, this is an invalid card
                # print("No nested bullet list found, ignoring this card.")
                continue

            front_tokens = tokens[region.list_open_token_index:region.inline_token_index + 1]
            back_tokens = tokens[region.inline_token_index + 1:region.list_close_token_index + 1]

        else:
            # This is an inline card. The front and back are based on splitting the
            # inline content at the symbol. The front content is all tokens leading
            # up to the child, and the back is all tokens after the child.
            left_child, right_child = copy(child), copy(child)
            left_child.content = left_text
            right_child.content = right_text
            front_children = inline_token.children[:region.symbol_child_index] + [left_child]
            back_children = [right_child] + inline_token.children[region.symbol_child_index + 1:]
            front_inline = copy(inline_token)
            back_inline = copy(inline_token)
            front_inline.children = front_children
            back_inline.children = back_children
            front_tokens = tokens[region.list_open_token_index:region.inline_token_index] + [front_inline]
            back_tokens = [back_inline]

        # Get higher order headings and list items as front context.
        context_tokens = find_prior_context(tokens, region.list_open_token_index)

        # TODO: Support directional cards, back-to-front and bi-directional. For
        # now, everything gets treated as front-to-back.
        front_tokens = context_tokens + front_tokens

        # If we have an incremental tag, we create a cloze for each list item.
        if 'incremental' in tags:
            notes.append(incrementalize(
                front_tokens, back_tokens,
                tags=tags - {'incremental'},
                context=context
            ))

        else:
            notes.append(genanki.Note(
                model=genanki.BASIC_MODEL,
                fields=field_dict_to_list({
                    'Front': context + render(front_tokens),
                    'Back': render(back_tokens),
                }, genanki.BASIC_MODEL),
                tags=set(tags),
            ))

    for region in cloze_indices:
        # Get higher order headings and list items as front context.
        context_tokens = find_prior_context(tokens, region.list_open_token_index)

        # The final tokens are the context, list open until inline, and the
        # modified clozed inline token.
        text_tokens = context_tokens + tokens[region.list_open_token_index:region.inline_token_index] + region.clozed_tokens

        # Add the cloze card
        notes.append(genanki.Note(
            model=genanki.CLOZE_MODEL,
            fields=field_dict_to_list({
                'Text': context + render(text_tokens),
            }, genanki.CLOZE_MODEL),
            tags=tags,
        ))

    return notes

# TODO: Finish genanki deck creation and export.
