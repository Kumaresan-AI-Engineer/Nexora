from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import PlainSerializer

Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class ProviderName(StrEnum):
    OPENAI = "openai"
    GEMINI = "gemini"


class BuyingMode(StrEnum):
    RETAIL = "retail"
    BUSINESS = "business"


class Market(StrEnum):
    INDIA = "india"
    GLOBAL = "global"
