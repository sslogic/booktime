import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "booktime_config.json"


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
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
    return config


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
    if isinstance(data, dict):
        return data.get("characters", [])
    return data if isinstance(data, list) else []


def save_custom_characters(characters, config=None):
    cfg = config or load_config()
    save_json(custom_characters_path(cfg), {"book_id": cfg.get("book_id", "booktime"), "characters": characters})


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
            name = (card.get("name") or "").strip()
            if not name:
                continue
            merged[normalize_name(name)] = {**card, "source": source}
    return sorted(merged.values(), key=lambda c: c.get("name", "").lower())


def upsert_custom_character(card, config=None):
    cfg = config or load_config()
    name = (card.get("name") or "").strip()
    if not name:
        raise ValueError("Character name is required.")
    clean = {
        "name": name,
        "role": (card.get("role") or "").strip(),
        "personality": split_lines(card.get("personality")),
        "relationships": split_lines(card.get("relationships")),
        "voice_rules": split_lines(card.get("voice_rules")),
        "do_not_change": split_lines(card.get("do_not_change")),
        "notes": (card.get("notes") or "").strip(),
    }
    existing = load_custom_characters(cfg)
    key = normalize_name(name)
    kept = [c for c in existing if normalize_name(c.get("name")) != key]
    kept.append(clean)
    kept.sort(key=lambda c: c.get("name", "").lower())
    save_custom_characters(kept, cfg)
    return clean


def copy_source_file(src, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
