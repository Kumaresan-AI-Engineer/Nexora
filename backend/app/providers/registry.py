from app.config import Settings
from app.providers.base import ProviderNotConfiguredError, VisionProvider
from app.schemas.common import ProviderName


class ProviderRegistry:
    """Routes to exactly the requested provider. There is deliberately no fallback logic."""

    def __init__(
        self, settings: Settings, overrides: dict[ProviderName, VisionProvider] | None = None
    ):
        self._settings = settings
        self._overrides = overrides or {}

    def missing_config(self, name: ProviderName) -> list[str]:
        s = self._settings
        if name == ProviderName.OPENAI:
            pairs = [
                ("OPENAI_API_KEY", s.openai_api_key),
                ("OPENAI_VISION_MODEL", s.openai_vision_model),
            ]
        else:
            pairs = [
                ("GEMINI_API_KEY", s.gemini_api_key),
                ("GEMINI_VISION_MODEL", s.gemini_vision_model),
            ]
        return [k for k, v in pairs if not v.strip()]

    def is_configured(self, name: ProviderName) -> bool:
        return name in self._overrides or not self.missing_config(name)

    def get(self, name: ProviderName) -> VisionProvider:
        if name in self._overrides:
            return self._overrides[name]
        missing = self.missing_config(name)
        if missing:
            raise ProviderNotConfiguredError(
                f"{name.value} is not configured. Set {', '.join(missing)} in the backend environment.",
                details={"provider": name.value, "missing": missing},
            )
        s = self._settings
        if name == ProviderName.OPENAI:
            from app.providers.openai_provider import OpenAIVisionProvider

            return OpenAIVisionProvider(
                s.openai_api_key, s.openai_vision_model, s.provider_timeout_seconds
            )
        from app.providers.gemini_provider import GeminiVisionProvider

        return GeminiVisionProvider(
            s.gemini_api_key, s.gemini_vision_model, s.provider_timeout_seconds
        )

    def capabilities(self) -> list[dict]:
        out = []
        for name in ProviderName:
            missing = self.missing_config(name)
            out.append(
                {
                    "provider": name.value,
                    "configured": self.is_configured(name),
                    "missing": [] if name in self._overrides else missing,
                }
            )
        return out
