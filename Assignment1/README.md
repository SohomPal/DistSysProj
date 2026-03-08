# TCP vs UDP Performance Experiments

This project measures and compares **TCP and UDP performance** in terms of:

- Mean RTT
- Median RTT
- Throughput

Experiments evaluate how performance changes with:
- **Number of clients**
- **Payload size**

---

# Files

```
server.py
client.py
runAllExperiments.py
analysis.py
```

---

# Step 1 — Setup ENV

Create an ENV file and set fields NETID and PASSWORD
These values will be used during the auto-run.

---

# Step 2 — Run Experiments

Run the experiment runner:

```
python3 runAllExperiments.py
```

This script automatically runs experiments varying:

- client counts  
- payload sizes  
- protocol (TCP / UDP)

The script will give final run results and plots in:

```
results/
```

The logs from each individual run will be on the ilab machine. These were not copied over due to the large number of them. Plus the results from these were already condensed into the results csv file. 

---

# Experiment Configuration

Experiments were run using:

### Client counts
```
1, 5, 10, 20, 50, 100, 200, 500
```

### Payload sizes (bytes)
```
64, 256, 1024, 2048, 4096, 8192
```

All plots in the report can be reproduced using these steps.