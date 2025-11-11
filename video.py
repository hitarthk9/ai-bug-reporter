import os
import tempfile
import ffmpeg


def extract_audio(video_path: str) -> str:
    """Extract audio as mono 16k WAV (avoids MP3 encoder availability issues)."""
    audio_path = video_path + ".wav"
    ffmpeg_path = os.getenv("FFMPEG_PATH") or "ffmpeg"
    stream = ffmpeg.input(video_path)
    stream = ffmpeg.output(
        stream,
        audio_path,
        acodec="pcm_s16le",   # WAV PCM 16-bit
        ar="16000",           # 16k sample rate
        ac=1                  # mono
    )
    cmdline = " ".join(ffmpeg.compile(stream))
    try:
        stream = ffmpeg.overwrite_output(
            stream).global_args("-vn", "-loglevel", "error")
        ffmpeg.run(
            stream,
            cmd=ffmpeg_path,
            overwrite_output=True,
            capture_stdout=True,
            capture_stderr=True
        )
    except ffmpeg.Error as e:
        details = ""
        for attr in ("stderr", "stdout"):
            buf = getattr(e, attr, None)
            if buf:
                try:
                    details = buf.decode("utf-8", "ignore")
                    break
                except Exception:
                    details = str(buf)
        if not details:
            details = str(e)
        raise RuntimeError(
            f"ffmpeg audio extraction failed.\nCommand: {cmdline}\nFFMPEG_PATH: {ffmpeg_path}\nDetails:\n{details}"
        )
    return audio_path


def extract_video_clip(video_path: str, start_sec: float, end_sec: float, output_path: str = None) -> str:
    """Extract a video clip from start_sec to end_sec. Returns path to the clip.
    Optimized for web playback and Jira compatibility."""
    if output_path is None:
        output_path = tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp4").name

    ffmpeg_path = os.getenv("FFMPEG_PATH") or "ffmpeg"
    duration = max(0.1, end_sec - start_sec)  # Ensure positive duration

    stream = ffmpeg.input(video_path, ss=start_sec)
    # Apply video filter to ensure even dimensions (required for H.264)
    stream = ffmpeg.filter(stream, "scale", "trunc(iw/2)*2", "trunc(ih/2)*2")

    stream = ffmpeg.output(
        stream,
        output_path,
        t=duration,
        vcodec="libx264",           # H.264 codec for maximum compatibility
        acodec="aac",               # AAC audio codec
        preset="medium",            # Better quality than fast
        # Quality setting (lower = better, 18-28 range)
        # Using CRF 28 for smaller file size while maintaining reasonable quality
        crf=28,
        # Ensure compatible pixel format (required for web)
        pix_fmt="yuv420p",
        # Limit video bitrate to reduce file size (500k for smaller clips)
        video_bitrate="500k",
        # Limit audio bitrate
        audio_bitrate="64k"
    )
    cmdline = " ".join(ffmpeg.compile(stream))
    try:
        stream = ffmpeg.overwrite_output(stream).global_args(
            "-movflags", "+faststart",  # Enable fast start for web playback
            "-loglevel", "error"        # Suppress verbose output
        )
        ffmpeg.run(
            stream,
            cmd=ffmpeg_path,
            overwrite_output=True,
            capture_stdout=True,
            capture_stderr=True
        )
    except ffmpeg.Error as e:
        details = ""
        for attr in ("stderr", "stdout"):
            buf = getattr(e, attr, None)
            if buf:
                try:
                    details = buf.decode("utf-8", "ignore")
                    break
                except Exception:
                    details = str(buf)
        if not details:
            details = str(e)
        raise RuntimeError(
            f"ffmpeg video clip extraction failed.\nCommand: {cmdline}\nFFMPEG_PATH: {ffmpeg_path}\nDetails:\n{details}"
        )
    return output_path
