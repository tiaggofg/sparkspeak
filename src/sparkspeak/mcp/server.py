"""Stdio MCP server entrypoint for SparkSpeak."""

import json
import logging
import sys
from typing import Any, cast

# Configure logging strictly to stderr before importing any other modules so
# stdout remains 100% reserved for MCP JSON-RPC frames.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)

from mcp import types  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

from sparkspeak.application.audio_service import AudioService  # noqa: E402
from sparkspeak.application.review_service import ReviewService  # noqa: E402
from sparkspeak.application.session_service import SessionService  # noqa: E402
from sparkspeak.config import SparkSpeakConfig, load_config  # noqa: E402
from sparkspeak.domain.errors import SparkSpeakError  # noqa: E402
from sparkspeak.domain.models import (  # noqa: E402
    CardType,
    InputMode,
    SessionMode,
    SourceType,
)
from sparkspeak.infrastructure.audio.piper_tts import (  # noqa: E402
    DEFAULT_PIPER_VOICE,
    PiperTTSAdapter,
)
from sparkspeak.infrastructure.audio.pipewire_device import probe_pipewire_devices  # noqa: E402
from sparkspeak.infrastructure.audio.ports import AudioStatus, STTEngine  # noqa: E402
from sparkspeak.infrastructure.audio.whisper_stt import WhisperSTTAdapter  # noqa: E402
from sparkspeak.infrastructure.db.migrator import run_migrations  # noqa: E402
from sparkspeak.infrastructure.db.repositories import SQLiteRepository  # noqa: E402

logger = logging.getLogger(__name__)


def _ok_result(payload: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload))],
        is_error=False,
    )


def _error_result(err: SparkSpeakError) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=err.to_json())],
        is_error=True,
    )


def create_server(
    config: SparkSpeakConfig | None = None,
    *,
    stt_adapter: STTEngine | None = None,
) -> MCPServer:
    """Create and configure the SparkSpeak MCPServer with SQLite migrations."""
    cfg = config or load_config()
    run_migrations(cfg.db_path, cfg.backups_dir)

    repo = SQLiteRepository(cfg.db_path)
    review_service = ReviewService(repo)
    session_service = SessionService(repo)
    tts_adapter = PiperTTSAdapter(cfg.models_dir)
    stt = stt_adapter or WhisperSTTAdapter(cfg.models_dir)

    def _probe_audio_status() -> AudioStatus:
        probe = probe_pipewire_devices()
        return AudioStatus(
            tts_ready=tts_adapter.is_ready(),
            stt_ready=stt.is_ready(),
            pipewire_input=probe.has_input,
            pipewire_output=probe.has_output,
        )

    audio_service = AudioService(
        tts=tts_adapter,
        stt=stt,
        device_probe=_probe_audio_status,
    )

    server = MCPServer("sparkspeak")

    @server.tool(
        description=(
            "Initialize an English study session in SQLite and report due queue counts "
            "and audio subsystem readiness."
        )
    )
    def start_session(
        deck_slug: str | None = None,
        mode: str = "mixed",
        input_mode: str = "voice",
    ) -> types.CallToolResult:
        try:
            audio_status = audio_service.get_audio_status().to_dict()
            res = session_service.start_session(
                deck_slug=deck_slug,
                mode=cast(SessionMode, mode),
                input_mode=cast(InputMode, input_mode),
                audio_status=audio_status,
            )
            deck_payload = (
                {
                    "id": res.deck.id,
                    "slug": res.deck.slug,
                    "name": res.deck.name,
                    "persona_prompt": res.deck.persona_prompt,
                }
                if res.deck is not None
                else None
            )
            return _ok_result(
                {
                    "session_id": res.session_id,
                    "deck": deck_payload,
                    "mode": res.mode,
                    "effective_input_mode": res.effective_input_mode,
                    "audio_status": res.audio_status,
                    "due_summary": {
                        "due_reviews": res.due_reviews,
                        "new_cards": res.new_cards,
                    },
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "Fetch due review flashcards ordered by due_at ASC followed by up to "
            "new_cards_limit unseen cards."
        )
    )
    def get_due_cards(
        deck_slug: str | None = None,
        limit: int = 10,
        new_cards_limit: int = 3,
        include_new: bool = True,
    ) -> types.CallToolResult:
        try:
            res = review_service.get_due_cards(
                deck_slug=deck_slug,
                limit=limit,
                new_cards_limit=new_cards_limit,
                include_new=include_new,
            )
            return _ok_result(
                {
                    "cards": [
                        {
                            "card_id": c.id,
                            "deck_slug": c.deck_slug,
                            "front_prompt": c.front_prompt,
                            "back_reference": c.back_reference,
                            "context_example": c.context_example,
                            "card_type": c.card_type,
                            "is_new": c.is_new,
                            "fsrs_state": c.fsrs_state,
                            "reps": c.reps,
                            "lapses": c.lapses,
                            "due_at": c.due_at,
                        }
                        for c in res.cards
                    ],
                    "queue_stats": {
                        "returned": res.queue_stats.returned,
                        "total_due_reviews": res.queue_stats.total_due_reviews,
                        "total_new_available": res.queue_stats.total_new_available,
                    },
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "Submit an FSRS review (rating 1=Again, 2=Hard, 3=Good, 4=Easy) inside a "
            "SQLite transaction and append an immutable review_logs row."
        )
    )
    def submit_review(
        card_id: int,
        rating: int,
        user_response_raw: str,
        input_mode: str,
        session_id: str | None = None,
        duration_ms: int | None = None,
        idempotency_key: str | None = None,
    ) -> types.CallToolResult:
        try:
            res = review_service.submit_review(
                card_id=card_id,
                rating=rating,
                user_response_raw=user_response_raw,
                input_mode=cast(InputMode, input_mode),
                session_id=session_id,
                duration_ms=duration_ms,
                idempotency_key=idempotency_key,
            )
            return _ok_result(
                {
                    "card_id": res.card_id,
                    "rating": res.rating,
                    "fsrs_state": res.fsrs_state,
                    "scheduled_days": res.scheduled_days,
                    "next_due_at": res.next_due_at,
                    "stability": res.stability,
                    "difficulty": res.difficulty,
                    "idempotent_replay": res.idempotent_replay,
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "Create a new flashcard in SQLite, deduplicating by normalized front_prompt "
            "within the target deck."
        )
    )
    def add_card(
        deck_slug: str,
        front_prompt: str,
        back_reference: str,
        card_type: str,
        context_example: str | None = None,
        source_type: str = "manual",
    ) -> types.CallToolResult:
        try:
            res = review_service.add_card(
                deck_slug=deck_slug,
                front_prompt=front_prompt,
                back_reference=back_reference,
                card_type=cast(CardType, card_type),
                context_example=context_example,
                source_type=cast(SourceType, source_type),
            )
            return _ok_result(
                {
                    "card_id": res.card_id,
                    "created": res.created,
                    "deck_slug": res.deck_slug,
                    "due_at": res.due_at,
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "End an active study session idempotently and return session metrics."
        )
    )
    def end_session(
        session_id: str,
        summary_notes: str | None = None,
    ) -> types.CallToolResult:
        try:
            res = session_service.end_session(session_id, summary_notes=summary_notes)
            return _ok_result(
                {
                    "session_id": res.session_id,
                    "status": res.status,
                    "started_at": res.started_at,
                    "ended_at": res.ended_at,
                    "cards_reviewed": res.cards_reviewed,
                    "errors_extracted": res.errors_extracted,
                    "summary_notes": res.summary_notes,
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "Synthesize English speech via local Piper ONNX and play PCM audio to "
            "the default PipeWire output sink."
        )
    )
    async def speak_text(
        text: str,
        voice: str = DEFAULT_PIPER_VOICE,
        speed: float = 1.0,
        blocking: bool = True,
    ) -> types.CallToolResult:
        try:
            res = await audio_service.speak_text(
                text,
                voice=voice,
                speed=speed,
                blocking=blocking,
            )
            return _ok_result(
                {
                    "spoken": res.spoken,
                    "voice": res.voice,
                    "duration_ms": res.duration_ms,
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "Record 16kHz mono PCM from PipeWire with Silero VAD endpointing and "
            "return a verbatim faster-whisper transcript without grammar auto-correction."
        )
    )
    async def listen_and_transcribe(
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> types.CallToolResult:
        try:
            res = await audio_service.listen_and_transcribe(
                silence_timeout_ms=silence_timeout_ms,
                initial_speech_timeout_ms=initial_speech_timeout_ms,
                max_duration_ms=max_duration_ms,
            )
            return _ok_result(
                {
                    "speech_detected": res.speech_detected,
                    "transcript": res.transcript,
                    "duration_ms": res.duration_ms,
                    "truncated_at_max_duration": res.truncated_at_max_duration,
                    "avg_logprob": res.avg_logprob,
                    "no_speech_prob": res.no_speech_prob,
                }
            )
        except SparkSpeakError as err:
            return _error_result(err)

    @server.tool(
        description=(
            "Report local TTS/STT model readiness and PipeWire input/output device availability."
        )
    )
    def get_audio_status() -> types.CallToolResult:
        return _ok_result(audio_service.get_audio_status().to_dict())

    return server


def main() -> None:
    """Run the SparkSpeak MCP server over stdio."""
    logger.info("Starting SparkSpeak MCP stdio server")
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
