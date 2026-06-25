# Book Time

Book Time is a local LM Studio book-writing helper. It keeps story memory on this machine, prepares copy-ready LM Studio prompts, and provides a small local MCP-style server for story memory.

It no longer uses the Oracle server as the story memory backend. Story data lives inside this package folder by default:

```text
booktime/story_memory
```

## Start

Run the web app:

```bat
start_booktime.bat
```

On a fresh clone, run setup before writing. Book Time does not ship with your machine-specific model paths or hard-coded local model names.

This is the normal launcher. It attempts to:

1. start Ollama
2. start LM Studio
3. start the LM Studio local server with `lms server start`
4. start the Book Time web server
5. open the Book Time page in your browser

Create Desktop and Start Menu shortcuts:

```powershell
powershell.exe -ExecutionPolicy Bypass -File install_booktime_shortcuts.ps1
```

Remove Desktop and Start Menu shortcuts:

```powershell
powershell.exe -ExecutionPolicy Bypass -File uninstall_booktime_shortcuts.ps1
```

Optional uninstall flags:

```powershell
powershell.exe -ExecutionPolicy Bypass -File uninstall_booktime_shortcuts.ps1 -StopServer
powershell.exe -ExecutionPolicy Bypass -File uninstall_booktime_shortcuts.ps1 -RemoveLmStudioPresets
powershell.exe -ExecutionPolicy Bypass -File uninstall_booktime_shortcuts.ps1 -RemoveStoryData
```

`-RemoveStoryData` only removes story data when the configured storage location is inside the Book Time folder.

Open setup directly:

```bat
start_booktime_setup.bat
```

Run the LM Studio watcher:

```bat
start_booktime_bridge.bat
```

Default URL:

```text
http://127.0.0.1:8765/
```

Setup page:

```text
http://127.0.0.1:8765/setup.html
```

## Setup

Use the setup page to configure:

- Ollama URL, for example `http://127.0.0.1:11434`
- Ollama executable, for example `C:\Users\<you>\AppData\Local\Programs\Ollama\ollama.exe`
- Ollama assistant model for Book Time prompt-prep, chosen from models installed in your local Ollama
- Local assistant model folders for status reporting when you have GGUF files to import into Ollama or LM Studio
- Ollama prompt timeout, default `45` seconds so the web page falls back instead of hanging on a slow local model
- LM Studio executable, for example `C:\Users\<you>\AppData\Local\Programs\LM Studio\LM Studio.exe`
- LM Studio conversations folder, usually `C:\Users\<you>\.lmstudio\conversations`
- LM Studio user files folder, usually `C:\Users\<you>\.lmstudio\user-files`
- Story and character data storage location, default `story_memory`
- trigger phrases that activate the watcher

The setup page has `Browse` buttons for executable and folder paths. They open a local Windows picker and write the selected full path into the setup field.

Download links shown on the setup page:

- Ollama: `https://ollama.com/download`
- LM Studio: `https://lmstudio.ai/download`
- LM Studio writing model you are using: `https://huggingface.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF`
- Small Book Time assistant model option: `https://huggingface.co/lmstudio-community/Qwen2.5-0.5B-Instruct-GGUF/tree/main`

If you have a local GGUF you want to use as the Book Time assistant, import it into Ollama first, then select the resulting Ollama model name in setup.

When LM Studio is running, the setup page also checks `lms ps` and shows the currently loaded writing model. If it sees `gemma-the-writer-n-restless-quill-10b-uncensored`, it shows the matching Hugging Face download link and this optional Ollama command:

```powershell
ollama run hf.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF:Q4_K_M
```

That storage location contains transcripts, source files, `latest_seed.md`, `continuity.json`, and `custom_characters.json`.

Config is saved in:

```text
booktime/booktime_config.json
```

## What It Stores

Book Time stores exact transcripts and memory files locally:

```text
booktime/story_memory/transcripts
booktime/story_memory/source-files
booktime/story_memory/memory/continuity.json
booktime/story_memory/memory/latest_seed.md
booktime/story_memory/memory/custom_characters.json
booktime/story_memory/manifest.jsonl
```

The exact story text is stored in `transcripts` and `source-files`. Ollama summaries, character cards, and continuation seed text live under `memory`.

## Book Time Web Form

The webpage is a form-based chapter prompt creator with:

- Premise
- genre dropdown plus custom genre box
- selected genre chips
- main character dropdown from saved cards
- New Character popup
- starting situation filled from local memory
- tone/style dropdown plus custom tone box
- persistent word bank
- style sample
- scene requirements
- quality rules
- chapter length
- AI-filled chapter structure
- JSON schema and final rules

Characters created in the popup are saved as SillyTavern-compatible Character Card V2 JSON (`spec: chara_card_v2`, `spec_version: 2.0`) so they can be reused outside Book Time. Individual character files are written to:

```text
booktime/story_memory/characters
```

If you choose a PNG in the character popup, Book Time embeds the character JSON into the PNG using the TavernAI/SillyTavern `chara` tEXt metadata convention. Existing PNG cards with embedded `chara` metadata can also be imported through the character API.

`Fill Structure` asks Ollama to fill the opening, development, complication, choice, and closing hook fields.

`Make LM Studio Prompt` asks Ollama to turn the completed form and latest story memory into a copy-ready LM Studio prompt.

## Local Story MCP

Book Time includes a local MCP-style stdio server:

```text
booktime/story_mcp_server.py
```

It exposes:

- `booktime_get_seed`
- `booktime_list_characters`
- `booktime_save_character`

Point an MCP client at:

```bat
python C:\path\to\booktime\story_mcp_server.py
```

## LM Studio Preset Files

Book Time includes pre-setup files for LM Studio writing models:

```text
booktime/lmstudio_presets/booktime-writer-system-prompt.md
booktime/lmstudio_presets/booktime-output-schema.json
booktime/lmstudio_presets/booktime-writer.preset.json
```

The setup page has an `Install LM Studio Presets` button. It writes:

```text
C:\Users\<you>\.lmstudio\config-presets\booktime-writer.preset.json
C:\Users\<you>\.lmstudio\user-files\booktime-writer-system-prompt.md
C:\Users\<you>\.lmstudio\user-files\booktime-output-schema.json
```

Restart LM Studio if the preset does not appear immediately.

## Files

```text
booktime_server.py          local web app and API
booktime_bridge.py          watches LM Studio and writes local story memory
story_memory.py             shared local memory/config helpers
story_mcp_server.py         local MCP-style story memory server
booktime_config.json        editable setup/config file
start_booktime.bat          starts the web app
start_booktime_setup.bat    starts the web app and opens setup
start_booktime_bridge.bat   starts the LM Studio watcher
web/index.html              main form page
web/setup.html              setup page
web/app.js                  main page browser logic
web/setup.js                setup page browser logic
web/styles.css              shared styling
```
