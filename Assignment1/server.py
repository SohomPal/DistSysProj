#!/usr/bin/env python3
"""
TCP/UDP echo server boilerplate.

Implements a small benchmark server for CS417 Assignment 1:
- TCP: accept `clients` connections; for each, echo `requests` payloads of size `payload_bytes`.
- UDP: receive and echo `clients * requests` datagrams of size `payload_bytes` (best-effort).

Logging format: JSON Lines (one JSON object per line) to the --log path.
"""
import argparse
import json
import os
import socket
import threading
import time
from typing import Optional

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

##### Required functions to implement. Do not change signatures. #####
def run_tcp_server(bind: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """Run the TCP server benchmark."""
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    start_wall = now_wall()
    start_mono = now_mono()

    with open(log_path, "w", encoding="utf-8") as fp:
        log_event(fp, {
            "ts_wall": start_wall,
            "ts_mono": start_mono,
            "role": "server",
            "proto": "tcp",
            "event": "start",
            "bind": bind,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
        })

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((bind, port))
            srv.listen(max(128, clients))
            srv.settimeout(1.0)

            served_lock = threading.Lock()
            served_connections = 0

            def handle_conn(conn: socket.socket, addr, conn_id: int) -> None:
                nonlocal served_connections
                conn.settimeout(10.0)
                log_event(fp, {
                    "ts_wall": now_wall(),
                    "ts_mono": now_mono(),
                    "role": "server",
                    "proto": "tcp",
                    "event": "accept",
                    "conn_id": conn_id,
                    "peer": f"{addr[0]}:{addr[1]}",
                })
                ok_reqs = 0
                try:
                    for i in range(requests):
                        data = recvall(conn, payload_bytes)
                        conn.sendall(data)
                        ok_reqs += 1
                        log_event(fp, {
                            "ts_wall": now_wall(),
                            "ts_mono": now_mono(),
                            "role": "server",
                            "proto": "tcp",
                            "event": "echo",
                            "conn_id": conn_id,
                            "seq": i,
                            "payload_bytes": payload_bytes,
                        })
                except Exception as e:
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": now_mono(),
                        "role": "server",
                        "proto": "tcp",
                        "event": "conn_error",
                        "conn_id": conn_id,
                        "error": repr(e),
                        "requests_completed": ok_reqs,
                    })
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    with served_lock:
                        served_connections += 1
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": now_mono(),
                        "role": "server",
                        "proto": "tcp",
                        "event": "close",
                        "conn_id": conn_id,
                        "requests_completed": ok_reqs,
                    })

            threads = []
            conn_id = 0
            while True:
                with served_lock:
                    if served_connections >= clients:
                        break
                try:
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                except Exception as e:
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": now_mono(),
                        "role": "server",
                        "proto": "tcp",
                        "event": "accept_error",
                        "error": repr(e),
                    })
                    continue

                t = threading.Thread(target=handle_conn, args=(conn, addr, conn_id), daemon=True)
                conn_id += 1
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=5.0)

        finally:
            try:
                srv.close()
            except Exception:
                pass

        end_mono = now_mono()
        end_wall = now_wall()
        log_event(fp, {
            "ts_wall": end_wall,
            "ts_mono": end_mono,
            "role": "server",
            "proto": "tcp",
            "event": "done",
            "elapsed_s": end_mono - start_mono,
        })

def run_udp_server(bind: str, port: int, log_path: str,
                   payload_bytes: int, requests: int, clients: int) -> None:
    """Run the UDP server benchmark."""
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    start_wall = now_wall()
    start_mono = now_mono()
    expected = clients * requests  # expected datagrams (best effort)

    with open(log_path, "w", encoding="utf-8") as fp:
        log_event(fp, {
            "ts_wall": start_wall,
            "ts_mono": start_mono,
            "role": "server",
            "proto": "udp",
            "event": "start",
            "bind": bind,
            "port": port,
            "payload_bytes": payload_bytes,
            "requests": requests,
            "clients": clients,
            "expected_datagrams": expected,
        })

        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((bind, port))
            srv.settimeout(1.0)

            count = 0
            while count < expected:
                try:
                    data, addr = srv.recvfrom(max(2048, payload_bytes + 64))
                except socket.timeout:
                    continue
                except Exception as e:
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": now_mono(),
                        "role": "server",
                        "proto": "udp",
                        "event": "recv_error",
                        "error": repr(e),
                    })
                    continue

                # Echo back unchanged
                try:
                    srv.sendto(data, addr)
                    count += 1
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": now_mono(),
                        "role": "server",
                        "proto": "udp",
                        "event": "echo",
                        "count": count,
                        "peer": f"{addr[0]}:{addr[1]}",
                        "payload_len": len(data),
                    })
                except Exception as e:
                    log_event(fp, {
                        "ts_wall": now_wall(),
                        "ts_mono": now_mono(),
                        "role": "server",
                        "proto": "udp",
                        "event": "send_error",
                        "peer": f"{addr[0]}:{addr[1]}",
                        "error": repr(e),
                    })

        finally:
            try:
                srv.close()
            except Exception:
                pass

        end_mono = now_mono()
        end_wall = now_wall()
        log_event(fp, {
            "ts_wall": end_wall,
            "ts_mono": end_mono,
            "role": "server",
            "proto": "udp",
            "event": "done",
            "elapsed_s": end_mono - start_mono,
            "received_datagrams": expected,
        })

def parse_args() -> argparse.Namespace:
    """Parse CLI args.

    Required flags:
    - --proto tcp|udp
    - --bind
    - --port
    - --payload-bytes
    - --requests
    - --clients
    - --log
    """
    p = argparse.ArgumentParser(description="TCP/UDP echo server for benchmarking")
    p.add_argument("--proto", choices=["tcp", "udp"], required=True)
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--port", type=int, default=5001)
    p.add_argument("--payload-bytes", type=int, default=1)
    p.add_argument("--requests", type=int, default=1)
    p.add_argument("--clients", type=int, default=1)
    p.add_argument("--log", required=True)
    return p.parse_args()

def main() -> None:
    """Entry point."""
    args = parse_args()
    if args.proto == "tcp":
        run_tcp_server(args.bind, args.port, args.log, args.payload_bytes, args.requests, args.clients)
    else:
        run_udp_server(args.bind, args.port, args.log, args.payload_bytes, args.requests, args.clients)

if __name__ == "__main__":
    main()
