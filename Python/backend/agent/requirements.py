from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = "http://192.168.1.14:11434"
MODEL = "qwen2.5:7b"

SYSTEM_PROMPT = (
    "You extract structured car-buying requirements from a buyer's message. "
    "Fill in max_price, vehicle_style, and fuel_type only if the buyer actually "
    "stated them — leave them null otherwise, don't guess or invent values. "
    "Capture anything else the buyer cares about (driving feel, features, "
    "priorities) in must_haves as short freeform phrases, not duplicating "
    "anything already captured in the fields above."
)


class BuyerRequirements(BaseModel):
    max_price: float | None = Field(default=None, description="Maximum budget in dollars, if mentioned.")
    vehicle_style: str | None = Field(default=None, description="Vehicle style/body type, e.g. SUV, Sedan, Truck, Coupe, if mentioned.")
    fuel_type: str | None = Field(default=None, description="Fuel type preference, e.g. diesel, electric, hybrid, if mentioned.")
    must_haves: list[str] = Field(default_factory=list, description="Other stated preferences that don't fit the fields above, e.g. 'sporty', 'good gas mileage'.")


_llm = ChatOllama(model=MODEL, base_url=OLLAMA_BASE_URL)
_structured_llm = _llm.with_structured_output(BuyerRequirements)


def gather_requirements(user_message: str) -> BuyerRequirements:
    return _structured_llm.invoke(
        [("system", SYSTEM_PROMPT), ("human", user_message)]
    )
