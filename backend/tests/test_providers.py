import httpx2
import openai
import pytest
from google.genai import errors as genai_errors

from app.config import Settings
from app.providers.base import (
    PreparedImage,
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderQuotaError,
    ProviderRejectedInputError,
    ProviderTimeoutError,
)
from app.providers.gemini_provider import GeminiVisionProvider
from app.providers.openai_provider import OpenAIVisionProvider
from app.providers.registry import ProviderRegistry
from app.schemas.common import ProviderName
from tests.factories import extraction

IMG = PreparedImage(data=b"\xff\xd8\xff fake", mime_type="image/jpeg")


def settings(**kw):
    return Settings(_env_file=None, **kw)


# ---- registry routing -----------------------------------------------------------------
def test_registry_routes_to_requested_provider_only():
    reg = ProviderRegistry(
        settings(
            openai_api_key="sk-x",
            openai_vision_model="m1",
            gemini_api_key="g",
            gemini_vision_model="m2",
        )
    )
    o, g = reg.get(ProviderName.OPENAI), reg.get(ProviderName.GEMINI)
    assert isinstance(o, OpenAIVisionProvider) and o.model == "m1"
    assert isinstance(g, GeminiVisionProvider) and g.model == "m2"


def test_unconfigured_provider_never_falls_back_and_names_missing_vars():
    reg = ProviderRegistry(settings(openai_api_key="sk-x", openai_vision_model="m1"))
    with pytest.raises(ProviderNotConfiguredError) as e:
        reg.get(ProviderName.GEMINI)
    assert "GEMINI_API_KEY" in e.value.message and "GEMINI_VISION_MODEL" in e.value.message
    assert e.value.details["missing"] == ["GEMINI_API_KEY", "GEMINI_VISION_MODEL"]


def test_model_name_required_not_hardcoded():
    reg = ProviderRegistry(settings(openai_api_key="sk-x"))
    with pytest.raises(ProviderNotConfiguredError) as e:
        reg.get(ProviderName.OPENAI)
    assert e.value.details["missing"] == ["OPENAI_VISION_MODEL"]


def test_capabilities_expose_missing_names_not_values():
    caps = ProviderRegistry(
        settings(openai_api_key="sk-secret", openai_vision_model="m")
    ).capabilities()
    assert {"provider": "openai", "configured": True, "missing": []} in caps
    assert "sk-secret" not in repr(caps)


# ---- OpenAI adapter ---------------------------------------------------------------------
class FakeResponses:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.kwargs = result, error, None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


class FakeOpenAI:
    def __init__(self, **kw):
        self.responses = FakeResponses(**kw)


class Parsed:
    def __init__(self, parsed):
        self.output_parsed = parsed


def oa_error(cls, status):
    req = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    return cls("boom", response=httpx2.Response(status, request=req), body=None)


async def test_openai_success_uses_structured_output_and_no_storage():
    client = FakeOpenAI(result=Parsed(extraction()))
    out = await OpenAIVisionProvider("k", "model-x", client=client).analyze(IMG)
    assert out.generic_name.value == "Paracetamol"
    kw = client.responses.kwargs
    assert kw["model"] == "model-x" and kw["text_format"].__name__ == "ExtractionOutput"
    assert kw["store"] is False
    assert kw["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (oa_error(openai.AuthenticationError, 401), ProviderAuthError),
        (oa_error(openai.RateLimitError, 429), ProviderQuotaError),
        (oa_error(openai.BadRequestError, 400), ProviderRejectedInputError),
        (openai.APITimeoutError(httpx2.Request("POST", "https://x")), ProviderTimeoutError),
        (openai.APIConnectionError(request=httpx2.Request("POST", "https://x")), ProviderError),
        (oa_error(openai.InternalServerError, 500), ProviderError),
    ],
)
async def test_openai_error_mapping(error, expected):
    prov = OpenAIVisionProvider("k", "m", client=FakeOpenAI(error=error))
    with pytest.raises(expected) as e:
        await prov.analyze(IMG)
    assert "sk-" not in e.value.message


async def test_openai_empty_or_malformed_output_rejected():
    with pytest.raises(ProviderBadResponseError):
        await OpenAIVisionProvider("k", "m", client=FakeOpenAI(result=Parsed(None))).analyze(IMG)
    with pytest.raises(ProviderBadResponseError):
        await OpenAIVisionProvider(
            "k", "m", client=FakeOpenAI(result=Parsed({"category": "nope"}))
        ).analyze(IMG)


# ---- Gemini adapter ---------------------------------------------------------------------
class GResp:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, result=None, error=None, delay=0):
        self.result, self.error, self.delay, self.kwargs = result, error, delay, None

    async def generate_content(self, **kwargs):
        import asyncio

        self.kwargs = kwargs
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


class FakeGenai:
    def __init__(self, **kw):
        self.aio = type("A", (), {"models": FakeModels(**kw)})()


async def test_gemini_success_uses_json_schema_config():
    client = FakeGenai(result=GResp(extraction().model_dump_json()))
    out = await GeminiVisionProvider("k", "gem-model", client=client).analyze(IMG)
    assert out.strength.value == "500 mg"
    kw = client.aio.models.kwargs
    assert kw["model"] == "gem-model"
    assert kw["config"].response_mime_type == "application/json"
    assert kw["config"].response_schema.__name__ == "ExtractionOutput"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (genai_errors.ClientError(403, {"error": {"message": "denied"}}), ProviderAuthError),
        (
            genai_errors.ClientError(400, {"error": {"message": "API key not valid"}}),
            ProviderAuthError,
        ),
        (genai_errors.ClientError(429, {"error": {"message": "quota"}}), ProviderQuotaError),
        (
            genai_errors.ClientError(400, {"error": {"message": "bad image"}}),
            ProviderRejectedInputError,
        ),
        (genai_errors.ServerError(503, {"error": {"message": "x"}}), ProviderError),
        (httpx2.ReadTimeout("slow"), ProviderTimeoutError),
        (httpx2.ConnectError("down"), ProviderError),
    ],
)
async def test_gemini_error_mapping(error, expected):
    prov = GeminiVisionProvider("k", "m", client=FakeGenai(error=error))
    with pytest.raises(expected):
        await prov.analyze(IMG)


async def test_gemini_malformed_empty_and_slow_responses():
    for result in (GResp("not json"), GResp('{"category": "medicine"}'), GResp(None)):
        with pytest.raises(ProviderBadResponseError):
            await GeminiVisionProvider("k", "m", client=FakeGenai(result=result)).analyze(IMG)
    slow = GeminiVisionProvider(
        "k", "m", timeout=0.05, client=FakeGenai(result=GResp("{}"), delay=1)
    )
    with pytest.raises(ProviderTimeoutError):
        await slow.analyze(IMG)
