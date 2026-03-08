import os
import subprocess
import time

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
SERVER_IP = "128.6.13.2"

payloads = [64, 256, 1024, 2048, 4096, 8192]
clients_list = [1, 5, 10, 20, 50, 100, 200, 500]

MAX_RETRIES = 2


def ssh_command(host, command):
    return subprocess.run(
        ["sshpass", "-p", PASSWORD,
         "ssh", "-o", "StrictHostKeyChecking=no",
         host, command],
        capture_output=True, text=True
    )

def scp_upload(host, local_file):
    subprocess.run(
        ["sshpass", "-p", PASSWORD,
         "scp", "-o", "StrictHostKeyChecking=no",
         local_file,
         f"{host}:{BASE_DIR}/"]
    )

def scp_download(host, remote_path, local_path):
    subprocess.run(
        ["sshpass", "-p", PASSWORD,
         "scp", "-o", "StrictHostKeyChecking=no",
         f"{host}:{remote_path}",
         local_path]
    )

def ensure_remote_file(host, filename):
    check_cmd = f"test -f {BASE_DIR}/{filename} && echo EXISTS || echo MISSING"
    result = ssh_command(host, check_cmd)

    if "MISSING" in result.stdout:
        print(f"Uploading {filename} to {host}")
        scp_upload(host, filename)

def setup_remote_machine(host):
    print(f"\nSetting up clean environment on {host}")

    ssh_command(host, f"mkdir -p {BASE_DIR}")
    ssh_command(host, f"rm -rf {BASE_DIR}/results")
    ssh_command(host, f"rm -rf {BASE_DIR}/plots")
    ssh_command(host, f"mkdir -p {BASE_DIR}/results")
    ssh_command(host, f"mkdir -p {BASE_DIR}/plots")

    ensure_remote_file(host, "server.py")
    ensure_remote_file(host, "client.py")
    ensure_remote_file(host, "analysis.py")

def validate_trial(proto, clients, payload):
    label = f"{proto}_c{clients}_p{payload}"
    log_path = f"{BASE_DIR}/results/client_{label}.jsonl"

    check_cmd = f"""
    if [ -f {log_path} ]; then
        grep '"event": "done"' {log_path} > /dev/null && echo OK || echo FAIL
    else
        echo FAIL
    fi
    """

    result = ssh_command(CLIENT_HOST, check_cmd)
    return "OK" in result.stdout

def delete_trial_logs(proto, clients, payload):
    label = f"{proto}_c{clients}_p{payload}"
    ssh_command(SERVER_HOST, f"rm -f {BASE_DIR}/results/server_{label}.jsonl")
    ssh_command(CLIENT_HOST, f"rm -f {BASE_DIR}/results/client_{label}.jsonl")

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
    python3 client.py --proto {proto} --host {SERVER_IP} --port 5001 \
    --payload-bytes {payload} --requests 100 --clients {clients} \
    --log results/client_{label}.jsonl
    """

    retries = 0

    while retries <= MAX_RETRIES:
        subprocess.Popen(
            ["sshpass", "-p", PASSWORD,
             "ssh", "-o", "StrictHostKeyChecking=no",
             SERVER_HOST, server_cmd]
        )

        time.sleep(3)
        ssh_command(CLIENT_HOST, client_cmd)
        time.sleep(2)

        if validate_trial(proto, clients, payload):
            print(f"{label} SUCCESS")
            return
        else:
            print(f"{label} FAILED — retrying...")
            delete_trial_logs(proto, clients, payload)
            retries += 1

    print(f"{label} permanently failed after retries.")

# MAIN EXECUTION

setup_remote_machine(SERVER_HOST)
setup_remote_machine(CLIENT_HOST)

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

print("\nRunning analysis...")
ssh_command(CLIENT_HOST, f"cd {BASE_DIR} && python3 analysis.py")

print("\nDownloading results...")
scp_download(CLIENT_HOST, f"{BASE_DIR}/*.csv", "./results/")
scp_download(CLIENT_HOST, f"{BASE_DIR}/*.png", "./results/")

print("\nAll experiments completed successfully.")