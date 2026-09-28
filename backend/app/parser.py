from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .nutrition import FOODS, FOODS_BY_KEY, FoodRecord

load_dotenv()

Size = Literal["small", "medium", "large", "unspecified"]


class AIParsedItem(BaseModel):
    raw_name: str = Field(description="The food phrase exactly as the user described it.")
    canonical_key: str = Field(description="A supplied NutriRoot catalogue key, or unknown.")
    quantity: float = Field(gt=0, le=5000)
    unit: str
    size: Size
    notes: str


class AIParsedMeal(BaseModel):
    items: list[AIParsedItem]


@dataclass(frozen=True)
class ParsedFood:
    raw_name: str
    canonical_key: str
    quantity: float
    unit: str
    size: str = "unspecified"
    notes: str = ""


NUMBER_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "half": 0.5,
    "quarter": 0.25,
}

UNIT_NORMALISATION = {
    "scoop": "scoop",
    "scoops": "scoop",
    "ladle": "ladle",
    "ladles": "ladle",
    "wrap": "wrap",
    "wraps": "wrap",
    "piece": "piece",
    "pieces": "piece",
    "cup": "cup",
    "cups": "cup",
    "serving": "serving",
    "servings": "serving",
    "plate": "plate",
    "plates": "plate",
    "bowl": "bowl",
    "bowls": "bowl",
    "ball": "ball",
    "balls": "ball",
    "slice": "slice",
    "slices": "slice",
    "spoon": "spoon",
    "spoons": "spoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "tbsp": "tablespoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "tsp": "teaspoon",
    "skewer": "skewer",
    "skewers": "skewer",
    "fillet": "fillet",
    "fillets": "fillet",
    "egg": "egg",
    "eggs": "egg",
    "bottle": "bottle",
    "bottles": "bottle",
    "glass": "glass",
    "glasses": "glass",
    "gram": "gram",
    "grams": "gram",
    "g": "gram",
    "kilogram": "kilogram",
    "kilograms": "kilogram",
    "kg": "kilogram",
    "millilitre": "millilitre",
    "millilitres": "millilitre",
    "milliliter": "millilitre",
    "milliliters": "millilitre",
    "ml": "millilitre",
    "litre": "litre",
    "litres": "litre",
    "liter": "litre",
    "liters": "litre",
    "l": "litre",
}

NUMBER_PATTERN = (
    r"one[ ]+and[ ]+a[ ]+half|"
    r"[0-9]+(?:[.][0-9]+)?|[0-9]+[ ]*/[ ]*[0-9]+|"
    r"a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|half|quarter"
)
UNIT_PATTERN = "|".join(
    sorted((re.escape(unit) for unit in UNIT_NORMALISATION), key=len, reverse=True)
)
DETAIL_PATTERN = re.compile(
    rf"(?P<num>{NUMBER_PATTERN})"
    rf"(?:[ ]+(?P<size>small|medium|large|big))?"
    rf"(?:[ ]+(?P<unit>{UNIT_PATTERN}))?"
    rf"(?:[ ]+of)?$"
)
DETAIL_WITHOUT_NUMBER_PATTERN = re.compile(
    rf"(?P<size>small|medium|large|big)[ ]+"
    rf"(?P<unit>{UNIT_PATTERN})"
    rf"(?:[ ]+of)?$"
)


def normalise_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("½", " half ").replace("¼", " quarter ")
    return re.sub("[ ]+", " ", value).strip()


def _number(value: str | None) -> float:
    if not value:
        return 1.0
    lowered = " ".join(value.lower().split())
    if lowered == "one and a half":
        return 1.5
    if lowered in NUMBER_WORDS:
        return NUMBER_WORDS[lowered]
    if "/" in lowered:
        numerator, denominator = lowered.split("/", maxsplit=1)
        try:
            return float(numerator.strip()) / float(denominator.strip())
        except (ValueError, ZeroDivisionError):
            return 1.0
    try:
        return float(lowered)
    except ValueError:
        return 1.0


def _normalise_quantity_unit(quantity: float, unit: str) -> tuple[float, str]:
    if unit == "kilogram":
        return quantity * 1000.0, "gram"
    if unit == "litre":
        return quantity * 1000.0, "millilitre"
    return quantity, unit


def _extract_details_before(text: str, start: int, default_unit: str) -> tuple[float, str, str]:
    before = text[max(0, start - 100):start]
    # Keep only the current food phrase, so a quantity from the previous item is not reused.
    phrase = re.split("[,;+]|(?:^|[ ])(?:and|with|plus|then)(?:[ ]|$)", before)[-1].strip()
    match = DETAIL_PATTERN.search(phrase) or DETAIL_WITHOUT_NUMBER_PATTERN.search(phrase)
    if not match:
        return 1.0, default_unit, "unspecified"

    quantity = _number(match.group("num"))
    unit_raw = match.group("unit")
    unit = UNIT_NORMALISATION.get(unit_raw, default_unit) if unit_raw else default_unit
    quantity, unit = _normalise_quantity_unit(quantity, unit)
    size = match.group("size") or "unspecified"
    if size == "big":
        size = "large"
    return quantity, unit, size


@lru_cache(maxsize=1)
def _alias_entries() -> tuple[tuple[str, FoodRecord], ...]:
    entries: list[tuple[str, FoodRecord]] = []
    for food in FOODS:
        aliases = set(food.aliases)
        aliases.add(food.name)
        for alias in aliases:
            normalised = normalise_text(alias)
            if normalised:
                entries.append((normalised, food))
    entries.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(entries)


def fallback_parse(text: str) -> list[ParsedFood]:
    lowered = normalise_text(text)
    candidates: list[tuple[int, int, str, FoodRecord]] = []
    for alias, food in _alias_entries():
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])")
        for match in pattern.finditer(lowered):
            candidates.append((match.start(), match.end(), alias, food))

    # Prefer earlier matches, and prefer the longest alias when two matches overlap.
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    selected: list[tuple[int, int, str, FoodRecord]] = []
    for candidate in candidates:
        start, end, _, _ = candidate
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end, _, _ in selected):
            continue
        selected.append(candidate)

    selected.sort(key=lambda item: item[0])
    parsed: list[ParsedFood] = []
    for start, _, alias, food in selected:
        quantity, unit, size = _extract_details_before(lowered, start, food.default_unit)
        parsed.append(
            ParsedFood(
                raw_name=alias,
                canonical_key=food.key,
                quantity=quantity,
                unit=unit,
                size=size,
                notes="Parsed locally from the V0.4 alias catalogue.",
            )
        )
    return parsed


@lru_cache(maxsize=1)
def _ai_catalogue_prompt() -> str:
    rows = []
    for food in FOODS:
        aliases = ", ".join(food.aliases)
        rows.append(f"{food.key} | {food.name} | aliases: {aliases} | default unit: {food.default_unit}")
    return "\n".join(rows)


def _match_ai_key(item: AIParsedItem) -> str | None:
    if item.canonical_key in FOODS_BY_KEY:
        return item.canonical_key
    if item.canonical_key == "unknown":
        return None
    local = fallback_parse(item.raw_name)
    return local[0].canonical_key if len(local) == 1 else None


def ai_parse(text: str) -> list[ParsedFood]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    system_prompt = (
        "You are NutriRoot's meal parser. Extract only foods the user explicitly says they ate. "
        "Map each food to exactly one canonical key from the supplied catalogue. Use canonical_key='unknown' "
        "when no entry is a clear match; never invent a key. Do not calculate calories or nutrients. Preserve "
        "an explicit quantity and household unit. Use quantity 1 when none is stated. Use a singular, simple unit "
        "such as gram, millilitre, cup, bowl, plate, ladle, scoop, wrap, ball, piece, slice, skewer, egg, "
        "tablespoon, teaspoon, serving, glass or bottle. For 'two small pieces of beef', return quantity 2, "
        "unit piece and size small. If the input is unrelated to food, return an empty items array.\n\n"
        "CATALOGUE:\n"
        + _ai_catalogue_prompt()
    )
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        text_format=AIParsedMeal,
        store=False,
    )
    result = response.output_parsed
    if result is None:
        return []

    parsed: list[ParsedFood] = []
    for item in result.items:
        canonical_key = _match_ai_key(item)
        if canonical_key is None:
            continue
        food = FOODS_BY_KEY[canonical_key]
        unit_raw = normalise_text(item.unit)
        unit = UNIT_NORMALISATION.get(unit_raw, unit_raw or food.default_unit)
        quantity, unit = _normalise_quantity_unit(item.quantity, unit)
        parsed.append(
            ParsedFood(
                raw_name=item.raw_name,
                canonical_key=canonical_key,
                quantity=quantity,
                unit=unit,
                size=item.size,
                notes=item.notes,
            )
        )
    return parsed


def parse_meal(text: str) -> tuple[list[ParsedFood], Literal["ai", "fallback"], str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    ai_enabled = os.getenv("OPENAI_PARSER_ENABLED", "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if api_key and ai_enabled:
        try:
            items = ai_parse(text)
            if items:
                model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
                return items, "ai", f"Parsed with OpenAI Structured Outputs using {model}."
        except Exception as exc:
            fallback = fallback_parse(text)
            return (
                fallback,
                "fallback",
                f"AI parsing was unavailable ({type(exc).__name__}); used the local V0.4 parser.",
            )

    items = fallback_parse(text)
    if api_key and not ai_enabled:
        note = "AI parsing is disabled by configuration; used the local V0.4 parser."
    elif api_key:
        note = "AI returned no recognised catalogue foods; used the local V0.4 parser."
    else:
        note = "OPENAI_API_KEY is not configured; used the local V0.4 parser."
    return items, "fallback", note
