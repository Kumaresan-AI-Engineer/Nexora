import base64
import logging

import openai
from openai import AsyncOpenAI
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

log = logging.getLogger("pharmasource.providers.openai")


class OpenAIVisionProvider(VisionProvider):
    name = ProviderName.OPENAI

    def __init__(
        self, api_key: str, model: str, timeout: float = 60.0, client: AsyncOpenAI | None = None
    ):
        self.model = model
        self._client = client or AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=0)

    async def analyze(self, image: PreparedImage) -> ExtractionOutput:
        data_url = f"data:{image.mime_type};base64,{base64.b64encode(image.data).decode()}"
        try:
            response = await self._client.responses.parse(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": USER_PROMPT},
                            {"type": "input_image", "image_url": data_url, "detail": "high"},
                        ],
                    }
                ],
                text_format=ExtractionOutput,
                store=False,
            )
        except openai.AuthenticationError as exc:
            raise ProviderAuthError("OpenAI rejected the configured API key.") from exc
        except openai.PermissionDeniedError as exc:
            raise ProviderAuthError("OpenAI denied access for this key or model.") from exc
        except openai.RateLimitError as exc:
            raise ProviderQuotaError(
                "OpenAI rate limit or quota exceeded. Check billing/usage and retry later."
            ) from exc
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError("OpenAI request timed out.") from exc
        except openai.BadRequestError as exc:
            raise ProviderRejectedInputError(
                "OpenAI rejected the request (unsupported image or model settings)."
            ) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("Could not reach OpenAI.") from exc
        except openai.APIStatusError as exc:
            raise ProviderError(f"OpenAI returned HTTP {exc.status_code}.") from exc

        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderBadResponseError(
                "OpenAI returned no structured output (refusal or empty)."
            )
        try:
            return ExtractionOutput.model_validate(parsed)
        except ValidationError as exc:
            raise ProviderBadResponseError("OpenAI output failed schema validation.") from exc
