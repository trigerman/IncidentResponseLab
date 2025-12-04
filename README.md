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

### 2. Run the Lab

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

🎯 **Good Luck, Defender!**