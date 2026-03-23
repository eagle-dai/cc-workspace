"""Clean and normalize German vocabulary data extracted from PDF pages.

Pipeline:
1. Load raw data + re-extracted data
2. Filter garbage pages (index/exercise/summary pages)
3. Merge cross-page entries (same word split across pages)
4. Deduplicate entries (keep most complete version)
5. Fix field content (normalize wort, wortart, fix misplaced content)
6. Validate and output

Usage:
    uv run python clean_vocab.py                     # clean only
    uv run python clean_vocab.py --re-extract        # re-extract failed pages only
    uv run python clean_vocab.py --re-extract --clean # both
"""

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path

RAW_FILE = Path("tmp/vocab_raw.jsonl")
RE_EXTRACTED_FILE = Path("tmp/vocab_re_extracted.jsonl")
CLEAN_FILE = Path("tmp/vocab_clean.jsonl")
LOG_FILE = Path("tmp/clean_log.json")
PAGES_DIR = Path("tmp/pdf_pages")

# Pages that are garbage (index/exercise/summary)
GARBAGE_PAGES = {
    "page-014.png",  # summary page, all words have fuller versions elsewhere
    "page-026.png",  # exercise page, bedeutung contains German synonyms
    "page-049.png",  # all bedeutung empty
    "page-107.png",  # chaotic content (Fließbänder, Auto, Wasser)
    "page-213.png",  # index/appendix page: wrong wortart, conjugated verbs, low quality
    "page-307.png",  # all empty, un- prefix word list
    "page-339.png",  # verb conjugation forms (hoffe, möchte), exercise page
    "page-348.png",  # index page, all empty
}

# Individual bad entries to remove (conjugated verbs, comparatives, phrases)
BAD_WORTS = {
    "baut", "lautete", "pfiff", "pflanzt", "steckt",  # conjugated verbs
    "häufiger", "populärer",  # comparative forms
    "großer Mensch",  # phrase, not a word entry
}

# Pages that failed JSON parsing and need re-extraction
FAILED_PAGES = [
    65, 66, 98, 103, 153, 164, 185, 187,
    192, 197, 200, 225, 252, 263, 312, 341, 343, 349,
]

# wortart normalization map
WORTART_MAP = {
    "adv.": "Adv.",
    "adj.": "Adj.",
    "Prä.": "Präp.",
    "Präp": "Präp.",
    "n": "n.",
    "s.": "n.",
    "vr.": "refl.",
    "vt. /vi.": "vt./vi.",
    "vi. / vt.": "vi./vt.",
    "vt. / vi.": "vt./vi.",
    "vt. /refl. /vi.": "vt./refl./vi.",
    "Konj. / Adv.": "Konj./Adv.",
    "Adj. / Adv.": "Adj./Adv.",
}

# wortart values that are actually grammar info, should go to deklination
WORTART_TO_DEKLINATION = {"+ A/ + für", "+ A", "+ D"}

# Numbered bullet characters for bedeutung merging
BULLETS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"


def load_jsonl(path: Path) -> list[dict]:
    entries = []
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                entries.append(json.loads(line))
    return entries


def save_jsonl(entries: list[dict], path: Path):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Step 1: Load and merge
# ---------------------------------------------------------------------------
def step_load() -> list[dict]:
    raw = load_jsonl(RAW_FILE)
    re_extracted = load_jsonl(RE_EXTRACTED_FILE)

    if not re_extracted:
        return raw

    # Pages that were re-extracted
    re_pages = {e["_page"] for e in re_extracted}

    # Keep raw entries not from re-extracted pages, then add re-extracted
    merged = [e for e in raw if e.get("_page") not in re_pages]
    merged.extend(re_extracted)
    return merged


# ---------------------------------------------------------------------------
# Step 2: Filter garbage pages
# ---------------------------------------------------------------------------
def step_filter_garbage(entries: list[dict], log: dict) -> list[dict]:
    before = len(entries)
    result = [
        e for e in entries
        if e.get("_page") not in GARBAGE_PAGES
        and e.get("wort", "").strip() not in BAD_WORTS
    ]
    removed = before - len(result)
    log["step2_garbage_removed"] = removed
    print(f"  Step 2: 过滤垃圾页+坏词条 → 移除 {removed} 条")
    return result


# ---------------------------------------------------------------------------
# Step 3: Cross-page merge
# ---------------------------------------------------------------------------
def count_bedeutung_items(text: str) -> int:
    """Count numbered items in bedeutung."""
    return sum(1 for c in text if c in BULLETS)


def merge_bedeutung(values: list[str]) -> str:
    """Merge bedeutung fields, concatenating numbered items."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return ""
    if len(non_empty) == 1:
        return non_empty[0]

    # Check if both have numbered items
    all_have_numbers = all(any(c in v for c in BULLETS) for v in non_empty)

    if all_have_numbers:
        # Extract all items and renumber
        items = []
        for v in non_empty:
            # Split by bullet characters
            parts = re.split(r"([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])", v)
            current_items = []
            for j in range(1, len(parts), 2):
                text = parts[j + 1].strip().rstrip(",，") if j + 1 < len(parts) else ""
                if text:
                    current_items.append(text)
            items.extend(current_items)

        # Remove duplicate items
        seen = set()
        unique_items = []
        for item in items:
            normalized = item.strip().lower()
            if normalized not in seen:
                seen.add(normalized)
                unique_items.append(item)

        if unique_items:
            return " ".join(f"{BULLETS[i]}{item}" for i, item in enumerate(unique_items) if i < len(BULLETS))

    # Fallback: return longest
    return max(non_empty, key=len)


def merge_beispiele(values: list[str]) -> str:
    """Merge example sentence fields."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return ""
    if len(non_empty) == 1:
        return non_empty[0]

    # Collect all unique examples
    all_examples = []
    seen = set()
    for v in non_empty:
        for ex in v.split("|"):
            ex = ex.strip()
            if ex and ex not in seen:
                seen.add(ex)
                all_examples.append(ex)
    return " | ".join(all_examples)


def merge_entry_group(group: list[dict]) -> dict:
    """Merge multiple entries for the same word."""
    if len(group) == 1:
        return group[0]

    MERGE_FIELDS = [
        "wort", "wortart", "deklination", "bedeutung",
        "beispiel_de", "beispiel_cn", "wortbildung",
        "synonyme", "antonyme", "erweiterung",
    ]

    merged = {}
    for field in MERGE_FIELDS:
        values = [e.get(field, "") for e in group]
        if field == "bedeutung":
            merged[field] = merge_bedeutung(values)
        elif field in ("beispiel_de", "beispiel_cn"):
            merged[field] = merge_beispiele(values)
        else:
            # Take longest non-empty value
            non_empty = [v for v in values if v.strip()]
            merged[field] = max(non_empty, key=len) if non_empty else ""

    # Keep first entry's page reference
    merged["_page"] = group[0]["_page"]
    return merged


def step_merge_cross_page(entries: list[dict], log: dict) -> list[dict]:
    # Build page-ordered index: group entries by page
    page_order = {}
    for e in entries:
        page = e.get("_page", "")
        page_order.setdefault(page, []).append(e)

    sorted_pages = sorted(page_order.keys())

    # Find cross-page candidates: same wort on adjacent pages
    merge_targets = {}  # wort -> list of (entry, page)
    for i in range(len(sorted_pages) - 1):
        p1, p2 = sorted_pages[i], sorted_pages[i + 1]
        words_p1 = {e.get("wort", "").strip() for e in page_order[p1]}
        words_p2 = {e.get("wort", "").strip() for e in page_order[p2]}
        common = words_p1 & words_p2
        for w in common:
            if w:
                if w not in merge_targets:
                    merge_targets[w] = []
                for e in page_order[p1] + page_order[p2]:
                    if e.get("wort", "").strip() == w and e not in merge_targets[w]:
                        merge_targets[w].append(e)

    # Perform merges
    merged_entries = set()  # ids of entries that got merged
    new_entries = []
    merge_count = 0

    for wort, group in merge_targets.items():
        if len(group) < 2:
            continue

        # Check if entries have different wortart (different words, e.g. Bund m./n.)
        wortarts = {classify_wortart(e.get("wortart", "")) for e in group}
        if len(wortarts) > 1 and "" not in wortarts:
            # Different word types, don't merge - handle in dedup
            continue

        result = merge_entry_group(group)
        new_entries.append(result)
        for e in group:
            merged_entries.add(id(e))
        merge_count += 1

    # Build result: non-merged entries + merged entries
    result = [e for e in entries if id(e) not in merged_entries]
    result.extend(new_entries)

    log["step3_merged_count"] = merge_count
    print(f"  Step 3: 跨页合并 → 合并 {merge_count} 组词条")
    return result


# ---------------------------------------------------------------------------
# Step 4: Deduplicate
# ---------------------------------------------------------------------------
def classify_wortart(wa: str) -> str:
    """Classify wortart into broad categories for dedup."""
    wa = wa.strip().lower().rstrip(".")
    if wa in ("m", "n", "f"):
        return wa  # Keep gender distinction
    if wa.startswith(("vt", "vi", "v", "refl")):
        return "V"
    if wa.startswith("adj"):
        return "ADJ"
    if wa.startswith("adv"):
        return "ADV"
    if wa.startswith("präp"):
        return "PREP"
    if wa.startswith("konj"):
        return "KONJ"
    return wa or "UNKNOWN"


def dedup_key(entry: dict) -> str:
    wort = entry.get("wort", "").strip()
    wa = classify_wortart(entry.get("wortart", ""))
    return f"{wort}|{wa}"


# Words where different genders are genuinely different words
KEEP_BOTH_GENDERS = {"Bund"}  # m.=联盟 vs n.=捆束


def step_deduplicate(entries: list[dict], log: dict) -> list[dict]:
    # Phase 1: dedup by wort+wortart key (same as before)
    groups = defaultdict(list)
    for e in entries:
        key = dedup_key(e)
        groups[key].append(e)

    phase1 = []
    dedup_count = 0
    for key, group in groups.items():
        if len(group) == 1:
            phase1.append(group[0])
        else:
            best = max(group, key=lambda e: len(e.get("bedeutung", "")))
            phase1.append(best)
            dedup_count += len(group) - 1

    # Phase 2: dedup same wort with different wortart (keep best version)
    # Exception: words in KEEP_BOTH_GENDERS where meanings are truly different
    wort_groups = defaultdict(list)
    for e in phase1:
        wort_groups[e.get("wort", "").strip()].append(e)

    result = []
    for wort, group in wort_groups.items():
        if len(group) == 1:
            result.append(group[0])
        elif wort in KEEP_BOTH_GENDERS:
            result.extend(group)
        else:
            # Keep the entry with the most complete data
            best = max(group, key=lambda e: (
                len(e.get("bedeutung", "")),
                len(e.get("beispiel_de", "")),
                len(e.get("wortbildung", "")),
            ))
            result.append(best)
            dedup_count += len(group) - 1

    log["step4_dedup_removed"] = dedup_count
    print(f"  Step 4: 去重 → 移除 {dedup_count} 条重复")
    return result


# ---------------------------------------------------------------------------
# Step 5: Fix fields
# ---------------------------------------------------------------------------
def normalize_wort(wort: str) -> str:
    """Normalize word format."""
    wort = wort.strip()

    # Reflexive verbs: "auskennen sich" → "sich auskennen"
    if wort.endswith(" sich"):
        verb = wort[: -len(" sich")]
        wort = f"sich {verb}"

    # Separable verb slash: "fort/bilden" → "fortbilden"
    if "/" in wort and not wort.startswith("/"):
        wort = wort.replace("/", "")

    # Leading hyphen: "-legen" → skip (invalid entry)
    if wort.startswith("-"):
        return ""

    return wort


def normalize_wortart_field(entry: dict) -> None:
    """Normalize wortart and move misplaced grammar info."""
    wa = entry.get("wortart", "").strip()

    # Move grammar info to deklination
    if wa in WORTART_TO_DEKLINATION:
        dekl = entry.get("deklination", "")
        entry["deklination"] = f"{wa}, {dekl}" if dekl else wa
        entry["wortart"] = ""
        return

    # Fix wortart='A' (should be verb)
    if wa == "A":
        entry["wortart"] = "vt."
        return

    # Fix noun-tagged verbs (e.g. austreten tagged as n.)
    wort = entry.get("wort", "").strip()
    if wa == "n." and wort and wort[0].islower() and not wort.startswith("sich"):
        # Lowercase wort tagged as noun is likely a verb
        bed = entry.get("bedeutung", "")
        if bed and any(kw in bed for kw in ["vi.", "vt.", "使", "做", "去", "来"]):
            entry["wortart"] = "v."
            return

    # Apply normalization map
    if wa in WORTART_MAP:
        entry["wortart"] = WORTART_MAP[wa]


def has_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def fix_misplaced_content(entry: dict) -> None:
    """Fix specific known field content errors."""
    wort = entry.get("wort", "").strip()

    # laufen: actually contains lauten's content (wort/bedeutung mismatch)
    if wort == "laufen":
        bed = entry.get("bedeutung", "")
        bsp = entry.get("beispiel_de", "")
        if "原文是" in bed or (bsp and "lautet" in bsp):
            # This entry is actually "lauten", fix wort
            entry["wort"] = "lauten"
            entry["bedeutung"] = "①原文是,内容是 ②听起来"

    # Schema: bedeutung contains example sentence translations, not definitions
    if wort == "Schema":
        bed = entry.get("bedeutung", "")
        if "不符合常规" in bed or "思维模式" in bed:
            entry["bedeutung"] = "①模式,图式 ②刻板的程序,常套"

    # Scherz: bedeutung contains example sentence translations
    if wort == "Scherz":
        bed = entry.get("bedeutung", "")
        if "玩笑不好笑" in bed or "某事不认真" in bed:
            entry["bedeutung"] = "玩笑,戏谑"

    # Verbrecher: wortart should be m. not n.
    if wort == "Verbrecher":
        if entry.get("wortart", "") == "n.":
            entry["wortart"] = "m."

    # austreten: wortart should be v. not n.
    if wort == "austreten":
        if entry.get("wortart", "") == "n.":
            entry["wortart"] = "vi."

    # einbrechen: bedeutung contains "例句" label text
    if wort == "einbrechen":
        bed = entry.get("bedeutung", "")
        if "例句" in bed:
            entry["bedeutung"] = re.sub(r'例句.*$', '', bed).strip().rstrip(",，")

    # empören: bedeutung content mixed into beispiel_de
    if wort == "empören":
        bsp = entry.get("beispiel_de", "")
        bed = entry.get("bedeutung", "")
        if not bed and bsp and has_chinese(bsp):
            # Try to split: Chinese part is bedeutung, German sentences are examples
            parts = re.split(r'(?<=[。；，\s])\s*(?=[A-ZÄÖÜ])', bsp, maxsplit=1)
            if len(parts) == 2:
                entry["bedeutung"] = parts[0].strip()
                entry["beispiel_de"] = parts[1].strip()

    # Bauwerk, Bundeskanzler: beispiel_de contains mixed Chinese translation
    if wort in ("Bauwerk", "Bundeskanzler"):
        bsp_de = entry.get("beispiel_de", "")
        bsp_cn = entry.get("beispiel_cn", "")
        if bsp_de and has_chinese(bsp_de) and not bsp_cn:
            # Split at first Chinese character sequence
            match = re.search(r'([\u4e00-\u9fff])', bsp_de)
            if match:
                idx = match.start()
                entry["beispiel_de"] = bsp_de[:idx].strip().rstrip("|").strip()
                entry["beispiel_cn"] = bsp_de[idx:].strip()


def step_fix_fields(entries: list[dict], log: dict) -> list[dict]:
    wort_changes = 0
    wortart_changes = 0
    content_fixes = 0

    result = []
    for e in entries:
        # Normalize wort
        old_wort = e.get("wort", "")
        new_wort = normalize_wort(old_wort)
        if new_wort != old_wort:
            if not new_wort:
                continue  # Skip invalid entries like "-legen"
            e["wort"] = new_wort
            wort_changes += 1

        # Normalize wortart
        old_wa = e.get("wortart", "")
        normalize_wortart_field(e)
        if e.get("wortart", "") != old_wa:
            wortart_changes += 1

        # Fix misplaced content
        fix_misplaced_content(e)

        result.append(e)

    log["step5_wort_changes"] = wort_changes
    log["step5_wortart_changes"] = wortart_changes
    print(f"  Step 5: 字段修复 → wort 修改 {wort_changes} 条, wortart 修改 {wortart_changes} 条")
    return result


# ---------------------------------------------------------------------------
# Step 6: Validate and output
# ---------------------------------------------------------------------------
def step_validate_and_output(entries: list[dict], log: dict) -> list[dict]:
    # Remove entries with empty wort
    entries = [e for e in entries if e.get("wort", "").strip()]

    # Sort by wort (case-insensitive)
    entries.sort(key=lambda e: e.get("wort", "").strip().lower())

    # Count quality stats
    empty_bedeutung = sum(1 for e in entries if not e.get("bedeutung", "").strip())
    empty_beispiel = sum(1 for e in entries if not e.get("beispiel_de", "").strip())
    empty_wortart = sum(1 for e in entries if not e.get("wortart", "").strip())

    log["final_count"] = len(entries)
    log["empty_bedeutung"] = empty_bedeutung
    log["empty_beispiel_de"] = empty_beispiel
    log["empty_wortart"] = empty_wortart

    # Save
    save_jsonl(entries, CLEAN_FILE)

    # Save log
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\n  最终: {len(entries)} 条词条")
    print(f"  空 bedeutung: {empty_bedeutung}, 空 beispiel_de: {empty_beispiel}, 空 wortart: {empty_wortart}")
    print(f"  输出: {CLEAN_FILE}")
    print(f"  日志: {LOG_FILE}")

    return entries


# ---------------------------------------------------------------------------
# Re-extraction of failed pages
# ---------------------------------------------------------------------------
def re_extract_failed_pages():
    """Re-extract pages that failed JSON parsing."""
    import anthropic
    from extract_vocab import extract_page

    client = anthropic.Anthropic()

    print(f"重新提取 {len(FAILED_PAGES)} 个失败页面...")

    all_entries = []
    for page_num in FAILED_PAGES:
        image_path = PAGES_DIR / f"page-{page_num:03d}.png"
        if not image_path.exists():
            print(f"  跳过 page-{page_num:03d} (文件不存在)")
            continue

        print(f"  提取 page-{page_num:03d}...", end=" ")
        entries = extract_page(client, image_path)

        for e in entries:
            e["_page"] = image_path.name

        print(f"→ {len(entries)} 条")
        all_entries.extend(entries)

        time.sleep(0.5)

    # Save
    save_jsonl(all_entries, RE_EXTRACTED_FILE)
    print(f"\n完成! 共 {len(all_entries)} 条，保存到 {RE_EXTRACTED_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_clean():
    """Run the full cleaning pipeline."""
    log = {}

    print("=== 数据清洗 Pipeline ===\n")

    # Step 1
    entries = step_load()
    log["step1_loaded"] = len(entries)
    print(f"  Step 1: 加载 → {len(entries)} 条")

    # Step 2
    entries = step_filter_garbage(entries, log)

    # Step 3
    entries = step_merge_cross_page(entries, log)

    # Step 4
    entries = step_deduplicate(entries, log)

    # Step 5
    entries = step_fix_fields(entries, log)

    # Step 6
    entries = step_validate_and_output(entries, log)

    return entries


def main():
    parser = argparse.ArgumentParser(description="Clean German vocabulary data")
    parser.add_argument("--re-extract", action="store_true",
                        help="Re-extract failed pages via Claude Vision API")
    parser.add_argument("--clean", action="store_true", default=True,
                        help="Run cleaning pipeline (default)")
    args = parser.parse_args()

    if args.re_extract:
        re_extract_failed_pages()

    run_clean()


if __name__ == "__main__":
    main()
