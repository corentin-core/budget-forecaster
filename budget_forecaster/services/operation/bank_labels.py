"""Read a bank statement label for the one word that says who was paid.

A label is neither a name nor a matching keyword: it carries the payment
channel, a reference number and often the month. Copied as a description it
becomes a name that ages badly; copied as a keyword it can never match again,
since keywords are substrings every future label must contain.
"""

import re
import unicodedata
from typing import Final

_NOISE: Final = frozenset(
    {
        # Payment channel
        "PRLV",
        "PREL",
        "PRELEVEMENT",
        "SEPA",
        "VIR",
        "VIREMENT",
        "VRST",
        "VERSEMENT",
        "CB",
        "CARTE",
        "PAIEMENT",
        "RETRAIT",
        "DEBIT",
        "CREDIT",
        "AVOIR",
        # Paperwork
        "FACT",
        "FACTURE",
        "ECH",
        "ECHEANCE",
        "REF",
        "MANDAT",
        "CONTRAT",
        "NUM",
        # Months, which is what makes a copied label unmatchable next time
        "JANVIER",
        "FEVRIER",
        "MARS",
        "AVRIL",
        "MAI",
        "JUIN",
        "JUILLET",
        "AOUT",
        "SEPTEMBRE",
        "OCTOBRE",
        "NOVEMBRE",
        "DECEMBRE",
    }
)

_WORD: Final = re.compile(r"[^\W\d_]+")
"""Runs of letters: anything with a digit in it is a date or a reference."""

_MIN_LENGTH: Final = 3


def _plain(word: str) -> str:
    """Uppercase without accents, so AOÛT and AOUT are the same noise."""
    decomposed = unicodedata.normalize("NFD", word.upper())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def recognizable_name(label: str) -> str:
    """The longest word of the label that names who was paid, or empty.

    Empty is a useful answer: an empty keyword skips description matching
    altogether, where a keyword taken from noise would reject everything.
    """
    words = [
        word
        for word in _WORD.findall(label)
        if len(word) >= _MIN_LENGTH and _plain(word) not in _NOISE
    ]
    return max(words, key=len, default="")
