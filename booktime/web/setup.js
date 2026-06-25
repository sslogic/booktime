const setupStatus = document.getElementById("setupStatus");
const ollamaUrl = document.getElementById("ollamaUrl");
const ollamaExe = document.getElementById("ollamaExe");
const ollamaModel = document.getElementById("ollamaModel");
const lmstudioExe = document.getElementById("lmstudioExe");
const lmstudioConversations = document.getElementById("lmstudioConversations");
const lmstudioUserFiles = document.getElementById("lmstudioUserFiles");
const memoryDir = document.getElementById("memoryDir");
const presetDir = document.getElementById("presetDir");
const triggerPhrases = document.getElementById("triggerPhrases");
const setupFiles = document.getElementById("setupFiles");
const saveSetup = document.getElementById("saveSetup");
const reloadSetup = document.getElementById("reloadSetup");
const checkStatus = document.getElementById("checkStatus");
const runtimeStatus = document.getElementById("runtimeStatus");
const installPresets = document.getElementById("installPresets");

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
    ollamaExe.value = config.ollama_exe_path || "";
    ollamaModel.value = config.ollama_model || "";
    lmstudioExe.value = config.lmstudio_exe_path || "";
    lmstudioConversations.value = config.lmstudio_conversations_dir || "";
    lmstudioUserFiles.value = config.lmstudio_user_files_dir || "";
    memoryDir.value = config.memory_dir || "story_memory";
    presetDir.value = config.lmstudio_preset_dir || "lmstudio_presets";
    triggerPhrases.value = (config.trigger_phrases || []).join("\n");
    setupFiles.textContent = `Config: ${data.configPath}\nMemory: ${data.memoryRoot}`;
    setStatus("Setup loaded.", "status-ready");
    await loadStatus();
  } catch (error) {
    setStatus(`Setup load failed: ${error}`, "status-error");
  }
}

function statusLine(label, ok, message, url) {
  const link = url ? ` <a href="${url}" target="_blank" rel="noreferrer">Download</a>` : "";
  return `<div class="${ok ? "status-card ok" : "status-card warn"}"><strong>${label}</strong><span>${message}${link}</span></div>`;
}

async function loadStatus() {
  runtimeStatus.innerHTML = "<div class=\"status-card\">Checking runtime status...</div>";
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    const ollama = data.ollama || {};
    const lmstudio = data.lmstudio || {};
    const booktime = data.booktime || {};
    runtimeStatus.innerHTML = [
      statusLine("Ollama", !!ollama.running, ollama.message || "Not checked.", ollama.running ? "" : ollama.downloadUrl),
      statusLine("Ollama model", !!ollama.modelAvailable, ollama.modelAvailable ? `Model ready: ${ollama.model}` : `Load or pull model: ${ollama.model || "not set"}`, ""),
      statusLine("LM Studio", !!lmstudio.exeExists, lmstudio.exeExists ? `Found: ${lmstudio.exePath}` : "LM Studio is not installed or path is not set.", lmstudio.exeExists ? "" : lmstudio.downloadUrl),
      statusLine("LM Studio server", !!lmstudio.serverRunning, lmstudio.serverRunning ? "Server is running." : "Start/load your LM Studio writing model if needed.", ""),
      statusLine("Book Time memory", !!booktime.seedExists, booktime.seedExists ? `Seed exists in ${booktime.memoryRoot}` : `No seed yet in ${booktime.memoryRoot}. Run the watcher or one-time sync.`, ""),
      statusLine("LM Studio presets", !!(booktime.presets && booktime.presets.files && booktime.presets.files.length), booktime.presets ? `Preset folder: ${booktime.presets.dir}` : "Preset folder not found.", "")
    ].join("");
  } catch (error) {
    runtimeStatus.innerHTML = statusLine("Status", false, `Could not check status: ${error}`, "");
  }
}

async function save() {
  saveSetup.disabled = true;
  setStatus("Saving setup...", "status-working");
  try {
    const payload = {
      ollama_url: ollamaUrl.value.trim(),
      ollama_exe_path: ollamaExe.value.trim(),
      ollama_model: ollamaModel.value.trim(),
      lmstudio_exe_path: lmstudioExe.value.trim(),
      lmstudio_conversations_dir: lmstudioConversations.value.trim(),
      lmstudio_user_files_dir: lmstudioUserFiles.value.trim(),
      memory_dir: memoryDir.value.trim() || "story_memory",
      lmstudio_preset_dir: presetDir.value.trim() || "lmstudio_presets",
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

async function installLmStudioPresets() {
  installPresets.disabled = true;
  setStatus("Installing Book Time files into LM Studio...", "status-working");
  try {
    const response = await fetch("/api/lmstudio/install-presets", { method: "POST" });
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Could not install LM Studio presets.", "status-error");
      return;
    }
    setupFiles.textContent = `Installed:\n${(data.installed || []).join("\n")}`;
    setStatus(data.message || "LM Studio presets installed.", "status-ready");
    await loadStatus();
  } catch (error) {
    setStatus(`Preset install failed: ${error}`, "status-error");
  } finally {
    installPresets.disabled = false;
  }
}

saveSetup.addEventListener("click", save);
reloadSetup.addEventListener("click", loadSetup);
checkStatus.addEventListener("click", loadStatus);
installPresets.addEventListener("click", installLmStudioPresets);
loadSetup();
