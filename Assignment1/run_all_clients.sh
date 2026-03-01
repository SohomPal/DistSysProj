#!/bin/bash

SERVER_IP="128.6.13.2"
PORT=5001
REQUESTS=100
RESULTS_DIR="results"
mkdir -p $RESULTS_DIR

run_client () {
    PROTO=$1
    CLIENTS=$2
    PAYLOAD=$3
    LABEL=$4

    echo "CLIENT $PROTO | clients=$CLIENTS | payload=$PAYLOAD"

    CLIENT_LOG="$RESULTS_DIR/client_${PROTO}_${LABEL}.jsonl"

    python3 client.py \
        --proto $PROTO \
        --host $SERVER_IP \
        --port $PORT \
        --payload-bytes $PAYLOAD \
        --requests $REQUESTS \
        --clients $CLIENTS \
        --log $CLIENT_LOG
}

################################
# PAYLOAD EXPERIMENTS (clients=10)
################################
CLIENTS=10
for PAYLOAD in 64 256 1024 4096 8192
do
    for PROTO in tcp udp
    do
        run_client $PROTO $CLIENTS $PAYLOAD "payload${PAYLOAD}"
        sleep 3
    done
done

################################
# CLIENT SCALING (payload=64)
################################
PAYLOAD=64
for CLIENTS in 1 5 10 20 100 1000
do
    if [[ "$CLIENTS" == "10" ]]
    then
        continue
    fi

    for PROTO in tcp udp
    do
        run_client $PROTO $CLIENTS $PAYLOAD "clients${CLIENTS}"
        sleep 3
    done
done

echo "All client experiments complete."