import os
import subprocess
import time

# Load .env
def load_env():
    with open(".env") as f:
        for line in f:
            key, value = line.strip().split("=")
            os.environ[key] = value

load_env()

NETID = os.environ["NETID"]
PASSWORD = os.environ["PASSWORD"]

SERVER_HOST = f"{NETID}@ilab1.cs.rutgers.edu"
CLIENT_HOST = f"{NETID}@ilab2.cs.rutgers.edu"

BASE_DIR = "~/DistSysProj/Assignment1"

payloads = [64, 256, 1024, 4096, 8192]
clients_list = [1, 5, 10, 20, 50, 100, 200]

def ssh_command(host, command):
    full_cmd = [
        "sshpass", "-p", PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        host,
        command
    ]
    subprocess.run(full_cmd)

def scp_download(host, remote_path, local_path):
    full_cmd = [
        "sshpass", "-p", PASSWORD,
        "scp", "-o", "StrictHostKeyChecking=no",
        f"{host}:{remote_path}",
        local_path
    ]
    subprocess.run(full_cmd)

def run_experiment(proto, clients, payload):
    label = f"{proto}_c{clients}_p{payload}"
    print(f"\nRunning {label}")

    server_cmd = f"""
    cd {BASE_DIR} &&
    python3 server.py --proto {proto} --bind 0.0.0.0 --port 5001 \
    --payload-bytes {payload} --requests 100 --clients {clients} \
    --log results/server_{label}.jsonl
    """

    client_cmd = f"""
    cd {BASE_DIR} &&
    python3 client.py --proto {proto} --host 128.6.13.2 --port 5001 \
    --payload-bytes {payload} --requests 100 --clients {clients} \
    --log results/client_{label}.jsonl
    """

    # Start server in background
    subprocess.Popen([
        "sshpass", "-p", PASSWORD,
        "ssh", "-o", "StrictHostKeyChecking=no",
        SERVER_HOST,
        server_cmd
    ])

    time.sleep(3)

    ssh_command(CLIENT_HOST, client_cmd)

    time.sleep(2)

# Payload scaling (clients=10)
for payload in payloads:
    for proto in ["tcp", "udp"]:
        run_experiment(proto, 10, payload)

# Client scaling (payload=64)
for clients in clients_list:
    if clients == 10:
        continue
    for proto in ["tcp", "udp"]:
        run_experiment(proto, clients, 64)

# Run analysis on client machine
print("\nRunning analysis on client machine...")
ssh_command(CLIENT_HOST, f"cd {BASE_DIR} && python3 analysis.py")

# Download results + plots
print("\nDownloading results and plots...")
scp_download(CLIENT_HOST, f"{BASE_DIR}/all_results_full.csv", "./")
scp_download(CLIENT_HOST, f"{BASE_DIR}/*.png", "./")

print("\nAll experiments complete and downloaded.")