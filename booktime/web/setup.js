const setupStatus = document.getElementById("setupStatus");
const ollamaUrl = document.getElementById("ollamaUrl");
const ollamaExe = document.getElementById("ollamaExe");
const ollamaModel = document.getElementById("ollamaModel");
const assistantModelDirs = document.getElementById("assistantModelDirs");
const ollamaTimeout = document.getElementById("ollamaTimeout");
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
const browseButtons = document.querySelectorAll(".browse-button");

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
    assistantModelDirs.value = (config.assistant_model_dirs || []).join("\n");
    ollamaTimeout.value = config.ollama_timeout_seconds || 45;
    lmstudioExe.value = config.lmstudio_exe_path || "";
    lmstudioConversations.value = config.lmstudio_conversations_dir || "";
    lmstudioUserFiles.value = config.lmstudio_user_files_dir || "";
    memoryDir.value = config.memory_dir || "story_memory";
    presetDir.value = config.lmstudio_preset_dir || "lmstudio_presets";
    triggerPhrases.value = (config.trigger_phrases || []).join("\n");
    setupFiles.textContent = `Config file: ${data.configPath}\nBook Time memory folder: ${data.memoryRoot}`;
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

function modelStatusLines(lmstudio) {
  const loaded = lmstudio.loadedModels || [];
  if (!loaded.length) {
    return [statusLine("LM Studio writing model", false, "No loaded LM Studio model found. Load the writing model in LM Studio.", "")];
  }
  return loaded.map((model) => {
    const download = model.download || {};
    const details = [model.model || model.identifier, model.status, model.size, model.context ? `${model.context} context` : ""].filter(Boolean).join(" | ");
    const command = download.ollama ? ` Ollama pull/run: ${download.ollama}` : "";
    return statusLine("LM Studio writing model", true, `${details}${command}`, download.url || "");
  });
}

function currentBrowseStart(target) {
  const value = target.value.trim();
  if (!value) {
    return "";
  }
  if (target.tagName === "TEXTAREA") {
    const lines = value.split("\n").map((line) => line.trim()).filter(Boolean);
    return lines[lines.length - 1] || "";
  }
  return value;
}

async function browseForPath(button) {
  const target = document.getElementById(button.dataset.target);
  if (!target) {
    return;
  }
  button.disabled = true;
  setStatus("Waiting for path selection...", "status-working");
  try {
    const response = await fetch("/api/browse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: button.dataset.mode || "dir",
        title: button.dataset.title || "Select path",
        initialDir: currentBrowseStart(target)
      })
    });
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Browse failed.", "status-error");
      return;
    }
    if (data.path) {
      if (button.dataset.append === "true") {
        const existing = target.value.split("\n").map((line) => line.trim()).filter(Boolean);
        if (!existing.includes(data.path)) {
          existing.push(data.path);
        }
        target.value = existing.join("\n");
      } else {
        target.value = data.path;
      }
      setStatus("Path selected. Save setup when ready.", "status-ready");
    } else {
      setStatus("Path selection cancelled.", "status-ready");
    }
  } catch (error) {
    setStatus(`Browse failed: ${error}`, "status-error");
  } finally {
    button.disabled = false;
  }
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
      ...modelStatusLines(lmstudio),
      statusLine("Book Time memory folder", !!booktime.seedExists, booktime.seedExists ? `Active memory folder: ${booktime.memoryRoot}` : `No seed yet. Active memory folder: ${booktime.memoryRoot}`, ""),
      statusLine("LM Studio presets", !!(booktime.presets && booktime.presets.files && booktime.presets.files.length), booktime.presets ? `Preset folder: ${booktime.presets.dir}` : "Preset folder not found.", ""),
      ...(booktime.localAssistantModels || []).map((entry) => {
        const message = `${entry.usable.length} usable GGUF, ${entry.projectors.length} projector, ${entry.partial.length} partial download in ${entry.dir}`;
        return statusLine("Local assistant files", entry.exists && entry.usable.length > 0, message, "");
      })
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
      assistant_model_dirs: assistantModelDirs.value.split("\n").map((line) => line.trim()).filter(Boolean),
      ollama_timeout_seconds: Number(ollamaTimeout.value || 45),
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
browseButtons.forEach((button) => {
  button.addEventListener("click", () => browseForPath(button));
});
loadSetup();
