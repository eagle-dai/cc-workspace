"""Build Anki .apkg file from extracted vocabulary and audio files."""

import json
import hashlib
import random
from pathlib import Path

import genanki

VOCAB_FILE = Path("tmp/vocab_clean.jsonl")
AUDIO_DIR = Path("tmp/audio")
AUDIO_MAPPING = Path("tmp/audio_mapping.json")
OUTPUT_FILE = Path("tmp/德语六级词汇.apkg")

# Stable IDs derived from project name
MODEL_ID = int(hashlib.md5(b"deutsch6-vocab-model").hexdigest()[:8], 16)
DECK_ID = int(hashlib.md5(b"deutsch6-vocab-deck").hexdigest()[:8], 16)

CARD_CSS = """\
.card {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #333;
    background-color: #fafafa;
    padding: 20px;
}
.word {
    font-size: 36px;
    font-weight: bold;
    color: #1a1a2e;
    margin-bottom: 8px;
}
.wortart {
    font-size: 18px;
    color: #888;
    margin-bottom: 16px;
}
.bedeutung {
    font-size: 24px;
    color: #16213e;
    margin-bottom: 16px;
    font-weight: 500;
}
.beispiel {
    font-size: 16px;
    color: #555;
    text-align: left;
    margin: 12px auto;
    max-width: 500px;
    line-height: 1.6;
}
.beispiel .de {
    font-style: italic;
    color: #333;
}
.beispiel .cn {
    color: #777;
    font-size: 14px;
}
hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 16px 0;
}
.extra {
    font-size: 13px;
    color: #888;
    text-align: left;
    max-width: 500px;
    margin: 8px auto;
    line-height: 1.5;
}
.extra b {
    color: #555;
}
"""

FRONT_TEMPLATE = """\
<div class="word">{{Wort}}</div>
<div class="wortart">{{Wortart}} {{Deklination}}</div>
{{Audio}}
"""

BACK_TEMPLATE = """\
<div class="word">{{Wort}}</div>
<div class="wortart">{{Wortart}} {{Deklination}}</div>
{{Audio}}
<hr>
<div class="bedeutung">{{Bedeutung}}</div>

{{#Beispiel}}
<div class="beispiel">{{Beispiel}}</div>
{{/Beispiel}}

{{#Extra}}
<hr>
<div class="extra">{{Extra}}</div>
{{/Extra}}
"""

model = genanki.Model(
    MODEL_ID,
    "德语六级词汇",
    fields=[
        {"name": "Wort"},
        {"name": "Wortart"},
        {"name": "Deklination"},
        {"name": "Bedeutung"},
        {"name": "Beispiel"},
        {"name": "Extra"},
        {"name": "Audio"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": FRONT_TEMPLATE,
            "afmt": BACK_TEMPLATE,
        },
    ],
    css=CARD_CSS,
)


def format_beispiel(de: str, cn: str) -> str:
    """Format example sentences as HTML."""
    de_list = [s.strip() for s in de.split("|") if s.strip()]
    cn_list = [s.strip() for s in cn.split("|") if s.strip()]

    parts = []
    for i, de_s in enumerate(de_list):
        cn_s = cn_list[i] if i < len(cn_list) else ""
        parts.append(f'<span class="de">{de_s}</span>')
        if cn_s:
            parts.append(f'<span class="cn">{cn_s}</span>')

    return "<br>".join(parts)


def format_extra(entry: dict) -> str:
    """Format extra info (synonyms, antonyms, word formation, etc.)."""
    parts = []
    if entry.get("wortbildung"):
        parts.append(f"<b>构词:</b> {entry['wortbildung']}")
    if entry.get("synonyme"):
        parts.append(f"<b>同义词:</b> {entry['synonyme']}")
    if entry.get("antonyme"):
        parts.append(f"<b>反义词:</b> {entry['antonyme']}")
    if entry.get("erweiterung"):
        parts.append(f"<b>拓展:</b> {entry['erweiterung']}")
    return "<br>".join(parts)


def build():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

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

    print(f"Building Anki deck with {len(entries)} entries...")

    # Load audio mapping
    audio_mapping = {}
    if AUDIO_MAPPING.exists():
        with open(AUDIO_MAPPING) as f:
            audio_mapping = json.load(f)

    deck = genanki.Deck(DECK_ID, "德语六级词汇")
    media_files = []

    for entry in entries:
        wort = entry["wort"].strip()

        # Audio
        audio_html = ""
        audio_file = audio_mapping.get(wort)
        if audio_file:
            audio_path = AUDIO_DIR / audio_file
            if audio_path.exists():
                audio_html = f"[sound:{audio_file}]"
                media_files.append(str(audio_path))

        # Example sentences
        beispiel = format_beispiel(
            entry.get("beispiel_de", ""),
            entry.get("beispiel_cn", ""),
        )

        # Extra info
        extra = format_extra(entry)

        # Generate stable GUID from word
        guid = genanki.guid_for(wort, "deutsch6")

        note = genanki.Note(
            model=model,
            fields=[
                wort,
                entry.get("wortart", ""),
                entry.get("deklination", ""),
                entry.get("bedeutung", ""),
                beispiel,
                extra,
                audio_html,
            ],
            guid=guid,
        )
        deck.add_note(note)

    # Package
    pkg = genanki.Package(deck)
    pkg.media_files = media_files
    pkg.write_to_file(str(OUTPUT_FILE))

    print(f"Done! Output: {OUTPUT_FILE}")
    print(f"  Cards: {len(entries)}")
    print(f"  Audio files: {len(media_files)}")


if __name__ == "__main__":
    build()
