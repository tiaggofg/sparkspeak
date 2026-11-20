"""Structured recoverable error codes and MCP error envelope."""

import json
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Canonical error codes returned by SparkSpeak services and MCP tools."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_RATING = "INVALID_RATING"
    CARD_NOT_FOUND = "CARD_NOT_FOUND"
    DECK_NOT_FOUND = "DECK_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    TTS_MODEL_MISSING = "TTS_MODEL_MISSING"
    AUDIO_OUTPUT_UNAVAILABLE = "AUDIO_OUTPUT_UNAVAILABLE"
    MICROPHONE_UNAVAILABLE = "MICROPHONE_UNAVAILABLE"
    MODEL_NOT_INSTALLED = "MODEL_NOT_INSTALLED"
    AUDIO_LOCK_BUSY = "AUDIO_LOCK_BUSY"


class SparkSpeakError(Exception):
    """Domain/application error carrying a structured MCP error envelope."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        *,
        recoverable: bool = True,
        fallback_hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.recoverable = recoverable
        self.fallback_hint = fallback_hint
        self.details: dict[str, Any] = details if details is not None else {}

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable structured error payload."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "recoverable": self.recoverable,
            "fallback_hint": self.fallback_hint,
            "details": self.details,
        }

    def to_json(self) -> str:
        """Serialize the structured error payload as JSON."""
        return json.dumps(self.to_dict())
