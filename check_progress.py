"""Check extraction progress with dynamic ETA based on rolling speed."""

import json
import time
from pathlib import Path

VOCAB_FILE = Path("tmp/vocab_raw.jsonl")
PROGRESS_LOG = Path("tmp/progress_log.jsonl")
TARGET_PAGES = 342


def get_current_stats():
    total = 0
    pages = set()
    with open(VOCAB_FILE) as f:
        for line in f:
            total += 1
            d = json.loads(line)
            pages.add(d.get("_page", ""))
    return len(pages), total, sorted(pages)[-1] if pages else "?"


def load_history():
    if not PROGRESS_LOG.exists():
        return []
    entries = []
    for line in PROGRESS_LOG.read_text().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def save_checkpoint(ts, pages, words):
    with open(PROGRESS_LOG, "a") as f:
        f.write(json.dumps({"ts": ts, "pages": pages, "words": words}) + "\n")


def main():
    now = time.time()
    done_pages, done_words, last_page = get_current_stats()

    # Save this checkpoint
    save_checkpoint(now, done_pages, done_words)

    # Load history for speed calculation
    history = load_history()
    remaining = TARGET_PAGES - done_pages
    pct = done_pages * 100 // TARGET_PAGES

    # Calculate speed from recent history (use last 3 checkpoints for smoothing)
    eta_str = "计算中"
    if len(history) >= 2:
        # Use oldest available vs now for more stable estimate
        # But cap at last 6 entries (~30 min) to stay responsive to speed changes
        lookback = history[-min(6, len(history)):]
        old = lookback[0]
        dt = now - old["ts"]
        dp = done_pages - old["pages"]
        if dt > 0 and dp > 0:
            pages_per_sec = dp / dt
            eta_sec = remaining / pages_per_sec
            eta_min = eta_sec / 60
            speed = 1 / pages_per_sec
            eta_str = f"~{eta_min:.0f} 分钟 ({speed:.1f}秒/页)"

    print(f"{done_pages}/{TARGET_PAGES} 页 ({pct}%) | {done_words} 词条 | 当前: {last_page} | 剩余: {eta_str}")


if __name__ == "__main__":
    main()
