#!/usr/bin/env python3
"""
TCP/UDP echo client boilerplate.

Implements a small benchmark client for CS417 Assignment 1:
- TCP work item: connect -> send N bytes -> recv N bytes (echo) -> disconnect
- UDP work item: send N bytes -> recv N bytes (echo)

Logging format: JSON Lines (one JSON object per line) to the --log path.
"""
import argparse
import json
import os
import socket
import threading
import time
from typing import Dict, Tuple, Optional, Any

##### Suggested helper functions; feel free to modify as needed. #####
def now_wall() -> float:
    return time.time()

def now_mono() -> float:
    return time.monotonic()

def log_event(fp, event: dict):
    fp.write(json.dumps(event, sort_keys=True) + "\n")
    fp.flush()

def recvall(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes from a TCP socket (or raise ConnectionError)."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed while receiving")
        buf.extend(chunk)
    return bytes(buf)

def build_payload(payload_bytes: int, client_id: int = 0, seq: int = 0, include_header: bool = False) -> bytes:
    """Build a payload of exactly payload_bytes. Optionally includes a 16B header for UDP matching."""
    if not include_header:
        return b"A" * payload_bytes
    header = client_id.to_bytes(8, "big", signed=False) + seq.to_bytes(8, "big", signed=False)
    if payload_bytes < len(header):
        # Should not happen with assignment defaults, but keep robust.
        return header[:payload_bytes]
    return header + (b"B" * (payload_bytes - len(header)))

##### Required functions to implement. Do not change signatures. #####
def run_tcp_client(host: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """Run the TCP client benchmark."""
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    # Aggregate counters across threads
    totals_lock = threading.Lock()
    total_req_ok = 0
    total_req_err = 0
    total_bytes = 0  # request + response bytes for successful ops
    conn_times: list[float] = []

    start_wall = now_wall()
    start_mono = now_mono()

    with open(log_path, "w", encoding="utf-8") as fp:
        log_event(fp, {
            "ts_wall": start_wall,
            "ts_mono": start_mono,
            "role": "client",
            "proto": "tcp",
            "event": "start",
            "host": host,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
        })

        def worker(client_id: int) -> None:
            nonlocal total_req_ok, total_req_err, total_bytes
            # Connect + measure setup time
            connect_t0 = now_mono()
            sock: Optional[socket.socket] = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.settimeout(10.0)
                sock.connect((host, port))
                connect_t1 = now_mono()
                ct = connect_t1 - connect_t0
                with totals_lock:
                    conn_times.append(ct)
                log_event(fp, {
                    "ts_wall": now_wall(),
                    "ts_mono": connect_t1,
                    "role": "client",
                    "proto": "tcp",
                    "event": "connect_ok",
                    "client_id": client_id,
                    "connect_time_s": ct,
                })

                payload = build_payload(payload_bytes)
                for seq in range(requests):
                    t_send = now_mono()
                    try:
                        sock.sendall(payload)
                        echoed = recvall(sock, payload_bytes)
                        t_recv = now_mono()
                        ok = (echoed == payload)
                        rtt = t_recv - t_send
                        if ok:
                            with totals_lock:
                                total_req_ok += 1
                                total_bytes += payload_bytes * 2
                            log_event(fp, {
                                "ts_wall": now_wall(),
                                "ts_mono": t_recv,
                                "role": "client",
                                "proto": "tcp",
                                "event": "rtt",
                                "client_id": client_id,
                                "seq": seq,
                                "payload_bytes": payload_bytes,
                                "rtt_s": rtt,
                            })
                        else:
                            with totals_lock:
                                total_req_err += 1
                            log_event(fp, {
                                "ts_wall": now_wall(),
                                "ts_mono": t_recv,
                                "role": "client",
                                "proto": "tcp",
                                "event": "bad_echo",
                                "client_id": client_id,
                                "seq": seq,
                                "payload_bytes": payload_bytes,
                                "rtt_s": rtt,
                            })
                    except Exception as e:
                        t_err = now_mono()
                        with totals_lock:
                            total_req_err += 1
                        log_event(fp, {
                            "ts_wall": now_wall(),
                            "ts_mono": t_err,
                            "role": "client",
                            "proto": "tcp",
                            "event": "request_error",
                            "client_id": client_id,
                            "seq": seq,
                            "payload_bytes": payload_bytes,
                            "error": repr(e),
                        })
                        break
            except Exception as e:
                t_err = now_mono()
                with totals_lock:
                    total_req_err += requests
                log_event(fp, {
                    "ts_wall": now_wall(),
                    "ts_mono": t_err,
                    "role": "client",
                    "proto": "tcp",
                    "event": "connect_error",
                    "client_id": client_id,
                    "error": repr(e),
                })
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

        threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(clients)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        end_mono = now_mono()
        end_wall = now_wall()
        elapsed = end_mono - start_mono

        # Throughput (bytes/sec) for successful request/response pairs.
        thr = (total_bytes / elapsed) if elapsed > 0 else 0.0

        # Summary event includes connection times list length to support analysis
        log_event(fp, {
            "ts_wall": end_wall,
            "ts_mono": end_mono,
            "role": "client",
            "proto": "tcp",
            "event": "done",
            "elapsed_s": elapsed,
            "total_requests_ok": total_req_ok,
            "total_requests_err": total_req_err,
            "total_bytes": total_bytes,
            "throughput_Bps": thr,
            "connections": clients,
            "connect_times_s": conn_times,  # for later median/avg
        })

def run_udp_client(host: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """Run the UDP client benchmark.

    Requirement: Use a single UDP socket on the client to send requests to the server.
    We implement multiple logical senders ("clients") via threads that share one socket,
    using a receiver thread to match responses by (client_id, seq) embedded in the payload.
    """
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    start_wall = now_wall()
    start_mono = now_mono()

    # Pending map: (client_id, seq) -> send_time_mono
    pending_lock = threading.Lock()
    pending: Dict[Tuple[int, int], float] = {}
    done_senders = threading.Event()

    # Results counters
    totals_lock = threading.Lock()
    total_ok = 0
    total_err = 0
    total_timeouts = 0
    total_bytes = 0

    # Condition variable to wake senders when response arrives
    cv = threading.Condition(lock=pending_lock)
    responses: Dict[Tuple[int, int], float] = {}  # (client_id, seq) -> recv_time_mono

    with open(log_path, "w", encoding="utf-8") as fp:
        log_event(fp, {
            "ts_wall": start_wall,
            "ts_mono": start_mono,
            "role": "client",
            "proto": "udp",
            "event": "start",
            "host": host,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
        })

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(0.5)
            server_addr = (host, port)

            def receiver() -> None:
                nonlocal total_ok, total_err, total_bytes
                while not done_senders.is_set() or True:
                    # Exit when no more pending and senders done
                    if done_senders.is_set():
                        with pending_lock:
                            if not pending:
                                break
                    try:
                        data, _addr = sock.recvfrom(max(2048, payload_bytes + 64))
                    except socket.timeout:
                        continue
                    except Exception as e:
                        with totals_lock:
                            total_err += 1
                        log_event(fp, {
                            "ts_wall": now_wall(),
                            "ts_mono": now_mono(),
                            "role": "client",
                            "proto": "udp",
                            "event": "recv_error",
                            "error": repr(e),
                        })
                        continue

                    recv_t = now_mono()
                    if len(data) < 16:
                        with totals_lock:
                            total_err += 1
                        log_event(fp, {
                            "ts_wall": now_wall(),
                            "ts_mono": recv_t,
                            "role": "client",
                            "proto": "udp",
                            "event": "short_packet",
                            "len": len(data),
                        })
                        continue

                    client_id = int.from_bytes(data[:8], "big", signed=False)
                    seq = int.from_bytes(data[8:16], "big", signed=False)

                    key = (client_id, seq)
                    with pending_lock:
                        if key in pending:
                            responses[key] = recv_t
                            cv.notify_all()
                        # Else: late/duplicate; ignore

            recv_thread = threading.Thread(target=receiver, daemon=True)
            recv_thread.start()

            def sender(client_id: int) -> None:
                nonlocal total_ok, total_err, total_timeouts, total_bytes
                for seq in range(requests):
                    payload = build_payload(payload_bytes, client_id=client_id, seq=seq, include_header=True)
                    send_t = now_mono()
                    key = (client_id, seq)

                    with pending_lock:
                        pending[key] = send_t

                    try:
                        sock.sendto(payload, server_addr)
                    except Exception as e:
                        with pending_lock:
                            pending.pop(key, None)
                        with totals_lock:
                            total_err += 1
                        log_event(fp, {
                            "ts_wall": now_wall(),
                            "ts_mono": now_mono(),
                            "role": "client",
                            "proto": "udp",
                            "event": "send_error",
                            "client_id": client_id,
                            "seq": seq,
                            "error": repr(e),
                        })
                        continue

                    # Wait for response (with timeout)
                    timeout_s = 2.0
                    recv_t: Optional[float] = None
                    with pending_lock:
                        end_by = now_mono() + timeout_s
                        while True:
                            if key in responses:
                                recv_t = responses.pop(key)
                                pending.pop(key, None)
                                break
                            remaining = end_by - now_mono()
                            if remaining <= 0:
                                pending.pop(key, None)
                                break
                            cv.wait(timeout=remaining)

                    if recv_t is None:
                        with totals_lock:
                            total_timeouts += 1
                        log_event(fp, {
                            "ts_wall": now_wall(),
                            "ts_mono": now_mono(),
                            "role": "client",
                            "proto": "udp",
                            "event": "timeout",
                            "client_id": client_id,
                            "seq": seq,
                            "payload_bytes": payload_bytes,
                            "timeout_s": timeout_s,
                        })
                        continue

                    rtt = recv_t - send_t
                    with totals_lock:
                        total_ok += 1
                        total_bytes += payload_bytes * 2
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": recv_t,
                        "role": "client",
                        "proto": "udp",
                        "event": "rtt",
                        "client_id": client_id,
                        "seq": seq,
                        "payload_bytes": payload_bytes,
                        "rtt_s": rtt,
                    })

            send_threads = [threading.Thread(target=sender, args=(i,), daemon=True) for i in range(clients)]
            for t in send_threads:
                t.start()
            for t in send_threads:
                t.join()

            done_senders.set()
            recv_thread.join(timeout=5.0)

        finally:
            try:
                sock.close()
            except Exception:
                pass

        end_mono = now_mono()
        end_wall = now_wall()
        elapsed = end_mono - start_mono
        thr = (total_bytes / elapsed) if elapsed > 0 else 0.0

        log_event(fp, {
            "ts_wall": end_wall,
            "ts_mono": end_mono,
            "role": "client",
            "proto": "udp",
            "event": "done",
            "elapsed_s": elapsed,
            "total_requests_ok": total_ok,
            "total_requests_err": total_err,
            "total_timeouts": total_timeouts,
            "total_bytes": total_bytes,
            "throughput_Bps": thr,
            "clients": clients,
            "requests_per_client": requests,
        })

def parse_args() -> argparse.Namespace:
    """Parse CLI args.

    Required flags:
    - --proto tcp|udp
    - --host
    - --port
    - --payload-bytes
    - --requests
    - --clients
    - --log
    """
    p = argparse.ArgumentParser(description="TCP/UDP echo client for benchmarking")
    p.add_argument("--proto", choices=["tcp", "udp"], required=True)
    p.add_argument("--host", required=True)
    p.add_argument("--port", type=int, default=5001)
    p.add_argument("--payload-bytes", type=int, default=64)
    p.add_argument("--requests", type=int, default=1)
    p.add_argument("--clients", type=int, default=1)
    p.add_argument("--log", required=True)
    return p.parse_args()

def main() -> None:
    """Entry point."""
    args = parse_args()
    if args.proto == "tcp":
        run_tcp_client(args.host, args.port, args.log, args.payload_bytes, args.requests, args.clients)
    else:
        run_udp_client(args.host, args.port, args.log, args.payload_bytes, args.requests, args.clients)

if __name__ == "__main__":
    main()
