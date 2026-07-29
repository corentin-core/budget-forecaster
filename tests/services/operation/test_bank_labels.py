"""Deriving a usable name from a bank statement label."""

import pytest

from budget_forecaster.services.operation.bank_labels import recognizable_name


class TestRecognizableName:
    """What survives a label, and what the caller gets when nothing does."""

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("PRLV SEPA EDF FACTURE 07/2026", "EDF"),
            ("VIR SEPA LOYER JUILLET", "LOYER"),
            ("CARTE 12/07 MONOPRIX PARIS", "MONOPRIX"),
            ("PRELEVEMENT ECHEANCE 2026-07 ASSURANCE HABITATION", "HABITATION"),
            ("VIREMENT DE SALAIRE AOÛT", "SALAIRE"),
        ],
    )
    def test_keeps_the_word_that_names_the_payment(
        self, label: str, expected: str
    ) -> None:
        """Channel words, paperwork words, months and references drop out."""
        assert recognizable_name(label) == expected

    def test_keeps_the_original_casing(self) -> None:
        """Keywords are matched as substrings, so the casing has to survive."""
        assert recognizable_name("Prlv Sepa Netflix") == "Netflix"

    @pytest.mark.parametrize("label", ["PRLV SEPA 07/2026", "CB 12/07", "", "8 4 21"])
    def test_gives_up_on_an_all_noise_label(self, label: str) -> None:
        """Nothing beats a keyword that would reject every future operation."""
        assert recognizable_name(label) == ""
