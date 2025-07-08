# Obsidian List Anki Parser
OLAP (haha) is a Markdown-to-Anki parser with contextual support for bullet lists, similar to how cards would be used in an Outliner like Logseq.

This plugin is inspired by https://github.com/debanjandhar12/logseq-anki-sync, namely to support features such as **incremental cloze cards** (for all top-level list items under a card, create a one-versus-rest cloze) and **list ancestor context** (for a card within a list, add all list parents to the card front as context).

This is currently designed as a Python script to parse from plaintext Markdown files following Commonmark syntax.
