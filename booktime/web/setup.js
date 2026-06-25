const setupStatus = document.getElementById("setupStatus");
const ollamaUrl = document.getElementById("ollamaUrl");
const ollamaModel = document.getElementById("ollamaModel");
const lmstudioConversations = document.getElementById("lmstudioConversations");
const lmstudioUserFiles = document.getElementById("lmstudioUserFiles");
const memoryDir = document.getElementById("memoryDir");
const triggerPhrases = document.getElementById("triggerPhrases");
const setupFiles = document.getElementById("setupFiles");
const saveSetup = document.getElementById("saveSetup");
const reloadSetup = document.getElementById("reloadSetup");

function setStatus(text, cls) {
  setupStatus.textContent = text;
  setupStatus.className = cls || "";
}

async function loadSetup() {
  setStatus("Loading current settings...", "status-working");
  try {
    const response = await fetch("/api/config");
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Could not load config.", "status-error");
      return;
    }
    const config = data.config;
    ollamaUrl.value = config.ollama_url || "";
    ollamaModel.value = config.ollama_model || "";
    lmstudioConversations.value = config.lmstudio_conversations_dir || "";
    lmstudioUserFiles.value = config.lmstudio_user_files_dir || "";
    memoryDir.value = config.memory_dir || "story_memory";
    triggerPhrases.value = (config.trigger_phrases || []).join("\n");
    setupFiles.textContent = `Config: ${data.configPath}\nMemory: ${data.memoryRoot}`;
    setStatus("Setup loaded.", "status-ready");
  } catch (error) {
    setStatus(`Setup load failed: ${error}`, "status-error");
  }
}

async function save() {
  saveSetup.disabled = true;
  setStatus("Saving setup...", "status-working");
  try {
    const payload = {
      ollama_url: ollamaUrl.value.trim(),
      ollama_model: ollamaModel.value.trim(),
      lmstudio_conversations_dir: lmstudioConversations.value.trim(),
      lmstudio_user_files_dir: lmstudioUserFiles.value.trim(),
      memory_dir: memoryDir.value.trim() || "story_memory",
      trigger_phrases: triggerPhrases.value.split("\n").map((line) => line.trim()).filter(Boolean)
    };
    const response = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Could not save setup.", "status-error");
      return;
    }
    setStatus("Setup saved.", "status-ready");
    await loadSetup();
  } catch (error) {
    setStatus(`Setup save failed: ${error}`, "status-error");
  } finally {
    saveSetup.disabled = false;
  }
}

saveSetup.addEventListener("click", save);
reloadSetup.addEventListener("click", loadSetup);
loadSetup();
