"""Module for the BNP Paribas bank adapter."""
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from budget_forecaster.amount import Amount
from budget_forecaster.bank_adapter.bank_adapter import BankAdapterBase
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.historic_operation_factory import (
    HistoricOperationFactory,
)
from budget_forecaster.types import Category

CATEGORY_MAPPING: dict[str, Category] = {
    "Achat multimedia, hightech": Category.ENTERTAINMENT,
    "Achat multimédia, high-tech": Category.ENTERTAINMENT,
    "Achats, shopping": Category.OTHER,
    "Activites enfants": Category.CHILDCARE,
    "Activités enfants": Category.CHILDCARE,
    "Alimentation, supermarche": Category.GROCERIES,
    "Alimentation, supermarché": Category.GROCERIES,
    "Assurances": Category.OTHER_INSURANCE,
    "Billet d'avion, Billet de train": Category.PUBLIC_TRANSPORT,
    "Billet d'avion, billet de train": Category.PUBLIC_TRANSPORT,
    "Bricolage et jardinage": Category.HOUSE_WORKS,
    "Cadeaux": Category.GIFTS,
    "Carburant": Category.CAR_FUEL,
    "Chauffage": Category.HOUSE_WORKS,
    "Coiffeur, cosmetique, soins": Category.CARE,
    "Coiffeur, cosmétique, soins": Category.CARE,
    "Crèche, baby-sitter": Category.CHILDCARE,
    "Divertissements, sorties culturelles": Category.LEISURE,
    "Dons caritatifs": Category.CHARITY,
    "Eau": Category.WATER,
    "Electricite, gaz": Category.ELECTRICITY,
    "Électricité, gaz": Category.ELECTRICITY,
    "Enfants - Autres": Category.CHILDCARE,
    "Entretien vehicule": Category.CAR_MAINTENANCE,
    "Entretien véhicule": Category.CAR_MAINTENANCE,
    "Epargne": Category.SAVINGS,
    "Épargne": Category.SAVINGS,
    "Frais bancaires": Category.BANK_FEES,
    "Frais professionnels": Category.PROFESSIONAL_EXPENSES,
    "Frais postaux": Category.OTHER,
    "Habillement": Category.CLOTHING,
    "Internet, TV": Category.INTERNET,
    "Loisirs et sorties - Autres": Category.LEISURE,
    "Medecins": Category.HEALTH_CARE,
    "Médecins": Category.HEALTH_CARE,
    "Mobilier, electromenager, deco.": Category.FURNITURE,
    "Mobilier, electroménager, déco.": Category.FURNITURE,
    "Musique, livres, films": Category.ENTERTAINMENT,
    "Pension alimentaire": Category.CHILD_SUPPORT,
    "Pharmacie": Category.HEALTH_CARE,
    "Remboursement emprunt": Category.HOUSE_LOAN,
    "Restaurants, bars": Category.LEISURE,
    "Salaires et revenus d'activité": Category.SALARY,
    "Sante - Autres": Category.HEALTH_CARE,
    "Santé - Autres": Category.HEALTH_CARE,
    "Scolarite, etudes": Category.CHILDCARE,
    "Scolarité, études": Category.CHILDCARE,
    "Sport": Category.LEISURE,
    "Stationnement": Category.PARKING,
    "Tabac, presse": Category.OTHER,
    "Telephone": Category.PHONE,
    "Téléphone": Category.PHONE,
    "Transports en commun": Category.PUBLIC_TRANSPORT,
    "Transports et vehicules - Autres": Category.PUBLIC_TRANSPORT,
    "Travaux, reparation, entretien": Category.HOUSE_WORKS,
    "Travaux, réparations, entretien": Category.HOUSE_WORKS,
    "Voyages, vacances": Category.HOLIDAYS,
    "Vie Quotidienne - Autres": Category.OTHER,
    "Mutuelle": Category.HEALTH_CARE,
    "Prêt immobilier": Category.HOUSE_LOAN,
    "Assurance vehicule": Category.CAR_INSURANCE,
    "Remboursement": Category.OTHER,
    "Chèque reçu": Category.OTHER,
    "Virement reçu": Category.OTHER,
    "Chèque emis": Category.OTHER,
    "Retrait d'espèces": Category.OTHER,
    "Autres depenses à categoriser": Category.OTHER,
    "Loyer": Category.RENT,
    "Location de vehicule": Category.HOLIDAYS,
    "Taxe foncière": Category.TAXES,
    "Impôts et taxes - Autres": Category.TAXES,
    "Autres revenus": Category.OTHER,
    "Virement emis": Category.OTHER,
    "Peage": Category.TOLL,
    "Assurance habitation": Category.HOUSE_INSURANCE,
    "Vie quotidienne - Autres": Category.OTHER,
    "Transports et véhicules - Autres": Category.OTHER,
    "Péage": Category.TOLL,
    "Aides et allocations": Category.BENEFITS,
    "Impôt sur le revenu": Category.TAXES,
    "Crédit auto": Category.CAR_LOAN,
    "Virement interne": Category.OTHER,
}


class BnpParibasBankAdapter(BankAdapterBase):
    """Adapter for the BNP Paribas bank export operations."""

    def __init__(self) -> None:
        super().__init__("bnp")

    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        # get export date
        export_date_cell = pd.read_excel(
            bank_export, index_col=None, usecols="B", header=0, nrows=0
        ).columns.values[0]
        if (re_match := re.match("Solde au (.*)", export_date_cell)) is not None:
            self._export_date = datetime.strptime(re_match.group(1), "%d/%m/%Y")
        else:
            self._export_date = datetime.now()
        # get balance
        self._balance = float(
            pd.read_excel(
                bank_export, index_col=None, usecols="C", header=0, nrows=0
            ).columns.values[0]
        )
        # get operations
        self._operations: list[HistoricOperation] = []
        operation_df = pd.read_excel(bank_export, header=2)
        for _, row in operation_df.iterrows():
            self._operations.append(
                operation_factory.create_operation(
                    description=row["Libelle operation"],
                    amount=Amount(row["Montant operation"]),
                    category=CATEGORY_MAPPING[row["Sous Categorie operation"]],
                    date=datetime.strptime(row["Date operation"], "%d-%m-%Y"),
                )
            )

    @classmethod
    def match(cls, bank_export: Path) -> bool:
        return bank_export.suffix == ".xls"
