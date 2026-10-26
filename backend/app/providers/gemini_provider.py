import asyncio
import logging

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.providers.base import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    PreparedImage,
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderError,
    ProviderQuotaError,
    ProviderRejectedInputError,
    ProviderTimeoutError,
    VisionProvider,
)
from app.schemas.common import ProviderName
from app.schemas.identity import ExtractionOutput

log = logging.getLogger("pharmasource.providers.gemini")


class GeminiVisionProvider(VisionProvider):
    name = ProviderName.GEMINI

    def __init__(
        self, api_key: str, model: str, timeout: float = 60.0, client: genai.Client | None = None
    ):
        self.model = model
        self._timeout = timeout
        self._client = client or genai.Client(api_key=api_key)

    async def analyze(self, image: PreparedImage) -> ExtractionOutput:
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ExtractionOutput,
            temperature=0,
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(data=image.data, mime_type=image.mime_type),
                        USER_PROMPT,
                    ],
                    config=config,
                ),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError("Gemini request timed out.") from exc
        except errors.ClientError as exc:
            code = getattr(exc, "code", None)
            message = str(getattr(exc, "message", "") or exc).lower()
            if code in (401, 403) or "api key" in message:
                raise ProviderAuthError("Gemini rejected the configured API key.") from exc
            if code == 429:
                raise ProviderQuotaError(
                    "Gemini quota or rate limit exceeded. Check plan/billing and retry later."
                ) from exc
            raise ProviderRejectedInputError(
                "Gemini rejected the request (unsupported image or model settings)."
            ) from exc
        except errors.ServerError as exc:
            raise ProviderError("Gemini service error; retry later.") from exc
        except Exception as exc:  # noqa: BLE001 - SDK may raise httpx or httpx2 transport errors
            if "Timeout" in type(exc).__name__:
                raise ProviderTimeoutError("Gemini request timed out.") from exc
            log.warning("gemini call failed: %s", type(exc).__name__)
            raise ProviderError("Could not reach Gemini.") from exc

        text = getattr(response, "text", None)
        if not text:
            raise ProviderBadResponseError("Gemini returned no content (possibly blocked).")
        try:
            return ExtractionOutput.model_validate_json(text)
        except ValidationError as exc:
            raise ProviderBadResponseError("Gemini output failed schema validation.") from exc
