import typer
import rich
from pathlib import Path

from anki import create_deck, export_deck
from extract import extract_cards

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
)

@app.command()
def main(
    path: str = typer.Argument(
        ...,
        help="Path to a markdown file or directory to extract cards from",
    ),
    name: str = typer.Option(
        "Extracted Cards",
        "-n", "--name",
        help="Name of the output Anki deck",
    ),
) -> None:
    """
    Recursively extract cards from a markdown file or all markdown files in a
    directory, and export as an Anki deck.
    """
    p = Path(path)
    if p.is_file():
        files = [p]
    elif p.is_dir():
        files = list(p.rglob("*.md"))
        if not files:
            print(f"No markdown files found in directory: {path}")
            raise typer.Exit(1)
    else:
        print(f"Path not found: {path}")
        raise typer.Exit(1)

    # Search up the directory tree for a .obsidian directory
    search_path = p if p.is_dir() else p.parent
    found_obsidian = False
    for ancestor in [search_path] + list(search_path.parents):
        obsidian_dir = ancestor / ".obsidian"
        if obsidian_dir.is_dir():
            parent_dir = str(ancestor)
            found_obsidian = True
            break
    if not found_obsidian:
        parent_dir = str(search_path)

    all_cards = []
    for file in files:
        cards = extract_cards(str(file), parent_dir=parent_dir)
        all_cards.extend(cards)

    deck = create_deck(all_cards, deck_name=name)

    print(
        f"Extracted {len(deck.notes)} notes into deck '{deck.name}' (ID: {deck.deck_id})")

    # Sanitize deck name for filename
    safe_name = "".join(c if c.isalnum() or c in ("-", "_")
                        else "_" for c in name).strip("_-")
    output_file = f"{safe_name or 'deck'}.apkg"
    export_deck(deck, output_path=output_file)
    print(f"Deck exported to {output_file}")


if __name__ == "__main__":
    app()
