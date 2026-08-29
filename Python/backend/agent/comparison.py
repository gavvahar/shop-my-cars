import re

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from .requirements import BuyerRequirements, MODEL, OLLAMA_BASE_URL

SYSTEM_PROMPT = (
    "You compare cars for a buyer based ONLY on the dataset results and web "
    "results provided below. Never invent a spec, price, or fact not present "
    "in that data — if you don't have a piece of information, omit it rather "
    "than guessing.\n\n"
    "Do NOT fill in msrp, highway_mpg, city_mpg, or horsepower yourself — "
    "leave those fields null. They are populated automatically from the "
    "dataset after you respond, so restating them is unnecessary and risks "
    "getting them wrong.\n\n"
    "Write pros/cons as QUALITATIVE, comparative statements (e.g. 'more "
    "fuel-efficient than the other option', 'stronger highway range', "
    "'noticeably more powerful') rather than restating exact numbers — the "
    "exact figures are shown separately and authoritatively, so you don't "
    "need to (and shouldn't) cite them in prose. If a number does slip into "
    "your prose anyway, make sure it belongs to the specific car/row being "
    "described, not a similar row for a different year, and never swap "
    "city vs. highway MPG.\n\n"
    "For each car's pros/cons, note in the 'sources' field whether the claim "
    "came from the dataset or a specific web result URL. When a claim comes "
    "from the dataset, use exactly the word 'dataset' in sources — not a "
    "description or restated fact. Compare only the "
    "3-5 most relevant candidates, not every result provided — prioritize "
    "based on the buyer's stated requirements. If no web results are "
    "available, still produce a comparison using the dataset alone, and set "
    "the 'notes' field to mention that current market pricing wasn't "
    "available.\n\n"
    "Every dollar figure you DO mention in prose (e.g. describing a web "
    "listing's price) MUST be either that car's exact MSRP from the dataset "
    "or a price explicitly given in a web result's snippet — never invent a "
    "trade-in value, financing estimate, or asking price that isn't "
    "literally present in the provided data. Every source URL you cite in "
    "'sources' MUST be copied exactly from a web result's actual url field "
    "— never construct, guess, or format a plausible-looking URL yourself."
)


class CarSummary(BaseModel):
    make: str
    model: str
    year: int
    msrp: float | None = Field(default=None, description="Populated programmatically from the dataset, not LLM-stated.")
    highway_mpg: int | None = Field(default=None, description="Populated programmatically from the dataset, not LLM-stated.")
    city_mpg: int | None = Field(default=None, description="Populated programmatically from the dataset, not LLM-stated.")
    horsepower: float | None = Field(default=None, description="Populated programmatically from the dataset, not LLM-stated.")
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list, description="'dataset' or a specific web result URL per claim.")


class CarComparison(BaseModel):
    cars: list[CarSummary]
    notes: str = Field(default="", description="Caveats, e.g. live pricing unavailable.")


def _format_dataset_results(dataset_results):
    lines = []
    for i, car in enumerate(dataset_results, start=1):
        lines.append(
            f"{i}. {car['make']} {car['model']} ({car['year']}) - MSRP: ${car['msrp']:,.0f}, "
            f"style: {car['vehicle_style']}, fuel: {car['engine_fuel_type']}, "
            f"HP: {car['engine_hp']}, highway MPG: {car['highway_mpg']}, city MPG: {car['city_mpg']}"
        )
    return "\n".join(lines)


def _format_web_results(web_results):
    if not web_results:
        return "(no web results available)"
    lines = []
    for i, result in enumerate(web_results, start=1):
        lines.append(f"{i}. {result['title']} — {result['snippet']} (price: {result.get('price')}) [{result['url']}]")
    return "\n".join(lines)


_llm = ChatOllama(model=MODEL, base_url=OLLAMA_BASE_URL)
_structured_llm = _llm.with_structured_output(CarComparison)


def compile_comparison(requirements: BuyerRequirements, dataset_results: list[dict], web_results: list[dict]) -> CarComparison:
    prompt = (
        f"Buyer requirements: max_price={requirements.max_price}, "
        f"vehicle_style={requirements.vehicle_style}, fuel_type={requirements.fuel_type}, "
        f"must_haves={requirements.must_haves}\n\n"
        f"Dataset results:\n{_format_dataset_results(dataset_results)}\n\n"
        f"Web results:\n{_format_web_results(web_results)}"
    )
    return _structured_llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])


MPG_CLAIM_PATTERN = re.compile(
    r"(\d+)(?:-(\d+))?\s*(?:(city|highway)\s+)?"
    r"(?:mpg|mi(?:le)?s?(?:\s+per\s+|/)gal(?:lon)?s?)\s*(city|highway)?",
    re.IGNORECASE,
)
HP_CLAIM_PATTERN = re.compile(r"(\d+)(?:-(\d+))?\s*(?:hp\b|horsepower)", re.IGNORECASE)


def _find_source_rows(car, dataset_results):
    return [row for row in dataset_results if row["make"].lower() == car.make.lower() and row["model"].lower() == car.model.lower() and row["year"] == car.year]


DOLLAR_CLAIM_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?")
URL_PATTERN = re.compile(r"https?://\S+")


def _parse_dollar_amount(text):
    return float(text.replace("$", "").replace(",", ""))


def _real_dollar_amounts(source_rows, web_results):
    amounts = {row["msrp"] for row in source_rows if row.get("msrp") is not None}
    for result in web_results:
        price_str = result.get("price")
        if price_str:
            try:
                amounts.add(_parse_dollar_amount(price_str))
            except ValueError:
                pass
    return amounts


def _claim_matches_source(text, source_rows, web_results):
    # MPG/HP figures are now redundant with the code-populated authoritative
    # fields on CarSummary (msrp, highway_mpg, city_mpg, horsepower) — rather
    # than trying to validate individual numbers in free-form comparative
    # prose (e.g. "20 vs 19 MPG", where extraction regexes keep finding new
    # phrasing gaps), strip any claim that mentions one of these units at
    # all. The real numbers are already shown separately and authoritatively.
    if MPG_CLAIM_PATTERN.search(text) or HP_CLAIM_PATTERN.search(text):
        return False

    real_dollars = _real_dollar_amounts(source_rows, web_results)
    for match in DOLLAR_CLAIM_PATTERN.finditer(text):
        claimed_amount = _parse_dollar_amount(match.group(0))
        if claimed_amount not in real_dollars:
            return False

    return True


def _is_valid_dataset_source(source):
    normalized = source.strip().strip(".").lower()
    return normalized in {"dataset", "the dataset", "car dataset", "local dataset"}


def _validate_sources(sources, web_results):
    real_urls = [result.get("url", "") for result in web_results if result.get("url")]
    kept = []
    dropped_count = 0
    for source in sources:
        urls_in_source = URL_PATTERN.findall(source)
        if urls_in_source:
            if any(claimed_url in real_url or real_url in claimed_url for claimed_url in urls_in_source for real_url in real_urls):
                kept.append(source)
            else:
                dropped_count += 1
        elif _is_valid_dataset_source(source):
            kept.append(source)
        else:
            dropped_count += 1
    return kept, dropped_count


def validate_comparison(comparison: CarComparison, dataset_results: list[dict], web_results: list[dict]) -> CarComparison:
    dropped_claims = []
    dropped_sources = []
    fabricated_cars = []
    validated_cars = []

    for car in comparison.cars:
        source_rows = _find_source_rows(car, dataset_results)

        if not source_rows:
            fabricated_cars.append(f"{car.make} {car.model} ({car.year})")
            continue

        kept_pros = [p for p in car.pros if _claim_matches_source(p, source_rows, web_results)]
        kept_cons = [c for c in car.cons if _claim_matches_source(c, source_rows, web_results)]
        dropped_count = (len(car.pros) - len(kept_pros)) + (len(car.cons) - len(kept_cons))
        if dropped_count:
            dropped_claims.append(f"{car.make} {car.model} ({car.year}): {dropped_count} claim(s) removed")

        kept_sources, source_drop_count = _validate_sources(car.sources, web_results)
        if source_drop_count:
            dropped_sources.append(f"{car.make} {car.model} ({car.year}): {source_drop_count} fabricated source(s) removed")

        validated_cars.append(car.model_copy(update={"pros": kept_pros, "cons": kept_cons, "sources": kept_sources}))

    notes = comparison.notes
    if dropped_claims:
        notes = (notes + " " if notes else "") + ("Data-accuracy check removed unverifiable claims: " + "; ".join(dropped_claims) + ".")
    if dropped_sources:
        notes = (notes + " " if notes else "") + ("Removed source citation(s) that didn't match any real web result: " + "; ".join(dropped_sources) + ".")
    if fabricated_cars:
        notes = (notes + " " if notes else "") + ("WARNING: could not match to any dataset result, excluded as likely fabricated: " + "; ".join(fabricated_cars) + ".")

    return comparison.model_copy(update={"cars": validated_cars, "notes": notes})


def apply_authoritative_specs(comparison: CarComparison, dataset_results: list[dict]) -> CarComparison:
    updated_cars = []
    for car in comparison.cars:
        source_rows = _find_source_rows(car, dataset_results)
        if not source_rows:
            updated_cars.append(car)
            continue

        primary_row = source_rows[0]
        updated_cars.append(
            car.model_copy(
                update={
                    "msrp": primary_row.get("msrp"),
                    "highway_mpg": primary_row.get("highway_mpg"),
                    "city_mpg": primary_row.get("city_mpg"),
                    "horsepower": primary_row.get("engine_hp"),
                }
            )
        )
    return comparison.model_copy(update={"cars": updated_cars})
