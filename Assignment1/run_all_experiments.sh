#!/bin/bash

SERVER_IP="128.6.13.3"
PORT=5001
REQUESTS=100

RESULTS_DIR="results"
mkdir -p $RESULTS_DIR

run_test () {
    PROTO=$1
    CLIENTS=$2
    PAYLOAD=$3
    LABEL=$4

    echo "Running $PROTO | clients=$CLIENTS | payload=$PAYLOAD"

    SERVER_LOG="$RESULTS_DIR/server_${PROTO}_${LABEL}.jsonl"
    CLIENT_LOG="$RESULTS_DIR/client_${PROTO}_${LABEL}.jsonl"

    # Start server in background
    python3 server.py \
        --proto $PROTO \
        --bind 0.0.0.0 \
        --port $PORT \
        --payload-bytes $PAYLOAD \
        --requests $REQUESTS \
        --clients $CLIENTS \
        --log $SERVER_LOG &

    SERVER_PID=$!
    sleep 2

    # SSH into ilab3 and run client
    ssh sp2160@ilab3.cs.rutgers.edu "
        cd ~/DistSysProj/Assignment1 && \
        python3 client.py \
            --proto $PROTO \
            --host $SERVER_IP \
            --port $PORT \
            --payload-bytes $PAYLOAD \
            --requests $REQUESTS \
            --clients $CLIENTS \
            --log results/client_${PROTO}_${LABEL}.jsonl
    "

    # Wait for server to finish
    wait $SERVER_PID
}

############################
# PAYLOAD EXPERIMENTS
############################
CLIENTS=10
for PAYLOAD in 64 256 1024 4096 8192
do
    for PROTO in tcp udp
    do
        run_test $PROTO $CLIENTS $PAYLOAD "payload${PAYLOAD}"
    done
done

############################
# CLIENT SCALING EXPERIMENTS
############################
PAYLOAD=64
for CLIENTS in 1 5 10 20 100 1000
do
    for PROTO in tcp udp
    do
        # Avoid duplicate: (clients=10, payload=64 already done above)
        if [[ "$CLIENTS" == "10" ]]
        then
            continue
        fi

        run_test $PROTO $CLIENTS $PAYLOAD "clients${CLIENTS}"
    done
done

echo "All experiments complete."