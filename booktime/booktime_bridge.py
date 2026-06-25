#!/usr/bin/env python
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from story_memory import (
    append_jsonl,
    continuity_path,
    copy_source_file,
    load_config,
    load_json,
    manifest_path,
    memory_root,
    save_json,
    seed_path,
    write_text,
)


ROOT = Path(__file__).resolve().parent


def state_path(config):
    return memory_root(config) / ".booktime_state.json"


def safe_slug(text, fallback="conversation"):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip()).strip("-")
    return cleaned[:80] or fallback


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def newest_conversation(conversations_dir):
    files = sorted(Path(conversations_dir).glob("*.conversation.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No .conversation.json files found in {conversations_dir}")
    return files[0]


def extract_text_nodes(value):
    chunks = []
    if isinstance(value, dict):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            chunks.append(value["text"])
        for child in value.values():
            chunks.extend(extract_text_nodes(child))
    elif isinstance(value, list):
        for item in value:
            chunks.extend(extract_text_nodes(item))
    return chunks


def extract_file_refs(value):
    refs = []
    if isinstance(value, dict):
        identifier = value.get("fileIdentifier") or value.get("identifier")
        if identifier and isinstance(identifier, str):
            refs.append({
                "identifier": identifier,
                "name": value.get("name") or value.get("fileName") or identifier,
                "file_type": value.get("fileType") or value.get("type") or "",
                "size_bytes": value.get("sizeBytes"),
            })
        for child in value.values():
            refs.extend(extract_file_refs(child))
    elif isinstance(value, list):
        for item in value:
            refs.extend(extract_file_refs(item))
    return refs


def selected_version(message):
    versions = message.get("versions") or []
    if not versions:
        return None
    selected = message.get("currentlySelected", 0)
    if not isinstance(selected, int) or selected < 0 or selected >= len(versions):
        selected = 0
    return versions[selected]


def step_text(step):
    if step.get("type") != "contentBlock":
        return []
    return extract_text_nodes(step.get("content", []))


def parse_conversation(path, user_files_dir):
    data = load_json(path)
    turns = []
    file_refs = []
    for index, message in enumerate(data.get("messages", []), start=1):
        version = selected_version(message)
        if not version:
            continue
        role = version.get("role", "unknown")
        texts = []
        if version.get("type") == "multiStep":
            for step in version.get("steps", []):
                texts.extend(step_text(step))
        else:
            texts.extend(extract_text_nodes(version.get("content", [])))
        file_refs.extend(extract_file_refs(version.get("content", [])))
        content = "\n\n".join(t.strip() for t in texts if t and t.strip())
        if content:
            turns.append({"index": index, "role": role, "content": content})

    seen = set()
    resolved_files = []
    for ref in file_refs:
        identifier = ref["identifier"]
        if identifier in seen:
            continue
        seen.add(identifier)
        local_path = Path(user_files_dir) / identifier
        if local_path.exists():
            resolved_files.append({**ref, "local_path": str(local_path)})

    return {
        "id": path.stem.replace(".conversation", ""),
        "name": data.get("name") or path.stem,
        "path": str(path),
        "turns": turns,
        "files": resolved_files,
    }


def render_transcript(conversation):
    lines = [
        f"# {conversation['name']}",
        "",
        f"- Conversation id: `{conversation['id']}`",
        f"- Source: `{conversation['path']}`",
        f"- Synced: `{utc_now()}`",
        "",
    ]
    if conversation["files"]:
        lines.append("## Attached Source Files")
        lines.append("")
        for f in conversation["files"]:
            lines.append(f"- `{f['identifier']}` from `{f['local_path']}`")
        lines.append("")

    for turn in conversation["turns"]:
        lines.append(f"## {turn['role'].title()} Turn {turn['index']}")
        lines.append("")
        lines.append(turn["content"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def normalize_trigger_text(text):
    text = text.lower().replace("'", "")
    return re.sub(r"\s+", " ", text).strip()


def conversation_has_trigger(conversation, trigger_phrases):
    haystack = normalize_trigger_text("\n".join(
        turn["content"] for turn in conversation["turns"] if turn["role"] == "user"
    ))
    return any(normalize_trigger_text(phrase) in haystack for phrase in trigger_phrases)


def should_sync_in_watch(config, conversation, state):
    if not config.get("require_trigger_for_watch", False):
        return True, "trigger not required"
    active = set(state.get("active_conversation_ids", []))
    if conversation["id"] in active:
        return True, "conversation already triggered"
    if conversation_has_trigger(conversation, config.get("trigger_phrases", [])):
        active.add(conversation["id"])
        state["active_conversation_ids"] = sorted(active)
        return True, "trigger phrase detected"
    return False, "waiting for trigger phrase"


def call_ollama(config, prompt):
    body = {
        "model": config["ollama_model"],
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }
    req = urllib.request.Request(
        config["ollama_url"].rstrip("/") + "/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=int(config.get("ollama_timeout_seconds", 120))) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("response", "").strip()


def extract_json_object(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Ollama response did not contain a JSON object")
    return json.loads(text[start:end + 1])


def build_analysis_prompt(conversation, transcript, config):
    analysis_text = transcript[-int(config.get("max_analysis_chars", 60000)):]
    return f"""You are a continuity archivist for a fiction-writing workflow.

Your job is not to continue the story. Preserve continuity for the next writing session.
Return one valid JSON object only. Keep the language continuity-focused.

Schema keys:
book_id, conversation_name, current_position, last_usable_sentence_or_fragment,
continuity_summary, character_cards, open_threads, style_rules, avoid, next_session_instruction

Book id: {config["book_id"]}
Conversation name: {conversation["name"]}

Transcript tail:
<<<TRANSCRIPT
{analysis_text}
TRANSCRIPT
"""


def fallback_analysis(config, conversation, transcript, error):
    last_line = ""
    for line in reversed(transcript[-4000:].splitlines()):
        if line.strip() and not line.startswith("#"):
            last_line = line.strip()
            break
    return {
        "book_id": config.get("book_id", "booktime"),
        "conversation_name": conversation["name"],
        "current_position": "Ollama analysis was unavailable; use the exact transcript snapshot for continuity.",
        "last_usable_sentence_or_fragment": last_line[:1000],
        "continuity_summary": ["Exact transcript was archived, but structured continuity analysis did not complete."],
        "character_cards": [],
        "open_threads": [],
        "style_rules": ["Continue from the exact last usable sentence in the archived transcript."],
        "avoid": ["Do not restart the chapter."],
        "next_session_instruction": "Read the archived transcript and continue from the exact last usable sentence without restarting the chapter.",
        "analysis_error": str(error),
    }


def render_seed(analysis, transcript_path, source_paths):
    lines = [
        "# LM Studio Continuation Seed",
        "",
        "Use this as the first message/context note in the next LM Studio session.",
        "",
        f"Archived exact transcript: `{transcript_path}`",
    ]
    if source_paths:
        lines.append("")
        lines.append("Archived exact source files:")
        for path in source_paths:
            lines.append(f"- `{path}`")
    lines.extend([
        "",
        "## Continue From",
        "",
        analysis.get("last_usable_sentence_or_fragment", "").strip(),
        "",
        "## Current Position",
        "",
        analysis.get("current_position", "").strip(),
        "",
        "## Continuity",
        "",
    ])
    for item in analysis.get("continuity_summary", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Character Cards", ""])
    for card in analysis.get("character_cards", []):
        lines.append(f"### {card.get('name', 'Unnamed')}")
        lines.append(f"- Role: {card.get('role', '')}")
        for key in ("personality", "relationships", "voice_rules", "do_not_change"):
            values = card.get(key) or []
            if values:
                lines.append(f"- {key.replace('_', ' ').title()}: {'; '.join(values)}")
        lines.append("")
    lines.extend(["## Open Threads", ""])
    for item in analysis.get("open_threads", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Style Rules", ""])
    for item in analysis.get("style_rules", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Avoid", ""])
    for item in analysis.get("avoid", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Instruction For Story Model", "", analysis.get("next_session_instruction", "").strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def sync_once(config, conversation_path=None, watch_mode=False):
    conv_path = Path(conversation_path) if conversation_path else newest_conversation(config["lmstudio_conversations_dir"])
    conversation = parse_conversation(conv_path, config["lmstudio_user_files_dir"])
    transcript = render_transcript(conversation)
    transcript_hash = sha256_text(transcript)

    state_file = state_path(config)
    state = load_json(state_file, default={}) or {}
    if watch_mode:
        allowed, reason = should_sync_in_watch(config, conversation, state)
        if not allowed:
            save_json(state_file, state)
            print(f"Idle: {conversation['name']} ({reason})")
            return False
        if reason == "trigger phrase detected":
            save_json(state_file, state)
            print(f"Book Time hook started: {conversation['name']}")

    prior_hash = state.get("conversation_hashes", {}).get(str(conv_path))
    if prior_hash == transcript_hash:
        print(f"No changes: {conv_path}")
        return False

    root = memory_root(config)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = safe_slug(conversation["name"], conversation["id"])
    transcript_path = root / "transcripts" / f"{stamp}-{conversation['id']}-{slug}.md"
    write_text(transcript_path, transcript)

    source_paths = []
    for src in conversation["files"]:
        local_path = Path(src["local_path"])
        dest = root / "source-files" / conversation["id"] / safe_slug(src["identifier"])
        copy_source_file(local_path, dest)
        source_paths.append(str(dest))

    try:
        raw = call_ollama(config, build_analysis_prompt(conversation, transcript, config))
        analysis = extract_json_object(raw)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        analysis = fallback_analysis(config, conversation, transcript, exc)

    analysis["book_id"] = config.get("book_id", "booktime")
    analysis["conversation_name"] = conversation["name"]
    analysis["updated_at"] = utc_now()
    analysis["transcript_path"] = str(transcript_path)
    analysis["source_file_paths"] = source_paths

    write_text(continuity_path(config), json.dumps(analysis, indent=2, ensure_ascii=False) + "\n")
    write_text(seed_path(config), render_seed(analysis, str(transcript_path), source_paths))
    append_jsonl(manifest_path(config), {
        "synced_at": utc_now(),
        "book_id": config.get("book_id", "booktime"),
        "conversation": conversation["name"],
        "conversation_path": str(conv_path),
        "transcript_sha256": transcript_hash,
        "transcript_path": str(transcript_path),
        "seed_path": str(seed_path(config)),
        "source_file_count": len(source_paths),
    })

    state.setdefault("conversation_hashes", {})[str(conv_path)] = transcript_hash
    state["last_sync"] = utc_now()
    state["last_conversation_path"] = str(conv_path)
    state["last_transcript_path"] = str(transcript_path)
    state["last_seed_path"] = str(seed_path(config))
    save_json(state_file, state)
    print(f"Synced: {conversation['name']}")
    print(f"Transcript: {transcript_path}")
    print(f"Seed: {seed_path(config)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Archive LM Studio book sessions to local Book Time memory.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Sync once and exit.")
    mode.add_argument("--watch", action="store_true", help="Watch the newest LM Studio conversation.")
    parser.add_argument("--conversation", help="Specific .conversation.json file to sync.")
    args = parser.parse_args()

    config = load_config()
    if args.once:
        sync_once(config, args.conversation)
        return 0

    print("Watching LM Studio conversations. Press Ctrl+C to stop.")
    while True:
        try:
            sync_once(config, args.conversation, watch_mode=True)
        except KeyboardInterrupt:
            print("Stopped.")
            return 0
        except Exception as exc:
            print(f"Sync failed: {exc}")
        time.sleep(int(config.get("poll_seconds", 10)))


if __name__ == "__main__":
    raise SystemExit(main())
