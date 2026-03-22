#!/usr/bin/env python3
"""
Faster-Whisper CLI wrapper for OpenClaw audio transcription.
Usage: faster_whisper_cli.py <audio_file> [--model MODEL] [--language LANG]
"""
import sys
import argparse
from faster_whisper import WhisperModel

DEFAULT_MODEL = "base"
DEFAULT_LANG = "zh"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Whisper model (default: base)")
    parser.add_argument("--language", default=DEFAULT_LANG, help="Language code (default: zh)")
    args, unknown = parser.parse_known_args()

    # Run transcription
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        args.audio_file,
        language=args.language,
        beam_size=5,
        vad_filter=True
    )

    # Print full transcript
    transcript = "".join([seg.text for seg in segments])
    print(transcript.strip())

if __name__ == "__main__":
    main()
