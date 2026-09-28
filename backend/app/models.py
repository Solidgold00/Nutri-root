from typing import Literal
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    meal: str = Field(min_length=2, max_length=1000)


class Nutrients(BaseModel):
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fibre_g: float
    sodium_mg: float
    potassium_mg: float
    calcium_mg: float
    magnesium_mg: float
    phosphorus_mg: float


class MealComponent(BaseModel):
    name: str
    canonical_key: str
    matched_food: str
    countries: list[str]
    category: str
    quantity: float
    unit: str
    size: str
    grams: float
    source_id: str
    source_ids: list[str]
    source_profile_codes: list[str]
    source: str
    source_url: str
    data_quality: Literal['verified_source', 'calculated_recipe', 'development_estimate']
    portion_confidence: Literal['low', 'medium', 'high']
    source_note: str


class AnalyzeResponse(BaseModel):
    query: str
    catalogue_version: str
    parser: Literal['ai', 'fallback']
    parser_note: str
    components: list[MealComponent]
    nutrients: Nutrients
    pral_meq: float
    pral_label: str
    confidence: Literal['low', 'medium', 'high']
    data_quality_summary: str
    explanation: str
    disclaimer: str
