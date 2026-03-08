import os
import json
import csv
import statistics
import matplotlib.pyplot as plt

RESULTS_DIR = "results"
OUTPUT_CSV = "all_results_full.csv"

rows = []

def parse_client_file(filepath):
    with open(filepath, "r") as f:
        lines = [json.loads(line) for line in f]

    proto = None
    clients = None
    payload = None
    requests = None
    rtts = []
    throughput_Bps = None
    total_ok = None

    for entry in lines:
        if entry.get("event") == "start":
            proto = entry.get("proto")
            clients = entry.get("clients")
            payload = entry.get("payload_bytes")
            requests = entry.get("requests")

        if entry.get("event") == "rtt":
            rtts.append(entry.get("rtt_s"))

        if entry.get("event") == "done":
            throughput_Bps = entry.get("throughput_Bps")
            total_ok = entry.get("total_requests_ok")

    if not rtts:
        return None

    total_expected = clients * requests if clients and requests else None

    if total_expected and total_ok != total_expected:
        print(f"WARNING incomplete run: {filepath}")

    mean_rtt_ms = statistics.mean(rtts) * 1000
    median_rtt_ms = statistics.median(rtts) * 1000

    throughput_mbps = None
    if throughput_Bps:
        throughput_mbps = (throughput_Bps * 8) / 1_000_000

    return {
        "proto": proto.upper(),
        "clients": clients,
        "payload": payload,
        "mean_rtt_ms": mean_rtt_ms,
        "median_rtt_ms": median_rtt_ms,
        "throughput_mbps": throughput_mbps
    }

for filename in os.listdir(RESULTS_DIR):
    if filename.startswith("client_") and filename.endswith(".jsonl"):
        parsed = parse_client_file(os.path.join(RESULTS_DIR, filename))
        if parsed:
            rows.append(parsed)

with open(OUTPUT_CSV, "w", newline="") as csvfile:
    writer = csv.DictWriter(csvfile,
        fieldnames=["proto","clients","payload",
                    "mean_rtt_ms","median_rtt_ms","throughput_mbps"])
    writer.writeheader()
    writer.writerows(rows)

print("Generated CSV:", OUTPUT_CSV)

payload_rows = [r for r in rows if r["clients"] == 10]
client_rows = [r for r in rows if r["payload"] == 64]

def plot_metric(rows, x_key, y_key, title, ylabel, filename):
    plt.figure(figsize=(8,6))

    for proto in ["TCP","UDP"]:
        subset = [r for r in rows if r["proto"] == proto]
        subset = sorted(subset, key=lambda x: x[x_key])

        x = [r[x_key] for r in subset]
        y = [r[y_key] for r in subset]

        plt.plot(x, y, marker='o', linewidth=2, label=f"{proto} ({y_key.replace('_',' ')})")

    plt.xlabel(x_key.capitalize(), fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.title(title, fontsize=14)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(filename)
    print("Saved:", filename)

# --- RTT vs Payload ---
plot_metric(payload_rows, "payload", "mean_rtt_ms",
            "Mean RTT vs Payload Size (10 Clients)",
            "Mean RTT (ms)",
            "mean_rtt_vs_payload.png")

plot_metric(payload_rows, "payload", "median_rtt_ms",
            "Median RTT vs Payload Size (10 Clients)",
            "Median RTT (ms)",
            "median_rtt_vs_payload.png")

# --- RTT vs Clients ---
plot_metric(client_rows, "clients", "mean_rtt_ms",
            "Mean RTT vs Number of Clients (64B Payload)",
            "Mean RTT (ms)",
            "mean_rtt_vs_clients.png")

plot_metric(client_rows, "clients", "median_rtt_ms",
            "Median RTT vs Number of Clients (64B Payload)",
            "Median RTT (ms)",
            "median_rtt_vs_clients.png")

# --- Throughput vs Payload ---
plot_metric(payload_rows, "payload", "throughput_mbps",
            "Throughput vs Payload Size (10 Clients)",
            "Throughput (Mbps)",
            "throughput_vs_payload.png")

# --- Throughput vs Clients ---
plot_metric(client_rows, "clients", "throughput_mbps",
            "Throughput vs Number of Clients (64B Payload)",
            "Throughput (Mbps)",
            "throughput_vs_clients.png")

print("All plots generated.")