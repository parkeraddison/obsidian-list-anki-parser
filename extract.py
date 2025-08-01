"""
Core extraction logic for parsing markdown files and extracting flashcards.

## Core formats

Inline flashcards have the front and back separated by a separator, e.g. `==>`.
These are converted to cloze cards where the back content is wrapped in cloze brackets.
- There must be text following the separator to be considered a valid flashcard.
- If there are only tags (`#tag-content`) after the separator, it is considered
empty.
```
This is the front ==> this is the back          [VALID - becomes cloze]
- List items are ==> also supported #and-tags   [VALID - becomes cloze]
- This is considered empty ==>                  [INVALID]
- This is empty ==> #tag-content                [INVALID]
```

List flashcards have the front ending with the separator, then followed by a
list of back items, each on a new line. These are converted to cloze cards
where each list item in the back is wrapped in cloze brackets.
- There must be no text after the separator (except for tags).
```
- This is the front ==> #tag-content
    - These are the back items (wrapped in {{c1:: ... }})
        - All children (and sub-children) are part of the back
    - This is another back item (also wrapped in {{c1:: ... }})
```

File flashcards have the front and back separated by a newline-surrounded separator,
e.g. `\n---\n`. These remain as basic front/back cards (not converted to cloze).
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
`~~back~~`. These are processed as traditional cloze cards.
```
This is the front, with the ~~back~~ hidden in a cloze.
```

## Additional sugar

- The separator supports forward, backward, and bi-directional cards, using
symbols `==>`, `<==`, and `<==>`, respectively. For cloze cards, these determine
which content gets the cloze brackets:
  - Forward (`==>`): back content gets cloze brackets
  - Backward (`<==`): front content gets cloze brackets
  - Bidirectional (`<==>`): same as forward (cloze cards don't support reversing)
- If the tag `#incremental` is used in a list flashcard, each top-level back
item gets its own incrementing cloze number (c1, c2, c3, etc.). Without this tag,
all items use the same cloze number (c1).
    ```
    - This is the front ==> #incremental
        - This is the first back item ({{c1:: ... }})
        - Each back item gets its own cloze card ({{c2:: ... }})
        - This is a third back item ({{c3:: ... }})
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
from pathlib import Path

import genanki
import yaml
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins import dollarmath, front_matter

from const import (BASIC_AND_REVERSED_CONTEXT_MODEL, BASIC_CONTEXT_MODEL,
                   CLOZE_CONTEXT_MODEL, FILE_SPLIT_PATTERN, INLINE_SYMBOL,
                   IndexCard, IndexCloze, SymbolDirection)

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

    html_content = str(soup)

    # Post-process to wrap symbols and tags with formatting spans
    # Wrap directional symbols (but not those already in spans)
    html_content = re.sub(r'(?<!>)(&lt;==&gt;|==&gt;|&lt;==)(?![^<]*</span>)', r'<span class="formatting">\1</span>', html_content)

    # Wrap tags (but not those already in spans)
    html_content = re.sub(r'(?<!>)(#[\w/][\w/-]*\w)(?![^<]*</span>)', r'<span class="formatting">\1</span>', html_content)

    return f"\n{html_content}\n"


def _field_dict_to_list(field_dict: dict, model: genanki.Model) -> list:
    """ Uses the field order from a model to convert a field dict to a list. """
    return [field_dict.get(field["name"], "") for field in model.fields]


def _build_filepath_context(file_path: str) -> str:
    """ Get the filepath relative to the vault root. """
    # TODO: For now, just return the filename. Add support for finding the vault
    # root.
    return Path(file_path).name


def _detect_symbol_direction(content: str) -> SymbolDirection | None:
    """Detect the direction symbol in text content and return the direction."""
    # Check bidirectional first since it contains both forward and backward symbols
    if INLINE_SYMBOL["bidirectional"] in content:
        return SymbolDirection.BIDIRECTIONAL
    elif INLINE_SYMBOL["forward"] in content:
        return SymbolDirection.FORWARD
    elif INLINE_SYMBOL["backward"] in content:
        return SymbolDirection.BACKWARD
    return None


def _parse_regions_of_interest(
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
                            direction = _detect_symbol_direction(child.content)
                            if direction is None:
                                continue

                            # Find where the list item closes, must be at the same level
                            for l in range(j + 1, len(tokens)):
                                if tokens[l].type == "list_item_close" and tokens[l].level == tokens[i].level:
                                    break

                            card_indices.append(IndexCard(
                                list_open_token_index=i,
                                inline_token_index=j,
                                symbol_child_index=k,
                                symbol_direction=direction,
                                list_close_token_index=l
                            ))
                            break

                    # Check if we have a cloze within the inline token
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


def _create_cloze_tokens(content: str, cloze_num: int, is_list_item: bool = False) -> tuple[Token, Token]:
    """Create cloze start and end tokens with appropriate spacing."""
    spacing = '' if is_list_item else ' '
    cloze_start = Token(type='text', content=f'{spacing}{{{{c{cloze_num}:: ', tag='', nesting=0)
    cloze_end = Token(type='text', content=' }}', tag='', nesting=0)
    return cloze_start, cloze_end


def _add_cloze_to_inline_token(token: Token, cloze_num: int, is_list_item: bool = False) -> None:
    """Add cloze brackets to an inline token's children."""
    if token.type == 'inline':
        cloze_start, cloze_end = _create_cloze_tokens('', cloze_num, is_list_item)
        token.children.insert(0, cloze_start)
        token.children.append(cloze_end)


def _create_cloze_card(
    front_tokens: list[Token],
    back_tokens: list[Token],
    symbol_direction: SymbolDirection,
    incremental: bool = False,
    tags: set[str] = set(),
    filepath_context: str = '',
    list_context: str = '',
) -> genanki.Note:
    """
    Create a cloze card from front and back tokens, handling directional symbols.

    For list cards, the back tokens contain the nested list items that will be clozed.
    For inline cards, the back tokens contain the inline content that will be clozed.
    For incremental cards, each top-level list item gets its own cloze number.
    For standard cards, all content uses the same cloze number (c1).
    For directional cards, cloze brackets are placed around the appropriate content.
    """
    is_inline_card = len(back_tokens) == 1 and back_tokens[0].type == 'inline'

    # Determine which tokens to use as context vs cloze content
    if symbol_direction == SymbolDirection.BACKWARD:
        context_tokens, cloze_tokens = deepcopy(back_tokens), deepcopy(front_tokens)
        if is_inline_card:
            # For backward inline cards, cloze the front content
            for token in reversed(cloze_tokens):
                if token.type == 'inline':
                    _add_cloze_to_inline_token(token, 1)
                    break
            final_tokens = cloze_tokens + context_tokens
        else:
            # For backward list cards, cloze the front content
            for token in cloze_tokens:
                if token.type == 'inline':
                    _add_cloze_to_inline_token(token, 1)
                    break
            final_tokens = cloze_tokens + context_tokens
    else:
        # Forward and bidirectional: cloze the back content
        context_tokens, cloze_tokens = deepcopy(front_tokens), deepcopy(back_tokens)

        if is_inline_card:
            # For inline cards, cloze the back content
            for token in cloze_tokens:
                if token.type == 'inline':
                    _add_cloze_to_inline_token(token, 1)
                    break
        else:
            # For list cards, add cloze brackets to each list item
            current_nesting = 0
            current_cloze_index = 1

            for token in cloze_tokens:
                if token.type == "list_item_open":
                    current_nesting += 1
                elif token.type == "list_item_close":
                    current_nesting -= 1
                    if current_nesting == 0 and incremental:
                        current_cloze_index += 1
                elif current_nesting > 0 and token.type == 'inline':
                    cloze_num = current_cloze_index if incremental else 1
                    _add_cloze_to_inline_token(token, cloze_num, is_list_item=True)

        final_tokens = context_tokens + cloze_tokens

    return genanki.Note(
        model=CLOZE_CONTEXT_MODEL,
        fields=_field_dict_to_list({
            'Text': list_context + render(final_tokens),
            'FilePath': filepath_context,
        }, CLOZE_CONTEXT_MODEL),
        tags=tags,
    )


def _find_prior_context(
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
    min_level = tokens[list_open_token_index].level - 1
    list_search = True
    in_heading = False
    min_heading = 6
    skipping = False

    for token in tokens[list_open_token_index-1:None:-1]:
        if list_search:
            # Because siblings necessarily have a list_item_close, if we ever
            # hit a close then we can skip until we reach a lower level.
            if token.type == "list_item_close" or token.type == "bullet_list_close" or token.type == "ordered_list_close":
                min_level = token.level - 1
                skipping = True

            if skipping:
                if token.level <= min_level:
                    skipping = False
                else:
                    continue

            context_tokens.append(token)

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


def _strip_trailing_closing_tags(context: str) -> str:
    """Remove closing </ul> and </li> tags from the end of an html string."""
    context = context.strip()
    while context.endswith('</ul>') or context.endswith('</li>'):
        context = context[:-5].rstrip()
    return context


def _build_context(tokens: list[Token], list_open_token_index: int, file_front_context: str,
                   filepath_context: str, has_file_card: bool) -> tuple[str, str]:
    """Build list and filepath context for a card."""
    context_tokens = _find_prior_context(tokens, list_open_token_index)
    list_context = render(context_tokens) if context_tokens else ''
    list_context = _strip_trailing_closing_tags(list_context)

    # Combine file context if this card is within a file card
    full_list_context = list_context + (file_front_context if has_file_card else '')
    return full_list_context, filepath_context


def _extract_tags(full_content_after_symbol: str) -> set[str]:
    """Extract tags from content."""
    tag_pattern = r"#([\w/][\w/-]*\w)"
    return set(re.findall(tag_pattern, full_content_after_symbol))


def extract_cards(file_path: str) -> list[genanki.Note]:
    """
    Parse a markdown file and return a list of Anki notes.
    """

    notes = []

    text, tokens, tags = read_file(file_path)
    filepath_context = _build_filepath_context(file_path)
    file_front_context = ''  # Will be set if this is a file card

    # First, check for file flashcards
    if "card" in tags:
        # Split the text at the card split symbol
        front_text, back_text = re.split(FILE_SPLIT_PATTERN, text, maxsplit=3)[2:]

        front_tokens = md.parse(front_text)
        back_tokens = md.parse(back_text)

        # Incremental tags
        if 'incremental' in tags:
            notes.append(_create_cloze_card(
                front_tokens, back_tokens, SymbolDirection.FORWARD,
                incremental=True, tags=tags,
                filepath_context=filepath_context, list_context=''
            ))
        else:
            notes.append(genanki.Note(
                model=BASIC_CONTEXT_MODEL,
                fields=_field_dict_to_list({
                    'FilePath': filepath_context,
                    'Context': '',
                    'Front': render(front_tokens),
                    'Back': render(back_tokens),
                }, BASIC_CONTEXT_MODEL),
                tags=tags,
            ))

        # Store the file front content for context in nested cards
        file_front_context = render(front_tokens)

    # Now check for inline and list flashcards. First we'll parse the tokens for
    # regions of interest, then extract the cards and context from those
    # regions.
    card_indices, cloze_indices = _parse_regions_of_interest(tokens)

    for region in card_indices:
        inline_token = tokens[region.inline_token_index]
        child = inline_token.children[region.symbol_child_index]
        left_text, right_text = child.content.split(INLINE_SYMBOL[region.symbol_direction], 1)

        # Extract tags and determine card type
        full_content_after_symbol = inline_token.content.split(INLINE_SYMBOL[region.symbol_direction], 1)[1]
        tags = _extract_tags(full_content_after_symbol)
        symbol_text = INLINE_SYMBOL[region.symbol_direction]

        # Determine if this is a list card (only tags after symbol, with nested list)
        # Remove tags temporarily to check if there's any other content
        tag_pattern = r"#[\w/][\w/-]*\w"
        content_without_tags = re.sub(tag_pattern, '', full_content_after_symbol).strip()
        is_list_card = not content_without_tags
        if is_list_card:
            # Verify there's an immediate nested bullet list
            has_immediate_nested_list = any(
                tokens[j].type == "bullet_list_open"
                for j in range(region.inline_token_index + 1, region.list_close_token_index)
                if tokens[j].type not in ["paragraph_open", "paragraph_close"]
            )
            if not has_immediate_nested_list:
                continue

        # Build front and back tokens based on card type
        if is_list_card:
            # List card: front = question line with tags, back = nested list
            modified_inline = copy(inline_token)
            modified_child = copy(child)
            modified_child.content = left_text + symbol_text + right_text

            modified_inline.children = (
                inline_token.children[:region.symbol_child_index] +
                [modified_child] +
                inline_token.children[region.symbol_child_index + 1:]
            )

            front_tokens = tokens[region.list_open_token_index:region.inline_token_index] + [modified_inline]
            back_tokens = tokens[region.inline_token_index + 1:region.list_close_token_index + 1]
        else:
            # Inline card: split at symbol
            left_child = copy(child)
            left_child.content = left_text + symbol_text
            right_child = copy(child)
            right_child.content = right_text

            front_children = inline_token.children[:region.symbol_child_index] + [left_child]
            back_children = ([right_child] + inline_token.children[region.symbol_child_index + 1:]
                           if right_text.strip() else [])

            front_inline = copy(inline_token)
            back_inline = copy(inline_token)
            front_inline.children = front_children
            back_inline.children = back_children

            front_tokens = tokens[region.list_open_token_index:region.inline_token_index] + [front_inline]
            back_tokens = [back_inline] if back_children else []

        # Build context and create cloze card
        full_list_context, full_filepath_context = _build_context(
            tokens, region.list_open_token_index, file_front_context, filepath_context, "card" in tags
        )

        is_incremental = 'incremental' in tags
        notes.append(_create_cloze_card(
            front_tokens, back_tokens, region.symbol_direction,
            incremental=is_incremental,
            tags=tags,
            filepath_context=full_filepath_context,
            list_context=full_list_context
        ))

    for region in cloze_indices:
        # Build context and create cloze card
        full_list_context, full_filepath_context = _build_context(
            tokens, region.list_open_token_index, file_front_context, filepath_context, "card" in tags
        )

        # The final tokens are the list open until inline, and the modified clozed inline token
        text_tokens = tokens[region.list_open_token_index:region.inline_token_index] + region.clozed_tokens

        notes.append(genanki.Note(
            model=CLOZE_CONTEXT_MODEL,
            fields=_field_dict_to_list({
                'Text': full_list_context + render(text_tokens),
                'FilePath': full_filepath_context,
            }, CLOZE_CONTEXT_MODEL),
            tags=tags,
        ))

    return notes
