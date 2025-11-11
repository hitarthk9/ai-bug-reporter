from utils import flatten_segments_text


def transcribe_with_timestamps(client, audio_path: str) -> tuple[list, str, str]:
    """
    Run Whisper (verbose_json) and return (segments, full_text, timestamped_text).
    Segments is a list of TranscriptionSegment objects (or dicts) with start/end/text attributes.
    """
    with open(audio_path, "rb") as audio:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio,
            response_format="verbose_json"
        )
    segments = transcription.segments if hasattr(
        transcription, "segments") else []
    full_text = getattr(transcription, "text", "")
    timestamped = flatten_segments_text(segments) if segments else full_text
    return segments, full_text, timestamped
