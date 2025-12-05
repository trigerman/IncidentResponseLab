# Network Lab - Intrusion Detection Simulation

## Setup Instructions

### 1. Install Dependencies

#### Docker (Required)
- Docker **must be installed manually**. You cannot install it via pip.
- Follow the official guide for your OS:
  - [Install Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
  - [Install Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
  - [Install Docker Engine for Linux](https://docs.docker.com/engine/install/)

#### Python Packages
Install required Python packages using pip:

```bash
pip install -r requirements.txt
```

> **Note:** You must have Python 3 and `pip` installed.

### 2. Run the Lab (Docker mode)

```bash
python3 run.py         # Normal mode
python3 run.py --debug # Debug mode
```

In debug mode, logs and attacker details are visible. In normal mode, you are dropped into the Snort container shell directly.

---

## Objective

- The Snort container will open with a **SECURITY BREACH** banner.
- Your mission:
  - Analyze network traffic (Snort, tcpdump)
  - Identify the attacker’s:
    - Payload
    - Last octet of IP address
    - Target port number
- Submit the flag using the `found` command:

```bash
found <payload>_<lastoctet>_<port>
```

### Example:

```bash
found shadow_2_8080
```

---

## Important Notes

- The attacker runs silently in the background.
- No clues are shown in **normal mode**.
- The attacker adapts if the wrong flag is submitted!
- The flag is generated fresh each session.

---

## Browser / v86 Prototype

An experimental browser-native delivery is under construction. Current workflow:

1. **Build VM images**
   ```bash
   python tools/build_images.py --role attacker --role defender
   ```
   - Add `--skip-packages` when working on Windows (apk installs require Linux).
   - Use `--image-type ext4 --image-size-mb 512` on Linux hosts with `mke2fs` installed to emit raw disks for v86.
2. **Fetch the v86 runtime assets (once)**
   ```bash
   python tools/fetch_v86_assets.py
   ```
   This downloads `libv86.js`, `v86.wasm`, BIOS blobs, and the sample Buildroot kernel into `web/vendor/v86/`.
3. **Serve the web UI** (from repo root)
   ```bash
   python -m http.server 8080
   ```
   Run the server from the project root so `/dist/images.json` resolves correctly, then open `http://localhost:8080/web/` to access the dual-console layout, manifest selector, flag generator, and bridge controls. The current build boots both VMs with the v86 Buildroot demo kernel so you can validate the environment while the custom lab images are still being provisioned.

The Docker workflow remains the supported path while the browser port stabilizes.

---

🎯 **Good Luck, Defender!**
