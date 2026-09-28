from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import AnalyzeRequest, AnalyzeResponse, MealComponent
from .nutrition import (
    CATALOG_METADATA,
    FOODS,
    SOURCES,
    FoodRecord,
    add_nutrients,
    calculate_pral,
    get_food,
    get_food_sources,
    nutrients_for_grams,
    resolve_portion_grams,
)
from .parser import normalise_text, parse_meal

VERSION = "0.4.0"

app = FastAPI(title="NutriRoot Nutrition API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _food_payload(food: FoodRecord, include_recipe: bool = False) -> dict:
    sources = get_food_sources(food)
    payload = {
        "key": food.key,
        "name": food.name,
        "aliases": list(food.aliases),
        "countries": list(food.countries),
        "category": food.category,
        "data_quality": food.data_quality,
        "source_ids": list(food.source_ids),
        "source_profile_codes": list(food.source_profile_codes),
        "sources": [source.title for source in sources],
        "default_unit": food.default_unit,
        "portions": [portion.__dict__ for portion in food.portions],
        "source_note": food.source_note,
    }
    if include_recipe:
        payload["nutrients_per_100g"] = food.nutrients_per_100g.model_dump()
        payload["recipe"] = food.recipe
    return payload


@app.get("/health")
def health():
    stats = CATALOG_METADATA["stats"]
    return {
        "status": "ok",
        "version": VERSION,
        "ai_parser_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "ai_parser_enabled": os.getenv("OPENAI_PARSER_ENABLED", "").strip().casefold()
        in {"1", "true", "yes", "on"},
        "ai_model": os.getenv("OPENAI_MODEL", "gpt-6-luna"),
        "catalogue_records": len(FOODS),
        "source_profiles": stats["source_profiles"],
        "countries": stats["countries"],
    }


@app.get("/coverage")
def coverage():
    return {
        "version": VERSION,
        "scope": CATALOG_METADATA["scope"],
        "methodology": CATALOG_METADATA["methodology"],
        "coverage_tiers": CATALOG_METADATA["coverage_tiers"],
        "stats": CATALOG_METADATA["stats"],
    }


@app.get("/catalog")
def catalog(
    country: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(default=250, ge=1, le=500),
):
    country_query = normalise_text(country) if country else None
    category_query = normalise_text(category) if category else None
    text_query = normalise_text(q) if q else None
    matches = []
    for food in FOODS:
        if country_query and not any(
            normalise_text(item) == country_query for item in food.countries
        ):
            continue
        if category_query and normalise_text(food.category) != category_query:
            continue
        if text_query:
            haystack = normalise_text(" ".join((food.name, *food.aliases)))
            if text_query not in haystack:
                continue
        matches.append(_food_payload(food))
        if len(matches) >= limit:
            break
    return matches


@app.get("/catalog/{key}")
def catalog_food(key: str):
    food = get_food(key)
    if food is None:
        raise HTTPException(status_code=404, detail="Food not found in the V0.4 catalogue.")
    return _food_payload(food, include_recipe=True)


@app.get("/sources")
def sources():
    return [source.__dict__ for source in SOURCES.values()]


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    parsed_items, parser_source, parser_note = parse_meal(payload.meal)

    recognised = []
    for item in parsed_items:
        food = get_food(item.canonical_key)
        if food is None:
            continue
        grams, portion_confidence, portion_note = resolve_portion_grams(
            food,
            item.quantity,
            item.unit,
            item.size,
        )
        recognised.append((item, food, grams, portion_confidence, portion_note))

    if not recognised:
        raise HTTPException(
            status_code=422,
            detail="No foods in the current V0.4 catalogue were recognised.",
        )

    nutrients = add_nutrients(
        [
            nutrients_for_grams(food, grams)
            for _, food, grams, _, _ in recognised
        ]
    )
    pral = calculate_pral(nutrients)

    if pral > 5:
        pral_label = "Higher estimated acid-producing load"
    elif pral < -5:
        pral_label = "Lower / alkaline-producing estimated load"
    else:
        pral_label = "Near-neutral estimated dietary acid load"

    qualities = [food.data_quality for _, food, _, _, _ in recognised]
    portion_confidences = [confidence for _, _, _, confidence, _ in recognised]

    if "development_estimate" in qualities:
        confidence = "low"
        data_quality_summary = (
            "Contains development-estimate food data. Treat totals as an early prototype estimate."
        )
    elif "low" in portion_confidences:
        confidence = "low"
        data_quality_summary = (
            "Published nutrient profiles or calculated recipes are available, but at least one portion uses a broad household assumption."
        )
    elif all(quality == "verified_source" for quality in qualities) and all(
        item == "high" for item in portion_confidences
    ):
        confidence = "high"
        data_quality_summary = (
            "All recognised foods use direct published profiles and high-confidence portions."
        )
    else:
        confidence = "medium"
        data_quality_summary = (
            "Uses published WAFCT profiles and/or transparent baseline recipes with stated household-portion assumptions."
        )

    components = []
    for item, food, grams, portion_confidence, portion_note in recognised:
        source_rows = get_food_sources(food)
        primary_source = source_rows[0]
        source_label = " | ".join(
            f"{source.publisher} — {source.title}" for source in source_rows
        )
        components.append(
            MealComponent(
                name=item.raw_name,
                canonical_key=food.key,
                matched_food=food.name,
                countries=list(food.countries),
                category=food.category,
                quantity=item.quantity,
                unit=item.unit,
                size=item.size,
                grams=round(grams, 1),
                source_id=primary_source.id,
                source_ids=list(food.source_ids),
                source_profile_codes=list(food.source_profile_codes),
                source=source_label,
                source_url=primary_source.url,
                data_quality=food.data_quality,
                portion_confidence=portion_confidence,
                source_note=f"{food.source_note} Portion: {portion_note}",
            )
        )

    return AnalyzeResponse(
        query=payload.meal,
        catalogue_version=VERSION,
        parser=parser_source,
        parser_note=parser_note,
        components=components,
        nutrients=nutrients,
        pral_meq=round(pral, 2),
        pral_label=pral_label,
        confidence=confidence,
        data_quality_summary=data_quality_summary,
        explanation=(
            "V0.4 maps each recognised food to a published WAFCT profile or a transparent baseline recipe, "
            "converts household portions to grams, scales per-100 g nutrients, totals the meal, then calculates PRAL in code."
        ),
        disclaimer=(
            "Development build, not medical advice. Mixed dishes and household portions vary by cook, brand and serving. "
            "PRAL estimates dietary acid load from nutrient composition; it does not measure blood pH or kidney function."
        ),
    )
