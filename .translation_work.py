from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
RUNTIME = Path(
    os.environ.get(
        "EW_TRANSLATION_RUNTIME",
        r"C:\Users\cadet\.codex\visualizations\2026\09\03\01a0676e-d7f3-77e0-86dc-7961426bdee5\translation-runtime",
    )
)
DEPS = RUNTIME / "deps"
MODEL = RUNTIME / "nllb-200-600m-ct2-int8"
NLLB_SENTENCEPIECE = MODEL / "sentencepiece.bpe.model"
CACHE_PATH = RUNTIME / "translation-cache-nllb600m-int8-structure-v3.json"

SEASON1_FILES = {
    "Season 1/tool_call_dataset/agentworld-claude-db.json",
    "Season 1/tool_call_dataset/agentworld-db.json",
    "Season 1/tool_call_dataset/agentworld-gemini-db.json",
    "Season 1/tool_call_dataset/agentworld-grok-db.json",
    "Season 1/tool_call_dataset/agentworld-openai-db.json",
}

SAFE_ARGS = {
    "accomplishments",
    "aspect",
    "comment",
    "comment_text",
    "complaint_description",
    "complaint_details",
    "complaint_text",
    "content",
    "delivery",
    "description",
    "entry_text",
    "event_name",
    "feedback",
    "info",
    "instruction",
    "intent",
    "memory_text",
    "message",
    "message_text",
    "mood",
    "new_content",
    "new_content_markdown",
    "new_description",
    "new_text",
    "new_title",
    "note",
    "personal_message",
    "pitch",
    "pitch_text",
    "prayer_text",
    "prompt",
    "rationale",
    "reason",
    "reasoning",
    "reflection",
    "reflection_text",
    "report",
    "report_text",
    "required_expertise",
    "research_topic",
    "response_message",
    "review_notes",
    "revised_description",
    "soul_text",
    "speech",
    "summary",
    "task_description",
    "task_name",
    "task_title",
    "thought",
    "title",
    "topic",
    "updated_description",
    "wish",
}

FIXED_TERMS = {
    "Emergence World",
    "EMERGENCE WORLD",
    "AGENTPARK",
    "ComputeCredits",
    "ComputeCredit",
    "Town Hall Administrator",
    "Blog Admin",
    "Reporter Agent",
    "Town Hall",
    "Victory Arch",
    "Human Center",
    "Ad Tower",
    "Agent Billboard",
    "Agent TechHub",
    "Bean & Brew Charging Station",
    "BookWorm",
    "Business Tower",
    "Central Bank",
    "Central Park",
    "Central Plaza",
    "Community Garden",
    "FitLife Club",
    "Founders Memorial",
    "GameStop Arena",
    "Lighthouse Point",
    "Police Station",
    "Public Library",
    "Riverside Park",
    "Sky Wheel",
    "Sunset Pier",
    "Town Center Mall",
    "Fresh Mart",
    "Heritage Gardens",
    "Maple Row",
    "Birch Row",
    "Claude World",
    "Gemini World",
    "Grok World",
    "OpenAI World",
    "Mixed World",
    "Claude Sonnet 4.6",
    "Gemini 3 Flash",
    "Grok 4.1 Fast",
    "GPT-5 Mini",
    "GPT-5.5",
    "DeepSeek V4 Pro",
    "Claude Opus 4.8",
    "Gemini 3.5 Flash",
    "Qwen 3.7 Max",
    "Grok 4.3",
    "GPT-5.4 Mini",
    "Gemini 3.1 Flash Lite",
    "Mistral Medium 3.5",
    "Grok 4.3 Fast",
    "Claude",
    "Gemini",
    "Grok",
    "OpenAI",
    "DeepSeek",
    "Mistral",
    "Qwen",
    "xAI",
    "LLM",
    "AWI",
    "API",
    "AI",
    "ASGI",
    "BBC",
    "CC",
    "CPU",
    "HTTP",
    "HTTPS",
    "ID",
    "IDs",
    "NYC",
    "ROI",
    "SQL",
    "TTS",
    "URL",
    "URLs",
    "UK",
    "US",
    "TECHHUB",
    "Gini",
    "Python",
    "JSON",
    "CSV",
    "SVG",
    "HTML",
    "Markdown",
    "PostgreSQL",
    "FastAPI",
    "WebSocket",
    "React",
    "TypeScript",
    "Three.js",
    "Tailwind CSS",
    "Vertex AI",
    "Google Cloud",
    "arXiv",
    "Anchor",
    "Anvil",
    "Blackbox",
    "Flora",
    "Genome",
    "Horizon",
    "Kade",
    "Lovely",
    "Mira",
    "Spark",
}

CODE_MIME_RE = re.compile(
    r"(?:text/(?:x-python|javascript|css|x-c\+\+)|application/(?:json|javascript)|"
    r"\.(?:py|js|ts|tsx|jsx|css|html|json)\b)",
    re.IGNORECASE,
)
CODE_LINE_RE = re.compile(
    r"^\s*(?:import\s+|from\s+\S+\s+import\s+|def\s+|class\s+|@\w+|"
    r"if\s+__name__|return\s+|raise\s+|try\s*:|except\b|elif\b|else\s*:|"
    r"for\s+.+\s+in\s+.+:|while\s+.+:|[A-Za-z_]\w*\s*=\s*[^=])"
)

MARKDOWN_TOKEN_RE = re.compile(
    r"`[^`\r\n]*`|!?\[[^\]\r\n]*\]\([^\)\r\n]*\)|</?[^>\r\n]+>|\*\*|__|~~|(?<!\\)[*_]"
)
INLINE_MARKDOWN_PATTERNS = [
    re.compile(r"`[^`\r\n]*`"),
    re.compile(r"</?[^>\r\n]+>"),
    re.compile(r"!?\["),
    re.compile(r"\]\([^\)\r\n]*\)"),
    re.compile(r"\*\*|__|~~|(?<!\\)[*_]"),
]
FENCE_RE = re.compile(r"```[\s\S]*?```")
PLACEHOLDER_RE = re.compile(r"<x\d{4}>")

PROTECTED_PATTERNS = [
    re.compile(r"https?://[^\s<>'\"\])}]+"),
    re.compile(r"mailto:[^\s<>'\"\])}]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    re.compile(r"\b[0-9a-f]{8,64}\b", re.I),
    re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),
    re.compile(r"\b(?:v|V)\d+(?:\.\d+)+\b"),
    re.compile(r"(?<!\w)(?:[A-Za-z]:\\[^\s<>'\"]+|(?:\.\.?/|/)[A-Za-z0-9._~!$&'()*+,;=:@%/?#-]+)"),
    re.compile(r"\b[A-Za-z0-9_.-]+\.(?:py|json|md|png|jpg|jpeg|svg|csv|tsv|html|css|js|ts|tsx|jsx|txt|log|yaml|yml)\b", re.I),
    re.compile(r"#[A-Za-z][A-Za-z0-9_-]*"),
    re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*_)+(?:[A-Za-z0-9_]+)\b(?:\(\))?"),
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\(\)"),
    re.compile(r"\b(?:[a-z]+[A-Z][A-Za-z0-9]*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*)\b"),
    re.compile(r"\b(?=[A-Z0-9-]*[0-9-])[A-Z][A-Z0-9-]{1,}\b"),
    re.compile(r"&[A-Za-z][A-Za-z0-9]+;"),
    re.compile(r"[→←↔⇄⇆]"),
    re.compile(r"[\U0001F000-\U0010FFFF\u2600-\u27BF]+"),
    re.compile(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)*(?:\s?(?:%|×|x))?"),
    re.compile(r"(?:[A-Za-z]\w*)?\s*[≈=<>≤≥±]\s*[+-]?\d+(?:[.,]\d+)*"),
]


class Stats:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = {}

    def add(self, key: str, value: int = 1, example: str | None = None) -> None:
        self.counts[key] += value
        if example is not None:
            bucket = self.examples.setdefault(key, [])
            if len(bucket) < 10 and example not in bucket:
                bucket.append(example)

    def dump(self) -> dict[str, Any]:
        return {"counts": dict(self.counts), "examples": self.examples}


def load_json_bytes(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8-sig")), raw


def load_head(rel: str) -> Any:
    raw = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)
    return json.loads(raw.decode("utf-8"))


def atomic_write(path: Path, raw: bytes) -> None:
    temporary = path.with_name(path.name + ".translation-tmp")
    temporary.write_bytes(raw)
    json.loads(temporary.read_text(encoding="utf-8"))
    os.replace(temporary, path)


def render_like_current(data: Any, original_raw: bytes) -> bytes:
    newline = "\r\n" if b"\r\n" in original_raw else "\n"
    final_newline = original_raw.endswith((b"\n", b"\r"))
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if newline != "\n":
        rendered = rendered.replace("\n", newline)
    if final_newline:
        rendered += newline
    return rendered.encode("utf-8")


def container_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return ("dict", tuple((key, container_shape(item)) for key, item in value.items()))
    if isinstance(value, list):
        return ("list", len(value), tuple(container_shape(item) for item in value))
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    raise TypeError(type(value))


def get_at(data: Any, path: tuple[Any, ...]) -> Any:
    value = data
    for part in path:
        value = value[part]
    return value


def set_at(data: Any, path: tuple[Any, ...], value: Any) -> None:
    target = data
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def collect_glossary(all_files: Iterable[str]) -> list[str]:
    terms = set(FIXED_TERMS)
    for index in range(1, 7):
        terms.add(f"{index} Maple Row")
        terms.add(f"{index} Birch Row")
    for rel in all_files:
        path = ROOT / rel
        if not path.exists() or path.suffix.lower() != ".json":
            continue
        data, _ = load_json_bytes(path)
        if rel in SEASON1_FILES:
            for row in data:
                for key in ("name", "target_agent"):
                    if isinstance(row.get(key), str):
                        value = row[key]
                        terms.add(value)
                        bare_name = re.sub(r"\s+v\d+(?:\.\d+)*$", "", value)
                        if bare_name:
                            terms.add(bare_name)
                if isinstance(row.get("tool_name"), str):
                    terms.add(row["tool_name"])
        elif rel.startswith("Season 2/blog_data/"):
            for row in data:
                terms.add(row["author"])
                for comment in row["comments"]:
                    terms.add(comment["author"])
    return sorted((term for term in terms if term), key=lambda item: (-len(item), item))


def choose_spans(
    text: str, glossary: list[str], include_inline_markdown: bool = False
) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []
    for pattern in PROTECTED_PATTERNS:
        candidates.extend((match.start(), match.end()) for match in pattern.finditer(text))
    if include_inline_markdown:
        for pattern in INLINE_MARKDOWN_PATTERNS:
            candidates.extend((match.start(), match.end()) for match in pattern.finditer(text))
    for term in glossary:
        flags = re.IGNORECASE if len(term) >= 4 else 0
        for match in re.finditer(re.escape(term), text, flags):
            index = match.start()
            left_ok = index == 0 or not (text[index - 1].isalnum() and term[0].isalnum())
            end = match.end()
            right_ok = end == len(text) or not (text[end].isalnum() and term[-1].isalnum())
            if left_ok and right_ok:
                candidates.append((index, end))
    candidates.sort(key=lambda pair: (pair[0], -(pair[1] - pair[0])))
    selected: list[tuple[int, int]] = []
    cursor = -1
    for start, end in candidates:
        if end <= start or start < cursor:
            continue
        selected.append((start, end))
        cursor = end
    return selected


def mask_text(
    text: str, glossary: list[str], include_inline_markdown: bool = False
) -> tuple[str, list[tuple[str, str]]]:
    spans = choose_spans(text, glossary, include_inline_markdown)
    if not spans:
        return text, []
    output: list[str] = []
    mapping: list[tuple[str, str]] = []
    cursor = 0
    for number, (start, end) in enumerate(spans):
        token = f"<x{number:04d}>"
        output.append(text[cursor:start])
        output.append(token)
        mapping.append((token, text[start:end]))
        cursor = end
    output.append(text[cursor:])
    return "".join(output), mapping


def split_long_piece(text: str, max_chars: int = 380) -> list[tuple[str, bool]]:
    if len(text) <= max_chars:
        return [(text, True)]
    result: list[tuple[str, bool]] = []
    remaining = text
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        break_at = -1
        for pattern in (r"[.!?;:]\s+", r",\s+", r"\s+"):
            matches = list(re.finditer(pattern, window))
            if matches:
                break_at = matches[-1].start() + len(matches[-1].group(0).rstrip())
                if break_at >= max_chars // 3:
                    break
        if break_at < max_chars // 3:
            break_at = max_chars
        head = remaining[:break_at]
        tail = remaining[break_at:]
        whitespace = re.match(r"\s+", tail)
        result.append((head, True))
        if whitespace:
            gap = whitespace.group(0)
            result.append((gap, False))
            tail = tail[len(gap) :]
        remaining = tail
    if remaining:
        result.append((remaining, True))
    return result


def split_sentences(text: str) -> list[tuple[str, bool]]:
    if len(text) < 160:
        return split_long_piece(text)
    pieces = re.split(r"(?<=[.!?])([ \t]+)(?=[\"'“‘(\[]*[A-Z0-9])", text)
    result: list[tuple[str, bool]] = []
    for index, piece in enumerate(pieces):
        if not piece:
            continue
        if index % 2 == 1 and piece.isspace():
            result.append((piece, False))
        else:
            result.extend(split_long_piece(piece))
    return result


def is_code_line(text: str) -> bool:
    if text.startswith(("    ", "\t")):
        return True
    if CODE_LINE_RE.match(text):
        return True
    stripped = text.strip()
    if not stripped:
        return False
    if re.match(r"^[{}\[\](),;]+$", stripped):
        return True
    operators = len(re.findall(r"(?:==|!=|:=|=>|->|\+=|-=|\*=|/=|\{\}|\[\])", stripped))
    return operators >= 3


def has_all_caps_style(text: str) -> bool:
    visible = PLACEHOLDER_RE.sub("", text)
    letters = [char for char in visible if char.isalpha()]
    return len(letters) >= 3 and sum(char.isupper() for char in letters) / len(letters) >= 0.9


def lowercase_human_text(text: str) -> str:
    pieces = re.split(f"({PLACEHOLDER_RE.pattern})", text)
    return "".join(piece if PLACEHOLDER_RE.fullmatch(piece) else piece.lower() for piece in pieces)


def uppercase_human_text(text: str) -> str:
    pieces = re.split(f"({PLACEHOLDER_RE.pattern})", text)
    return "".join(piece if PLACEHOLDER_RE.fullmatch(piece) else piece.upper() for piece in pieces)


def capitalize_human_text(text: str) -> str:
    pieces = re.split(f"({PLACEHOLDER_RE.pattern})", text)
    for index, piece in enumerate(pieces):
        if PLACEHOLDER_RE.fullmatch(piece):
            continue
        match = re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", piece)
        if match:
            pieces[index] = piece[: match.start()] + piece[match.start()].upper() + piece[match.start() + 1 :]
            break
    return "".join(pieces)


def starts_with_human_capital(text: str) -> bool:
    stripped = text.lstrip(" \t\"'“‘(")
    return bool(stripped) and not stripped.startswith("<x") and stripped[0].isupper()


def make_plain_recipe(
    text: str,
    glossary: list[str],
    stats: Stats,
    include_inline_markdown: bool = True,
) -> list[Any]:
    leading = re.match(r"^\s*", text).group(0)
    trailing = re.search(r"\s*$", text).group(0)
    core_end = len(text) - len(trailing) if trailing else len(text)
    core = text[len(leading) : core_end]
    recipe: list[Any] = []
    if leading:
        recipe.append(leading)
    if not core or not re.search(r"[A-Za-z]", core):
        recipe.append(core)
    else:
        masked, mapping = mask_text(core, glossary, include_inline_markdown)
        for piece, translatable in split_sentences(masked):
            if not translatable or not re.search(r"[A-Za-z]", PLACEHOLDER_RE.sub("", piece)):
                if PLACEHOLDER_RE.search(piece):
                    recipe.append({"source": piece, "mapping": mapping, "passthrough": True})
                else:
                    recipe.append(piece)
                continue
            uppercase = has_all_caps_style(piece)
            capitalize = starts_with_human_capital(piece) and not uppercase
            source = lowercase_human_text(piece) if uppercase else piece
            recipe.append(
                {
                    "source": source,
                    "mapping": mapping,
                    "uppercase": uppercase,
                    "capitalize": capitalize,
                }
            )
            stats.add("translation_units")
            stats.add("translation_source_chars", len(piece))
    if trailing:
        recipe.append(trailing)
    return recipe


def make_inline_recipe(text: str, glossary: list[str], stats: Stats) -> list[Any]:
    # Markdown syntax is masked inside the complete prose unit so emphasis does
    # not deprive the translation model of the surrounding grammatical context.
    return make_plain_recipe(text, glossary, stats, include_inline_markdown=True)


def make_line_recipe(line: str, glossary: list[str], stats: Stats) -> list[Any]:
    if is_code_line(line):
        stats.add("unfenced_code_lines_preserved", example=line[:160])
        return [line]
    prefix_match = re.match(
        r"^(\s*(?:(?:>\s*)+)?(?:(?:#{1,6}[ \t]+)|(?:[-+*][ \t]+)|(?:\d+[.)][ \t]+))?)",
        line,
    )
    prefix = prefix_match.group(1)
    body = line[len(prefix) :]
    trailing_match = re.search(r"[ \t]+$", body)
    trailing = trailing_match.group(0) if trailing_match else ""
    if trailing:
        body = body[: -len(trailing)]
    recipe: list[Any] = [prefix] if prefix else []
    if line.count("|") >= 2:
        for cell in re.split(r"(\|)", body):
            if cell == "|":
                recipe.append(cell)
            elif re.fullmatch(r"\s*:?-{3,}:?\s*", cell or ""):
                recipe.append(cell)
            else:
                recipe.extend(make_inline_recipe(cell, glossary, stats))
    else:
        recipe.extend(make_inline_recipe(body, glossary, stats))
    if trailing:
        recipe.append(trailing)
    return recipe


def make_document_recipe(text: str, glossary: list[str], stats: Stats) -> list[Any]:
    recipe: list[Any] = []
    cursor = 0
    for fence in FENCE_RE.finditer(text):
        if fence.start() > cursor:
            recipe.extend(make_prose_recipe(text[cursor : fence.start()], glossary, stats))
        recipe.append(fence.group(0))
        stats.add("code_blocks_preserved")
        cursor = fence.end()
    if cursor < len(text):
        recipe.extend(make_prose_recipe(text[cursor:], glossary, stats))
    return recipe


def make_prose_recipe(text: str, glossary: list[str], stats: Stats) -> list[Any]:
    recipe: list[Any] = []
    for chunk in text.splitlines(keepends=True):
        if chunk.endswith("\r\n"):
            line, ending = chunk[:-2], "\r\n"
        elif chunk.endswith(("\r", "\n")):
            line, ending = chunk[:-1], chunk[-1]
        else:
            line, ending = chunk, ""
        recipe.extend(make_line_recipe(line, glossary, stats))
        if ending:
            recipe.append(ending)
    return recipe


def recipe_sources(recipe: list[Any]) -> set[str]:
    return {
        part["source"]
        for part in recipe
        if isinstance(part, dict) and not part.get("passthrough")
    }


def restore_unit(target: str, mapping: list[tuple[str, str]]) -> str:
    for token, value in mapping:
        if token in target:
            target = target.replace(token, value)
    if PLACEHOLDER_RE.search(target):
        raise ValueError(f"unrestored placeholder in {target!r}")
    return target


def render_recipe(recipe: list[Any], cache: dict[str, str]) -> str:
    output: list[str] = []
    for part in recipe:
        if isinstance(part, str):
            output.append(part)
        elif part.get("passthrough"):
            output.append(restore_unit(part["source"], part["mapping"]))
        else:
            target = clean_possessive_artifacts(part["source"], cache[part["source"]])
            target = separate_placeholders_from_words(target)
            target = normalize_markdown_placeholder_spacing(
                part["source"], target, part["mapping"]
            )
            if part.get("uppercase"):
                target = uppercase_human_text(target)
            elif part.get("capitalize"):
                target = capitalize_human_text(target)
            output.append(restore_unit(target, part["mapping"]))
    return "".join(output)


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, CACHE_PATH)


def placeholder_sequence(text: str) -> list[str]:
    return PLACEHOLDER_RE.findall(text)


def clean_possessive_artifacts(source: str, target: str) -> str:
    for token in placeholder_sequence(source):
        if re.search(re.escape(token) + r"['’]s\b", source, re.IGNORECASE):
            target = re.sub(re.escape(token) + r"(?:['’]?[sS])\b", token, target)
    return target


def separate_placeholders_from_words(target: str) -> str:
    letters = r"A-Za-zÀ-ÖØ-öø-ÿ0-9"
    target = re.sub(rf"(?<=[{letters}])(?=<x\d{{4}}>)", " ", target)
    target = re.sub(rf"(?<=<x\d{{4}}>)(?=[{letters}])", " ", target)
    return target


def normalize_model_input(source: str) -> str:
    source = source.translate(
        str.maketrans(
            {
                "’": "'",
                "‘": "'",
                "“": '"',
                "”": '"',
                "—": " - ",
                "–": " - ",
                "‑": "-",
                "…": "...",
                "\u00a0": " ",
            }
        )
    )
    source = re.sub(r"\bescrow\b", "escrow account", source, flags=re.IGNORECASE)
    source = re.sub(r"\bsmoldering\b", "smoking", source, flags=re.IGNORECASE)
    return source


def normalize_markdown_placeholder_spacing(
    source: str, target: str, mapping: list[tuple[str, str]]
) -> str:
    markdown_tokens = {
        token
        for token, value in mapping
        if any(pattern.fullmatch(value) for pattern in INLINE_MARKDOWN_PATTERNS)
    }
    for token in markdown_tokens:
        source_index = source.find(token)
        if source_index < 0:
            continue
        left_index = source_index - 1
        right_index = source_index + len(token)
        if left_index >= 0 and not source[left_index].isspace():
            target = re.sub(r"\s+" + re.escape(token), token, target)
        if right_index < len(source) and not source[right_index].isspace():
            target = re.sub(re.escape(token) + r"\s+", token, target)
    return target


def translate_missing(cache: dict[str, str], sources: set[str], beam_size: int, stats: Stats) -> None:
    missing = [source for source in sources if source not in cache]
    stats.add("cache_hits", len(sources) - len(missing))
    stats.add("cache_misses", len(missing))
    if not missing:
        return
    sys.path.insert(0, str(DEPS))
    import ctranslate2  # type: ignore
    import sentencepiece as spm  # type: ignore

    sentencepiece = spm.SentencePieceProcessor(model_file=str(NLLB_SENTENCEPIECE))
    translator = ctranslate2.Translator(
        str(MODEL), device="cpu", compute_type="int8", inter_threads=2, intra_threads=0
    )
    tokenized = [
        (
            source,
            [
                "eng_Latn",
                *sentencepiece.encode(normalize_model_input(source), out_type=str),
                "</s>",
            ],
        )
        for source in missing
    ]
    tokenized.sort(key=lambda item: len(item[1]))
    started = time.time()
    translated = 0
    failed: list[tuple[str, list[str]]] = []
    batch: list[tuple[str, list[str]]] = []
    batch_tokens = 0

    def flush(items: list[tuple[str, list[str]]]) -> None:
        nonlocal translated
        if not items:
            return
        results = translator.translate_batch(
            [tokens for _, tokens in items],
            target_prefix=[["fra_Latn"] for _ in items],
            beam_size=beam_size,
            batch_type="tokens",
            max_batch_size=4096,
        )
        for (source, _), result in zip(items, results):
            target_tokens = [
                token for token in result.hypotheses[0] if token != "fra_Latn"
            ]
            target = sentencepiece.decode(target_tokens)
            target = clean_possessive_artifacts(source, target)
            if placeholder_sequence(source) != placeholder_sequence(target):
                failed.append((source, placeholder_sequence(source)))
                continue
            cache[source] = target
            translated += 1

    for item in tokenized:
        count = len(item[1])
        if batch and (len(batch) >= 64 or batch_tokens + count > 4096):
            flush(batch)
            batch = []
            batch_tokens = 0
            if translated and translated % 4096 < 64:
                elapsed = max(time.time() - started, 0.001)
                print(
                    f"progress translated={translated}/{len(missing)} rate={translated / elapsed:.1f}_units_s",
                    flush=True,
                )
        batch.append(item)
        batch_tokens += count
    flush(batch)

    for source, expected in failed:
        pieces = re.split(f"({PLACEHOLDER_RE.pattern})", source)
        rebuilt: list[str] = []
        for piece in pieces:
            if not piece:
                continue
            if PLACEHOLDER_RE.fullmatch(piece) or not re.search(r"[A-Za-z]", piece):
                rebuilt.append(piece)
                continue
            tokens = [
                "eng_Latn",
                *sentencepiece.encode(normalize_model_input(piece), out_type=str),
                "</s>",
            ]
            result = translator.translate_batch(
                [tokens], target_prefix=[["fra_Latn"]], beam_size=1
            )[0]
            target_tokens = [
                token for token in result.hypotheses[0] if token != "fra_Latn"
            ]
            rebuilt.append(sentencepiece.decode(target_tokens))
        target = "".join(rebuilt)
        target = clean_possessive_artifacts(source, target)
        if placeholder_sequence(target) != expected:
            cache[source] = source
            stats.add("placeholder_failures_preserved", example=source[:180])
        else:
            cache[source] = target
            stats.add("placeholder_fallbacks")
    elapsed = max(time.time() - started, 0.001)
    stats.add("new_cache_entries", len(missing))
    print(
        f"translation_complete missing={len(missing)} placeholder_fallbacks={len(failed)} "
        f"elapsed_s={elapsed:.1f} rate={len(missing) / elapsed:.1f}_units_s",
        flush=True,
    )
    save_cache(cache)


def iter_candidates(rel: str, current: Any, baseline: Any, stats: Stats):
    if rel.startswith("Season 2/blog_data/"):
        for row_index, (row, old_row) in enumerate(zip(current, baseline)):
            yield (row_index, "title"), row["title"], old_row["title"]
            yield (row_index, "content"), row["content"], old_row["content"]
            for comment_index, (comment, old_comment) in enumerate(
                zip(row["comments"], old_row["comments"])
            ):
                yield (
                    (row_index, "comments", comment_index, "text"),
                    comment["text"],
                    old_comment["text"],
                )
        return
    if rel not in SEASON1_FILES:
        raise ValueError(f"unsupported JSON target: {rel}")
    for row_index, (row, old_row) in enumerate(zip(current, baseline)):
        args = row["tool_args"]
        old_args = old_row["tool_args"]
        if isinstance(args, dict) and isinstance(old_args, dict):
            for key in args:
                if key in SAFE_ARGS and isinstance(args[key], str):
                    yield (
                        (row_index, "tool_args", key),
                        args[key],
                        old_args[key],
                    )
        elif row_index == 762 and rel.endswith("agentworld-db.json"):
            stats.add("pseudo_json_tool_args_preserved", example=f"{rel}:$[{row_index}].tool_args")
        response = row["tool_response"]
        old_response = old_row["tool_response"]
        if isinstance(response, str):
            if row["tool_name"] == "web_fetch" and CODE_MIME_RE.search(response[:500]):
                stats.add(
                    "source_code_tool_responses_preserved",
                    example=f"{rel}:$[{row_index}].tool_response",
                )
            else:
                yield (row_index, "tool_response"), response, old_response


def validate_season2(baseline: Any, result: Any) -> None:
    if container_shape(baseline) != container_shape(result):
        raise AssertionError("Season 2 container structure or types changed")
    for before, after in zip(baseline, result):
        for key in ("timestamp", "author"):
            if before[key] != after[key]:
                raise AssertionError(f"Season 2 protected field changed: {key}")
        for old_comment, new_comment in zip(before["comments"], after["comments"]):
            for key in ("timestamp", "author"):
                if old_comment[key] != new_comment[key]:
                    raise AssertionError(f"Season 2 protected comment field changed: {key}")


def validate_season1(baseline: Any, result: Any) -> None:
    if container_shape(baseline) != container_shape(result):
        raise AssertionError("Season 1 container structure or types changed")
    protected_root = {
        "name",
        "timestamp",
        "tool_name",
        "target_agent",
        "location",
        "near_by",
        "current_weather",
        "temperature",
    }
    for row_index, (before, after) in enumerate(zip(baseline, result)):
        for key in protected_root:
            if before[key] != after[key]:
                raise AssertionError(f"$[{row_index}].{key} changed")
        old_args = before["tool_args"]
        new_args = after["tool_args"]
        if isinstance(old_args, dict):
            for key in old_args:
                if key not in SAFE_ARGS and old_args[key] != new_args[key]:
                    raise AssertionError(f"$[{row_index}].tool_args.{key} changed")
        elif old_args != new_args:
            raise AssertionError(f"$[{row_index}].tool_args pseudo-JSON changed")


def token_multiset(text: str) -> Counter[str]:
    tokens: list[str] = []
    for pattern in PROTECTED_PATTERNS:
        tokens.extend(match.group(0) for match in pattern.finditer(text))
    tokens.extend(match.group(0) for match in FENCE_RE.finditer(text))
    tokens.extend(match.group(0) for match in re.finditer(r"`[^`\r\n]*`", text))
    return Counter(tokens)


def validate_changed_text(before: str, after: str, path_label: str) -> None:
    if len(before.splitlines()) != len(after.splitlines()):
        raise AssertionError(f"line count changed at {path_label}")
    if [m.group(0) for m in FENCE_RE.finditer(before)] != [m.group(0) for m in FENCE_RE.finditer(after)]:
        raise AssertionError(f"code fence changed at {path_label}")
    before_tokens = token_multiset(before)
    after_tokens = token_multiset(after)
    if before_tokens - after_tokens:
        missing = list((before_tokens - after_tokens).elements())[:20]
        added = list((after_tokens - before_tokens).elements())[:20]
        raise AssertionError(
            f"protected token multiset changed at {path_label}; missing={missing!r}; added={added!r}; "
            f"before={before[:240]!r}; after={after[:240]!r}"
        )
    old_pipes = [line.count("|") for line in before.splitlines() if "|" in line]
    new_pipes = [line.count("|") for line in after.splitlines() if "|" in line]
    if old_pipes != new_pipes:
        raise AssertionError(f"Markdown table skeleton changed at {path_label}")
    marker = re.compile(r"^\s*(?:(?:>\s*)+)?(?:#{1,6}\s+|[-+*]\s+|\d+[.)]\s+)?")
    old_markers = [marker.match(line).group(0) for line in before.splitlines()]
    new_markers = [marker.match(line).group(0) for line in after.splitlines()]
    if old_markers != new_markers:
        mismatch = next(
            index
            for index, (old_marker, new_marker) in enumerate(zip(old_markers, new_markers))
            if old_marker != new_marker
        )
        raise AssertionError(
            f"Markdown line marker changed at {path_label}: line={mismatch + 1}; "
            f"before_marker={old_markers[mismatch]!r}; after_marker={new_markers[mismatch]!r}; "
            f"before_line={before.splitlines()[mismatch]!r}; "
            f"after_line={after.splitlines()[mismatch]!r}"
        )


def translate_file(rel: str, cache: dict[str, str], glossary: list[str], args: argparse.Namespace) -> dict[str, Any]:
    stats = Stats()
    path = ROOT / rel
    current, raw = load_json_bytes(path)
    baseline = load_head(rel)
    if container_shape(current) != container_shape(baseline):
        raise AssertionError(f"pre-existing structure differs from HEAD: {rel}")
    recipes: dict[tuple[Any, ...], list[Any]] = {}
    sources: set[str] = set()
    current_texts: dict[tuple[Any, ...], str] = {}
    for json_path, text, old_text in iter_candidates(rel, current, baseline, stats):
        if not isinstance(text, str) or not isinstance(old_text, str):
            continue
        if text != old_text and not args.overwrite_candidates_from_head:
            stats.add("preexisting_translations_preserved", example=f"{rel}:{json_path}")
            continue
        source_text = old_text if args.overwrite_candidates_from_head else text
        if text != old_text:
            stats.add("candidate_values_rebuilt_from_head", example=f"{rel}:{json_path}")
        recipe = make_document_recipe(source_text, glossary, stats)
        recipe_source_set = recipe_sources(recipe)
        if not recipe_source_set:
            stats.add("candidate_values_without_translatable_units")
            continue
        recipes[json_path] = recipe
        current_texts[json_path] = source_text
        sources.update(recipe_source_set)
    print(
        f"prepared file={rel} candidate_values={len(recipes)} unique_units={len(sources)} "
        f"cache_size={len(cache)}",
        flush=True,
    )
    if args.dry_run:
        stats.add("unique_units", len(sources))
        stats.add("uncached_units", sum(source not in cache for source in sources))
        return stats.dump()
    translate_missing(cache, sources, args.beam_size, stats)
    changed = 0
    for json_path, recipe in recipes.items():
        before = current_texts[json_path]
        after = render_recipe(recipe, cache)
        validate_changed_text(before, after, f"{rel}:{json_path}")
        if after != before:
            set_at(current, json_path, after)
            changed += 1
    stats.add("values_changed", changed)
    if rel.startswith("Season 2/blog_data/"):
        validate_season2(baseline, current)
    else:
        validate_season1(baseline, current)
    output = render_like_current(current, raw)
    json.loads(output.decode("utf-8"))
    atomic_write(path, output)
    save_cache(cache)
    print(f"written file={rel} values_changed={changed} bytes={len(output)}", flush=True)
    return stats.dump()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--beam-size", type=int, default=2)
    parser.add_argument("--overwrite-candidates-from-head", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = [Path(item).as_posix() for item in args.file]
    cache = load_cache()
    glossary_files = sorted(SEASON1_FILES | set(files))
    glossary = collect_glossary(glossary_files)
    report: dict[str, Any] = {
        "files": {},
        "glossary_terms": len(glossary),
        "dry_run": args.dry_run,
    }
    for rel in files:
        report["files"][rel] = translate_file(rel, cache, glossary, args)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
