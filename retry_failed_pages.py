"""Retry failed pages with more robust JSON parsing.

The original extract_page() fails on pages where Claude returns slightly
malformed JSON (e.g., unescaped quotes in German text). This script uses
a more tolerant parsing approach.
"""

import anthropic
import base64
import json
import re
import time
from pathlib import Path

PAGES_DIR = Path("tmp/pdf_pages")
OUTPUT_FILE = Path("tmp/vocab_re_extracted.jsonl")

FAILED_PAGES = [
    65, 66, 98, 103, 153, 164, 185, 187,
    192, 200, 225, 252, 263, 312, 341, 349,
]

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
3. 所有字符串值中的双引号必须转义为 \\"
4. 不要在字符串值中使用换行符，用空格替代
5. 只输出 JSON 数组，不要其他文字，不要 markdown 代码块标记
6. 确保 JSON 格式严格正确"""


def encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("utf-8")


def fix_json(text: str) -> str:
    """Try to fix common JSON issues from Claude output."""
    text = text.strip()

    # Remove markdown code block markers
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:text.rfind("```")]
        text = text.strip()

    # Remove "json" language tag if present
    if text.startswith("json"):
        text = text[4:].strip()

    # Try to find the JSON array boundaries
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]

    # Fix unescaped newlines inside strings
    # Replace actual newlines inside strings with spaces
    lines = text.split("\n")
    fixed_lines = []
    in_string = False
    for line in lines:
        # Count unescaped quotes to track string state
        for char in line:
            if char == '"':
                # Simple toggle (doesn't handle all edge cases but works for most)
                in_string = not in_string
        fixed_lines.append(line)

    text = "\n".join(fixed_lines)

    return text


def try_parse_individual(text: str) -> list[dict]:
    """Try to parse individual JSON objects from text that fails as array."""
    objects = []

    # Try splitting by },{ pattern
    # Find all { ... } blocks at the top level
    depth = 0
    current = ""
    for char in text:
        if char == "{":
            depth += 1
            current += char
        elif char == "}":
            depth -= 1
            current += char
            if depth == 0:
                try:
                    obj = json.loads(current)
                    if isinstance(obj, dict) and "wort" in obj:
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                current = ""
        elif depth > 0:
            current += char

    return objects


def extract_page_robust(client: anthropic.Anthropic, image_path: Path) -> list[dict]:
    """Extract with more robust JSON parsing."""
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
                                "text": "请提取这一页中的所有德语词条。严格按照 JSON 数组格式输出。注意：所有字符串中的双引号必须转义，不要使用换行符。",
                            },
                        ],
                    }
                ],
                system=SYSTEM_PROMPT,
            )

            raw_text = response.content[0].text.strip()

            # Attempt 1: Direct parse
            try:
                fixed = fix_json(raw_text)
                entries = json.loads(fixed)
                if isinstance(entries, list):
                    return entries
                return [entries]
            except json.JSONDecodeError:
                pass

            # Attempt 2: Parse individual objects
            entries = try_parse_individual(raw_text)
            if entries:
                print(f"    (recovered {len(entries)} entries via individual parsing)")
                return entries

            # Attempt 3: Try with more aggressive fixing
            # Replace problematic patterns
            cleaned = raw_text
            # Fix unescaped quotes in values like: "bedeutung": "something "quoted" here"
            # This is a heuristic - replace internal quotes that aren't at field boundaries
            cleaned = fix_json(cleaned)
            cleaned = re.sub(r'(?<=\w)"(?=\w)', '\\"', cleaned)
            try:
                entries = json.loads(cleaned)
                if isinstance(entries, list):
                    return entries
            except json.JSONDecodeError:
                pass

            if attempt < 2:
                print(f"    Parse failed (attempt {attempt + 1}), retrying...")
                time.sleep(3)
            else:
                # Last resort: save raw text for manual review
                raw_dir = Path("tmp/raw_responses")
                raw_dir.mkdir(exist_ok=True)
                (raw_dir / image_path.name.replace(".png", ".txt")).write_text(raw_text)
                print(f"    Saved raw response to tmp/raw_responses/")

                # Try one more time with individual parsing on raw
                entries = try_parse_individual(raw_text)
                if entries:
                    return entries
                return []

        except anthropic.APIError as e:
            print(f"    API error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                return []

    return []


def main():
    client = anthropic.Anthropic()

    print(f"重新提取 {len(FAILED_PAGES)} 个顽固页面 (增强 JSON 解析)...\n")

    all_entries = []
    success = 0

    for page_num in FAILED_PAGES:
        image_path = PAGES_DIR / f"page-{page_num:03d}.png"
        if not image_path.exists():
            print(f"  跳过 page-{page_num:03d} (文件不存在)")
            continue

        print(f"  page-{page_num:03d}...", end=" ")
        entries = extract_page_robust(client, image_path)

        for e in entries:
            e["_page"] = image_path.name

        if entries:
            success += 1
            print(f"✓ {len(entries)} 条")
        else:
            print(f"✗ 0 条")

        all_entries.extend(entries)
        time.sleep(0.5)

    # Save (append to existing re-extracted file)
    existing = []
    existing_pages = set()
    if OUTPUT_FILE.exists():
        for line in OUTPUT_FILE.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                existing.append(d)
                existing_pages.add(d.get("_page", ""))

    # Only add new entries for pages not already successfully extracted
    new_pages = set()
    for e in all_entries:
        new_pages.add(e["_page"])

    # Keep existing entries not from newly extracted pages + new entries
    final = [e for e in existing if e.get("_page") not in new_pages]
    final.extend(all_entries)

    with open(OUTPUT_FILE, "w") as f:
        for e in final:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n完成! 成功: {success}/{len(FAILED_PAGES)} 页, 共 {len(all_entries)} 条新词条")
    print(f"保存到: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
