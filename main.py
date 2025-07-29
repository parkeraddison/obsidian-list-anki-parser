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

import typer
import rich

from anki import create_deck
from extract import extract_cards

def single(filepath: str = typer.Argument(..., help="Path to the markdown file extract cards from")) -> None:
    """
    Extract cards from a single markdown file and print the cards.
    """
    cards = extract_cards(filepath)
    for card in cards:
        rich.print(card)
        print('\n---\n')  # Separator for readability


if __name__ == "__main__":

    typer.run(single)
