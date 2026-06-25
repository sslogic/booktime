const seedStatus = document.getElementById("seedStatus");
const refreshSeed = document.getElementById("refreshSeed");
const fillStructure = document.getElementById("fillStructure");
const chapterRequest = document.getElementById("chapterRequest");
const premise = document.getElementById("premise");
const genreSelect = document.getElementById("genreSelect");
const newGenre = document.getElementById("newGenre");
const addGenre = document.getElementById("addGenre");
const selectedGenres = document.getElementById("selectedGenres");
const characterSelect = document.getElementById("characterSelect");
const addSelectedCharacter = document.getElementById("addSelectedCharacter");
const selectedCharacters = document.getElementById("selectedCharacters");
const startingSituation = document.getElementById("startingSituation");
const toneSelect = document.getElementById("toneSelect");
const newTone = document.getElementById("newTone");
const addTone = document.getElementById("addTone");
const selectedTones = document.getElementById("selectedTones");
const rawPrompt = document.getElementById("rawPrompt");
const wordBank = document.getElementById("wordBank");
const styleSample = document.getElementById("styleSample");
const sceneRequirements = document.getElementById("sceneRequirements");
const qualityRules = document.getElementById("qualityRules");
const chapterLength = document.getElementById("chapterLength");
const openingScene = document.getElementById("openingScene");
const developmentScene = document.getElementById("developmentScene");
const complicationScene = document.getElementById("complicationScene");
const choiceScene = document.getElementById("choiceScene");
const closingHook = document.getElementById("closingHook");
const outputFormat = document.getElementById("outputFormat");
const finalRules = document.getElementById("finalRules");
const preparedPrompt = document.getElementById("preparedPrompt");
const preparePrompt = document.getElementById("preparePrompt");
const copyPrompt = document.getElementById("copyPrompt");
const openCharacterModal = document.getElementById("openCharacterModal");
const characterModal = document.getElementById("characterModal");
const closeCharacterModal = document.getElementById("closeCharacterModal");
const cancelCharacter = document.getElementById("cancelCharacter");
const saveCharacter = document.getElementById("saveCharacter");
const characterName = document.getElementById("characterName");
const characterRole = document.getElementById("characterRole");
const characterPersonality = document.getElementById("characterPersonality");
const characterRelationships = document.getElementById("characterRelationships");
const characterVoice = document.getElementById("characterVoice");
const characterCanon = document.getElementById("characterCanon");
const characterNotes = document.getElementById("characterNotes");

let allCharacters = [];
let pickedCharacters = [];
let pickedGenres = JSON.parse(localStorage.getItem("bookTimeGenres") || "[]");
let pickedTones = JSON.parse(localStorage.getItem("bookTimeTones") || "[]");
wordBank.value = localStorage.getItem("bookTimeWordBank") || "";

function setStatus(text, cls) {
  seedStatus.textContent = text;
  seedStatus.className = cls || "";
}

function key(text) {
  return (text || "").trim().toLowerCase();
}

function renderTextChips(container, values, onRemove) {
  container.innerHTML = "";
  for (const value of values) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.append(document.createTextNode(value));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "X";
    remove.addEventListener("click", () => onRemove(value));
    chip.appendChild(remove);
    container.appendChild(chip);
  }
}

function savePersistentLists() {
  localStorage.setItem("bookTimeGenres", JSON.stringify(pickedGenres));
  localStorage.setItem("bookTimeTones", JSON.stringify(pickedTones));
  localStorage.setItem("bookTimeWordBank", wordBank.value);
}

function addTextChoice(select, input, list, renderer) {
  const value = (input.value || select.value || "").trim();
  if (!value) return;
  if (!list.some((item) => key(item) === key(value))) {
    list.push(value);
    list.sort((a, b) => a.localeCompare(b));
  }
  input.value = "";
  select.value = "";
  renderer();
  savePersistentLists();
}

function renderGenres() {
  renderTextChips(selectedGenres, pickedGenres, (value) => {
    pickedGenres = pickedGenres.filter((item) => key(item) !== key(value));
    renderGenres();
    savePersistentLists();
  });
}

function renderTones() {
  renderTextChips(selectedTones, pickedTones, (value) => {
    pickedTones = pickedTones.filter((item) => key(item) !== key(value));
    renderTones();
    savePersistentLists();
  });
}

function characterKey(card) {
  return key(card.name);
}

function renderCharacterOptions() {
  characterSelect.innerHTML = "";
  if (!allCharacters.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No characters yet";
    characterSelect.appendChild(option);
    return;
  }
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select previous character";
  characterSelect.appendChild(placeholder);
  for (const card of allCharacters) {
    const option = document.createElement("option");
    option.value = characterKey(card);
    option.textContent = `${card.name}${card.source === "custom" ? " (custom)" : ""}`;
    characterSelect.appendChild(option);
  }
}

function renderPickedCharacters() {
  selectedCharacters.innerHTML = "";
  for (const card of pickedCharacters) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.append(document.createTextNode(card.name));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "X";
    remove.addEventListener("click", () => {
      pickedCharacters = pickedCharacters.filter((item) => characterKey(item) !== characterKey(card));
      renderPickedCharacters();
    });
    chip.appendChild(remove);
    selectedCharacters.appendChild(chip);
  }
}

function addCurrentCharacter() {
  const selected = characterSelect.value;
  if (!selected) return;
  const card = allCharacters.find((item) => characterKey(item) === selected);
  if (!card) return;
  if (!pickedCharacters.some((item) => characterKey(item) === selected)) {
    pickedCharacters.push(card);
    renderPickedCharacters();
  }
  characterSelect.value = "";
}

function extractSection(text, heading) {
  const pattern = new RegExp(`## ${heading}\\n\\n([\\s\\S]*?)(\\n\\n## |$)`);
  const match = text.match(pattern);
  return match ? match[1].trim() : "";
}

async function checkSeed() {
  setStatus("Checking local book memory...", "status-working");
  try {
    const response = await fetch("/api/seed");
    const data = await response.json();
    if (!data.ok) {
      setStatus(`Local book memory not ready: ${data.error}`, "status-error");
      return;
    }
    const current = extractSection(data.seed, "Current Position");
    const continueFrom = extractSection(data.seed, "Continue From");
    if (!startingSituation.value.trim()) {
      startingSituation.value = [current, continueFrom && `Continue from: ${continueFrom}`].filter(Boolean).join("\n\n");
    }
    const size = new Blob([data.seed]).size;
    setStatus(`Local book memory loaded from ${data.path} (${size.toLocaleString()} bytes)`, "status-ready");
  } catch (error) {
    setStatus(`Could not reach Book Time server: ${error}`, "status-error");
  }
}

async function loadCharacters() {
  try {
    const response = await fetch("/api/characters");
    const data = await response.json();
    if (!data.ok) {
      setStatus(`Character memory not ready: ${data.error}`, "status-error");
      return;
    }
    allCharacters = data.characters || [];
    renderCharacterOptions();
  } catch (error) {
    setStatus(`Could not load characters: ${error}`, "status-error");
  }
}

function modalLines(value) {
  return value.split("\n").map((line) => line.trim()).filter(Boolean);
}

function clearCharacterModal() {
  characterName.value = "";
  characterRole.value = "";
  characterPersonality.value = "";
  characterRelationships.value = "";
  characterVoice.value = "";
  characterCanon.value = "";
  characterNotes.value = "";
}

async function saveNewCharacter() {
  const card = {
    name: characterName.value.trim(),
    role: characterRole.value.trim(),
    personality: modalLines(characterPersonality.value),
    relationships: modalLines(characterRelationships.value),
    voice_rules: modalLines(characterVoice.value),
    do_not_change: modalLines(characterCanon.value),
    notes: characterNotes.value.trim()
  };
  if (!card.name) {
    characterName.focus();
    return;
  }
  saveCharacter.disabled = true;
  try {
    const response = await fetch("/api/characters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character: card })
    });
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Could not save character.", "status-error");
      return;
    }
    allCharacters = data.characters || [];
    renderCharacterOptions();
    const saved = data.character;
    if (!pickedCharacters.some((item) => characterKey(item) === characterKey(saved))) {
      pickedCharacters.push(saved);
      renderPickedCharacters();
    }
    characterModal.close();
    clearCharacterModal();
    setStatus(`Saved ${saved.name} to local character memory.`, "status-ready");
  } catch (error) {
    setStatus(`Could not save character: ${error}`, "status-error");
  } finally {
    saveCharacter.disabled = false;
  }
}

function formPayload() {
  return {
    chapterRequest: chapterRequest.value,
    premise: premise.value,
    selectedGenres: pickedGenres,
    selectedCharacters: pickedCharacters,
    startingSituation: startingSituation.value,
    selectedTones: pickedTones,
    prompt: rawPrompt.value,
    sceneRequirements: sceneRequirements.value,
    wordBank: wordBank.value,
    qualityRules: qualityRules.value,
    styleSample: styleSample.value,
    chapterLength: chapterLength.value,
    chapterStructure: {
      opening: openingScene.value,
      development: developmentScene.value,
      complication: complicationScene.value,
      choice: choiceScene.value,
      closingHook: closingHook.value
    },
    outputFormat: outputFormat.value,
    finalRules: finalRules.value,
    mode: "chapter-template"
  };
}

async function fillChapterStructure() {
  fillStructure.disabled = true;
  setStatus("Ollama is filling the chapter structure...", "status-working");
  try {
    const response = await fetch("/api/structure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload())
    });
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Could not fill structure.", "status-error");
      return;
    }
    const structure = data.structure || {};
    openingScene.value = structure.opening || openingScene.value;
    developmentScene.value = structure.development || developmentScene.value;
    complicationScene.value = structure.complication || complicationScene.value;
    choiceScene.value = structure.choice || choiceScene.value;
    closingHook.value = structure.closingHook || structure.closing_hook || closingHook.value;
    setStatus(data.warning || "Chapter structure filled.", data.warning ? "status-working" : "status-ready");
  } catch (error) {
    setStatus(`Could not fill structure: ${error}`, "status-error");
  } finally {
    fillStructure.disabled = false;
  }
}

async function prepare() {
  const payload = formPayload();
  const hasDetails = payload.premise.trim() || payload.prompt.trim() || payload.startingSituation.trim() || payload.selectedCharacters.length;
  if (!hasDetails) {
    premise.focus();
    return;
  }
  savePersistentLists();
  preparePrompt.disabled = true;
  copyPrompt.disabled = true;
  preparedPrompt.value = "";
  setStatus("Ollama is preparing LM Studio syntax...", "status-working");
  try {
    const response = await fetch("/api/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!data.ok) {
      setStatus(data.error || "Prompt preparation failed.", "status-error");
      return;
    }
    preparedPrompt.value = data.preparedPrompt;
    copyPrompt.disabled = false;
    setStatus(data.warning || "Prompt ready for LM Studio.", data.warning ? "status-working" : "status-ready");
  } catch (error) {
    setStatus(`Prompt preparation failed: ${error}`, "status-error");
  } finally {
    preparePrompt.disabled = false;
  }
}

async function copyOutput() {
  await navigator.clipboard.writeText(preparedPrompt.value);
  setStatus("Copied. Paste it into LM Studio.", "status-ready");
}

refreshSeed.addEventListener("click", checkSeed);
fillStructure.addEventListener("click", fillChapterStructure);
addGenre.addEventListener("click", () => addTextChoice(genreSelect, newGenre, pickedGenres, renderGenres));
addTone.addEventListener("click", () => addTextChoice(toneSelect, newTone, pickedTones, renderTones));
addSelectedCharacter.addEventListener("click", addCurrentCharacter);
openCharacterModal.addEventListener("click", () => characterModal.showModal());
closeCharacterModal.addEventListener("click", () => characterModal.close());
cancelCharacter.addEventListener("click", () => characterModal.close());
saveCharacter.addEventListener("click", saveNewCharacter);
preparePrompt.addEventListener("click", prepare);
copyPrompt.addEventListener("click", copyOutput);
wordBank.addEventListener("input", savePersistentLists);

renderGenres();
renderTones();
checkSeed();
loadCharacters();
