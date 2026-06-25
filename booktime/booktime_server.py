#!/usr/bin/env python
import argparse
import json
import subprocess
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
    import_character_png,
    list_characters,
    load_config,
    memory_root,
    read_text,
    save_character_png,
    save_config,
    seed_path,
    upsert_custom_character,
)


WEB_DIR = ROOT / "web"


def preset_dir(config):
    raw = Path(config.get("lmstudio_preset_dir", "lmstudio_presets"))
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw


def preset_summary(config):
    path = preset_dir(config)
    files = []
    if path.exists():
        for item in sorted(path.glob("*")):
            if item.is_file():
                files.append(str(item))
    return {"dir": str(path), "files": files}


def local_assistant_model_summary(config):
    dirs = config.get("assistant_model_dirs", [])
    if isinstance(dirs, str):
        dirs = [dirs]
    results = []
    for raw in dirs:
        folder = Path(raw)
        entry = {"dir": str(folder), "exists": folder.exists(), "usable": [], "projectors": [], "partial": []}
        if folder.exists():
            for item in sorted(folder.glob("*.gguf*")):
                record = {"path": str(item), "name": item.name, "bytes": item.stat().st_size}
                lower = item.name.lower()
                if lower.endswith(".part"):
                    entry["partial"].append(record)
                elif lower.startswith("mmproj-"):
                    entry["projectors"].append(record)
                elif lower.endswith(".gguf"):
                    entry["usable"].append(record)
        results.append(entry)
    return results


def known_model_downloads():
    return {
        "gemma-the-writer-n-restless-quill-10b-uncensored": {
            "label": "Gemma The Writer N Restless Quill 10B Uncensored GGUF",
            "url": "https://huggingface.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF",
            "ollama": "ollama run hf.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF:Q4_K_M",
        },
        "qwen2.5-0.5b-instruct": {
            "label": "Qwen2.5 0.5B Instruct GGUF",
            "url": "https://huggingface.co/lmstudio-community/Qwen2.5-0.5B-Instruct-GGUF/tree/main",
            "ollama": "",
        },
    }


def parse_lms_ps(stdout):
    models = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("IDENTIFIER"):
            continue
        parts = [part.strip() for part in line.split("  ") if part.strip()]
        if len(parts) >= 2:
            downloads = known_model_downloads()
            item = {
                "identifier": parts[0],
                "model": parts[1],
                "status": parts[2] if len(parts) > 2 else "",
                "size": parts[3] if len(parts) > 3 else "",
                "context": parts[4] if len(parts) > 4 else "",
            }
            item["download"] = downloads.get(item["identifier"].lower()) or downloads.get(item["model"].lower()) or {}
            models.append(item)
    return models


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
LM Studio preset files:
{json.dumps(preset_summary(config), indent=2)}
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


def command_text(args, timeout=10):
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"Not found: {args[0]}"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "Timed out"}


def check_ollama(config):
    url = config.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
    model = config.get("ollama_model", "")
    result = {
        "url": url,
        "model": model,
        "running": False,
        "modelAvailable": False,
        "downloadUrl": "https://ollama.com/download",
        "message": "",
    }
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        result["running"] = True
        names = [item.get("name") for item in payload.get("models", [])]
        result["modelAvailable"] = model in names if model else False
        result["models"] = names
        if not model:
            result["message"] = "Ollama is running. Choose an assistant model in setup."
        elif result["modelAvailable"]:
            result["message"] = "Ollama is running."
        else:
            result["message"] = "Ollama is running, but the configured model is not listed."
    except Exception as exc:
        result["message"] = f"Ollama is not reachable: {exc}"
    return result


def check_lmstudio(config):
    exe = config.get("lmstudio_exe_path", "")
    conversations = config.get("lmstudio_conversations_dir", "")
    user_files = config.get("lmstudio_user_files_dir", "")
    server = command_text(["lms", "server", "status"], timeout=10)
    loaded = command_text(["lms", "ps"], timeout=10)
    return {
        "exePath": exe,
        "exeExists": Path(exe).exists() if exe else False,
        "downloadUrl": "https://lmstudio.ai/download",
        "conversationsDir": conversations,
        "conversationsDirExists": Path(conversations).exists() if conversations else False,
        "userFilesDir": user_files,
        "userFilesDirExists": Path(user_files).exists() if user_files else False,
        "serverStatus": server,
        "serverRunning": server["returncode"] == 0 and "not running" not in (server["stdout"] + server["stderr"]).lower(),
        "message": server["stdout"] or server["stderr"],
        "loadedModels": parse_lms_ps(loaded["stdout"]) if loaded["returncode"] == 0 else [],
        "loadedModelsRaw": loaded,
    }


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
        elif self.path == "/api/status":
            self.handle_status()
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
        elif self.path == "/api/characters/import-png":
            self.handle_import_character_png()
        elif self.path == "/api/lmstudio/install-presets":
            self.handle_install_lmstudio_presets()
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

    def handle_status(self):
        config = load_config()
        status = {
            "ok": True,
            "ollama": check_ollama(config),
            "lmstudio": check_lmstudio(config),
            "booktime": {
                "memoryRoot": str(memory_root(config)),
                "seedExists": seed_path(config).exists(),
                "configPath": str(CONFIG_PATH),
                "presets": preset_summary(config),
                "localAssistantModels": local_assistant_model_summary(config),
            },
        }
        self.send_json(200, status)

    def handle_save_config(self):
        try:
            current = load_config()
            body = self.read_json_body()
            allowed = {
                "book_id", "lmstudio_conversations_dir", "lmstudio_user_files_dir",
                "lmstudio_exe_path", "ollama_exe_path", "ollama_url", "ollama_model", "assistant_model_dirs", "memory_dir", "booktime_host",
                "booktime_port", "lmstudio_preset_dir", "ollama_timeout_seconds", "poll_seconds", "max_analysis_chars",
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
            raw_character = body.get("character") or body
            character = upsert_custom_character(raw_character, config)
            png_path = None
            if body.get("pngBase64"):
                png_path = save_character_png(raw_character, body["pngBase64"], config)
            self.send_json(200, {
                "ok": True,
                "character": character,
                "characters": list_characters(config),
                "pngPath": png_path,
                "customPath": str(custom_characters_path(config)),
            })
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})

    def handle_import_character_png(self):
        try:
            body = self.read_json_body()
            filename = body.get("filename") or "character.png"
            data = body.get("pngBase64") or ""
            if "," in data:
                data = data.split(",", 1)[1]
            import base64
            character = import_character_png(filename, base64.b64decode(data), load_config())
            self.send_json(200, {"ok": True, "character": character, "characters": list_characters(load_config())})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})

    def handle_install_lmstudio_presets(self):
        try:
            config = load_config()
            lm_root = Path(config.get("lmstudio_conversations_dir", "")).parent
            if not lm_root.exists():
                raise RuntimeError("LM Studio folder was not found. Set LM Studio paths first.")
            config_presets = lm_root / "config-presets"
            user_files = lm_root / "user-files"
            config_presets.mkdir(parents=True, exist_ok=True)
            user_files.mkdir(parents=True, exist_ok=True)

            src_dir = preset_dir(config)
            preset_src = src_dir / "booktime-writer.preset.json"
            prompt_src = src_dir / "booktime-writer-system-prompt.md"
            schema_src = src_dir / "booktime-output-schema.json"
            for src in (preset_src, prompt_src, schema_src):
                if not src.exists():
                    raise RuntimeError(f"Missing preset source file: {src}")

            installed = []
            preset_dest = config_presets / "booktime-writer.preset.json"
            prompt_dest = user_files / "booktime-writer-system-prompt.md"
            schema_dest = user_files / "booktime-output-schema.json"
            preset_dest.write_text(preset_src.read_text(encoding="utf-8"), encoding="utf-8")
            prompt_dest.write_text(prompt_src.read_text(encoding="utf-8"), encoding="utf-8")
            schema_dest.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
            installed.extend([str(preset_dest), str(prompt_dest), str(schema_dest)])
            self.send_json(200, {"ok": True, "installed": installed, "message": "Installed Book Time preset files into LM Studio. Restart LM Studio if the preset does not appear immediately."})
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
