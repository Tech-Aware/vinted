"""Tests for the GPT client helpers."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.gpt_client import ListingGenerator


@pytest.fixture
def generator() -> ListingGenerator:
    return ListingGenerator(model="test-model", api_key="test-key")


def test_extract_title_and_description_with_markers(generator: ListingGenerator) -> None:
    content = (
        "TITRE\nMon super titre\nDESCRIPTION\nLigne 1\nLigne 2"
    )

    title, description = generator._extract_title_and_description(content)

    assert title == "Mon super titre"
    assert description == "Ligne 1\nLigne 2"


def test_extract_title_and_description_without_markers(generator: ListingGenerator) -> None:
    content = "Titre libre\nCorps de la description\nDeuxième ligne"

    title, description = generator._extract_title_and_description(content)

    assert title == "Titre libre"
    assert description == "Corps de la description\nDeuxième ligne"


def test_extract_title_and_description_with_missing_description(generator: ListingGenerator) -> None:
    content = "TITRE\nTitre seul"

    title, description = generator._extract_title_and_description(content)

    assert title == "Titre seul"
    assert description == ""


def test_extract_title_and_description_strips_colons(generator: ListingGenerator) -> None:
    content = "TITRE\n:Mon titre\nDESCRIPTION\n: Premiere ligne\n Deuxieme"

    title, description = generator._extract_title_and_description(content)

    assert title == "Mon titre"
    assert description == "Premiere ligne\nDeuxieme"
