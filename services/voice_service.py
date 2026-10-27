"""
InvestMate AI — Voice Service (ElevenLabs Integration)

Provides:
  • Text-to-speech via ElevenLabs API
  • Audio caching to avoid redundant API calls
  • Graceful degradation when API is unavailable
  • Optional speech-to-text (when ElevenLabs or browser API supports it)
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional

from config import (
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_AVAILABLE,
    VOICE_ENABLED, logger,
)

# Audio cache directory
CACHE_DIR = Path(tempfile.gettempdir()) / "investmate_audio_cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_key(text: str, voice_id: str) -> str:
    """Generate a deterministic cache key for a (text, voice) pair."""
    h = hashlib.sha256(f"{voice_id}:{text}".encode()).hexdigest()[:16]
    return h


def text_to_speech(text: str, voice_id: str | None = None) -> bytes | None:
    """
    Convert text to speech using ElevenLabs API.

    Returns audio bytes (MP3), or None if:
      • Voice is disabled
      • ElevenLabs API key is not configured
      • API call fails

    Caches audio locally to avoid redundant calls.
    """
    if not VOICE_ENABLED:
        logger.debug("Voice disabled — skipping TTS.")
        return None

    if not ELEVENLABS_AVAILABLE:
        logger.debug("ElevenLabs API key not configured — TTS unavailable.")
        return None

    vid = voice_id or ELEVENLABS_VOICE_ID
    cache_id = _cache_key(text, vid)
    cache_file = CACHE_DIR / f"{cache_id}.mp3"

    # Return cached audio if available
    if cache_file.exists():
        logger.debug("TTS cache hit for %s", cache_id)
        return cache_file.read_bytes()

    # Call ElevenLabs API
    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        # Generate audio
        audio_iterator = client.text_to_speech.convert(
            text=text[:5000],  # ElevenLabs has text-length limits
            voice_id=vid,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        # Collect all audio chunks
        audio_bytes = b""
        for chunk in audio_iterator:
            audio_bytes += chunk

        if audio_bytes:
            cache_file.write_bytes(audio_bytes)
            logger.info("TTS generated and cached: %d bytes", len(audio_bytes))
            return audio_bytes
        else:
            logger.warning("ElevenLabs returned empty audio.")
            return None

    except ImportError:
        logger.warning("elevenlabs package not installed.")
        return None
    except Exception as e:
        logger.error("ElevenLabs TTS error: %s", e)
        return None


def is_voice_available() -> bool:
    """Check whether voice output is available."""
    return VOICE_ENABLED and ELEVENLABS_AVAILABLE


def get_voice_status() -> dict:
    """Return a status dict for the UI."""
    return {
        "enabled": VOICE_ENABLED,
        "api_configured": ELEVENLABS_AVAILABLE,
        "available": is_voice_available(),
        "voice_id": ELEVENLABS_VOICE_ID,
        "cache_dir": str(CACHE_DIR),
        "message": (
            "Voice output is ready."
            if is_voice_available()
            else "Voice output unavailable — "
                 + ("API key not configured." if not ELEVENLABS_AVAILABLE else "Voice disabled in settings.")
        ),
    }


def clear_cache() -> int:
    """Clear the audio cache. Returns number of files deleted."""
    count = 0
    for f in CACHE_DIR.glob("*.mp3"):
        f.unlink()
        count += 1
    logger.info("Cleared %d cached audio files.", count)
    return count


def transcribe_speech(audio_file_or_bytes) -> str | None:
    """
    Transcribe microphone speech audio to text using Groq Whisper model (whisper-large-v3).
    Supports audio bytes or file-like buffer (WAV/MP3/M4A/WEBM).
    Returns transcribed string or None on failure.
    """
    from config import GROQ_API_KEY, GROQ_AVAILABLE
    if not GROQ_AVAILABLE:
        logger.warning("Groq API key not configured for audio transcription.")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        if isinstance(audio_file_or_bytes, bytes):
            audio_bytes = audio_file_or_bytes
            filename = "speech.wav"
        elif hasattr(audio_file_or_bytes, "read"):
            audio_bytes = audio_file_or_bytes.read()
            filename = getattr(audio_file_or_bytes, "name", "speech.wav")
        else:
            return None

        if not audio_bytes or len(audio_bytes) < 100:
            return None

        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3",
            response_format="text",
            temperature=0.0,
        )
        text = str(transcription).strip()
        logger.info("Transcribed audio query: '%s'", text)
        return text
    except Exception as e:
        logger.error("Audio transcription failed: %s", e)
        return None
