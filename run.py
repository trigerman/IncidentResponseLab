from pathlib import Path
import subprocess
import random
import time
import os
import argparse
import yaml
from rich.progress import Progress

SHARED_VOLUME = "./network-lab-final/shared"
COMPOSE_FILE = "./network-lab-final/docker-compose.yml"
ATTACKER_COMPOSE_KEY = "attacker"
TARGET_IP = "172.20.0.10"

def get_attacker_ip():
    last_octet = random.randint(2, 254)
    return f"172.20.0.{last_octet}"

def update_compose_ip(ip):
    with open(COMPOSE_FILE, "r") as f:
        data = yaml.safe_load(f)

    data['services'][ATTACKER_COMPOSE_KEY]['networks']['labnet']['ipv4_address'] = ip

    with open(COMPOSE_FILE, "w") as f:
        yaml.dump(data, f)

def reset_shared_files():
    Path(f"{SHARED_VOLUME}/stop_attack.txt").write_text("0")
    Path(f"{SHARED_VOLUME}/attack_info.txt").write_text("")

def main(debug=False):
    attacker_ip = get_attacker_ip()
    port = random.randint(1025, 65535)
    payload = random.choice(["eagle", "falcon", "panther", "ghost"])
    flag = f"{payload}_{attacker_ip.split('.')[-1]}_{port}"

    update_compose_ip(attacker_ip)
    reset_shared_files()

    mode = "DEBUG" if debug else "NORMAL"
    print(f"[INFO] Starting lab in {mode} mode...")

    steps = [
        ("Tearing down previous lab environment...", ["docker", "compose", "-f", COMPOSE_FILE, "down"]),
        ("Building and starting containers...", ["docker", "compose", "-f", COMPOSE_FILE, "up", "--build", "-d"])
    ]

    with Progress() as progress:
        for desc, cmd in steps:
            task = progress.add_task(f"[•] {desc}", total=None)
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            progress.update(task, advance=1)
            progress.remove_task(task)

    if debug:
        print(f"[INFO] Assigning attacker IP: {attacker_ip}")
        print(f"[FLAG] Expected format: <payload>_{attacker_ip.split('.')[-1]}_{port}")
        print("[DEBUG] To enter Snort shell, run:")
        print("    docker exec -it snort bash")
    else:
        print("[✓] Lab started Successfuly dropping shell...\n")
        subprocess.run(["docker", "exec", "-it", "snort", "bash"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Intrusion Detection Lab")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args = parser.parse_args()
    main(debug=args.debug)
