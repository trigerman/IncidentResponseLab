const DEFAULT_MANIFEST_URL = "../dist/images.json";
const SAMPLE_VM_ASSETS = {
  wasm_path: "./vendor/v86/v86.wasm",
  bios: "./vendor/v86/seabios.bin",
  vga_bios: "./vendor/v86/vgabios.bin",
  kernel: "./vendor/v86/buildroot-bzimage.bin",
};

const state = {
  manifestUrl: DEFAULT_MANIFEST_URL,
  images: [],
  sessions: {
    defender: null,
    attacker: null,
  },
  serialBuffers: {
    defender: "",
    attacker: "",
  },
  flagSeed: null,
  bridgeRunning: false,
};

const elements = {
  manifestSelect: document.getElementById("manifest-select"),
  reloadManifest: document.getElementById("reload-manifest"),
  defenderStatus: document.getElementById("defender-status"),
  attackerStatus: document.getElementById("attacker-status"),
  defenderBoot: document.getElementById("defender-boot"),
  attackerBoot: document.getElementById("attacker-boot"),
  defenderReset: document.getElementById("defender-reset"),
  attackerReset: document.getElementById("attacker-reset"),
  defenderScreen: document.getElementById("defender-screen"),
  attackerScreen: document.getElementById("attacker-screen"),
  flagSeed: document.getElementById("flag-seed"),
  regenFlag: document.getElementById("regen-flag"),
  toggleBridge: document.getElementById("toggle-bridge"),
  networkStatus: document.getElementById("network-status"),
  eventLog: document.getElementById("event-log"),
};

function logEvent(message) {
  const ts = new Date().toISOString();
  elements.eventLog.textContent += `[${ts}] ${message}\n`;
  elements.eventLog.scrollTop = elements.eventLog.scrollHeight;
}

async function loadManifest(url = state.manifestUrl) {
  logEvent(`Loading manifest from ${url}`);
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.images = data.images || [];
    refreshManifestSelect();
    logEvent(`Loaded ${state.images.length} image entries`);
  } catch (error) {
    logEvent(`Manifest load failed: ${error.message}`);
  }
}

function refreshManifestSelect() {
  const select = elements.manifestSelect;
  select.innerHTML = "";
  state.images.forEach((entry, index) => {
    const opt = document.createElement("option");
    opt.value = entry.file;
    opt.textContent = `${entry.role} – ${Math.round(entry.size_bytes / 1024)} KB`;
    if (index === 0) opt.selected = true;
    select.appendChild(opt);
  });
}

function randomFlagSeed() {
  const payloads = ["eagle", "falcon", "panther", "ghost"];
  const payload = payloads[Math.floor(Math.random() * payloads.length)];
  const ipSuffix = Math.floor(Math.random() * 253) + 2;
  const port = Math.floor(Math.random() * (65535 - 1025)) + 1025;
  state.flagSeed = `${payload}_${ipSuffix}_${port}`;
  elements.flagSeed.textContent = state.flagSeed;
  logEvent(`Generated flag seed: ${state.flagSeed}`);
}

function setVmStatus(role, status) {
  const el = role === "defender" ? elements.defenderStatus : elements.attackerStatus;
  el.textContent = status;
}

function ensureV86Loaded(timeoutMs = 10000) {
  if (window.V86) return Promise.resolve();
  logEvent("Waiting for v86 runtime to load…");
  return new Promise((resolve, reject) => {
    const start = performance.now();
    const interval = setInterval(() => {
      if (window.V86) {
        clearInterval(interval);
        resolve();
      } else if (performance.now() - start > timeoutMs) {
        clearInterval(interval);
        reject(new Error("v86 runtime not available"));
      }
    }, 100);
  });
}

function destroyVm(role) {
  const session = state.sessions[role];
  if (session) {
    try {
      session.stop();
    } catch (error) {
      logEvent(`${role} stop error: ${error.message}`);
    }
    state.sessions[role] = null;
    state.serialBuffers[role] = "";
  }
}

async function bootVm(role) {
  try {
    await ensureV86Loaded();
  } catch (error) {
    logEvent(`Cannot boot ${role}: ${error.message}`);
    return;
  }

  destroyVm(role);

  logEvent(`Boot requested for ${role} (sample buildroot image)`);
  setVmStatus(role, "booting");

  const screen = role === "defender" ? elements.defenderScreen : elements.attackerScreen;
  if (!screen) {
    logEvent(`Missing screen container for ${role}`);
    return;
  }

  const shell = document.createElement("div");
  shell.className = "v86-screen";
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 400;
  shell.appendChild(canvas);
  const keyboard = document.createElement("textarea");
  keyboard.className = "phone_keyboard";
  shell.appendChild(keyboard);
  screen.replaceChildren(shell);

  const emulator = new window.V86({
    wasm_path: SAMPLE_VM_ASSETS.wasm_path,
    memory_size: 128 * 1024 * 1024,
    vga_memory_size: 16 * 1024 * 1024,
    screen_container: shell,
    bios: { url: SAMPLE_VM_ASSETS.bios },
    vga_bios: { url: SAMPLE_VM_ASSETS.vga_bios },
    bzimage: { url: SAMPLE_VM_ASSETS.kernel },
    cmdline: "console=ttyS0",
    autostart: true,
  });

  emulator.add_listener("emulator-ready", () => {
    setVmStatus(role, "running");
    logEvent(`${role} VM running (buildroot)`);
  });

  emulator.add_listener("halt", () => {
    setVmStatus(role, "halted");
    logEvent(`${role} VM halted`);
  });

  emulator.add_listener("cpu-exception", (type) => {
    logEvent(`${role} CPU exception: ${type}`);
  });

  emulator.add_listener("serial0-output-char", (charCode) => {
    const char = String.fromCharCode(charCode);
    state.serialBuffers[role] += char;
    if (char === "\n") {
      logEvent(`${role}> ${state.serialBuffers[role].trimEnd()}`);
      state.serialBuffers[role] = "";
    }
  });

  state.sessions[role] = emulator;
}

function resetVm(role) {
  destroyVm(role);
  setVmStatus(role, "idle");
  logEvent(`${role} VM reset`);
}

function toggleBridge() {
  state.bridgeRunning = !state.bridgeRunning;
  const status = state.bridgeRunning ? "bridge active" : "bridge idle";
  elements.networkStatus.textContent = status;
  elements.toggleBridge.textContent = state.bridgeRunning ? "Stop Bridge" : "Start Bridge";
  logEvent(`Network bridge ${state.bridgeRunning ? "enabled" : "disabled"} (stub)`);
}

function attachEventHandlers() {
  elements.reloadManifest.addEventListener("click", () => loadManifest());
  elements.defenderBoot.addEventListener("click", () => bootVm("defender"));
  elements.attackerBoot.addEventListener("click", () => bootVm("attacker"));
  elements.defenderReset.addEventListener("click", () => resetVm("defender"));
  elements.attackerReset.addEventListener("click", () => resetVm("attacker"));
  elements.regenFlag.addEventListener("click", randomFlagSeed);
  elements.toggleBridge.addEventListener("click", toggleBridge);
}

async function init() {
  attachEventHandlers();
  randomFlagSeed();
  await loadManifest();
  logEvent("Ready. Boot either VM to load the sample OS image.");
}

init();
