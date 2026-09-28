export type Nutrients = {
  calories_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fibre_g: number;
  sodium_mg: number;
  potassium_mg: number;
  calcium_mg: number;
  magnesium_mg: number;
  phosphorus_mg: number;
};

export type MealComponent = {
  name: string;
  canonical_key: string;
  matched_food: string;
  countries: string[];
  category: string;
  quantity: number;
  unit: string;
  size: string;
  grams: number;
  source_id: string;
  source_ids: string[];
  source_profile_codes: string[];
  source: string;
  source_url: string;
  data_quality: 'verified_source' | 'calculated_recipe' | 'development_estimate';
  portion_confidence: 'low' | 'medium' | 'high';
  source_note: string;
};

export type AnalysisResult = {
  query: string;
  catalogue_version: string;
  parser: 'ai' | 'fallback';
  parser_note: string;
  components: MealComponent[];
  nutrients: Nutrients;
  pral_meq: number;
  pral_label: string;
  confidence: 'low' | 'medium' | 'high';
  data_quality_summary: string;
  explanation: string;
  disclaimer: string;
};
