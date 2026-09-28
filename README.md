# NutriRoot MVP — V0.4

V0.4 expands NutriRoot from a five-food prototype into a UK-facing Nigerian and West African nutrition catalogue, then connects that catalogue to an optional AI meal parser.

## What is included

- A build pipeline that reads 1,028 nutrient profiles from the FAO/INFOODS Food Composition Table for Western Africa 2019.
- 101 user-facing foods across 16 geographic West African countries.
- 53 foods that use a direct published WAFCT profile.
- 48 mixed dishes calculated from named WAFCT ingredient profiles and a stored final cooked yield.
- Nigerian and Ghanaian depth first, followed by Sierra Leonean, Gambian, Senegalese, Ivorian, Liberian, Guinean and wider regional coverage.
- Local alias parsing for names such as `iyan`, `ceebu jën`, `domoda`, `moin moin`, `koose`, `ewa riro`, `attieké` and `bofrot`.
- Optional OpenAI Structured Outputs parsing for freer meal descriptions.
- Catalogue, source, recipe, coverage and search endpoints.

Examples include jollof rice, egusi, ogbono, efo riro, edikang ikong, afang, bitterleaf soup, pepper soup, waakye, banku, kenkey, red red, kontomire stew, thieboudienne, yassa, maafe/domoda, benachin, cassava-leaf stew, plasas, palm-butter soup, attiéké, kedjenou, cachupa, dambou, djenkoume, riz gras, suya, akara, moi moi, puff puff, chin chin and common staples, proteins, fish, leaves and drinks.

## Why the UK coverage starts with Nigeria and Ghana

The coverage plan uses Census 2021 evidence for England and Wales rather than treating every cuisine as equally represented in the first release. ONS reported Nigerian and Ghanaian as the two largest specified backgrounds within the Black African write-in groups, at roughly 271,000 and 113,000 people respectively. Country-of-birth data also records 270,768 Nigerian-born residents in England and Wales.

- [ONS: Ethnic group, England and Wales — Census 2021](https://www.ons.gov.uk/peoplepopulationandcommunity/culturalidentity/ethnicity/bulletins/ethnicgroupenglandandwales/census2021)
- [ONS: 2021 Census statistics — Nigerians in the UK](https://www.ons.gov.uk/aboutus/transparencyandgovernance/freedomofinformationfoi/2021censusstatisticsnigeriansintheuk)
- [ONS: Country of birth dataset TS004](https://www.ons.gov.uk/datasets/TS004/editions/2021/versions/3)

Those figures are a prioritisation signal, not a claim about the exact UK population in 2026. The catalogue still provides at least some coverage for every geographic West African country.

## Nutrition methodology

The generated database is in `backend/data/catalog.json`. Its two active quality classes are:

- `verified_source`: a direct per-100 g published WAFCT profile.
- `calculated_recipe`: a NutriRoot baseline calculated from WAFCT ingredient profiles and a stated final cooked weight.

V0.4 has no active `development_estimate` foods. A calculated recipe still is not a universal recipe. Oil, water loss, protein choice, seasoning and household portions can change the result substantially, so every mixed dish exposes its ingredient weights, source profile codes and final yield through `GET /catalog/{key}`.

Primary source:

- [FAO/INFOODS Food Composition Table for Western Africa 2019](https://www.fao.org/food-composition/tables-and-databases/detail/food-composition-tables/en)

The source workbook permits attributed use for private study, research, teaching and non-commercial products. FAO directs requests for translation or adaptation rights, resale and other commercial use to its permissions service. V0.4 is therefore a development prototype and is not cleared for commercial distribution. Read [DATA_LICENSE.md](DATA_LICENSE.md) before publishing or commercialising the catalogue.

The UK [Composition of Foods Integrated Dataset 2021](https://www.gov.uk/government/publications/composition-of-foods-integrated-dataset-cofid) is registered as a future UK-market validation source. V0.4 nutrient rows are generated from WAFCT.

To rebuild the JSON files, download the official `WAFCT_2019.xlsx` workbook into `backend/data/reference/`, install `openpyxl`, then run:

```powershell
cd backend
py tools/build_catalog.py
```

The build validates source codes, required nutrient fields, duplicate keys, duplicate aliases and country tags before writing the runtime database. It does not copy the full WAFCT profile library into the distributable app. For a local audit export only, run `py tools/build_catalog.py --write-source-profiles`; `backend/data/source_profiles.json` is ignored and excluded from release packages.

## AI parser

NutriRoot uses its expanded local parser by default. The AI parser runs only when both `OPENAI_PARSER_ENABLED=true` and an `OPENAI_API_KEY` are present. It sends the meal description and compact catalogue to the OpenAI Responses API and parses a typed Pydantic result. Returned canonical keys are checked against the local catalogue before nutrition is calculated. If the API is unavailable, the request automatically falls back to local parsing.

Create `backend/.env` from the example:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-6-luna
OPENAI_PARSER_ENABLED=false
```

Keep the API key in the backend only. Never put it in Expo or client-side code. The integration follows the official [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## API endpoints

- `GET /health` — version, parser configuration and catalogue counts.
- `GET /coverage` — country tiers, country counts and category counts.
- `GET /catalog` — searchable summaries; accepts `country`, `category`, `q` and `limit`.
- `GET /catalog/{key}` — complete nutrient, recipe and provenance detail.
- `GET /sources` — registered source records.
- `POST /analyze` — parse a meal, resolve portions, total nutrients and calculate estimated PRAL.

## Windows setup

Backend:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Mobile/web frontend:

```powershell
cd mobile
npm install
npx expo start --web --lan
```

Create `mobile/.env` from `mobile/.env.example` and set it to the deployed backend URL:

```env
EXPO_PUBLIC_API_URL=https://YOUR-RENDER-URL.onrender.com
```

Expo embeds `EXPO_PUBLIC_*` variables at build time, so restart Expo and rebuild Android after changing this value. For local device testing, you can temporarily set it to a reachable LAN URL in the uncommitted `mobile/.env` file.

## Render deployment

The repository-root `render.yaml` defines a free Python web service with `backend` as its root directory. Render installs `backend/requirements.txt`, starts `uvicorn app.main:app`, and checks `/health`. The runtime catalogue is loaded from `backend/data/catalog.json`, so deployment does not require the local WAFCT workbook or any Windows path.

Push the repository to GitHub, create a Render Blueprint from that repository, and let Render read `render.yaml`. Do not add an OpenAI key unless you intend to enable the AI parser. After Render reports a successful deployment, verify `https://YOUR-RENDER-URL.onrender.com/health`, place that service origin in `mobile/.env`, and rebuild the Android app.

## Tests

```powershell
cd backend
py -m pip install -r requirements-dev.txt
py -m pytest -q
```

The test suite covers catalogue scale, country coverage, provenance, recipe detail, portion conversion, alias overlap, Nigerian, Ghanaian and Francophone/Senegambian meal descriptions, and unknown-food handling.

## Prototype limits

- Baseline recipes need validation against weighed UK household and restaurant recipes before health-critical use.
- Direct WAFCT profiles can still represent a specific variety, preparation method or compiled average.
- Household-unit weights remain assumptions unless the user supplies grams.
- AI parsing improves language understanding but does not improve the underlying nutrient profile.
- PRAL is a calculated dietary acid-load estimate, not a measure of kidney function or blood pH.
