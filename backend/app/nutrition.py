from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .models import Nutrients

DataQuality = Literal["verified_source", "calculated_recipe", "development_estimate"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SourceRef:
    id: str
    kind: str
    title: str
    publisher: str
    url: str
    licence: str
    note: str


@dataclass(frozen=True)
class PortionRule:
    unit: str
    grams: float
    confidence: Confidence
    note: str


@dataclass(frozen=True)
class FoodRecord:
    key: str
    name: str
    aliases: tuple[str, ...]
    countries: tuple[str, ...]
    category: str
    default_unit: str
    nutrients_per_100g: Nutrients
    source_ids: tuple[str, ...]
    source_profile_codes: tuple[str, ...]
    data_quality: DataQuality
    source_note: str
    portions: tuple[PortionRule, ...]
    recipe: dict[str, Any] | None

    @property
    def source_id(self) -> str:
        """Compatibility shortcut for clients that expect one primary source."""
        return self.source_ids[0]


CATALOG_PATH = Path(__file__).parents[1] / "data" / "catalog.json"


def _load_catalogue() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        raise RuntimeError(
            f"Missing generated catalogue at {CATALOG_PATH}. "
            "Run backend/tools/build_catalog.py with the WAFCT workbook available."
        )
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


_CATALOGUE = _load_catalogue()

CATALOG_METADATA = {
    key: value
    for key, value in _CATALOGUE.items()
    if key != "foods"
}

SOURCES: dict[str, SourceRef] = {
    source["id"]: SourceRef(**source)
    for source in _CATALOGUE["sources"]
}

FOODS: tuple[FoodRecord, ...] = tuple(
    FoodRecord(
        key=food["key"],
        name=food["name"],
        aliases=tuple(food["aliases"]),
        countries=tuple(food["countries"]),
        category=food["category"],
        default_unit=food["default_unit"],
        nutrients_per_100g=Nutrients.model_validate(food["nutrients_per_100g"]),
        source_ids=tuple(food["source_ids"]),
        source_profile_codes=tuple(food["source_profile_codes"]),
        data_quality=food["data_quality"],
        source_note=food["source_note"],
        portions=tuple(PortionRule(**portion) for portion in food["portions"]),
        recipe=food["recipe"],
    )
    for food in _CATALOGUE["foods"]
)

FOODS_BY_KEY = {food.key: food for food in FOODS}


def scale_nutrients(nutrients: Nutrients, factor: float) -> Nutrients:
    return Nutrients(
        **{
            field: getattr(nutrients, field) * factor
            for field in Nutrients.model_fields.keys()
        }
    )


def add_nutrients(items: list[Nutrients]) -> Nutrients:
    fields = Nutrients.model_fields.keys()
    totals = {field: sum(getattr(item, field) for item in items) for field in fields}
    return Nutrients(**totals)


def calculate_pral(nutrients: Nutrients) -> float:
    """Estimate potential renal acid load using the Remer-Manz equation."""
    return (
        0.4888 * nutrients.protein_g
        + 0.0366 * nutrients.phosphorus_mg
        - 0.0205 * nutrients.potassium_mg
        - 0.0263 * nutrients.magnesium_mg
        - 0.0125 * nutrients.calcium_mg
    )


def get_food(key: str) -> FoodRecord | None:
    return FOODS_BY_KEY.get(key)


def get_source(source_id: str) -> SourceRef:
    return SOURCES[source_id]


def get_food_sources(food: FoodRecord) -> tuple[SourceRef, ...]:
    return tuple(get_source(source_id) for source_id in food.source_ids)


def resolve_portion_grams(
    food: FoodRecord,
    quantity: float,
    unit: str,
    size: str = "unspecified",
) -> tuple[float, Confidence, str]:
    normalised = unit.strip().lower()
    if normalised in {"g", "gram", "grams"}:
        base_grams, confidence, note = 1.0, "high", "Direct gram weight."
    else:
        rule = next((item for item in food.portions if item.unit == normalised), None)
        if rule is None:
            rule = next(
                (item for item in food.portions if item.unit == food.default_unit),
                food.portions[0],
            )
            base_grams = rule.grams
            confidence = "low"
            note = (
                f"Unit {unit!r} has no food-specific conversion; "
                f"used the {food.default_unit!r} assumption. {rule.note}"
            )
        else:
            base_grams, confidence, note = rule.grams, rule.confidence, rule.note

    size_factor = {
        "small": 0.70,
        "medium": 1.0,
        "large": 1.35,
        "unspecified": 1.0,
    }.get(size, 1.0)
    grams = quantity * base_grams * size_factor
    if size != "unspecified" and normalised not in {"g", "gram", "grams"}:
        note = f"{note} Size adjustment: {size} × {size_factor:.2f}."
    return grams, confidence, note


def nutrients_for_grams(food: FoodRecord, grams: float) -> Nutrients:
    return scale_nutrients(food.nutrients_per_100g, grams / 100.0)
