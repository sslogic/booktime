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
- Ollama model, for example `aitraining-odysseus-storyteller-file:latest`
- LM Studio conversations folder, usually `C:\Users\<you>\.lmstudio\conversations`
- LM Studio user files folder, usually `C:\Users\<you>\.lmstudio\user-files`
- Book Time local memory folder, default `story_memory`
- trigger phrases that activate the watcher

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
