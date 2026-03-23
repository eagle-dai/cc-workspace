"""Extract German vocabulary from scanned PDF page images using Claude Vision."""

import anthropic
import base64
import json
import sys
import time
from pathlib import Path

OUTPUT_FILE = Path("tmp/vocab_raw.jsonl")
PAGES_DIR = Path("tmp/pdf_pages")

SYSTEM_PROMPT = """你是一个德语词汇提取专家。请从给定的词汇书页面图片中，精确提取所有德语词条。

每个词条提取为一个 JSON 对象，包含以下字段：
- wort: 德语单词原形（不含词性标注）
- wortart: 词性（如 n., v., Adj., Adv. 等，保持原书缩写）
- deklination: 变格/变位形式（如名词的 -s, -e；动词的变位等）
- bedeutung: 中文释义（多个义项用数字标注，如 "①流出,出水口 ②经过,过程"）
- beispiel_de: 德语例句（多条用 | 分隔）
- beispiel_cn: 对应中文翻译（多条用 | 分隔，与例句一一对应）
- wortbildung: 构词法/相关词（构词法部分的内容）
- synonyme: 同义词（同义词部分）
- antonyme: 反义词（反义词部分）
- erweiterung: 拓展记忆（拓展记忆部分的内容）

重要规则：
1. 保持德语特殊字符的准确性：ä, ö, ü, ß, Ä, Ö, Ü
2. 如果某个字段在页面中不存在，设为空字符串 ""
3. 词条标题通常是粗体或较大字号
4. "例 句" 后面是例句，"构词法" 后面是构词信息，"同义词" "反义词" "拓展记忆" 各有对应内容
5. 如果一个词条跨页（在页面底部被截断），仍然提取已有的部分
6. 仔细区分主词条和其派生词/相关词，只有主词条作为独立条目
7. 动词词条可能有 "+ A"、"+ D"、"sich + ..." 等用法标注，归入 deklination

输出格式：一个 JSON 数组，包含该页所有词条。只输出 JSON，不要其他文字。"""


def encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def extract_page(client: anthropic.Anthropic, image_path: Path) -> list[dict]:
    """Extract vocabulary entries from a single page image."""
    b64 = encode_image(image_path)

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "请提取这一页中的所有德语词条。严格按照 JSON 数组格式输出。",
                            },
                        ],
                    }
                ],
                system=SYSTEM_PROMPT,
            )

            text = response.content[0].text.strip()
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[: text.rfind("```")]
                text = text.strip()

            entries = json.loads(text)
            if isinstance(entries, list):
                return entries
            return [entries]

        except json.JSONDecodeError as e:
            print(f"  JSON parse error (attempt {attempt + 1}): {e}")
            if attempt == 2:
                print(f"  WARNING: Failed to parse {image_path.name}, saving raw text")
                return []
        except anthropic.APIError as e:
            print(f"  API error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                return []

    return []


def get_processed_pages(output_file: Path) -> set[str]:
    """Get set of already processed page filenames."""
    processed = set()
    if output_file.exists():
        for line in output_file.read_text().splitlines():
            if line.strip():
                data = json.loads(line)
                processed.add(data.get("_page", ""))
    return processed


def main():
    start_page = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    end_page = int(sys.argv[2]) if len(sys.argv) > 2 else 349

    client = anthropic.Anthropic()

    # Collect page images
    pages = sorted(PAGES_DIR.glob("page-*.png"))
    pages = [
        p
        for p in pages
        if start_page <= int(p.stem.split("-")[1]) <= end_page
    ]

    print(f"Found {len(pages)} page images to process (pages {start_page}-{end_page})")

    # Check for already processed pages (resume support)
    processed = get_processed_pages(OUTPUT_FILE)
    pages_to_process = [p for p in pages if p.name not in processed]
    print(f"Already processed: {len(processed)}, remaining: {len(pages_to_process)}")

    total_entries = 0

    with open(OUTPUT_FILE, "a") as f:
        for i, page_path in enumerate(pages_to_process):
            page_num = page_path.stem.split("-")[1]
            print(f"[{i + 1}/{len(pages_to_process)}] Processing page {page_num}...")

            entries = extract_page(client, page_path)

            for entry in entries:
                entry["_page"] = page_path.name
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            total_entries += len(entries)
            print(f"  → {len(entries)} entries (total: {total_entries})")

            # Small delay to avoid rate limits
            if i < len(pages_to_process) - 1:
                time.sleep(0.5)

    print(f"\nDone! Total entries extracted: {total_entries}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
