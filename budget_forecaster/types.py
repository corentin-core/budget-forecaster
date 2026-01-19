"""Module containing custom types for the budget_forecaster package."""
import enum
from datetime import datetime

OperationId = int
"""Unique identifier for a historic operation."""

PlannedOperationId = int
"""Unique identifier for a planned operation."""

BudgetId = int
"""Unique identifier for a budget."""

OperationLinkId = int
"""Unique identifier for an operation link."""

IterationDate = datetime
"""Date identifying a specific iteration of a planned operation or budget."""


class Category(enum.StrEnum):
    """A category is a group of transactions."""

    # Income
    SALARY = "Salaire"
    TAX_CREDIT = "Crédit d'impot"
    BENEFITS = "Allocations"

    # Housing
    HOUSE_LOAN = "Prêt maison"
    WORKS_LOAN = "Prêt travaux"
    RENT = "Loyer"
    LOAN_INSURANCE = "Assurance prêt"
    HOUSE_WORKS = "Travaux"
    FURNITURE = "Mobilier, electromenager, deco."

    # Investments
    SAVINGS = "Epargne"

    # Insurance
    CAR_INSURANCE = "Assurance auto"
    HOUSE_INSURANCE = "Assurance habitation"
    OTHER_INSURANCE = "Autre assurance"

    # Children
    CHILDCARE = "Enfants"
    CHILD_SUPPORT = "Pension alimentaire"

    # Leisure
    ENTERTAINMENT = "Divertissement"
    LEISURE = "Loisirs"
    HOLIDAYS = "Voyages, vacances"

    # Utilities
    ELECTRICITY = "Electricité"
    WATER = "Eau"
    INTERNET = "Internet"
    PHONE = "Téléphone"

    # Daily life
    GROCERIES = "Courses"
    CLOTHING = "Habillement"
    HEALTH_CARE = "Santé"
    CARE = "Coiffeur, cosmétique, soins"
    PUBLIC_TRANSPORT = "Transports publics"
    CAR_FUEL = "Carburant"
    PARKING = "Stationnement"
    TOLL = "Péage"
    CAR_MAINTENANCE = "Entretien automobile"
    CAR_LOAN = "Crédit auto"
    GIFTS = "Cadeaux"

    # Professional
    PROFESSIONAL_EXPENSES = "Frais professionnels"

    # Other
    OTHER = "Autre"
    CHARITY = "Dons"
    BANK_FEES = "Commissions bancaires"
    TAXES = "Impôts, taxes"
