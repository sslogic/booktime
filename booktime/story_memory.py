import json
import shutil
import base64
import struct
import zlib
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "booktime_config.json"


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def load_config():
    config = load_json(CONFIG_PATH, default={})
    if not config:
        config = {}
    config.setdefault("memory_dir", "story_memory")
    config.setdefault("booktime_host", "127.0.0.1")
    config.setdefault("booktime_port", 8765)
    config.setdefault("ollama_url", "http://127.0.0.1:11434")
    config.setdefault("ollama_model", "")
    config.setdefault("book_id", "booktime")
    apply_runtime_defaults(config)
    return config


def apply_runtime_defaults(config):
    home = Path.home()
    local_appdata = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    if not config.get("lmstudio_conversations_dir"):
        config["lmstudio_conversations_dir"] = str(home / ".lmstudio" / "conversations")
    if not config.get("lmstudio_user_files_dir"):
        config["lmstudio_user_files_dir"] = str(home / ".lmstudio" / "user-files")
    if not config.get("lmstudio_exe_path"):
        candidate = local_appdata / "Programs" / "LM Studio" / "LM Studio.exe"
        config["lmstudio_exe_path"] = str(candidate) if candidate.exists() else ""
    if not config.get("ollama_exe_path"):
        candidate = local_appdata / "Programs" / "Ollama" / "ollama.exe"
        config["ollama_exe_path"] = str(candidate) if candidate.exists() else ""


def save_config(config):
    save_json(CONFIG_PATH, config)


def memory_root(config=None):
    config = config or load_config()
    raw = Path(config.get("memory_dir", "story_memory"))
    if not raw.is_absolute():
        raw = ROOT / raw
    raw.mkdir(parents=True, exist_ok=True)
    for child in ("transcripts", "source-files", "memory"):
        (raw / child).mkdir(parents=True, exist_ok=True)
    return raw


def continuity_path(config=None):
    return memory_root(config) / "memory" / "continuity.json"


def seed_path(config=None):
    return memory_root(config) / "memory" / "latest_seed.md"


def custom_characters_path(config=None):
    return memory_root(config) / "memory" / "custom_characters.json"


def manifest_path(config=None):
    return memory_root(config) / "manifest.jsonl"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text(path, default=""):
    path = Path(path)
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def split_lines(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").replace(";", "\n").splitlines() if part.strip()]


def normalize_name(name):
    return " ".join((name or "").strip().lower().split())


def load_continuity(config=None):
    return load_json(continuity_path(config), default={}) or {}


def load_custom_characters(config=None):
    data = load_json(custom_characters_path(config), default={"characters": []})
    chars = data.get("characters", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    cfg = config or load_config()
    char_dir = memory_root(cfg) / "characters"
    if char_dir.exists():
        for png in sorted(char_dir.glob("*.png")):
            card = read_png_character_card(png)
            if card:
                chars.append(card)
    return chars


def save_custom_characters(characters, config=None, write_png=False):
    cfg = config or load_config()
    cards = [to_sillytavern_card(c) for c in characters]
    save_json(custom_characters_path(cfg), {"book_id": cfg.get("book_id", "booktime"), "characters": cards})
    char_dir = memory_root(cfg) / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    for card in cards:
        name = card.get("data", {}).get("name") or card.get("name") or "character"
        filename = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in name).strip("-") or "character"
        save_json(char_dir / f"{filename}.json", card)
        if write_png and not (char_dir / f"{filename}.png").exists():
            write_png_character_card(char_dir / f"{filename}.png", card)


def list_characters(config=None):
    cfg = config or load_config()
    continuity = load_continuity(cfg)
    cards = continuity.get("character_cards", []) if isinstance(continuity, dict) else []
    custom = load_custom_characters(cfg)
    merged = {}
    for source, collection in (("continuity", cards), ("custom", custom)):
        for card in collection:
            if not isinstance(card, dict):
                continue
            flat = flatten_character(card)
            name = (flat.get("name") or "").strip()
            if not name:
                continue
            merged[normalize_name(name)] = {**flat, "card": to_sillytavern_card(card), "source": source}
    return sorted(merged.values(), key=lambda c: c.get("name", "").lower())


def upsert_custom_character(card, config=None):
    cfg = config or load_config()
    flat_input = flatten_character(card)
    name = (flat_input.get("name") or "").strip()
    if not name:
        raise ValueError("Character name is required.")
    clean = {
        "name": name,
        "role": (flat_input.get("role") or "").strip(),
        "description": (flat_input.get("description") or "").strip(),
        "personality": split_lines(flat_input.get("personality")),
        "scenario": (flat_input.get("scenario") or "").strip(),
        "first_mes": (flat_input.get("first_mes") or "").strip(),
        "mes_example": (flat_input.get("mes_example") or "").strip(),
        "relationships": split_lines(flat_input.get("relationships")),
        "voice_rules": split_lines(flat_input.get("voice_rules")),
        "do_not_change": split_lines(flat_input.get("do_not_change")),
        "creator_notes": (flat_input.get("creator_notes") or flat_input.get("notes") or "").strip(),
        "system_prompt": (flat_input.get("system_prompt") or "").strip(),
        "post_history_instructions": (flat_input.get("post_history_instructions") or "").strip(),
        "tags": split_lines(flat_input.get("tags")),
        "creator": (flat_input.get("creator") or "Book Time").strip(),
        "character_version": (flat_input.get("character_version") or "1.0").strip(),
    }
    existing = load_custom_characters(cfg)
    key = normalize_name(name)
    kept = [c for c in existing if normalize_name(flatten_character(c).get("name")) != key]
    kept.append(to_sillytavern_card(clean))
    kept.sort(key=lambda c: flatten_character(c).get("name", "").lower())
    save_custom_characters(kept, cfg)
    return flatten_character(to_sillytavern_card(clean))


def import_character_png(filename, png_bytes, config=None):
    cfg = config or load_config()
    card = read_png_character_card_bytes(png_bytes)
    if not card:
        raise ValueError("PNG does not contain a SillyTavern/TavernAI chara card.")
    flat = flatten_character(card)
    name = flat.get("name") or Path(filename).stem
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in name).strip("-") or "character"
    char_dir = memory_root(cfg) / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    png_path = char_dir / f"{safe_name}.png"
    json_path = char_dir / f"{safe_name}.json"
    png_path.write_bytes(png_bytes)
    save_json(json_path, to_sillytavern_card(card))
    return flatten_character(card)


def save_character_png(card, png_base64, config=None):
    cfg = config or load_config()
    png_bytes = base64.b64decode(png_base64)
    st_card = to_sillytavern_card(card)
    flat = flatten_character(st_card)
    name = flat.get("name") or "character"
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in name).strip("-") or "character"
    char_dir = memory_root(cfg) / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    png_path = char_dir / f"{safe_name}.png"
    png_path.write_bytes(embed_png_character_card(png_bytes, st_card))
    return str(png_path)


def flatten_character(card):
    if not isinstance(card, dict):
        return {}
    data = card.get("data") if isinstance(card.get("data"), dict) else None
    if data is not None:
        extensions = data.get("extensions", {}) if isinstance(data.get("extensions"), dict) else {}
        booktime = extensions.get("booktime", {}) if isinstance(extensions.get("booktime"), dict) else {}
        return {
            "name": data.get("name", ""),
            "role": booktime.get("role", card.get("role", "")),
            "description": data.get("description", ""),
            "personality": data.get("personality", ""),
            "scenario": data.get("scenario", ""),
            "first_mes": data.get("first_mes", ""),
            "mes_example": data.get("mes_example", ""),
            "creator_notes": data.get("creator_notes", ""),
            "system_prompt": data.get("system_prompt", ""),
            "post_history_instructions": data.get("post_history_instructions", ""),
            "tags": data.get("tags", []),
            "creator": data.get("creator", ""),
            "character_version": data.get("character_version", ""),
            "relationships": booktime.get("relationships", card.get("relationships", [])),
            "voice_rules": booktime.get("voice_rules", card.get("voice_rules", [])),
            "do_not_change": booktime.get("do_not_change", card.get("do_not_change", [])),
            "notes": data.get("creator_notes", ""),
        }
    return dict(card)


def to_sillytavern_card(card):
    if isinstance(card, dict) and card.get("spec") == "chara_card_v2" and isinstance(card.get("data"), dict):
        return card
    flat = flatten_character(card)
    description_parts = []
    if flat.get("description"):
        description_parts.append(flat["description"])
    if flat.get("role"):
        description_parts.append(f"Role: {flat['role']}")
    if flat.get("relationships"):
        description_parts.append("Relationships: " + "; ".join(split_lines(flat.get("relationships"))))
    if flat.get("voice_rules"):
        description_parts.append("Voice rules: " + "; ".join(split_lines(flat.get("voice_rules"))))
    if flat.get("do_not_change"):
        description_parts.append("Do not change: " + "; ".join(split_lines(flat.get("do_not_change"))))
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": flat.get("name", ""),
            "description": "\n".join(description_parts).strip(),
            "personality": "\n".join(split_lines(flat.get("personality"))),
            "scenario": flat.get("scenario", ""),
            "first_mes": flat.get("first_mes", ""),
            "mes_example": flat.get("mes_example", ""),
            "creator_notes": flat.get("creator_notes") or flat.get("notes", ""),
            "system_prompt": flat.get("system_prompt", ""),
            "post_history_instructions": flat.get("post_history_instructions", ""),
            "alternate_greetings": [],
            "tags": split_lines(flat.get("tags")),
            "creator": flat.get("creator") or "Book Time",
            "character_version": flat.get("character_version") or "1.0",
            "extensions": {
                "booktime": {
                    "role": flat.get("role", ""),
                    "relationships": split_lines(flat.get("relationships")),
                    "voice_rules": split_lines(flat.get("voice_rules")),
                    "do_not_change": split_lines(flat.get("do_not_change"))
                }
            }
        }
    }


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_chunk(kind, data):
    kind_bytes = kind.encode("ascii")
    crc = zlib.crc32(kind_bytes + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind_bytes + data + struct.pack(">I", crc)


def split_png_chunks(png_bytes):
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise ValueError("Not a PNG file.")
    offset = len(PNG_SIGNATURE)
    chunks = []
    while offset + 8 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset:offset + 4])[0]
        kind = png_bytes[offset + 4:offset + 8].decode("ascii", errors="replace")
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        data = png_bytes[data_start:data_end]
        raw = png_bytes[offset:crc_end]
        chunks.append((kind, data, raw))
        offset = crc_end
        if kind == "IEND":
            break
    return chunks


def read_png_character_card(path):
    try:
        return read_png_character_card_bytes(Path(path).read_bytes())
    except Exception:
        return None


def read_png_character_card_bytes(png_bytes):
    for kind, data, _raw in split_png_chunks(png_bytes):
        if kind not in ("tEXt", "iTXt"):
            continue
        if b"\x00" not in data:
            continue
        keyword, value = data.split(b"\x00", 1)
        if keyword.decode("latin-1", errors="ignore").lower() != "chara":
            continue
        # iTXt can contain compression/language fields; for Book Time exports we use tEXt.
        payload = value.strip()
        try:
            decoded = base64.b64decode(payload)
            return json.loads(decoded.decode("utf-8"))
        except Exception:
            continue
    return None


def embed_png_character_card(png_bytes, card):
    chunks = split_png_chunks(png_bytes)
    card_json = json.dumps(to_sillytavern_card(card), ensure_ascii=False, separators=(",", ":"))
    payload = b"chara\x00" + base64.b64encode(card_json.encode("utf-8"))
    text_chunk = png_chunk("tEXt", payload)
    out = bytearray(PNG_SIGNATURE)
    inserted = False
    for kind, data, raw in chunks:
        if kind == "tEXt" and data.split(b"\x00", 1)[0].lower() == b"chara":
            continue
        if not inserted and kind != "IHDR":
            out.extend(text_chunk)
            inserted = True
        out.extend(raw)
    if not inserted:
        out.extend(text_chunk)
    return bytes(out)


def write_png_character_card(path, card):
    # Minimal transparent 1x1 PNG fallback if the user did not provide art.
    blank_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    write_text(Path(path).with_suffix(".note.txt"), "Generated placeholder PNG. Replace this with character art when available.\n")
    Path(path).write_bytes(embed_png_character_card(blank_png, card))


def copy_source_file(src, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
