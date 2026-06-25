# LM Studio Presets For Book Time

These files are pre-setup material for LM Studio writing models.

Use them before a writing session:

1. Open LM Studio.
2. Load your writing model.
3. Create or edit a preset.
4. Copy the contents of `booktime-writer-system-prompt.md` into the model/system prompt area.
5. Keep `booktime-output-schema.json` nearby so the model knows the expected JSON shape.
6. If your LM Studio build supports importing preset JSON, try `booktime-writer.preset.json`.

Book Time also includes these preset paths in the prompt-preparation context so Ollama knows what LM Studio is supposed to follow.
