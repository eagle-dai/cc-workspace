"""Generate German pronunciation audio files using Edge TTS."""

import asyncio
import json
import re
from pathlib import Path

import edge_tts

VOCAB_FILE = Path("tmp/vocab_clean.jsonl")
AUDIO_DIR = Path("tmp/audio")
VOICE = "de-DE-KatjaNeural"


def sanitize_filename(word: str, idx: int) -> str:
    """Create a safe filename from a German word."""
    safe = re.sub(r'[^\w\-]', '_', word)
    return f"{idx:04d}_{safe}.mp3"


async def generate_all():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Load vocabulary
    entries = []
    seen = set()
    with open(VOCAB_FILE) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                wort = d["wort"].strip()
                if wort and wort not in seen:
                    seen.add(wort)
                    entries.append(d)

    print(f"Generating audio for {len(entries)} unique words...")

    # Track mapping: word -> audio filename
    mapping = {}
    failed = []

    for i, entry in enumerate(entries):
        wort = entry["wort"].strip()
        filename = sanitize_filename(wort, i)
        output_path = AUDIO_DIR / filename

        if output_path.exists():
            mapping[wort] = filename
            continue

        for attempt in range(3):
            try:
                comm = edge_tts.Communicate(wort, VOICE)
                await comm.save(str(output_path))
                mapping[wort] = filename

                if (i + 1) % 50 == 0:
                    print(f"  [{i + 1}/{len(entries)}] Generated: {wort}")

                # Rate limit: small delay every request, longer pause every 50
                await asyncio.sleep(0.3)
                if (i + 1) % 50 == 0:
                    await asyncio.sleep(2)
                break

            except Exception as e:
                if attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"  RETRY {attempt + 1}: {wort} - {e}, waiting {wait}s")
                    await asyncio.sleep(wait)
                else:
                    print(f"  FAILED: {wort} - {e}")
                    failed.append(wort)

    # Save mapping
    mapping_file = Path("tmp/audio_mapping.json")
    with open(mapping_file, "w") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Generated {len(mapping)} audio files")
    if failed:
        print(f"Failed: {len(failed)} words: {failed[:10]}...")
    print(f"Mapping saved to: {mapping_file}")


if __name__ == "__main__":
    asyncio.run(generate_all())
