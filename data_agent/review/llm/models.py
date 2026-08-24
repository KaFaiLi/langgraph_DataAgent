"""Logical cost roles used by the controlled review workflow."""

from enum import StrEnum


class ModelTier(StrEnum):
    LOW_COST = "low_cost"
    HIGH_COST = "high_cost"
