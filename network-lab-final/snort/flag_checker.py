import os

# === Read correct flag data ===
try:
    with open("/shared/attack_info.txt", "r") as f:
        payload, port, attack_type, ip_last_octet = f.read().strip().split(",")
except FileNotFoundError:
    print("❌ Error: Cannot find attack info.")
    exit()

# === Set IP suffix dynamically if needed
expected_flag = f"{payload}_{ip_last_octet}_{port}".strip()

# === Prompt for student flag ===
user_flag = input("\nEnter your FLAG: ").strip()

# === Compare and act ===
if user_flag == expected_flag:
    print("\n✅ Correct! Attack stopped successfully.\n")
    with open("/shared/stop_attack.txt", "w") as f:
        f.write("stop\n")
else:
    print("\n❌ Wrong flag! Increasing delay...\n")
    try:
        with open("/shared/stop_attack.txt", "r") as f:
            current = int(f.read().strip())
    except:
        current = 0
    with open("/shared/stop_attack.txt", "w") as f:
        f.write(str(current + 5))
