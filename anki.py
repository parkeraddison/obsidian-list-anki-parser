"""
Anki deck creation and export functionality.
"""

import os
from typing import Dict, List
import genanki


def create_deck(notes: list[genanki.Note], deck_name: str = "Extracted Cards") -> genanki.Deck:
    """
    Create an Anki deck from a list of notes.

    Args:
        notes: List of genanki.Note objects to include in the deck
        deck_name: Name for the created deck

    Returns:
        genanki.Deck object ready for export
    """
    # Create a unique deck ID based on the deck name
    deck_id = hash(deck_name) % (10**9)  # Ensure it's a reasonable size
    if deck_id < 0:
        deck_id = -deck_id  # Make sure it's positive

    # Create the deck
    deck = genanki.Deck(
        deck_id=deck_id,
        name=deck_name
    )

    # Add all notes to the deck
    for note in notes:
        deck.add_note(note)

    return deck


def export_deck(deck: genanki.Deck, output_path: str) -> None:
    """
    Export an Anki deck to a .apkg file.

    Args:
        deck: genanki.Deck object to export
        output_path: Path where the .apkg file should be saved
    """
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Create a package with the deck
    package = genanki.Package(deck)

    # Write the package to file
    package.write_to_file(output_path)


def create_and_export_deck(
    notes: list[genanki.Note],
    output_path: str,
    deck_name: str = "Extracted Cards"
) -> None:
    """
    Convenience function to create and export a deck in one step.

    Args:
        notes: List of genanki.Note objects to include in the deck
        output_path: Path where the .apkg file should be saved
        deck_name: Name for the created deck
    """
    deck = create_deck(notes, deck_name)
    export_deck(deck, output_path)


def get_deck_statistics(deck: genanki.Deck) -> Dict[str, int]:
    """
    Get statistics about a deck.

    Args:
        deck: genanki.Deck object to analyze

    Returns:
        Dictionary with statistics about the deck
    """
    stats = {
        'total_notes': len(deck.notes),
        'model_counts': {},
        'tag_counts': {},
    }

    # Count notes by model
    for note in deck.notes:
        model_name = note.model.name
        stats['model_counts'][model_name] = stats['model_counts'].get(model_name, 0) + 1

    # Count notes by tags
    for note in deck.notes:
        for tag in note.tags:
            stats['tag_counts'][tag] = stats['tag_counts'].get(tag, 0) + 1

    return stats


def print_deck_summary(deck: genanki.Deck) -> None:
    """
    Print a summary of the deck contents.

    Args:
        deck: genanki.Deck object to summarize
    """
    stats = get_deck_statistics(deck)

    print(f"Deck: {deck.name} (ID: {deck.deck_id})")
    print(f"Total notes: {stats['total_notes']}")

    if stats['model_counts']:
        print("\nModel distribution:")
        for model, count in stats['model_counts'].items():
            print(f"  {model}: {count} notes")

    if stats['tag_counts']:
        print("\nTag distribution:")
        for tag, count in sorted(stats['tag_counts'].items()):
            print(f"  #{tag}: {count} notes")


def merge_decks(decks: List[genanki.Deck], merged_name: str = "Merged Deck") -> genanki.Deck:
    """
    Merge multiple decks into a single deck.

    Args:
        decks: List of genanki.Deck objects to merge
        merged_name: Name for the merged deck

    Returns:
        New genanki.Deck containing all notes from input decks
    """
    all_notes = []
    for deck in decks:
        all_notes.extend(deck.notes)

    return create_deck(all_notes, merged_name)
