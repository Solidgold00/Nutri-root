"""Build the NutriRoot V0.4 catalogue from the official WAFCT workbook.

Run from ``backend`` or the repository root after downloading WAFCT_2019.xlsx
to ``backend/data/reference``. The generated JSON files are runtime assets, so
the API itself does not need openpyxl or the source workbook.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl

from catalog_seed import COVERAGE_TIERS, DIRECT_FOODS, RECIPES, WEST_AFRICAN_COUNTRIES


BACKEND = Path(__file__).parents[1]
WORKBOOK = BACKEND / "data" / "reference" / "WAFCT_2019.xlsx"
CATALOG_OUTPUT = BACKEND / "data" / "catalog.json"
PROFILES_OUTPUT = BACKEND / "data" / "source_profiles.json"
SHEET = "05 NV_sum_57 (per 100g EP)"

NUTRIENT_COLUMNS = {
    "calories_kcal": 9,
    "protein_g": 11,
    "fat_g": 12,
    "carbs_g": 13,
    "fibre_g": 14,
    "calcium_mg": 17,
    "magnesium_mg": 19,
    "phosphorus_mg": 20,
    "potassium_mg": 21,
    "sodium_mg": 22,
}

SOURCES = [
    {
        "id": "fao_wafct_2019",
        "kind": "food_composition",
        "title": "FAO/INFOODS Food Composition Table for Western Africa (2019)",
        "publisher": "FAO/INFOODS",
        "url": "https://www.fao.org/food-composition/tables-and-databases/detail/food-composition-tables/en",
        "licence": (
            "FAO copyright statement permits attributed private study, research, teaching and "
            "non-commercial use. Translation, adaptation, resale and other commercial rights "
            "must be requested from FAO."
        ),
        "note": (
            "Primary nutrient source. Values are per 100 g edible portion. See DATA_LICENSE.md "
            "before distributing or commercially using this catalogue."
        ),
    },
    {
        "id": "uk_cofid_2021",
        "kind": "food_composition_reference",
        "title": "McCance and Widdowson's Composition of Foods Integrated Dataset 2021",
        "publisher": "Public Health England / GOV.UK",
        "url": "https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid",
        "licence": "Open Government Licence v3.0, except where otherwise stated",
        "note": "Registered UK-market reference for future validation; V0.4 nutrient rows are generated from WAFCT.",
    },
    {
        "id": "ons_census_2021",
        "kind": "coverage_research",
        "title": "Census 2021: ethnic group and country of birth, England and Wales",
        "publisher": "Office for National Statistics",
        "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/culturalidentity/ethnicity/bulletins/ethnicgroupenglandandwales/census2021",
        "licence": "Open Government Licence v3.0",
        "note": "Used to prioritise Nigerian and Ghanaian coverage; it is not a nutrition source.",
    },
]

PORTION_TEMPLATES: dict[str, tuple[str, list[tuple[str, float, str, str]]]] = {
    "rice": (
        "cup",
        [
            ("cup", 195, "medium", "Level cooked cup assumption."),
            ("serving", 195, "medium", "One cooked-cup serving assumption."),
            ("plate", 350, "low", "Plate sizes vary substantially."),
            ("bowl", 300, "low", "Bowl sizes vary substantially."),
        ],
    ),
    "plate": (
        "plate",
        [
            ("plate", 400, "low", "Composite plate assumption."),
            ("serving", 400, "low", "Composite serving assumption."),
            ("bowl", 350, "low", "Bowl sizes vary substantially."),
        ],
    ),
    "swallow": (
        "wrap",
        [
            ("wrap", 250, "medium", "One prepared wrap assumption."),
            ("ball", 180, "low", "Hand-formed balls vary substantially."),
            ("serving", 250, "medium", "Prepared serving assumption."),
        ],
    ),
    "porridge": (
        "bowl",
        [
            ("bowl", 300, "medium", "Medium breakfast bowl assumption."),
            ("cup", 240, "medium", "One metric-style cup assumption."),
            ("serving", 300, "medium", "Prepared serving assumption."),
        ],
    ),
    "staple": (
        "serving",
        [
            ("serving", 200, "medium", "Prepared staple serving assumption."),
            ("piece", 100, "medium", "Medium cooked piece assumption."),
            ("slice", 60, "medium", "Medium slice assumption."),
            ("cup", 180, "medium", "One cooked cup assumption."),
        ],
    ),
    "dry_staple": (
        "cup",
        [
            ("cup", 160, "medium", "Level dry cup assumption."),
            ("tablespoon", 10, "medium", "Level tablespoon assumption."),
            ("serving", 80, "low", "Dry serving assumption; hydration changes final weight."),
        ],
    ),
    "beans": (
        "cup",
        [
            ("cup", 175, "medium", "One cooked cup assumption."),
            ("serving", 175, "medium", "Cooked serving assumption."),
            ("bowl", 300, "low", "Bowl sizes vary substantially."),
        ],
    ),
    "vegetable": (
        "cup",
        [
            ("cup", 150, "medium", "Cooked leafy-vegetable cup assumption."),
            ("serving", 150, "medium", "Cooked serving assumption."),
            ("spoon", 30, "low", "Serving-spoon sizes vary."),
        ],
    ),
    "soup": (
        "ladle",
        [
            ("ladle", 120, "medium", "Medium ladle assumption."),
            ("scoop", 120, "medium", "Medium scoop assumption."),
            ("serving", 240, "low", "Two-ladle serving assumption."),
            ("bowl", 300, "low", "Bowl sizes vary substantially."),
        ],
    ),
    "stew": (
        "ladle",
        [
            ("ladle", 120, "medium", "Medium ladle assumption."),
            ("scoop", 120, "medium", "Medium scoop assumption."),
            ("serving", 240, "low", "Two-ladle serving assumption."),
            ("bowl", 300, "low", "Bowl sizes vary substantially."),
        ],
    ),
    "protein": (
        "piece",
        [
            ("piece", 75, "medium", "Medium cooked meat piece assumption."),
            ("serving", 100, "high", "100 g cooked serving reference."),
        ],
    ),
    "fish": (
        "piece",
        [
            ("piece", 120, "medium", "Medium cooked fish piece assumption."),
            ("fillet", 120, "medium", "Medium cooked fillet assumption."),
            ("serving", 120, "medium", "Cooked fish serving assumption."),
        ],
    ),
    "egg": (
        "egg",
        [
            ("egg", 50, "high", "One medium edible egg assumption."),
            ("piece", 50, "high", "One medium edible egg assumption."),
            ("serving", 50, "high", "One medium edible egg assumption."),
        ],
    ),
    "condiment": (
        "tablespoon",
        [
            ("tablespoon", 15, "medium", "Level tablespoon assumption."),
            ("teaspoon", 5, "medium", "Level teaspoon assumption."),
            ("serving", 15, "medium", "Condiment serving assumption."),
        ],
    ),
    "drink": (
        "cup",
        [
            ("cup", 250, "high", "250 ml cup; density approximated as 1 g/ml."),
            ("glass", 250, "medium", "Medium glass assumption."),
            ("bottle", 330, "medium", "Small bottle assumption."),
            ("millilitre", 1, "high", "For these drinks, 1 ml is approximated as 1 g."),
        ],
    ),
    "snack": (
        "piece",
        [
            ("piece", 70, "medium", "Medium piece assumption."),
            ("serving", 100, "medium", "100 g serving reference."),
        ],
    ),
    "skewer": (
        "skewer",
        [
            ("skewer", 100, "medium", "Medium meat skewer assumption."),
            ("piece", 100, "medium", "Medium serving assumption."),
            ("serving", 100, "medium", "100 g serving reference."),
        ],
    ),
}


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text:
        return None
    if text.casefold() in {"tr", "trace", "n", "-"}:
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else None


def normalise_alias(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def load_profiles() -> dict[str, dict]:
    workbook = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    worksheet = workbook[SHEET]
    profiles: dict[str, dict] = {}
    for row in worksheet.iter_rows(min_row=5, values_only=True):
        code = row[0]
        if not isinstance(code, str) or not re.fullmatch(r"\d{2}_\d{3}", code):
            continue
        nutrients = {
            nutrient: parse_number(row[column])
            for nutrient, column in NUTRIENT_COLUMNS.items()
        }
        profiles[code] = {
            "code": code,
            "name": str(row[1]),
            "name_fr": str(row[2]) if row[2] else "",
            "scientific_name": str(row[3]) if row[3] else "",
            "bibliography": str(row[4]) if row[4] else "",
            "nutrients_per_100g": nutrients,
        }
    return profiles


def require_profile(profiles: dict[str, dict], code: str) -> dict:
    if code not in profiles:
        raise ValueError(f"Unknown WAFCT profile code: {code}")
    profile = profiles[code]
    missing = [name for name, value in profile["nutrients_per_100g"].items() if value is None]
    if missing:
        raise ValueError(f"WAFCT {code} is missing required nutrients: {', '.join(missing)}")
    return profile


def portions(kind: str) -> tuple[str, list[dict]]:
    default_unit, rows = PORTION_TEMPLATES[kind]
    result = [
        {"unit": unit, "grams": grams, "confidence": confidence, "note": note}
        for unit, grams, confidence, note in rows
    ]
    result.append(
        {"unit": "gram", "grams": 1, "confidence": "high", "note": "Direct gram weight."}
    )
    return default_unit, result


def direct_food(seed: dict, profiles: dict[str, dict]) -> dict:
    profile = require_profile(profiles, seed["profile_code"])
    default_unit, portion_rows = portions(seed["portion_kind"])
    note = (
        f"Direct published WAFCT 2019 profile {profile['code']}: {profile['name']}. "
        "Values are per 100 g edible portion."
    )
    if seed["note"]:
        note = f"{note} {seed['note']}"
    return {
        "key": seed["key"],
        "name": seed["name"],
        "aliases": list(seed["aliases"]),
        "countries": list(seed["countries"]),
        "category": seed["category"],
        "default_unit": default_unit,
        "portions": portion_rows,
        "nutrients_per_100g": profile["nutrients_per_100g"],
        "data_quality": "verified_source",
        "source_ids": ["fao_wafct_2019"],
        "source_profile_codes": [profile["code"]],
        "source_note": note,
        "recipe": None,
    }


def calculated_food(seed: dict, profiles: dict[str, dict]) -> dict:
    totals = {nutrient: 0.0 for nutrient in NUTRIENT_COLUMNS}
    ingredient_rows = []
    profile_codes = []
    for code, amount_g, label in seed["ingredients"]:
        profile = require_profile(profiles, code)
        profile_codes.append(code)
        ingredient_rows.append(
            {
                "source_profile_code": code,
                "name": label,
                "source_name": profile["name"],
                "grams": amount_g,
            }
        )
        for nutrient, value in profile["nutrients_per_100g"].items():
            totals[nutrient] += value * amount_g / 100.0

    scale = 100.0 / seed["final_weight_g"]
    nutrient_profile = {
        nutrient: round(total * scale, 4)
        for nutrient, total in totals.items()
    }
    default_unit, portion_rows = portions(seed["portion_kind"])
    return {
        "key": seed["key"],
        "name": seed["name"],
        "aliases": list(seed["aliases"]),
        "countries": list(seed["countries"]),
        "category": seed["category"],
        "default_unit": default_unit,
        "portions": portion_rows,
        "nutrients_per_100g": nutrient_profile,
        "data_quality": "calculated_recipe",
        "source_ids": ["fao_wafct_2019"],
        "source_profile_codes": sorted(set(profile_codes)),
        "source_note": (
            "NutriRoot baseline calculated from published WAFCT 2019 ingredient profiles and the stated final yield. "
            f"{seed['note']}"
        ),
        "recipe": {
            "kind": "nutriroot_baseline",
            "final_weight_g": seed["final_weight_g"],
            "ingredients": ingredient_rows,
        },
    }


def validate(foods: list[dict]) -> None:
    keys = [food["key"] for food in foods]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate food keys: {duplicates}")

    known_countries = set(WEST_AFRICAN_COUNTRIES)
    for food in foods:
        unknown = set(food["countries"]) - known_countries
        if unknown:
            raise ValueError(f"{food['key']} has unsupported countries: {sorted(unknown)}")
        if not food["aliases"]:
            raise ValueError(f"{food['key']} has no aliases")
        for name, value in food["nutrients_per_100g"].items():
            if value is None or value < 0 or not math.isfinite(value):
                raise ValueError(f"{food['key']} has invalid {name}: {value}")

    alias_owner: dict[str, str] = {}
    for food in foods:
        for alias in food["aliases"]:
            normalised = normalise_alias(alias)
            owner = alias_owner.get(normalised)
            if owner and owner != food["key"]:
                raise ValueError(f"Alias {alias!r} is shared by {owner} and {food['key']}")
            alias_owner[normalised] = food["key"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-source-profiles",
        action="store_true",
        help=(
            "Write the complete 1,028-profile WAFCT audit export locally. This file is not "
            "required at runtime and must not be included in the distributable package."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not WORKBOOK.exists():
        raise SystemExit(f"Missing source workbook: {WORKBOOK}")

    profiles = load_profiles()
    foods = [direct_food(seed, profiles) for seed in DIRECT_FOODS]
    foods.extend(calculated_food(seed, profiles) for seed in RECIPES)
    foods.sort(key=lambda food: (food["category"], food["name"]))
    validate(foods)

    country_counts = {
        country: sum(country in food["countries"] for food in foods)
        for country in WEST_AFRICAN_COUNTRIES
    }
    category_counts = dict(sorted(Counter(food["category"] for food in foods).items()))
    catalogue = {
        "schema_version": "1.0",
        "app_version": "0.4.0",
        "scope": "UK-facing Nigerian and West African food catalogue",
        "methodology": (
            "Published WAFCT per-100 g profiles are used directly for simple foods. Mixed dishes are transparent "
            "NutriRoot baseline recipes calculated from WAFCT ingredients and a stated final cooked yield."
        ),
        "coverage_tiers": COVERAGE_TIERS,
        "sources": SOURCES,
        "stats": {
            "source_profiles": len(profiles),
            "catalogue_foods": len(foods),
            "verified_source_foods": sum(food["data_quality"] == "verified_source" for food in foods),
            "calculated_recipe_foods": sum(food["data_quality"] == "calculated_recipe" for food in foods),
            "countries": len(WEST_AFRICAN_COUNTRIES),
            "country_counts": country_counts,
            "category_counts": category_counts,
        },
        "foods": foods,
    }

    CATALOG_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_OUTPUT.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.write_source_profiles:
        PROFILES_OUTPUT.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "source_id": "fao_wafct_2019",
                    "profiles": sorted(profiles.values(), key=lambda profile: profile["code"]),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(
        f"Built {len(foods)} catalogue foods using {len(profiles)} WAFCT profiles "
        f"across {len(WEST_AFRICAN_COUNTRIES)} countries."
    )


if __name__ == "__main__":
    main()
