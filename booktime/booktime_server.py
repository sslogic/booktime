#!/usr/bin/env python
import argparse
import json
import sys
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from booktime_bridge import call_ollama
from story_memory import (
    CONFIG_PATH,
    ROOT,
    custom_characters_path,
    list_characters,
    load_config,
    memory_root,
    read_text,
    save_config,
    seed_path,
    upsert_custom_character,
)


WEB_DIR = ROOT / "web"


def build_prompt(config, raw_prompt, seed_text, mode):
    seed_tail = seed_text[-30000:]
    return f"""You are Book Time, a prompt-preparation assistant for an LM Studio fiction-writing workflow.

Your job:
- Do not write the story.
- Do not continue the chapter yourself.
- Convert the user's form into a clean, copy-ready prompt for LM Studio.
- Use the latest continuity seed to orient the LM Studio story model.
- Preserve the user's intent, but make the instruction clear, structured, and hard to misread.
- Keep wording focused on continuity, syntax, character consistency, and where to continue.

Return only the final LM Studio prompt text. No explanation before or after.

Mode: {mode}
Book id: {config["book_id"]}
Latest continuity seed:
<<<SEED
{seed_tail}
SEED

User form:
<<<USER_FORM
{raw_prompt}
USER_FORM

The final prompt should contain these sections:
1. BOOK MEMORY CONTEXT
2. USER REQUEST
3. EXACT WRITING INSTRUCTION FOR LM STUDIO
4. CONTINUITY RULES
5. OUTPUT FORMAT
"""


def fallback_prepared_prompt(raw_prompt, seed_text):
    seed_tail = seed_text[-5000:].strip()
    return f"""BOOK MEMORY CONTEXT
Use the latest Book Time memory below to orient the story before writing:

{seed_tail}

USER REQUEST
{raw_prompt.strip()}

EXACT WRITING INSTRUCTION FOR LM STUDIO
Continue the active book from the current position in the memory context. Do not restart the chapter. Do not summarize. Write the next prose directly from the last usable sentence or fragment.

CONTINUITY RULES
Keep character personalities, relationships, timeline, location, unresolved threads, and prior corrections consistent with the Book Time memory. If the user's request conflicts with the memory, follow the user's latest correction while preserving everything else.

OUTPUT FORMAT
Return only valid JSON matching the requested schema. The actual prose goes in chapter_text."""


def compose_user_prompt(body):
    parts = []
    for key, title in (
        ("chapterRequest", "Chapter request"),
        ("premise", "Premise"),
        ("startingSituation", "Starting situation"),
        ("prompt", "Extra prompt"),
        ("sceneRequirements", "Scene Requirements"),
        ("wordBank", "Word Bank"),
        ("qualityRules", "Quality Rules"),
        ("styleSample", "Style Sample"),
        ("chapterLength", "Chapter Length"),
        ("outputFormat", "JSON Schema / Output Format"),
        ("finalRules", "Final Rules"),
    ):
        if body.get(key):
            parts.append(f"{title}:\n{body[key].strip()}")

    genres = body.get("selectedGenres") or []
    if genres:
        parts.insert(2, "Genre:\n" + ", ".join(str(g).strip() for g in genres if str(g).strip()))

    tones = body.get("selectedTones") or []
    if tones:
        parts.append("Tone/style:\n" + ", ".join(str(t).strip() for t in tones if str(t).strip()))

    selected = body.get("selectedCharacters") or []
    if selected:
        char_parts = ["Main character / selected characters:"]
        for card in selected:
            lines = [f"- {card.get('name', 'Unnamed')}"]
            if card.get("role"):
                lines.append(f"  Role: {card['role']}")
            for key, label in (
                ("personality", "Personality"),
                ("relationships", "Relationships"),
                ("voice_rules", "Voice rules"),
                ("do_not_change", "Do not change"),
            ):
                values = card.get(key) or []
                if values:
                    lines.append(f"  {label}: {'; '.join(values)}")
            if card.get("notes"):
                lines.append(f"  Notes: {card['notes']}")
            char_parts.append("\n".join(lines))
        parts.insert(3, "\n".join(char_parts))

    structure = body.get("chapterStructure") or {}
    if any(str(v or "").strip() for v in structure.values()):
        parts.append("Chapter Structure:\n" + "\n".join(
            f"- {label}: {structure.get(key, '').strip()}"
            for key, label in (
                ("opening", "Opening scene"),
                ("development", "Development scene"),
                ("complication", "Complication scene"),
                ("choice", "Choice scene"),
                ("closingHook", "Closing hook"),
            )
            if structure.get(key, "").strip()
        ))
    return "\n\n".join(parts).strip()


def build_structure_prompt(config, body, seed_text):
    seed_tail = seed_text[-12000:]
    raw = compose_user_prompt({k: v for k, v in body.items() if k != "chapterStructure"})
    return f"""You are Book Time, a planning helper for a fiction-writing workflow.

Return one valid JSON object only with these keys:
opening, development, complication, choice, closingHook

Each value should be one concise scene instruction for the LM Studio writer.
Do not write prose. Fill the chapter structure from the user's prompt and the latest memory.

Latest continuity seed:
<<<SEED
{seed_tail}
SEED

User form:
<<<FORM
{raw}
FORM
"""


class BookTimeHandler(BaseHTTPRequestHandler):
    server_version = "BookTime/2.0"

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        elif self.path == "/setup.html":
            self.send_file(WEB_DIR / "setup.html", "text/html; charset=utf-8")
        elif self.path == "/styles.css":
            self.send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        elif self.path == "/app.js":
            self.send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        elif self.path == "/setup.js":
            self.send_file(WEB_DIR / "setup.js", "application/javascript; charset=utf-8")
        elif self.path == "/api/config":
            self.handle_get_config()
        elif self.path == "/api/seed":
            self.handle_seed()
        elif self.path == "/api/characters":
            self.handle_characters()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/config":
            self.handle_save_config()
        elif self.path == "/api/prepare":
            self.handle_prepare()
        elif self.path == "/api/structure":
            self.handle_structure()
        elif self.path == "/api/characters":
            self.handle_save_character()
        else:
            self.send_error(404)

    def send_file(self, path, content_type):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def handle_get_config(self):
        config = load_config()
        root = memory_root(config)
        self.send_json(200, {
            "ok": True,
            "config": config,
            "configPath": str(CONFIG_PATH),
            "memoryRoot": str(root),
        })

    def handle_save_config(self):
        try:
            current = load_config()
            body = self.read_json_body()
            allowed = {
                "book_id", "lmstudio_conversations_dir", "lmstudio_user_files_dir",
                "ollama_url", "ollama_model", "memory_dir", "booktime_host",
                "booktime_port", "poll_seconds", "max_analysis_chars",
                "require_trigger_for_watch", "trigger_phrases",
            }
            for key, value in body.items():
                if key in allowed:
                    current[key] = value
            save_config(current)
            memory_root(current)
            self.send_json(200, {"ok": True, "config": current, "configPath": str(CONFIG_PATH)})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})

    def handle_seed(self):
        try:
            config = load_config()
            seed = read_text(seed_path(config))
            self.send_json(200, {"ok": True, "seed": seed, "path": str(seed_path(config))})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def handle_characters(self):
        try:
            config = load_config()
            self.send_json(200, {
                "ok": True,
                "characters": list_characters(config),
                "customPath": str(custom_characters_path(config)),
            })
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def handle_save_character(self):
        try:
            body = self.read_json_body()
            config = load_config()
            character = upsert_custom_character(body.get("character") or body, config)
            self.send_json(200, {
                "ok": True,
                "character": character,
                "characters": list_characters(config),
                "customPath": str(custom_characters_path(config)),
            })
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})

    def handle_prepare(self):
        try:
            body = self.read_json_body()
            config = load_config()
            raw_prompt = compose_user_prompt(body)
            if not raw_prompt:
                self.send_json(400, {"ok": False, "error": "Enter prompt details first."})
                return
            seed = read_text(seed_path(config))
            try:
                prepared = call_ollama(config, build_prompt(config, raw_prompt, seed, body.get("mode", "chapter-template")))
                if not prepared:
                    prepared = fallback_prepared_prompt(raw_prompt, seed)
            except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                prepared = fallback_prepared_prompt(raw_prompt, seed)
                self.send_json(200, {"ok": True, "preparedPrompt": prepared, "warning": f"Ollama failed, used fallback: {exc}"})
                return
            self.send_json(200, {"ok": True, "preparedPrompt": prepared})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def handle_structure(self):
        try:
            body = self.read_json_body()
            config = load_config()
            seed = read_text(seed_path(config))
            try:
                raw = call_ollama(config, build_structure_prompt(config, body, seed))
                start = raw.find("{")
                end = raw.rfind("}")
                if start == -1 or end == -1 or end <= start:
                    raise ValueError("Ollama did not return JSON.")
                structure = json.loads(raw[start:end + 1])
            except Exception as exc:
                structure = {
                    "opening": "Open with a concrete action tied to the user's premise.",
                    "development": "Develop the main character's immediate goal and pressure.",
                    "complication": "Introduce a problem that changes the scene direction.",
                    "choice": "Force the main character to make a meaningful choice.",
                    "closingHook": "End with a hook that changes the situation.",
                }
                self.send_json(200, {"ok": True, "structure": structure, "warning": f"Ollama structure fill failed, used fallback: {exc}"})
                return
            self.send_json(200, {"ok": True, "structure": structure})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    parser = argparse.ArgumentParser(description="Run the Book Time local web app.")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--open", action="store_true", help="Open Book Time in the default browser.")
    parser.add_argument("--setup", action="store_true", help="Open the setup page.")
    args = parser.parse_args()

    config = load_config()
    host = args.host or config.get("booktime_host", "127.0.0.1")
    port = args.port or int(config.get("booktime_port", 8765))
    memory_root(config)

    httpd = ThreadingHTTPServer((host, port), BookTimeHandler)
    url = f"http://{host}:{port}/"
    print(f"Book Time is running at {url}")
    if args.open:
        webbrowser.open(url + ("setup.html" if args.setup else ""))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Book Time stopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
