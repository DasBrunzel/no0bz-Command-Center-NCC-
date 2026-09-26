#!/usr/bin/env python3
"""
no0bz Command Center (NCC) - Version v3.8.2
High-Performance Single-File System Monitor & Multi-PC Hub
FastAPI, WebSockets, NVML, DuckDB, File Transfer & HTML/JS Frontend
"""

import os
import sys
import time
import json
import shutil
import socket
import platform
import asyncio
import threading
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# Optional: nvidia-ml-py or pynvml for NVIDIA GPU
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")
warnings.filterwarnings("ignore", message=".*pynvml package is deprecated.*")

try:
    import nvidia_ml_py as pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    try:
        import pynvml
        PYNVML_AVAILABLE = True
    except ImportError:
        PYNVML_AVAILABLE = False

# Optional: duckdb for time-series logging
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

# Optional: python-multipart for file upload forms
try:
    import multipart
    MULTIPART_AVAILABLE = True
except ImportError:
    MULTIPART_AVAILABLE = False

from contextlib import asynccontextmanager

VERSION = "v3.8.2"
PORT = 8350
LHM_URL = "http://127.0.0.1:8085/data.json"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "ncc_config.json")
CACHE_FILE = os.path.join(BASE_DIR, "ncc_system_cache.json")

# Separate Storage Directories for Server-Betrieb vs Standalone (Lokal)
SERVER_DATA_DIR = os.path.join(BASE_DIR, "data", "server")
LOCAL_DATA_DIR = os.path.join(BASE_DIR, "data", "local")
SERVER_VAULT_DIR = os.path.join(SERVER_DATA_DIR, "vault")
LOCAL_VAULT_DIR = os.path.join(LOCAL_DATA_DIR, "vault")
LEGACY_UPLOAD_DIR = os.path.join(BASE_DIR, "ncc_uploads")

os.makedirs(SERVER_VAULT_DIR, exist_ok=True)
os.makedirs(LOCAL_VAULT_DIR, exist_ok=True)
os.makedirs(LEGACY_UPLOAD_DIR, exist_ok=True)

def load_ncc_config() -> Dict[str, Any]:
    cfg = {
        "server_mode": "host",
        "client_server_url": "192.168.1.100:8350",
        "version": VERSION
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_ncc_config(cfg: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[CONFIG] Error saving config: {e}")

initial_cfg = load_ncc_config()
server_mode = initial_cfg.get("server_mode", "host")
client_server_url = initial_cfg.get("client_server_url", "192.168.1.100:8350")

def get_active_vault_dir() -> str:
    """Im Server-Betrieb serverseitig in SERVER_VAULT_DIR; im Standalone Modus lokal in LOCAL_VAULT_DIR."""
    if server_mode == "host":
        return SERVER_VAULT_DIR
    elif server_mode == "local":
        return LOCAL_VAULT_DIR
    else:
        return LOCAL_VAULT_DIR

def get_active_db_path() -> str:
    """Im Server-Betrieb: data/server/no0bz_server.duckdb; im Standalone Modus: data/local/no0bz_local.duckdb."""
    if server_mode == "host":
        return os.path.join(SERVER_DATA_DIR, "no0bz_server.duckdb")
    elif server_mode == "local":
        return os.path.join(LOCAL_DATA_DIR, "no0bz_local.duckdb")
    else:
        return os.path.join(LOCAL_DATA_DIR, "no0bz_local.duckdb")

# Thread-safe locks
data_lock = threading.Lock()
chat_lock = threading.Lock()
nodes_lock = threading.Lock()
db_lock = threading.Lock()

# Connected Multi-PC Nodes store
connected_nodes: Dict[str, Dict[str, Any]] = {
    "host_node": {
        "id": "host_node",
        "pc_name": os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "no0bz-RIG"),
        "display_name": "Host Workstation",
        "role": "Master Server & GPU Station",
        "avatar": "👑",
        "ip": "127.0.0.1",
        "os": f"{platform.system()} {platform.release()}",
        "ping_ms": 1,
        "cpu_load": 18.5,
        "ram_percent": 34.2,
        "net_recv_mbps": 12.4,
        "net_sent_mbps": 4.8,
        "is_host": True,
        "last_seen": "Jetzt"
    },
    "client_rig": {
        "id": "client_rig",
        "pc_name": "PC-GAMING-RIG",
        "display_name": "Gaming Beast",
        "role": "RTX 4090 Gaming Node",
        "avatar": "🎮",
        "ip": "192.168.1.142",
        "os": "Windows 11 Pro 64-bit",
        "ping_ms": 4,
        "cpu_load": 42.1,
        "ram_percent": 58.6,
        "net_recv_mbps": 45.8,
        "net_sent_mbps": 8.2,
        "is_host": False,
        "last_seen": "vor 2 Sek"
    },
    "client_linux": {
        "id": "client_linux",
        "pc_name": "DEV-SERVER-LINUX",
        "display_name": "Linux HPC",
        "role": "CachyOS Kernel Builder",
        "avatar": "🚀",
        "ip": "192.168.1.178",
        "os": "Linux 6.10-cachyos x86_64",
        "ping_ms": 7,
        "cpu_load": 8.4,
        "ram_percent": 21.0,
        "net_recv_mbps": 1.2,
        "net_sent_mbps": 0.4,
        "is_host": False,
        "last_seen": "vor 5 Sek"
    }
}

# Fast-Boot Hardware & System Cache Probe
def probe_system_profile() -> Dict[str, Any]:
    hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "no0bz-RIG")
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # Disk layout
    disk_info = []
    try:
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt' and ('cdrom' in part.opts or part.fstype == ''):
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_info.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024**3), 1)
                })
            except (PermissionError, OSError):
                continue
    except Exception:
        pass

    # Network adapters
    net_ifaces = []
    try:
        addrs = psutil.net_if_addrs()
        for iface_name, addr_list in addrs.items():
            for a in addr_list:
                if a.family == socket.AF_INET and not a.address.startswith("127."):
                    net_ifaces.append({"name": iface_name, "ip": a.address})
    except Exception:
        pass

    return {
        "hostname": hostname,
        "os_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu_model": platform.processor() or "AMD/Intel x86_64 Core",
        "cpu_logical_cores": psutil.cpu_count(logical=True) or 8,
        "cpu_physical_cores": psutil.cpu_count(logical=False) or 4,
        "cpu_freq_max_mhz": round(cpu_freq.max, 0) if cpu_freq else 4200.0,
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "swap_total_gb": round(swap.total / (1024**3), 1),
        "disks": disk_info,
        "network_interfaces": net_ifaces,
        "gpu_name": "NVIDIA RTX Series / Integrated Core",
        "python_version": platform.python_version(),
        "ncc_version": VERSION,
        "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def get_or_create_system_cache(force_refresh: bool = False) -> Dict[str, Any]:
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["from_cache"] = True
                return data
        except Exception as e:
            print(f"[CACHE] Read error, reprobing: {e}")
    
    profile = probe_system_profile()
    profile["from_cache"] = False
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        print(f"[FAST-BOOT] System cache written to {CACHE_FILE}")
    except Exception as e:
        print(f"[CACHE] Write warning: {e}")
    return profile

# Initial fast-boot probe call
system_hardware_profile = get_or_create_system_cache()

live_data: Dict[str, Any] = {
    "version": VERSION,
    "timestamp": time.time(),
    "hostname": os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "no0bz-RIG"),
    "cpu": {
        "load": 0.0,
        "cores": [],
        "freq_current": 0.0,
        "freq_max": 0.0,
        "count": psutil.cpu_count(logical=True) or 8,
        "power_w": None,
        "temp_c": None
    },
    "ram": {
        "total_gb": 0.0,
        "used_gb": 0.0,
        "percent": 0.0,
        "swap_total_gb": 0.0,
        "swap_used_gb": 0.0,
        "swap_percent": 0.0
    },
    "gpu": {
        "name": "NVIDIA RTX / Unified Core",
        "load": 0.0,
        "vram_total_gb": 0.0,
        "vram_used_gb": 0.0,
        "vram_percent": 0.0,
        "temp_c": None,
        "power_w": None
    },
    "disks": [],
    "total_disk_io": {
        "read_mbs": 0.0,
        "write_mbs": 0.0
    },
    "network": {
        "sent_mbps": 0.0,
        "recv_mbps": 0.0,
        "total_sent_gb": 0.0,
        "total_recv_gb": 0.0
    },
    "fans": [],
    "lhm_active": False,
    "uptime_seconds": 0
}

# Chat & File Transfer State
chat_messages: List[Dict[str, Any]] = [
    {
        "id": "msg_init_1",
        "sender": "PC-A (Main Workstation)",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "type": "prompt",
        "title": "System Prompt • PyTorch CUDA Optimizer",
        "content": "You are an expert HPC engineer. Optimize this PyTorch training loop for dual RTX 4090 with NVLink, FP8 mixed-precision via TransformerEngine, and zero-redundancy optimizer (ZeRO-3). Ensure NCCL p2p bandwidth reaches >= 45 GB/s.",
        "tokens": 48,
        "attachments": []
    }
]

# Database manager
class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_active_db_path()
        self.conn = None
        self.connect()

    def connect(self):
        if DUCKDB_AVAILABLE:
            try:
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                with db_lock:
                    self.conn = duckdb.connect(self.db_path, read_only=False)
                    self.init_db()
                print(f"[DB] Connected to DuckDB: {self.db_path} (Mode: {server_mode})")
            except Exception as e:
                print(f"[DB] Init warning on {self.db_path}: {e}")
                self.conn = None

    def switch_mode(self, new_mode: str):
        target_path = get_active_db_path()
        if target_path == self.db_path and self.conn:
            return
        with db_lock:
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None
            self.db_path = target_path
        self.connect()

    def init_db(self):
        if not self.conn:
            return
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    ts TIMESTAMP PRIMARY KEY,
                    cpu_load DOUBLE,
                    ram_percent DOUBLE,
                    gpu_load DOUBLE,
                    gpu_temp DOUBLE,
                    net_recv_mbps DOUBLE,
                    net_sent_mbps DOUBLE,
                    disk_read_mbs DOUBLE,
                    disk_write_mbs DOUBLE
                );
            """)
            # Multi-PC Node Metrics persistence table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS node_metrics (
                    ts TIMESTAMP,
                    node_id VARCHAR,
                    pc_name VARCHAR,
                    display_name VARCHAR,
                    cpu_load DOUBLE,
                    ram_percent DOUBLE,
                    net_recv_mbps DOUBLE,
                    net_sent_mbps DOUBLE,
                    is_host BOOLEAN
                );
            """)
            # Chat messages table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id VARCHAR PRIMARY KEY,
                    sender VARCHAR,
                    timestamp VARCHAR,
                    msg_type VARCHAR,
                    title VARCHAR,
                    content VARCHAR,
                    tokens INTEGER,
                    words INTEGER,
                    attachments_json VARCHAR,
                    created_at TIMESTAMP
                );
            """)
            # Chat files table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_files (
                    id VARCHAR PRIMARY KEY,
                    filename VARCHAR,
                    filepath VARCHAR,
                    size_bytes BIGINT,
                    ext VARCHAR,
                    is_image BOOLEAN,
                    sender VARCHAR,
                    storage_mode VARCHAR,
                    uploaded_at TIMESTAMP
                );
            """)
        except Exception as e:
            print(f"[DB] Table creation error: {e}")

    def insert_metric(self, snapshot: Dict[str, Any]):
        if not self.conn:
            return
        try:
            now = datetime.now()
            with db_lock:
                self.conn.execute("""
                    INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now,
                    snapshot["cpu"]["load"],
                    snapshot["ram"]["percent"],
                    snapshot["gpu"]["load"],
                    snapshot["gpu"]["temp_c"] or 0.0,
                    snapshot["network"]["recv_mbps"],
                    snapshot["network"]["sent_mbps"],
                    snapshot["total_disk_io"]["read_mbs"],
                    snapshot["total_disk_io"]["write_mbs"]
                ))
                # Also log as host in node_metrics
                hostname = snapshot.get("hostname", "no0bz-RIG")
                self.conn.execute("""
                    INSERT INTO node_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now,
                    "host_node",
                    hostname,
                    "Host Workstation",
                    float(snapshot["cpu"]["load"] or 0),
                    float(snapshot["ram"]["percent"] or 0),
                    float(snapshot["network"]["recv_mbps"] or 0),
                    float(snapshot["network"]["sent_mbps"] or 0),
                    True
                ))
                # Purge data older than 24h
                cutoff = now - timedelta(hours=24)
                self.conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
                self.conn.execute("DELETE FROM node_metrics WHERE ts < ?", (cutoff,))
        except Exception as e:
            print(f"[DB] Insert error: {e}")

    def insert_node_metric(self, node_id: str, pc_name: str, display_name: str,
                           cpu_load: float, ram_percent: float,
                           net_recv_mbps: float, net_sent_mbps: float, is_host: bool = False):
        if not self.conn:
            return
        try:
            now = datetime.now()
            with db_lock:
                self.conn.execute("""
                    INSERT INTO node_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now,
                    node_id,
                    pc_name,
                    display_name,
                    float(cpu_load or 0),
                    float(ram_percent or 0),
                    float(net_recv_mbps or 0),
                    float(net_sent_mbps or 0),
                    bool(is_host)
                ))
        except Exception as e:
            print(f"[DB] Node insert error: {e}")

    def save_chat_message(self, msg: Dict[str, Any]):
        if not self.conn:
            return
        try:
            now = datetime.now()
            att_json = json.dumps(msg.get("attachments", []))
            with db_lock:
                self.conn.execute("""
                    INSERT OR REPLACE INTO chat_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg.get("id"),
                    msg.get("sender", "PC-User"),
                    msg.get("timestamp", now.strftime("%H:%M:%S")),
                    msg.get("type", "prompt"),
                    msg.get("title", ""),
                    msg.get("content", ""),
                    int(msg.get("tokens", 0)),
                    int(msg.get("words", 0)),
                    att_json,
                    now
                ))
        except Exception as e:
            print(f"[DB] Save chat error: {e}")

    def load_chat_messages(self, limit: int = 300) -> List[Dict[str, Any]]:
        default_seed = [
            {
                "id": "msg_init_1",
                "sender": "PC-A (Main Workstation)",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "type": "prompt",
                "title": "System Prompt • PyTorch CUDA Optimizer",
                "content": "You are an expert HPC engineer. Optimize this PyTorch training loop for dual RTX 4090 with NVLink, FP8 mixed-precision via TransformerEngine, and zero-redundancy optimizer (ZeRO-3). Ensure NCCL p2p bandwidth reaches >= 45 GB/s.",
                "tokens": 48,
                "words": 31,
                "attachments": []
            }
        ]
        if not self.conn:
            return default_seed
        try:
            with db_lock:
                res = self.conn.execute(f"""
                    SELECT id, sender, timestamp, msg_type, title, content, tokens, words, attachments_json
                    FROM chat_messages
                    ORDER BY created_at ASC
                    LIMIT {limit}
                """).fetchall()
            if not res:
                self.save_chat_message(default_seed[0])
                return default_seed
            
            loaded = []
            for r in res:
                att = []
                try:
                    att = json.loads(r[8]) if r[8] else []
                except Exception:
                    pass
                loaded.append({
                    "id": r[0],
                    "sender": r[1],
                    "timestamp": r[2],
                    "type": r[3],
                    "title": r[4],
                    "content": r[5],
                    "tokens": r[6],
                    "words": r[7],
                    "attachments": att
                })
            return loaded
        except Exception as e:
            print(f"[DB] Load chat error: {e}")
            return default_seed

    def save_chat_file(self, file_info: Dict[str, Any]):
        if not self.conn:
            return
        try:
            now = datetime.now()
            with db_lock:
                self.conn.execute("""
                    INSERT OR REPLACE INTO chat_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_info.get("id", f"file_{int(time.time()*1000)}"),
                    file_info.get("name", "unnamed"),
                    file_info.get("path", ""),
                    int(file_info.get("size", 0)),
                    file_info.get("ext", "FILE"),
                    bool(file_info.get("is_image", False)),
                    file_info.get("sender", "PC-User"),
                    server_mode,
                    now
                ))
        except Exception as e:
            print(f"[DB] Save chat file error: {e}")

    def delete_chat_file(self, filename: str):
        if not self.conn:
            return
        try:
            with db_lock:
                self.conn.execute("DELETE FROM chat_files WHERE filename = ?", (filename,))
        except Exception as e:
            print(f"[DB] Delete chat file error: {e}")

    def query_history(self, limit: int = 120) -> List[Dict[str, Any]]:
        if not self.conn:
            return []
        try:
            with db_lock:
                res = self.conn.execute(f"""
                    SELECT ts, cpu_load, ram_percent, gpu_load, gpu_temp, net_recv_mbps, net_sent_mbps, disk_read_mbs, disk_write_mbs
                    FROM metrics
                    ORDER BY ts DESC
                    LIMIT {limit}
                """).fetchall()
            history = []
            for r in reversed(res):
                history.append({
                    "time": r[0].strftime("%H:%M:%S") if hasattr(r[0], "strftime") else str(r[0]),
                    "cpu": float(r[1] or 0),
                    "ram": float(r[2] or 0),
                    "gpu": float(r[3] or 0),
                    "gpu_temp": float(r[4] or 0),
                    "recv": float(r[5] or 0),
                    "sent": float(r[6] or 0),
                    "disk_read": float(r[7] or 0),
                    "disk_write": float(r[8] or 0),
                })
            return history
        except Exception as e:
            print(f"[DB] Query history error: {e}")
            return []

db_mgr = DatabaseManager()
chat_messages = db_mgr.load_chat_messages()

# Background data collector
class DataCollector(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.time()
        self.prev_disk_io_perdisk = {}
        try:
            self.prev_disk_io_perdisk = psutil.disk_io_counters(perdisk=True) or {}
        except Exception:
            pass

    def run(self):
        # Initialize NVML
        nvml_handle = None
        if PYNVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                nvml_handle = None

        while self.running:
            try:
                now_time = time.time()
                dt = max(now_time - self.prev_time, 0.1)

                # CPU Metrics
                cpu_load = psutil.cpu_percent(interval=None)
                cores_load = psutil.cpu_percent(interval=None, percpu=True)
                freq = psutil.cpu_freq()
                freq_curr = round(freq.current, 1) if freq else 3600.0
                freq_max = round(freq.max, 1) if freq and freq.max else 5400.0

                # RAM Metrics
                ram = psutil.virtual_memory()
                swap = psutil.swap_memory()
                ram_total = round(ram.total / (1024**3), 2)
                ram_used = round(ram.used / (1024**3), 2)
                swap_total = round(swap.total / (1024**3), 2)
                swap_used = round(swap.used / (1024**3), 2)

                # GPU Metrics
                gpu_load = 0.0
                gpu_vram_total = 0.0
                gpu_vram_used = 0.0
                gpu_vram_pct = 0.0
                gpu_temp = None
                gpu_power = None
                gpu_name = "NVIDIA RTX System Core"

                if nvml_handle:
                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(nvml_handle)
                        gpu_load = float(util.gpu)
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(nvml_handle)
                        gpu_vram_total = round(mem_info.total / (1024**3), 2)
                        gpu_vram_used = round(mem_info.used / (1024**3), 2)
                        gpu_vram_pct = round((mem_info.used / mem_info.total) * 100, 1)
                        gpu_temp = pynvml.nvmlDeviceGetTemperature(nvml_handle, pynvml.NVML_TEMPERATURE_GPU)
                        gpu_power = round(pynvml.nvmlDeviceGetPowerUsage(nvml_handle) / 1000.0, 1)
                        raw_name = pynvml.nvmlDeviceGetName(nvml_handle)
                        gpu_name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else raw_name
                    except Exception:
                        pass

                # Per-Disk I/O and Capacity
                current_disk_io_perdisk = {}
                try:
                    current_disk_io_perdisk = psutil.disk_io_counters(perdisk=True) or {}
                except Exception:
                    pass

                disks_info = []
                total_read_bytes_sec = 0.0
                total_write_bytes_sec = 0.0

                try:
                    partitions = psutil.disk_partitions(all=False)
                    seen_mounts = set()

                    for p in partitions:
                        if p.mountpoint in seen_mounts or "cdrom" in p.opts:
                            continue
                        seen_mounts.add(p.mountpoint)
                        try:
                            usage = psutil.disk_usage(p.mountpoint)
                            dev_name = os.path.basename(p.device)
                            
                            # Match per-disk I/O
                            matched_read_mbs = 0.0
                            matched_write_mbs = 0.0
                            matched_key = None

                            if dev_name in current_disk_io_perdisk:
                                matched_key = dev_name
                            else:
                                for k in current_disk_io_perdisk.keys():
                                    if k in dev_name or dev_name in k or (p.mountpoint.startswith(k)):
                                        matched_key = k
                                        break

                            if matched_key and matched_key in self.prev_disk_io_perdisk:
                                curr_d = current_disk_io_perdisk[matched_key]
                                prev_d = self.prev_disk_io_perdisk[matched_key]
                                r_bytes = max(curr_d.read_bytes - prev_d.read_bytes, 0)
                                w_bytes = max(curr_d.write_bytes - prev_d.write_bytes, 0)
                                matched_read_mbs = round((r_bytes / dt) / (1024 * 1024), 1)
                                matched_write_mbs = round((w_bytes / dt) / (1024 * 1024), 1)
                                total_read_bytes_sec += (r_bytes / dt)
                                total_write_bytes_sec += (w_bytes / dt)

                            disks_info.append({
                                "device": p.device,
                                "mount": p.mountpoint,
                                "fstype": p.fstype,
                                "total_gb": round(usage.total / (1024**3), 1),
                                "used_gb": round(usage.used / (1024**3), 1),
                                "free_gb": round(usage.free / (1024**3), 1),
                                "percent": usage.percent,
                                "read_mbs": matched_read_mbs,
                                "write_mbs": matched_write_mbs
                            })
                        except Exception:
                            continue
                except Exception:
                    pass

                self.prev_disk_io_perdisk = current_disk_io_perdisk

                # Fallback total I/O if per-disk match didn't catch all
                total_read_mbs = round(total_read_bytes_sec / (1024 * 1024), 1)
                total_write_mbs = round(total_write_bytes_sec / (1024 * 1024), 1)

                # Network I/O
                curr_net = psutil.net_io_counters()
                net_sent_mbps = round(((curr_net.bytes_sent - self.prev_net.bytes_sent) * 8) / (dt * 1_000_000), 2)
                net_recv_mbps = round(((curr_net.bytes_recv - self.prev_net.bytes_recv) * 8) / (dt * 1_000_000), 2)
                self.prev_net = curr_net
                self.prev_time = now_time

                # LHM REST Fallback
                lhm_active = False
                cpu_power = None
                cpu_temp = None
                fans = []

                try:
                    req = urllib.request.Request(LHM_URL, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=0.4) as response:
                        if response.status == 200:
                            lhm_active = True
                            data = json.loads(response.read().decode())
                            def parse_lhm(node):
                                nonlocal cpu_power, cpu_temp, fans
                                text = node.get("Text", "")
                                if "CPU Package" in text and "Power" in node.get("Type", ""):
                                    val = node.get("Value", "").split()[0].replace(",", ".")
                                    try: cpu_power = float(val)
                                    except ValueError: pass
                                if "Core (Tctl/Tdie)" in text or "CPU Package" in text:
                                    if "Temperature" in node.get("Type", ""):
                                        val = node.get("Value", "").split()[0].replace(",", ".")
                                        try: cpu_temp = float(val)
                                        except ValueError: pass
                                if "Fan" in node.get("Type", "") or "RPM" in node.get("Value", ""):
                                    val = node.get("Value", "").split()[0].replace(",", ".")
                                    try:
                                        rpm = int(float(val))
                                        if rpm > 0:
                                            fans.append({"name": text, "rpm": rpm})
                                    except ValueError: pass
                                for child in node.get("Children", []):
                                    parse_lhm(child)
                            parse_lhm(data)
                except Exception:
                    pass

                # Thermal fallback if psutil has sensors
                if cpu_temp is None and hasattr(psutil, "sensors_temperatures"):
                    try:
                        temps = psutil.sensors_temperatures()
                        for k, entries in temps.items():
                            if entries and ("core" in k.lower() or "cpu" in k.lower() or "k10temp" in k.lower()):
                                cpu_temp = entries[0].current
                                break
                    except Exception:
                        pass

                uptime = int(time.time() - psutil.boot_time())

                # Update state safely
                with data_lock:
                    live_data["timestamp"] = now_time
                    live_data["cpu"]["load"] = cpu_load
                    live_data["cpu"]["cores"] = cores_load
                    live_data["cpu"]["freq_current"] = freq_curr
                    live_data["cpu"]["freq_max"] = freq_max
                    live_data["cpu"]["power_w"] = cpu_power
                    live_data["cpu"]["temp_c"] = cpu_temp
                    live_data["ram"]["total_gb"] = ram_total
                    live_data["ram"]["used_gb"] = ram_used
                    live_data["ram"]["percent"] = ram.percent
                    live_data["ram"]["swap_total_gb"] = swap_total
                    live_data["ram"]["swap_used_gb"] = swap_used
                    live_data["ram"]["swap_percent"] = swap.percent
                    live_data["gpu"]["load"] = gpu_load
                    live_data["gpu"]["name"] = gpu_name
                    live_data["gpu"]["vram_total_gb"] = gpu_vram_total
                    live_data["gpu"]["vram_used_gb"] = gpu_vram_used
                    live_data["gpu"]["vram_percent"] = gpu_vram_pct
                    live_data["gpu"]["temp_c"] = gpu_temp
                    live_data["gpu"]["power_w"] = gpu_power
                    live_data["disks"] = disks_info
                    live_data["total_disk_io"]["read_mbs"] = total_read_mbs
                    live_data["total_disk_io"]["write_mbs"] = total_write_mbs
                    live_data["network"]["sent_mbps"] = net_sent_mbps
                    live_data["network"]["recv_mbps"] = net_recv_mbps
                    live_data["network"]["total_sent_gb"] = round(curr_net.bytes_sent / (1024**3), 2)
                    live_data["network"]["total_recv_gb"] = round(curr_net.bytes_recv / (1024**3), 2)
                    live_data["fans"] = fans
                    live_data["lhm_active"] = lhm_active
                    live_data["uptime_seconds"] = uptime

                # Time-series record to DuckDB
                db_mgr.insert_metric(live_data)

            except Exception as e:
                print(f"[Collector Error] {e}")

            time.sleep(1.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    collector = DataCollector()
    collector.start()
    yield

# FastAPI Application
app = FastAPI(title="no0bz Command Center", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_websockets: List[WebSocket] = []

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        while True:
            with data_lock:
                snapshot = dict(live_data)
            
            # Synchronize host node live metrics
            with nodes_lock:
                if "host_node" in connected_nodes:
                    connected_nodes["host_node"]["cpu_load"] = snapshot["cpu"]["load"]
                    connected_nodes["host_node"]["ram_percent"] = snapshot["ram"]["percent"]
                    connected_nodes["host_node"]["net_recv_mbps"] = snapshot["network"]["recv_mbps"]
                    connected_nodes["host_node"]["net_sent_mbps"] = snapshot["network"]["sent_mbps"]
                    connected_nodes["host_node"]["pc_name"] = snapshot.get("hostname", "no0bz-RIG")

                snapshot["multipc"] = {
                    "mode": server_mode,
                    "server_active": True,
                    "server_port": PORT,
                    "client_server_url": client_server_url,
                    "connected_count": len(connected_nodes),
                    "nodes": list(connected_nodes.values())
                }

            await websocket.send_text(json.dumps(snapshot))
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, asyncio.CancelledError):
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

# ================= FAST-BOOT HARDWARE PROFILE ENDPOINTS =================
@app.get("/api/system/profile")
def get_system_profile_endpoint():
    return get_or_create_system_cache(force_refresh=False)

@app.post("/api/system/profile/reprobe")
def reprobe_system_profile_endpoint():
    return get_or_create_system_cache(force_refresh=True)

# ================= MULTI-PC HUB & CLUSTER ENDPOINTS =================
@app.get("/api/nodes")
def get_connected_nodes():
    with nodes_lock:
        return {
            "server_mode": server_mode,
            "server_port": PORT,
            "connected_count": len(connected_nodes),
            "nodes": list(connected_nodes.values())
        }

@app.post("/api/nodes/register")
def register_node(payload: Dict[str, Any]):
    node_id = payload.get("id") or f"client_{int(time.time()*1000)}"
    pc_name = payload.get("pc_name") or "Remote-PC"
    display_name = payload.get("display_name") or pc_name
    role = payload.get("role") or "Client Node"
    avatar = payload.get("avatar") or "💻"
    ip = payload.get("ip") or "192.168.1.x"
    os_info = payload.get("os") or "Unknown OS"

    with nodes_lock:
        connected_nodes[node_id] = {
            "id": node_id,
            "pc_name": pc_name,
            "display_name": display_name,
            "role": role,
            "avatar": avatar,
            "ip": ip,
            "os": os_info,
            "ping_ms": payload.get("ping_ms", 12),
            "cpu_load": float(payload.get("cpu_load", 0.0)),
            "ram_percent": float(payload.get("ram_percent", 0.0)),
            "net_recv_mbps": float(payload.get("net_recv_mbps", 0.0)),
            "net_sent_mbps": float(payload.get("net_sent_mbps", 0.0)),
            "is_host": False,
            "last_seen": "Jetzt"
        }
    return {"status": "ok", "node_id": node_id, "server_mode": server_mode}

@app.post("/api/nodes/telemetry")
def receive_node_telemetry(payload: Dict[str, Any]):
    node_id = payload.get("node_id")
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id required")

    cpu_load = float(payload.get("cpu_load", 0.0))
    ram_percent = float(payload.get("ram_percent", 0.0))
    net_recv_mbps = float(payload.get("net_recv_mbps", 0.0))
    net_sent_mbps = float(payload.get("net_sent_mbps", 0.0))
    pc_name = payload.get("pc_name", "Remote-Node")
    display_name = payload.get("display_name", pc_name)

    with nodes_lock:
        if node_id in connected_nodes:
            node = connected_nodes[node_id]
            node["cpu_load"] = cpu_load
            node["ram_percent"] = ram_percent
            node["net_recv_mbps"] = net_recv_mbps
            node["net_sent_mbps"] = net_sent_mbps
            node["last_seen"] = "Jetzt"
            if "ping_ms" in payload:
                node["ping_ms"] = payload["ping_ms"]
        else:
            connected_nodes[node_id] = {
                "id": node_id,
                "pc_name": pc_name,
                "display_name": display_name,
                "role": payload.get("role", "Client Node"),
                "avatar": payload.get("avatar", "💻"),
                "ip": payload.get("ip", "192.168.1.x"),
                "os": payload.get("os", "Client OS"),
                "ping_ms": payload.get("ping_ms", 10),
                "cpu_load": cpu_load,
                "ram_percent": ram_percent,
                "net_recv_mbps": net_recv_mbps,
                "net_sent_mbps": net_sent_mbps,
                "is_host": False,
                "last_seen": "Jetzt"
            }

    # Store telemetry persistently in DuckDB on Server
    db_mgr.insert_node_metric(
        node_id=node_id,
        pc_name=pc_name,
        display_name=display_name,
        cpu_load=cpu_load,
        ram_percent=ram_percent,
        net_recv_mbps=net_recv_mbps,
        net_sent_mbps=net_sent_mbps,
        is_host=False
    )
    return {"status": "recorded"}

@app.get("/api/multipc/mode")
def get_multipc_mode():
    vault_dir = get_active_vault_dir()
    db_path = get_active_db_path()
    storage_type = "serverseitig" if server_mode == "host" else "lokal"
    desc = (
        "Server-Betrieb: Speicherung der Chat-Dateien & DuckDB-Datenbankhaltung erfolgt ausschließlich serverseitig."
        if server_mode == "host" else
        "Standalone Modus: Speicherung der Chat-Dateien & DuckDB-Datenbankhaltung erfolgt ausschließlich lokal."
        if server_mode == "local" else
        "Client Node: Speicherung der Chat-Dateien & DuckDB-Datenbankhaltung erfolgt ausschließlich auf dem Server."
    )
    return {
        "status": "ok",
        "mode": server_mode,
        "client_server_url": client_server_url,
        "storage_type": storage_type,
        "vault_dir": vault_dir,
        "db_path": db_path,
        "description": desc
    }

@app.post("/api/multipc/mode")
def set_multipc_mode(payload: Dict[str, Any]):
    global server_mode, client_server_url
    new_mode = payload.get("mode")
    if new_mode in ["local", "host", "client"]:
        server_mode = new_mode
    if "client_server_url" in payload:
        client_server_url = payload["client_server_url"]

    save_ncc_config({
        "server_mode": server_mode,
        "client_server_url": client_server_url,
        "version": VERSION
    })

    db_mgr.switch_mode(server_mode)
    os.makedirs(get_active_vault_dir(), exist_ok=True)

    storage_type = "serverseitig" if server_mode == "host" else "lokal"
    return {
        "status": "ok",
        "mode": server_mode,
        "client_server_url": client_server_url,
        "storage_type": storage_type,
        "vault_dir": get_active_vault_dir(),
        "db_path": get_active_db_path()
    }

# Broadcast helper for chat & file events
async def broadcast_chat_event(event_type: str, data: Any):
    msg = json.dumps({"type": event_type, "data": data})
    for ws in list(connected_websockets):
        try:
            await ws.send_text(msg)
        except Exception:
            pass

@app.get("/api/processes")
def get_processes():
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            info = p.info
            procs.append({
                "pid": info['pid'],
                "name": info['name'] or 'unknown',
                "cpu": round(info['cpu_percent'] or 0.0, 1),
                "ram": round(info['memory_percent'] or 0.0, 1),
                "status": info['status'] or 'running'
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x['cpu'], reverse=True)
    return procs[:40]

@app.post("/api/kill")
def kill_process(payload: Dict[str, int]):
    pid = payload.get("pid")
    if not pid:
        raise HTTPException(status_code=400, detail="PID required")
    try:
        p = psutil.Process(pid)
        p.terminate()
        return {"status": "success", "message": f"Process {pid} terminated"}
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail="Process not found")
    except psutil.AccessDenied:
        raise HTTPException(status_code=403, detail="Access denied")

@app.get("/api/history")
def get_history(limit: int = 120):
    return db_mgr.query_history(limit=limit)

# ================= CHAT & PROMPT ENDPOINTS =================
@app.get("/api/chat/messages")
def get_chat_messages():
    with chat_lock:
        msgs = db_mgr.load_chat_messages(limit=300)
        return msgs

@app.post("/api/chat/message")
async def post_chat_message(payload: Dict[str, Any]):
    content = payload.get("content", "").strip()
    sender = payload.get("sender", "PC-User")
    msg_type = payload.get("type", "prompt")
    title = payload.get("title", "Prompt Transfer")
    attachments = payload.get("attachments", [])

    if not content and not attachments:
        raise HTTPException(status_code=400, detail="Content or attachments required")

    words = len(content.split()) if content else 0
    tokens = int(len(content) / 3.8) if content else 0

    new_msg = {
        "id": f"msg_{int(time.time()*1000)}",
        "sender": sender,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "type": msg_type,
        "title": title,
        "content": content,
        "tokens": tokens,
        "words": words,
        "attachments": attachments
    }

    # Persist in DuckDB and in-memory list
    with chat_lock:
        db_mgr.save_chat_message(new_msg)
        chat_messages.append(new_msg)
        if len(chat_messages) > 300:
            chat_messages.pop(0)

    await broadcast_chat_event("chat_message", new_msg)
    return {"status": "ok", "message": new_msg, "storage": "serverseitig" if server_mode == "host" else "lokal"}

# ================= FILE BROWSER & UPLOAD ENDPOINTS =================
# Server-Betrieb: Speicherung serverseitig in SERVER_VAULT_DIR
# Standalone-Betrieb: Speicherung lokal in LOCAL_VAULT_DIR
if MULTIPART_AVAILABLE:
    @app.post("/api/chat/upload")
    async def upload_files(
        files: List[UploadFile] = File(...),
        sender: str = Form("PC-User"),
        title: Optional[str] = Form(None),
        note: Optional[str] = Form(None)
    ):
        if len(files) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 files allowed per upload batch")

        active_vault = get_active_vault_dir()
        os.makedirs(active_vault, exist_ok=True)
        saved_attachments = []

        for f in files:
            safe_filename = os.path.basename(f.filename or f"file_{int(time.time()*1000)}")
            file_path = os.path.join(active_vault, safe_filename)

            # Write file to active vault directory
            size_bytes = 0
            with open(file_path, "wb") as buffer:
                while chunk := await f.read(1024 * 1024):
                    buffer.write(chunk)
                    size_bytes += len(chunk)

            ext = os.path.splitext(safe_filename)[1].lower()
            is_image = ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]

            att_info = {
                "name": safe_filename,
                "size": size_bytes,
                "ext": ext.replace(".", "").upper() or "FILE",
                "is_image": is_image,
                "url": f"/api/chat/download/{safe_filename}",
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            saved_attachments.append(att_info)

            # Save file metadata into DuckDB
            db_mgr.save_chat_file({
                "id": f"file_{int(time.time()*1000)}_{len(saved_attachments)}",
                "name": safe_filename,
                "path": file_path,
                "size": size_bytes,
                "ext": att_info["ext"],
                "is_image": is_image,
                "sender": sender
            })

        # Create associated chat message
        msg_title = title or f"Shared {len(saved_attachments)} file(s)"
        msg_content = note or f"Uploaded {len(saved_attachments)} file(s) to {'server-side' if server_mode == 'host' else 'local'} vault."
        new_msg = {
            "id": f"msg_{int(time.time()*1000)}",
            "sender": sender,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": "files",
            "title": msg_title,
            "content": msg_content,
            "tokens": 0,
            "words": len(msg_content.split()),
            "attachments": saved_attachments
        }

        with chat_lock:
            db_mgr.save_chat_message(new_msg)
            chat_messages.append(new_msg)

        await broadcast_chat_event("chat_message", new_msg)
        return {
            "status": "ok",
            "uploaded_count": len(saved_attachments),
            "storage": "serverseitig" if server_mode == "host" else "lokal",
            "vault_dir": active_vault,
            "attachments": saved_attachments,
            "message": new_msg
        }
else:
    @app.post("/api/chat/upload")
    async def upload_files_fallback():
        raise HTTPException(
            status_code=501,
            detail="File upload requires 'python-multipart'. Please run: pip install python-multipart"
        )

@app.get("/api/chat/files")
def list_uploaded_files():
    active_vault = get_active_vault_dir()
    os.makedirs(active_vault, exist_ok=True)
    file_list = []
    seen = set()

    for vdir in [active_vault, SERVER_VAULT_DIR, LOCAL_VAULT_DIR, LEGACY_UPLOAD_DIR]:
        if os.path.exists(vdir):
            for fname in os.listdir(vdir):
                if fname in seen:
                    continue
                fpath = os.path.join(vdir, fname)
                if os.path.isfile(fpath):
                    seen.add(fname)
                    stat = os.stat(fpath)
                    ext = os.path.splitext(fname)[1].lower()
                    is_img = ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]
                    file_list.append({
                        "name": fname,
                        "size": stat.st_size,
                        "ext": ext.replace(".", "").upper() or "FILE",
                        "is_image": is_img,
                        "url": f"/api/chat/download/{fname}",
                        "storage_mode": "serverseitig" if vdir == SERVER_VAULT_DIR else "lokal",
                        "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    })

    file_list.sort(key=lambda x: x["uploaded_at"], reverse=True)
    return file_list

@app.get("/api/chat/download/{filename}")
def download_file(filename: str):
    safe_name = os.path.basename(filename)
    active_vault = get_active_vault_dir()

    for vdir in [active_vault, SERVER_VAULT_DIR, LOCAL_VAULT_DIR, LEGACY_UPLOAD_DIR]:
        fpath = os.path.join(vdir, safe_name)
        if os.path.exists(fpath) and os.path.isfile(fpath):
            return FileResponse(fpath, filename=safe_name)

    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/api/chat/files/{filename}")
def delete_file(filename: str):
    safe_name = os.path.basename(filename)
    active_vault = get_active_vault_dir()
    deleted = False

    for vdir in [active_vault, SERVER_VAULT_DIR, LOCAL_VAULT_DIR, LEGACY_UPLOAD_DIR]:
        fpath = os.path.join(vdir, safe_name)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                deleted = True
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    db_mgr.delete_chat_file(safe_name)

    if deleted:
        return {"status": "ok", "message": f"Deleted {safe_name}"}
    raise HTTPException(status_code=404, detail="File not found")


# ================= CHANGELOG ROUTES =================
DEFAULT_CHANGELOG_MD = """# 📜 no0bz Command Center (NCC) – Changelog

Alle wichtigen Änderungen, neuen Funktionen und Optimierungen für das **no0bz Command Center (NCC)** werden in dieser Datei chronologisch dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

---

## [v3.8.2] - 2026-09-26

### 🚀 Neu & Hervorgehoben
- **Exklusive serverseitige Speicherung im Server-Betrieb**:
  - Im **Server-Betrieb (Host)**: Sämtliche Chat-Dateien (`data/server/vault/`) und die DuckDB-Datenbankhaltung (`no0bz_server.duckdb`) erfolgen *ausschließlich serverseitig*. Verbundene Clients übertragen Dateien und Telemetriedaten direkt an den Master-Server, der sie zentral speichert und an alle Clients streamt.
  - Im **Standalone-Modus (Lokal)**: Vollständig autarker Betrieb, bei dem Chat-Dateien (`data/local/vault/`) und die DuckDB-Datenbank (`no0bz_local.duckdb`) *ausschließlich lokal* auf dem Rechner gehalten werden.
  - Im **Client Node Modus**: Reine Remote-Verbindung zum Server (z. B. `192.168.1.100:8350`). Keine lokale Datenbanküberlastung; alle Dateien und Nachrichten werden serverseitig vorgehalten.
- **Konfigurationspersistenz (`ncc_config.json`)**:
  - Der gewählte Betriebsmodus (Server / Standalone / Client) sowie die Server-URL werden in `ncc_config.json` persistent gespeichert und beim Start automatisch geladen.
  - Dynamisches Umschalten des Betriebsmodus zur Laufzeit via `POST /api/multipc/mode` mit sofortigem Wechsel der Datenbankverbindung und des aktiven Vault-Speicherorts.
- **100% Funktionstüchtig ohne Platzhalter**:
  - Vollständiger Multipart-Form-Data Upload (`POST /api/chat/upload`) mit automatischer Dateiablage und DuckDB-Katalogisierung.
  - Echter Dateidownload (`GET /api/chat/download/{filename}`) und Löschfunktion (`DELETE /api/chat/files/{filename}`).
  - Chat-Nachrichten und Attachments werden in DuckDB (`chat_messages`, `chat_files`) persistiert und über WebSockets in Echtzeit an alle verbundenen Browser übertragen.

---

## [v3.8.1] - 2026-09-26

### 🚀 Neu & Hervorgehoben
- **Echtzeit Network I/O Canvas-Graph**:
  - 60 FPS HTML5 Canvas-Graph mit leuchtenden Dual-Kurven für Download (RX) und Upload (TX).
  - Dynamische Skalierung, Spitzenwert-Anzeige (*Peak Mbps*) und 60-Sekunden-Verlauf.
- **Multi-PC Systemarchitektur**:
  - Modusauswahl zwischen Lokal, Server Hosten und Client Node.
  - DuckDB `node_metrics` für persistente Telemetrie aller verbundenen Rechner.
- **Benutzerprofil & PC-Name**:
  - Echter PC-Name (Hostname) als Absender mit anpassbarem Benutzer-Alias, Avatar und Rolle in den Einstellungen.

---

## [v3.7.0] - 2026-09-25

### 🚀 Neu & Hervorgehoben
- **Integrierter Changelog-Viewer im NCC**: Das Changelog kann nun direkt im Command Center über das Seitenmenü, den Header-Button oder durch Klick auf das Versions-Badge `v3.7.0` eingesehen werden.
- **Vollständig autarkes Single-File Dashboard**: Das identische High-Performance React-Frontend ist jetzt direkt als komprimiertes Bundle in `main.py` eingebettet. Das Ausführen von `python main.py` benötigt keinen separaten Node.js- oder npm-Build-Schritt mehr – die Cyber-Oberfläche lädt sofort vollständig und einsatzbereit.
- **Vorkompilierter `dist/`-Ordner im Repository**: Für Nutzer, die das Repository klonen oder herunterladen, ist das gebaute Frontend direkt verfügbar.
- **Dynamische WebSocket-Host-Erkennung**: Der WebSocket (`/ws/live`) ermittelt die Server-Adresse dynamisch über `window.location.host`. Das ermöglicht den nahtlosen Zugriff über LAN-IPs (z. B. `192.168.x.x:8350`), Hostnames, Reverse Proxies oder Port-Weiterleitungen ohne harte Bindung an `localhost`.
- **Neue Backend-Routen**:
  - `/api/changelog`: Liefert das aktuelle Changelog als JSON/Text für den Client.
  - `/changelog`: Eigenständige, formatierte HTML-Changelog-Seite für Direktaufrufe im Browser.

### ⚡ Verbesserungen & Performance
- **NVIDIA GPU-Treiber Modernisierung**: Bevorzugt primär das offizielle, moderne `nvidia-ml-py` vor dem veralteten `pynvml`-Paket, wodurch lästige Deprecation-Warnungen beim Start entfallen.
- **Bereinigte Dokumentation**: GitHub-Synchronisations-Befehle aus der allgemeinen `README.md` entfernt, um die Anleitung fokussiert und übersichtlich zu halten.
- **Automatischer Browser-Start**: Die Windows-Batchdatei `start_ncc.bat` öffnet nach dem Starten des Python-Servers automatisch `http://localhost:8350`.

### 🐛 Fehlerbehebungen
- Behebung des Problems, bei dem nach dem Klonen von GitHub nur die minimalistische Platzhalter-Infobox statt des vollen Command Centers angezeigt wurde.
- Versionsanzeige im Footer und Header einheitlich auf `v3.7.0` synchronisiert.

---

## [v3.6.3] - 2026-09-18

### 🚀 Neu
- **P2P Chat & Prompt Sync Hub**: Lokaler, hochperformanter Echtzeit-Chat zum Synchronisieren von KI-Prompts, Code-Snippets und System-Befehlen zwischen mehreren PCs im lokalen Netzwerk.
- **Dateibrowser & Chat Vault**: Drag-and-Drop Dateitransfer mit automatischer Vorschau für Bilder, Dateigrößen-Formatierung und Download-Verwaltung (`/api/chat/upload`, `/api/chat/download/*`).
- **Prozess-Manager mit Task-Kill**: Vollwertige Prozesstabelle mit CPU- und RAM-Sortierung, Schnellsuche und Prozessbeendigung via `POST /api/kill`.
- **DuckDB 24h Telemetrie-Historie**: Lokale Zeitreihen-Datenbank (`no0bz_metrics.duckdb`) für 1-Sekunden-Metriken mit automatischer 24h-Bereinigung und Verlaufs-Charts.
- **Dual-Style Logo & Themes**: Umschaltbar zwischen **Classic Cyber Cyan** (`#00ffc8` / `#06b6d4`) und **Nightmare Red** (`#ef4444`) mit interaktivem Bento-Grid-Layout.

---

## [v3.5.0] - 2026-09-02

### 🚀 Neu
- **LibreHardwareMonitor (LHM) Fallback**: Automatischer Abruf erweiterter Sensordaten über den lokalen LHM-Webserver (`http://127.0.0.1:8085/data.json`).
- **Lüfterdrehzahl- & Mainboard-Überwachung**: Auslesen von Lüfter-Drehzahlen (RPM) und CPU-Package-Leistungsaufnahme (Watt).
- **SVG Circular Gauges**: Dynamische Kreisdiagramme mit Gradienten-Bögen für CPU-, GPU- und RAM-Auslastung.

### ⚡ Verbesserungen
- Thread-sichere Datensammlung via Python `threading.Lock` (`data_lock`) zur Vermeidung von Race Conditions bei parallelen WebSocket-Clients.

---

## [v3.1.0] - 2026-08-15

### 🚀 Neu
- **Echtzeit-WebSockets (`/ws/live`)**: Umstellung von HTTP-Polling auf Push-Streaming im 1-Sekunden-Takt für minimale Latenz und geringe Systemlast.
- **Native NVIDIA NVML-Unterstützung**: Direktes Auslesen von GPU-Load, VRAM-Belegung, GPU-Temperatur und Power-Draw über die NVIDIA C-API.
- **Multi-Core & NVMe Monitoring**: psutil-Integration für Einzelkern-Auslastung, Festplatten-Durchsatz (MB/s Read/Write) und Netzwerktraffic.

---

## [v3.0.0] - 2026-07-28

### 🚀 Initialer Release
- **no0bz Command Center (NCC)**: Erstveröffentlichung als ultra-schneller, schlanker System-Monitor auf Basis von Python 3, FastAPI und Uvicorn auf Port 8350.
- Cyberpunk- und Bento-Grid-Design im no0bz Community-Look.
"""

@app.get("/api/changelog")
def get_changelog():
    changelog_path = os.path.join(BASE_DIR, "CHANGELOG.md")
    content = ""
    if os.path.exists(changelog_path):
        try:
            with open(changelog_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            pass
    if not content:
        content = DEFAULT_CHANGELOG_MD
    return {"version": VERSION, "changelog": content}

@app.get("/changelog", response_class=HTMLResponse)
def changelog_html_page():
    data = get_changelog()
    md = data.get("changelog", "")
    html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>no0bz Command Center (NCC) – Changelog</title>
  <style>
    body {{
      background: #080d1a;
      color: #e4e4e7;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      margin: 0;
      padding: 40px 20px;
      line-height: 1.6;
    }}
    .container {{
      max-width: 860px;
      margin: 0 auto;
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 30px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #334155;
      padding-bottom: 20px;
      margin-bottom: 25px;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      color: #38bdf8;
      font-family: monospace;
    }}
    .back-btn {{
      padding: 8px 16px;
      background: #0284c7;
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 13px;
      font-family: monospace;
      font-weight: bold;
    }}
    .back-btn:hover {{
      background: #0369a1;
    }}
    pre {{
      background: #030712;
      border: 1px solid #1f2937;
      padding: 20px;
      border-radius: 8px;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 13px;
      color: #93c5fd;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>👑 no0bz Command Center // Changelog</h1>
      <a href="/" class="back-btn">← Zurück zum Dashboard</a>
    </header>
    <pre>{md}</pre>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)

# Static files mounting (React Frontend build support)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
ASSETS_DIR = os.path.join(DIST_DIR, "assets")

if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.get("/no0bzlogo.png")
def get_logo():
    for p in [
        os.path.join(DIST_DIR, "no0bzlogo.png"),
        os.path.join(BASE_DIR, "public", "no0bzlogo.png"),
        os.path.join(BASE_DIR, "src", "assets", "no0bzlogo.png")
    ]:
        if os.path.exists(p):
            return FileResponse(p)
    raise HTTPException(status_code=404, detail="Logo not found")

# ================= EMBEDDED STANDALONE REACT APP DASHBOARD =================
# Pre-compiled high-performance React bundle (Identical to AI Studio Preview)
import gzip
import base64

REACT_APP_BUNDLE_B64 = """H4sIAEzGt2oC/+x9fZ/btpHw//kU9LZxxS4li3pbLWV669pO47s4Tm2nvd7avxUlQSvGFKkjqX2xrO/+zAwAEnyVVuv0F+fp9eIVgcFgMBgMBsBg8PjBLJjGtyumLeKl9+Sbx/hH8xz/0j6asaMn32ja4wVzZvgDfi5Z7GjThRNGLLaPfn73XXN4pD1SM31nyeyjK5ddr4IwPtKmgR8zH4Cv3Vm8sGfsyp2yJn0Ymuu7set4zWjqeMw2W+0UWezGHnviB+3JJ+1ZsFw6/kx7BohYqDV+fPZM1666rWGr8/gRB+SFovgWfz/68wMtdlzv2vVn0yjSrnqtbqurfdZevXyn/QD1+xGDr0UcryLr0SMFtDUNltqfH33zF8+5hZpWYbBiYeyyaPOXaL3CFkVao9FoXrPJRzduLm5XC0Bm+YHPdF1DGht+EGuNpRNeun4zDt2l5fqei9m6FgDtjeYy+NQMQhfaIrOUgtPAC0IrvJw05iGQErKZFmqX2gSK65s/G9aEzYOQGZYzB04YljVxph9nQOWm2YyvoT7HjzwnZs0bqz3KJd0Wkz7JJOoAKGSqn7fZz0/yMwxiXoXovkzqbWnqp2xq9JFd58tTWq50tHJAWG6bIbtiIHKS2pl75c5K0idBOGNhk6TAigLPnfH0y9CZIb+bqyAC7IGfrSXJRpZbf2jD/+UyrlynND0OSpOjOADBKq8DUNXmIw0pne1vS4onuf1CdhykuWZbZnswgF3/MlvjHAYmyLF7uYizGSAe048F8GjhzIJrq621NaXJPLXJpbYEvul4q4WjkOLC0IsrkKl5ZSgz+XnEIVBcVojS6+qrKqjklhenLIIqqTGYz7E46TmrvbopZvEq/zCfz4t55RVOvHWOxkmI3eezKCdNqHRDJ4oLMnZLQzmbvFgzMUzzDIDBlUMRwIB04/wodeJ1WCgesRWMmkwSKirZtqqMsq5Qs/P9ruZF7qccEVI9lvEuyapgYgJQzs0ku4KtSX4VfxOAMkYnmaUcT3LLWZ9ml/QBwisqcLvdiskuXrAl21hhEMSGtQiiGOYUUhIRTBdW01mtYBKIbqOYLQ3trzBxfXzlTN/S93cAZmhHb9llwLSfXx4Z2ptgEsQBpH3PvCsWu1NH+5GtGeQc/QgZ2lvACR9PQyDB0LAGIDZ055D/FCuCOR/EQHuxDH5xjxTUJSlvb5eTwEswqwVHogXLwA+stUt/aU4xtLffvYKP5ht2ufac0NBeMd8DeiHRmcLfZ4EPE4gTAdYf3AnjPMPcACt6FqxhAg+hSdfwmWCF6kh6YV6aNTvtthV89KaLxnDY6n+rtdqDjmYOW91uT88AdlPAdmsIgKbZ08zTVv/EzAL2EsCTdquHgKem1um0OuYgC9hPAAfd1gkAdronWqcPVecwDhLA/gkH7PW1zkmr2+lnAYcJYK/Hqz4BjIPW8PQ0C3iaAHZPWwME7JlY9UmnmwPsS0DIxVa3TzuIsd3rpIDOElivcPK0wyvvaKeAsjfIQyqsPGmdIuTgVDs1W4N2Pw+aMnPY4VwfnmpDaFznNA+asvNkwLEOhxp0QXuYh0z5ORjw1p+can3oc7MAepKyvk/iYQ66Wm/YOj0tgCrMh65BUOjO3qDVaZt50JT9PZOzCnjV67dO270CaNoBnFdt6FIAHXQVXoFGCB0vI6M9Tm2vq5mDXuv0ZFiE7qkM6wtpgfa1OqoUSGhFWoXIIDD0dAlmRWClePUF5hKqFR7LkTUEaGij2SlCKwwB3iJD+qZmnnRa/b4CPb11fFUiTRo37aHWafdBeM0cpMI4wYoODJz2CXB7mANVuDbkYtbvaR3TbPW7OUhFIM2kNzpmH7iQr1+RyDZH2hmAzjCzA5JAFW5h6802qIJOFwrkCVXkkfTaEAF7rc4wjzGjDGiMQ9tRvZzmGZryvtsWvEcyoY9PlX6FSZxl9SoHPQUN08sSSqAZzXoq29Q3W0OzmwPN6NYTGo59wjro9HKgirx2aDh2QF93QB6HZp5WRVx7JK6kX6HYcGjmQFPugxIYEij0KYyw7skgB6qwVWi5HjALxLrf6eRBU5kWzMIpYwDF1FEOa1/3MlAa1uczVqcLJJycwLA5SYFX6xANga6qP4lh5qnWbQ9aXVUMBHBPFVhUS512F4CBYlUvCeAMf2lSgq7otrut0wLoQFWixDTQzN02dIs6EASwwrZhyyQ9MwBg0GHDYvMUxp1y4N4pYT7J8AKMIJXevuhkU+tCh3fVCYIvuNOhI5UuTo8wNNvq1MxhU3o7XHvB1EjdfNLvF2ATcs2OwNsh6cmMn0+uP22aqe4acN3VBhJAO3VP8qDqxEuAPQ7YycFlpl2TIAcECf/lQDPjjLSH2SfQ9uAkB9pXO5fqNxErTGbdYQ50oJonHPSEQE8KBJwog4cAuwQ4bOcbn+mqntKodrebA1V6Km094BzmcSrd1BOM6nPQTkYhgf1OGwtJ0vXCBSNfLBbR1sT1eavTD9mSYPzYcX00lW48q9fJp/YgtT/Ip/YhddDLpw4g9aSA4QRSh22eGrObuHkTWSCHmYRmEzezmgu+pQALomnD1B5pLS5WBBQtrdYwUyxalhWDlmHJoVJ04kTMMpWSmFBaFouaSTnv0jJhalDr9C5Ly51QQYRNCkOrzVam7I1XV1Yp2qGyatFOadkOFUzLdalclknd8pKcS6Zkk7Kh0/SDcOmAKJAIqRlLNnPXS6tfyIjY0oVl1MwaFLIo+aSYTGJ6yncnxJ5RM8YsFlpNmJZ5AzI5mN7JZVy7M2aVJ4dWAQ0mw1K8ZVKy2NmCFYXn3LAZcG7Q6UM67oeto+ZyZqFa46wUaSAQrWwKcLyVA6Le4ymO7y5RxUag7C38RzMjDTvDCTXXn+MymilgKxyZ+A+CTdcTd9qcsE+wWGy0DQ3+v9UxQDpLS649EHH6V+vkyrZ6vPCgqvAkWPtTZvE/WLUCg3sfOPSGtA1FX8AYs5N+4iAZpJ+kRfim1YzNnbUX8z1j2ldMdxDAQI3KQWJ3ib0yB2IIsrQtxAilPMnW3Fm63q115YQNZfdBBcPVdhUs5unJhgZqCNwzF3vlcus83TOfBDe4Z4Q9JraOIWXEf1ptje8g8618qz1aOTPaRW1vLWvu4l4I89g0RoW9juPAPxgdHrnIHRdxsMB1o/uJNZ3ZL2uQd9rwip0J3+PqjVRtAOpjVGRICVuNr3ITRxeNY7jXhVyPY+BbVNrMHIzB9aDAAAVcktxaHEWoBEvSO86quQDWe6QH+YYlSf/KCZkfbxfhRnRNeyS3MxfAmFgIQzMOVmJr2FzdbJ3JJLSuAYA1zuk064OeFYQZmwZizK19KI+dr82COGaz0S6A7cI0Fh1j0TUWPWPRNxaDDR9WfK+Uk5U9C6C0rbPJkl5F0b8rvyJ9OzGiOAz8y43aCJyyWLidBjNmfJzMjMhZroxVyDbV4ySvV4xff79wP8lWCLufeKeIamQ8FQ6YYbcRpHmKwAzb326jNbB8vdrgpjWoBK/pwDjwLdS2KHcKhpP+txlFBUpPHk7hhB27VwyxgeIE/bkE2wBtgC3ihgECn/gFOs9jG+p8WKbioWlbjqLSoQWJnrOCiVT+2Fp04joPpusIz1jESLP8IG6489BZMl3fBOsYCbWcdRxsV2FwGbIoqmohULgENX67mbnRCqYay3MjoA5U6DbwjLVnLJm/3lAiP4rE4+Gtu7w0oqtLA48uA2Pq+FcgLc565gYGJ8NgywmbGcHkF5hV8nUv3dnMYyNZ48QLph8JJaHbLJ0bqVBwohD8ptbwyclw/dU6NviUZQSr+DIM1isD+Qo6y6EuzqqDglRmckuETeZ7kICnsGKVIpOzvSWPNcwRzsZIjD+TR2J04iW6k9tj1XPub59uLm6cbsuNGudLGIsuzI4fjHMcJR/QMUD0R5kOuxMC/AGN2wjjoskdDEAMnTC2OmDSVfFROCwIeObPrB4Bg7RN2YIo2SRt3yrOEOS1kDhEgH0BdrGDpqiwNVbOrahDekCIVSXUFcN4jMAw5OpmdaNvshVyvk7XIc6qZBKoNYtcWh8v3ZsGWOaeMzHQZ4L+0SvQqQVgMY5FRBWUpfXb3xqaMp2DQblNxgnoBSRWjk7gkGx6BA2fLpQZalPCFNIEaZkZmu4OSBAYzAxk01uzDVjOiWHnLfi0x3WAnPGy5akorOriRB2JTpx77KYKtjl3mTeLmtchEhduVNu2HLmUKNI81XDNW2gqx753EZiX4sUdy8xArO5WYgFz8F0Jc/01dNDdCkUgANCjd63Jg/nioJIgEjOXLXcWwxNqf+bgpuX0I+ObvlMHVMAms5YQ0yUYPy7MULBi4csafmhP4qtOKInZertiNs8ArURfMFJYLD9gll+6Mdi1yljg4FUKqQxQNsX1fVLUMFIEtDrhpXAwq9fAnS9gTmX+B9UgEGn22o9dD2wG0O6gXpORhe1/4C5RATlg58uF5jSAJB9URTQSKWso7pLfWGsVuOi11mRXCNBEFJtsGmdr68qNXLR16C8WBwuVJ21bzgSsS2jNJjGgZMq2NXdv2CzNoM9tSxpYm6LJ1YpAd328TXP497YlfF7MDfdqoV0mbkKKSVHX/qw1TX3b4oBtAdiGorik6ZLdVlGsC8UQqE1Abf5hvn/UoW9Qujyl877Vr0HTafUBT5NcNqC+MN0OK6+RA7YFYFsmUC11hXk9HptjLfinAg7r+NTstDefyDy9gUkWE3ppQo8S+mlCHxKSndVNarVt/4Kbc47WoKQndg/3W/WNAptaeZS3LZQY1pQYlpWg/d+KEpRXKDGsoWpYStXpoLoE5W23reVNE8dk1gzhw7S1hP7D7pI+lZWyQV22RPlVQLNQlN/ZjarDIbu7IbscsrcbsoeQk0xbxMKnrjmTtDkCutAiANkXpymRdvYC73Dg7l7AXQ7c2wuYmOFlmFEzyjjVXkZGCJxLCE12m+zaqIXmT5JGtlDrEqbKJAk/ti2u7zMKHrUbil/OnpLJzWxtamICkqlbNcdafDkrs+gLiOAdqG7uV/TcAjquFqzDgXai6wh03XqwLgfaia4r0PXqwXoEtAMXxzSoBxoQ0Ek90AkBDeuBhgR0Wg90SkBme0cftTnYjj4yeSeZO5hlcm6ZOzhhclZ0dtDW4bR1dlTa4ZV2djCtw7nW3dHSLm/pcAdtQ07bfO15EpAmxBZOFEQz/dhJNwd/fz7oXy3ef1ALYUqaPyzkDzP5p+18Pqak+f0BrKSzAJQEELh4A4heR0CkizlKkhDRNGSgdtS1XpuquOaqgM+OdZrgGjRBHVSHw+xC1hHIurVQXQ6zC1lXIOvVQvUIph4TxzOohRkQzEktzAnBDGthhgRzWgtzSjAw/ms7ps2h6jvGFD1Tz6QO51K3HleX4xrU4xpwXO/Pzf77b0EohcnZ/xZTadApRigkrW426eEECf01HgkqZhuvIuN2oEvIXi1kT4Hs10L2FchBLeRAgTyphTxRIEENpKNY2q9pg5Fb+XxKkQDEuOy+Kx/dWLbTTsc/z6cUbpWARYd/YK3NP6NFiH5E7Y3yRQuk9DYPjM/CBZ+qoTpKgET7s+V0rST1FhdVyidfmBUuEFGViWdHh2S+/a1YFX6RersVlZat7g6tkF9nMmE0Z+8+mfJOQXL9KZfyiadwZ/8EuSivVCfK00KV3386hRUovwIAP2fsUnTuPAiXm+RXilLesDIUpPJ+VUnaJzWN360qpEC5bSvrLbDhn7gDwGGz2Qo8+jNUQq/4MiTjxlANjLkKNG7OVAJjJsBO12EUhE0/wI1QL7hmsw1PspSkBEzsrUgQ8ZlkfwqCJW4MyXz5jTsmuLUrd3hh9bKQac3bwr4vrSVw4z+C0Uy/Y7ZckYhB4nrpR1bIVsyJG6YBSgD0RKNtmPNQ19WinfqinZqiw/qiw0JRUi4AxbXMzA2Z8M2ggiIf94M3yS8L/4FFDVQSNeXp14Y2o+m4K0qPxATQlG5oZkB4kgRg/iyTS3VBosynk4oiBCVvW+gK4c5vmxMWX6P9JL/FJVOL3xcUuSm4oCoPLSmT6UhbHial79JZ8eUq/KhbpiKcSUD5hTrl1GMwExSdGqiOhKlH1kmQdWugugKmVwMDBoTYJW3JK5nmE9owtTwnipvThevheUvFpU25IYBrZHEWVV5PqrKyOHQ9iwPPp8oxiMmpWYOqpC3Axy/QnOouPaRptdgOambnV2tj5wu2sHNw+7q/Wvu6X7B93YPb1/vV2tf7gu3rHdy+X28MfskRePj4G/xq7Rt8wfYN7tw+eR2/snkl9/UTB0ncIxZuMkld6j1+XfWZ2xdOWQ3DGlblTZ4UXc+RUihaZEURR4EX8gbB+0eDdhlbMh5Mf+icwP+c09O7ejfco84yLwi5WlavQOjaoOgOAYsXWCCA1cn9sgLgwhyMcIt5nruK3GhE1xW4yAAhaEWOEiC+475tyYSm2IKvBhBnQ+m32PZXAHI4AKSA5TaH5VZgIRceNttkHXe413+SS/sfWQjOrdRfXE+BaWsgC90xeye9YXfQO8FdAAnoXdYh9S4VnMtZHehypoDWk5qhNN4oo4ZOOzPtV8cUPzjNsYfnbzKBN+qHp7KzJFI6dy/eUYpnmnA3BaFSkTSCt3MfRByyiGqyubt2y2gfFdnMiRYgncX4JjxjVJKWlE2uL2fHvjrOExC9WOr9o26u5B/mp6fTdrs3u6Om2gP1LoWUEqp1SzRSsYJ+Oe3D9v1p7x9Oe38v2gfltN95htgD9R1oH+yifbBb0gZFSRuU9tZsdtK7d28NDu+twV69NSjtLU77PXtrcHhvDfbtrfePTsppn3TvT/vJ4bSf7KL9pJTvkxOQ0/vy/eRwvp/sxffh7lEyLI6S01J9fDLpdtuDe+rj08P18ele+vi0v7PFAJK2WN7Iry4kIXJl+jvL9MvKlKifLqie+fxg9VONeRdfEyrrlI8MLrCjsYNCY8v1ldnvz+bTg8dNNea9GrtLW6XoT8oJP1hZVWPen/CTHYSXayqz1zthg/tx/ORgju/SUzIcSbV4SQi9UOb9o16+se32rMPmg8GBja3GvKuxCZVab0dj+zsb2y80ttxChrnzBKbQ2X0ae5CBnFBZp49T9P1ywg/WeNWY9ye8v4Pwwc5eGhR6qVzjgZXQmfQPHn/VmPdq7GCf8Veu8TjhB2u8asz7E36yg/CTnb10Uuilk4peOumddu7XSycH99JeWnK4s7HDQmOHFVqyPz8Z3k9LDg/WksN9tGS5DWq2e2zQu5/GOz1Y453uo/FqDVAJkfaSEm2supgCVFqyXOucDE4Oluda5LuYpZJbJ9VK7LTyEXnaH9y7BSf3acGucZmGkaruvBRGz5cb7FEu0+ci4mJ1IQGQLTHYVaJQR7naOJ23T8zOwWqjEvGu3hAFa5VGgnxYTvV0el+qh4dSPaynulzTDTvm0HQO1nSViPehepeeEzE1S6juDWAte3o/qvuHUt3fk+peOdX3kutSxHtTXSPXSSy36hGcgOjFUiXjwZx1Truzg8dDDepd7U0JrRsTMnRadYMlhJ4tM9xZZlhWpmR9wg9JD16fVGPe/yi0v4NBw9I588DT3d2Y73eGW0B/Uk74wWuNasz7E36yD+HDcsIPHk3VmPcnvHQsXTbfn7//Q3titk32/sOmJIIEZaWQw/bMdMohKSuFPG3PzVk5JGWlkIP2SbsCJ2WptZ+2Z1W1QxZBJtGUi2DFXV6xY3SpnkzuLtUvlHr/yCwpKU7JgC137fedqO9wSmaW97xSQaea9m73frR37kd7p472U6mDCrTzU4gDNNxO1Hc4hRjspH1YTfsBumIn6jvQPqylvb/XKBErWKVUhaT1BuZp27yHpFWi3rPF/Z2SJg23CtoPsAp3or4D7b2dtA+qab/PKOnfb5T0d46SvpisK2if3FNmTu5H+8lO2ofVtN9nhPfvN8L71SOcYqjWj24C0VNovhArDT51kGdOLdrdx0lIXPkKL0Hcq6B3cDitvcNp7dXS2q/m7QFLj1q0e9Lbr6V3UEHv6eG0Dg6ndVBL67CC1unhtA4Pp3VYT2u/Ug5m9+BtGdp96e3X0XtaLbfsHuPs9HD+ntby97Sav/POPeg9nL+nVfyVfiX1Sjr1LblMXmmoGJ7mtHs6ZKeHiVEd5r0O/+uMZflmxB6NTcxN+VVhbZqDTq8/OMjarMe8X2NrbM0Ufa+a8MHgXoT37kV4bxfhg2rC7yFe/XuJV3+3eFUYmZzwyf1E5eRehJ/sInxYTfh0ei/Ch/civGI2Sz156ga06s1zqTjE7CzTz5ep2JjhviUHbczUY97ft8SsYVD1rgwn/CDtVY95f8I7NYTXzDF0KH+QEqjHvP+h/KCO8P4+4pXMMfKrqpf63W6vf3gvHTzHJFTW95I8Pasg/KBFWz3m/Qnv7iK8V034QZNjPeb9Ce/tIrxfTfhBS7l6zPsT3t9F+KCa8HsM6P69BnR/94CuWuAR4QdNjvWY9ye8YnJUniusV0YKoJ4p2d+3ZD9fcqcCVAALJSvsp3a7M+10DrKfdiLf1zmnzorKVDKsbsFBsrIT+Z1aUCEx6UN59Z2XwvG+U12S6spl3ZIulcfoKrq8O213B4eZzLtw7+JXWr6yw9UqhtXkH9Tfu3DfhfyK3k4cu+q6THHuukwdu3aVGKglduoC6ZOilqg83MGz2YNMoVrEe7vNdKp5WW0HHeyitAPx/VyUFOSDaqoPmpJrEe9NdcWEnDwfWWUDzc2TzuQgG2gH6v2cjU7b1VaQUsGwmvaDNMYO1HegfbiT9tNq2g/ajt2B+g60n9bS3q+kvdMemMP70N6/H+39/WjvV9J+0LbyDtR3ob18e5kiZdRrfwLhuj91qasroLrVXea8mQrMOdhXahfme/tKyadV92jsaaaxNbsiQ/jf5CCNXY95r8bW7Yqk6IfVhB/eS6f36qXTPXqpQm9wwg/SG/WY9yf8tI7w6vX2KfzvPqLSv5eo9HeJSvUqkAg/aElQj3l/wk92ET6sJvweMt6/l4z3d8l49dxIhN9Dxvv3kvGamfESw/XAZzMOmhMeQyZJSl5/iQONR5/RZC3q22bu0rlkFn/vNincSILZJOiiOFhFul6oNqyplgLofJla52GwTM9qs0CYV35aOyrBZhVruXIdnmcU82R7dEMrZmLNekV6fck40EtT01Ky0clxzY5GJycKv4dGK3e1djRbubH1e2i4MsbLWq5kf+WtRY2V+HrlIQ9zH6tHeQ/3sRrEXyXbS7UosOj3qEPxE6Pv72ywhPo9NDjdjq5vcrod/bXrTtfzlKsq+Fl5PYVgabbsloHKnAxkvxKyn0LKE4ZStEqmhMd9vlJqRYYKN6iC4zvN/FFh+RLGRnzO3dgSSQrIFT71qgJcYZB0EfxcPhRaEwAdw59LsHwIdBEAvR6LKdB0dsB1ONRuhB2BsLsDrsuhdiPsCoS9HXA9gtqFjeMa7IAacPbtYgo9L7O6SftAPqZX6IqbTF9IsNouuUn7pB5eENHZu4KOrKC7H3yXQ/f2g+5x6D1pIUpuM/Iu3lOtk/pbheUcusDx2yzH63CaEmlnL/COAN4XvWB3rNBc9lgiAqgoqx83NCXCzh7AHQ7a3QOU+jlUQMMdr9WtJmo/lL+YuJqobN31AOJqolS/8wXE1UQRyp1PIK685mkCXfMAIr4/RbGWxVMWyqvQ8hULSkIUaiZ+iyxinJpHCTCF4JPjy8AP+OPjc2fpereCZUmeLuAisHur4DBPkonhknkivZrCp2eRoY/UB4eTqdtjDnLByAI3mwqwLtF3q9B374K+W4UeXzUpx485+1eA0OU1eJfl+L3L/bF7l+W4o2U57mi5P+5oWY67iu93YXsV12+iCtzRHXBH5bjfnw/pPa60giHGWBZ5p7m8UyXPbOcyzbaaa+ZzKXazoIw/9qzSapmj7GvbCSi+znwjAz1LaN6yHEgZN/IgYrjy62WEkr6v1TJKiljcjvYBkqgDb7YXZoDbiRhhpCZiM3e93Aczh9yFW0AJ7H4QLh1vH+wcchd2ASW1I1u6+/JFwu6qIYGjJ8OmH2m6JFUuXzajNDkqMiAgKSzmT6DTTFIOlEfMwj1Qs3Av5ACmoL92Z6weN0LsQkwwOazhbrThPngL5EbxbsxRvA/qCDlNZ7n8KY1VyPhzW+pjCTJRKBi+LO3A2q7q1neHlncKcLcGuJsH7tUA91Jg2uspp0JmZUC71aDdHGivGlQhgFbS5QTIrAxotxq0mwPtVYMqBKhL92pfzW6xQK+2gFKD2GspryDNzIH36sAV7LgTUM4/kaMCdisBu1nAXiVgrup+JWA/CzioBBykgIlXxaYq7hJ3liNg7mBR7VVBQHSQZpbWLbMyoJ1q0E4OtFsN2s2B9qpBeznQfjVoPwc6qAblPF2vViycoslLhdLnKJMMgPFBN9LrfwQzY9MgpBcbydqykmxc0YAeW8CExVJ6LEtJrafbmeJ6JhEa8VknOwGq3BiW6xvxC59OlYm9NLXVS5NPlOSTNHmoJA+3rWjhzAL+9C1/Aom+rbbW6a9uNHwLVmuaHfg3fSSJlyASDXklv42PfNzI0gms60csFqnqxiZPD3HaKGZScjCflxetKCRSkga9P29ftC8GZLlmG9bWBpXNma5DPO+gj99siy7e/2HeP2XtyZ2aJsr8NluF642L8HLivG8M3hvmsPPe6JjwT/t9q/deL2knFqgUycFkMOsNBl9dUwcHNvX09DffVHMwfG8M+9DW3gm1tXvntjrDfn9+0pv95tva6Z6+N7C9+N9BEszmPfi/r0CCOz3oUrMP7TTNA0WYq6XfrAh37qqYOl+tYkqb2gcBNrttHK0DPlr7d25sdzLszAf9336/7jlcO1/tcK1uav/Apg7bv/2m5jXTASLMVdNvVoT7d1VN/a9WNVU3tX9gU3+zIlzdVPPQtnZ++926p2bqf7WaqV+tmcw7t5UrJtP5bba1U73C6ZQ2tbNzhdPtfnVNrRitu9v6Wx2tdd16aFt/q/tGSlsLtrA5vHNjuS3cYV9fYw/oWd7Yr6Bn83POAW3lk87X0NbCpHN3KeazzlcgxYXGHtCzvLG/2Z6tMScq5tid5sRvdY7t3nne6X6F8453mWsG7ZmREdjs7jp+AUvQgHb3AA4PAJq9PQr8VtqP+Zs8pJUtTtUbutam/5H3oAlNPC6ngd6X1/Vc5m/4gGfirYVvB/6y8J/GcHWjj+auF7MwpQ1zDKVhE3Jv9FkUqano7R46UWxk7wzcRsA4piYu1qwZBrETZ1Jd/4qFmcKRE6/DHFTEVq6jJszCYCWaZIg2paeKabs4vMzVv/42Lmc1TVzOvu4WKp+bfD73BVQSGqC0YFRmNtRU+LwG0rViYXOvwu25Li7rKCAVpKT1VVSX4vyd9JRyUlxu6Cqm347+zB0ol3QIt4Cn07IOKS2HtfzOOD2sNFBO78Dp4S7RJ8uFDf7D6TKZ/pKc5jL9/zenaw4+78Jqs/Mfqb4Lr+8j1jt5/R+5zvK6j/4oyT/A7ZMvye05/d+k+/8Ptznpm6++Be8ffL1teOAuMVqE48ewPnGmHymT1iJyhyGTWlixeJcor9ds8tGNU9ACO1QcGb4kGaUMSrLLOJVklrIsyS3nXZJdZGKSJfxeS/PKOJ1mcpaP/sOPDD/yEpYshWsljNbE/5Gw/0jYARIWLfeRsGj5Hwn7j4TtK2F0F4SCqGzSn80VwECdtzxkkpEPW2eoTyYbwTqm66r8K397hKdi4BIjisPgIzOK4V+MQogZIx/rxZBNTXetjeQeC/+F94IMzmXBTd7JRsVgMPLfMzdaec6tgV3J6YjciethrRghBbNWgYt38ZvsCgCikcKy2F3iRvd87U8p+F3Cc+ZETFxgnrG5s/bEBZzSYjB0lczZmjNRsZhFSjVCCaFnOrfpeF5pB0P6V9QKEqboty2pXxE7xZgq5afI+4pak6iD0vbsUha/9YbK33QzMVPeanWi0pogXSnXLZbrVpTrQrmIeRgfisc3EAp0HeEFaMqwMGOUT0iK4dgqLYYZo3zC9i94h9/RGgvUsxb9q29aOJBhdsSv9xb1VdNs9y03aljXCxayBofQeQHtz7o4RCbIGwtgvx0pKbeFlE88hT7SfhHl1UUnLw+9kCFJXio02+06ouSFQ3PbEgWlUhLRwzjoRlVVVVHGsgjkFc9dCJSroCUITvZEcJJBkL48Jwvv+f5cDsHpHRCcViDAMMxVSA5+J+1u1dzv0bS0LvloyX5cSaEzfBFXZ/fBkN6yzRY/3b94vva8UO2M7X5ShmB4BwTDCgT4ZEilXPCw+Hd/keRu1ewfI79bKxdpXf1dTbr7sx93q2b/JvWrm5SJ5CBqqo3noJYTgQoqi6WBDPKlejtK9QqlKIpAZRkZY0AtIW/+VxZSQgOIcsntelFmxxV8DEYzXUeJGpfBNCxKrlbjStCNLIJkJtqBQI13mUEgNc6O8qm2EcXJOUgWu7sfVPt35AclOCLXKGhOqXyR6VF8C8YKWV/FpMSQotY/sXvtkC1hgEfL9xYPiLgRi1zxuaWs6+agt6EiVZEpMZIdhxy2ayGH7QTSWceBgMWfPPkydEmPRM3uhn7HbLmiiB6QuF76kRWyFXPiRtcAY3rp3DTahjkPdYF17rGbZhhcb+jHzA0Zt9AhiQPAcFxGMoYeRcFrUlISRA+B9gvFSZCTZjsf66+9LbB5yNm8nMGAwJiMCZfpa0sZSHGSjh88uaJbMCvlVaeeV50Cr7LF78zqbPFeffFeafHanqKG7+ipPJMHPc5k77KUl5icktyvJ7mfJzlf2VAMnBvvPowAtHL9qckYU3zp2bzZRLd+7NxYR38+Grk+rBzcOLLmjhcx+IQFmeM1rxzQ1yBulUhuvwSST4cjESulvRGY5Qhu74vg0+EI+OK/rg0VJW7vXOLT/iWij+z6LjQR/B0o4vHJbmE+BmsjYodLwMy9cmdfBJOwGWgu2xtLFHjuLI+pEI58f75k9vqSYo/JUHiygxbypKxEeOU6XxQfTK1fEh1FdD+AT0k0+AN5XOyjxx7zL+NFEwNTAZRzyXa1rP1tLXlfoIZ+TRVKGPp71GC2i1WIiJ/7c1YJKrl/IRnB8A7Kg3tE7z3SwVgvFT7VYeiutTcdb7VQRtT9OK1a+/dvl4rtrq3LlP2ibUyXP3eYuNIly5diyyFkFBZd9ycmXVDekRvq6jI/3p/cdc5TMe7gSV6bz+fzOmxfik90OWdvDqVH5PuXkefmd5pA+GH6/kXSE/a7SB0eu+8PLw/T9tdk4oD+DiXw1H5/cPX+yiGF7jpO1aJfVHfl/UTvIJGqW8chxQ6Q6IJLyAFFD5DxEneSAwrfVerzrigHlLz7OMi6sdxBQMUJZ12Jj+x2HjpLFmnRyvU3YGen4VI5VxvdQXvGLnHTIAVeoQl10v/WgAJJlNJRWpQ6s9HJFVpDlRuwLtOgpP0MwCRY+1O2aRNax3eXTun59HQ9cafNCfvksrDRGhptwzRMXak9We3/q9Hs9L/Vt1jnnvjagK7VyeKjvcbtN99o8H+PH9Ga7ck3+HMBNiv9mgSzW23qOVFkHymvYGqZYLya4+PId52IzY6ecGywotTcmX0UBkF89OTxI/gWOdE0dFexFt+umH20DGZrj0GhKyfUmP2aXjNqTUOG5/qx/J6xueuzn4QQGL5Mv2Tx62tfpj9nHHUQGmE5xI/YG4arZEJOHCApr+eGI9NXMrG1cCKluBHYDaBKt5808L/48+cGazRie8Nu6JTG2my3ekt8AJzBbH/teboRy0TdiBCFawRGBCg27rzhPnyIVQVzzbXtMX/Oafz5s5Im+3OsQ6fhHqc2tcOGqxue3TbW9rTFzRZjNvIer0fe8bE+s6fn3gfjgdMCcfWgwpn+8OHsgW0HUBl+Ghtou9Vg9hP3nH3QWxPXnzWQVoA0mL/GqNcTj1kPGpHtN1xI1T9/jlppzlYfhQzGu6+xrTG1G74RGgEyJbB9m1p9ttlarOE2fB0a3Qg/f37g43+tiwsWvaJeh09BoG+MhdvEWD+LG0H6aWz4dOJnqGpvdSsw0DOjIZnT0Dcei0GEZsEUAH0pRC88hl+Nsef6H8d6K2TeD24Uj4Dz7OFD1pInbOrvxpiL5QqAA2c21nXe1hHyn2rRoGuSiv5vzcLbt+QGEYRPoTlU1zkUlvItEB19AFR+g+kjn11rr9YxDdvXk4iFoK2xNzayhhhrYDpQGbdopIAcTBeuN0PiuSAkhMQtZzZjsx+DGYt01oLZGeUcS/zw8sf/HmPLkBb4zjbr4UOkBSQ24BQ0ZIuMTVIV8NqI1pM4ZJztI8lvDeSIsxzkf5sIQwv96i5BEd8+fAikJ1+2kgMSBgTNWRiy8KfAc6ccNptk52FwFEGXzhjpmgjyp2EQRa9hZnd9bNw6Yk0FYHw2BvXkrWdsbBVgHdB8t8tgjVDB0o3H1jgCnjUDghgb8TZpJ/IIxylrsZWUA/xtP2jjWwKabyMnRnMWTxcAtACqQTJBETT0EY5Vzw4aDaE2Nqq4qjVA7qZU1zWcVBsZjA9bBQeYJlHgsda1E/qN8bdRo9Vq6ZobaTPs5SnI/wxf7V15Dvz7X86V85Yr3zfMmcZcr7OopX0bQZPP2x/gH/MD0p42P8Tmi94VOok9UPTUA3aGox11yQscUOcv2IfPn9n5+C9/cWMYrzAkxoBXlFS12RmMatSOaV0uZwQDFYndC22LwzUOKtBewFpxUIDCDTW0fPgLWmlMbXmGTRkTw32bHY9b4+N49Jyd+0BMQ3IJpAnGzdEzx/9TjAePHjRcg3odbRosVzAX+iDNCydGBvpBrN1C94KQgNzOWtq7BaTC/zuQBVaSoU3WAAgA4mnkmYvshuzJ+hJ5fhusQ81ZrTxMh9a1tJfQHphXDQ1IdS+BnYE2jgFrK0JzZKzxwxXvVgtCjUsBYBtTpmZrMMjGvMe0xBq6duMFUMwAPILCM40DQ+2YCI1L2tU6MmKD6QaxBERX4bqDXAeR3RAtiBsGl0Ef5EF7E9sx/wTRjuynIm+9mkFdoQ1a/TVLsQUglelX9EVxTzO4vVQyx+NjBWyNGXF4u0EIEonYfmBuoRumiw38bG9RrQKILQRDiE3MBQSMByGub2+Xk8BTZfbhQ57WioO3MS7U3zmXKPTFVBwEqgiTuIK08lE+lgrT5xNgbIzfQY8Bg3AffqaB6UiyBo3xxawEqUgW9KqQRZoYteU6irUJg57GpdkMhcoBMUAqIBnmCaatI/wAUUW/ttbYCMFyQMWfcmwmdRyfunVJHPzGibJs9OqJxv/jH3k+6NUfhTIoHaufP5fg45Sm2EYRyDQqUtBtYE5ql8wSXfxd6Fzi5DQeUcYzmQ6acu56LBTpF0kB7IppDKYGE1mTNGsdrZgfyYybQgbNsjzzOsl8Ci2/gvlLZLxLMv7hsut3iQPmeJttolCVumiZzMF5GnLBqpkA8Q8fZpUUaLUpc6+gQ0kGwHwEHPDFkeEIh5ngmRzdyObvwmD5DnA39FRXee5HBvok0UmkKlvaTx46wGrINkTvRtEa5AKnZdmXgvuLpIk/4XU8T7T8ViZruY4eP+ODWsBdSThQ3hdivFcU0EFlw+8IbTzJeIsPXTQE0GUmsTHsTK0GoMEJI4c5lgNubJApBBP9d0EI8+TsDZvDdJ9+NEB5HI91bD+v+G3SvNjONZBM5NgWFi4MGzLOcBZ6xZbB2IqFcDILi16snFu0tAwk+QL3R0aolgRyKN3Ad8+4XtpulUGXjsx5OjLtSyaGyfjxk/GoVMhAF6G5pwzJZ2khsA2gHFLAGYujXjI1Phs/hinzePwEeMMhBWGZ0orOWIEy5ou2d62nad8I1gg1wJdfYNsq882ykRgUL7ishyiWTZi7ph/xgckmrZrHSpGF4MJPTC5oxqAhwZgWLdmxHEzgEYIYB8uglhvRcPgnmE7oLcJJgnkiEW0oAkumq8Cdae2UlktupCjWm755AUbGC5hYjJyl8W1kaVSztCgcmrthgIa3qJNRWU+nDKZ00M7XLhgkIYtg2YNjdYx+YmgEzMaguRCaE4a2yMs5mheaz4TC5zhwzkcrVswMaBwIS4DM+dQYMKh0tAjWkLpyePUOmjYzdw42N9pBnM7GIo5XkfXoEXUR2KZXj3Bt8wi05BT3+mhG18G2ADn2cxxFfpTbtMw4AqYccWvWR6bN3ct1urZLmX2RCNmsQZYBDTcpbc/P0dZs4J8i80FdI1eQcYyvAdHG0K6hnSGM1StuGXND2DxtaZhJvXQNfAjZ5dqDejkXXorOgWlWFsVDT2Ltf739H02sMfn87KI9OV8DgQhNmhZ0K+4FpDYQUkJqiQuXGC1ps6+42QRratdwOAdgXY2l0oG2kYPcAh2IvyxmAFet2KAqgK8XAQ49K9wasCrP1gVLdTFQK3sIKoMeUlfdpiHW4qihdOtOJbGnL7Y4xVxEMCKB/G2VcAgI4whqc9EOnAG2rIyYRhb7NSwrhfQY8oxGrxa+ixmDCfGlPw8OwMxbvwv5W1RmB2B3d6N+50SHYHZSzHNYzX+CiaKR+QbO8+Fs5JJReFPZvOX6L5khr8QkiOsLjgA7mUQPf6TcSL6wAakk0Nqf/2wlPW6zQpKuLsoZIxsf/z1TEBVL2aZu7TdN8uJixqYl2TqyyeL18C4ZqOEzrC8FIbbqiCeblCGnLCdL3S7yFW1I7c0vxtVWPXiQb9dS6TmfivMZc3NkH1ljuz02jiz80RnLPZzxH8EeAlVDD4E1Hp3b1odHl0ay56AQAGpX1dWTrGBUMZ1mVVI9DVio4aduAGW4hKMP6K9kHdXoDtStCKJfLhBEF3FLVeml1DQlnpNBBhbGL2Q/g4W2CEHDYwOdKPBHYp/Ryhvnsv/lAgWkDLS935gaU91KKrfHsFpA5w4wMnl+wifcx1CkSMJRL8vCKdGGoNaO9a1xJxxJywzZJsSBQ/aLMGi7Fd9pN9yIyUmZmiTbRjTRKJbL58+UMAlgXnZg0Yik8yUmrbkjWJePhHVLqRHuqjEPTGjRIYEgf4L7cvHYog/RJ/xDLKAsKjoBqj/yFgmpsxJ5ya1tlsySa5xcUTTfBY8iabgbN41IGc96woEtrvaAybiv4dgO/BzxHXpXrDpa4+NJIzLauuXKyfsVazj6WcOHfGPKBwMwxrenybB7AxbrHx8+wmUR/AOVO1QhwJcMRAbdbTkJnhixw18nHWrwFT18GGECUEUZnz+vOQSIim/fQgX+MU/gXfH5c77E2Xhs4TDlpSpIPZ7qhvsAWw6lZeVAUaQn2HhalKi9B1FB7SE3irqwowOHfdwHXq2jBTRSN0zivg22n8Jvyz2GRYzxiqYueWTi2e2R95iJsxI6JXFthqckgT2FHnINTzeiY/sGfiGrA+hbLolQg2fjNqjcxfQKZzK4uQ52pw9yyYBtjY+fP2d3Zn8mO/SVs4rQziZzHKxsuSpIdnha2s8RLcmdMHRucW8fOAbWJlmpwsoEY53vI+KK/SNu5YEl6Yl1EZ0JjR40oGktH9bVDV1vzfCOATTW5eM9bS+woLLFNGzlzsVGWWuSmivbCLppkH5OBsaIK47YFqocssRyj5sXwAmwkLH51MN8/SH2pWm50pjjZSVYQB03cMU9Phd7H7z4B9y55wm0CwqMirTN+FjYLvgJVbZ+CVxgv6GheG5BucEfPVk/LUEnxbiA4hsMtA/seUxsZM6TfjK0tdotKf/lWjFS9rCZ3PIs7qfxjcbQPv9guNBNCeMYGPowtMtHdyyPyJjhQo+BFRcqe7csOZ24SCaKpilnedqu8PmfkFRZgFbvKEzUQoizRBjbIUjvzAZLE8+FHX8K4hNcN6AuMS/hgRWYoks3YukcB3TjLiqDKkKccqgKvoKllrowbHTU725ucvQLNLdxlzDbhPTbNBK8ti94mDYGMIn2AM/Km0FlQHectcR8P4pBfcjGlc3HMou33tm66TzM11HAO7esoCsZBjNDZia/S4M7SoPjQoPV3qvttdRkMZCEQntT20HmJBaEUd/gtKSrWB1bXZUyI+kVzn1X3UobCX3ipCYWtQc37WyYVbO8kbYxJbQV5rj6NsdXUw42RRiBqrQVuV0Cz/l0a2kv5P4qLunFHgxSp81ugSJ3qvGAZA2djo2SoxwA5bu0lvZt9M03/8Ijn2kwY3JvxQuCj7QJa2nfaBqdBmivbpNtW83WsPoGoLWfyCr+1HqkgPxJ17/55jlQjvrKmU5dPN4EEm611RoU5TqEX5MQ5mFUp6gvqQUc1Rlt9SdH6S7wJJ2XvprmUyPCdOAK81R0baoK3yr7kd/n9yML3f7S57POAknkjfoefsLcDGo+8JGrjNJpmygCttNJO7CHPGKIOem5VHLKxnfep9T6hbMCi12DoQkIk+JzmGGCa76dh+Mmsr4xW9q/cDaig8SFcwW2qRstcfMVwfA+BlQSIQI+PTq+7CictWDeakTr6QInUJ7//PUr/ZuOihTaQuYt7TlCyTdrjxFCavM33SIBeG4UL4gXeLa0uk2rF3uKtNMITfzmLQMjunyb0OVcbiKXm3TgityIXTSDJgEI8AIthECjbQFq19y90XCfDHfeJmDw0LGEcrrIoJfftZzo1p+mJy5Rs6kcOSqr3HetdzA3bbYjn7YoIjvO7E9z14rIAFuTnzjOvnNhLRHRbPeWxQaUhwlH7piDRgHd6gLWtyO0cblguej7ktiGobreDRPXnrBgNoFKK7bj+NjgkI0A7DSmy6+p8YnJkwJsHe3KbGGJhZpgEydCnm8IX27lElvoelloc2sKKzSYrg2z/Zilw4Wbr89ZzPWDAyM2vASzjRZdKBMcSSQHCVkTaYvI1IrFadRszcTx5HrCt+bpHIEfRoWsiXtWDLeiAQgNLi5uyZkoClHU0l4DR8JrsENQoYgbwCCvUPfl2oGKY8a4aRnM+YijfTDago0fpIyink++hZdNmqB8818FDfJPpiWncq7vAzeUjsQm0EDivnboxsLHLAg9QBJGkFQ5lp2Y9DvoHjokmNGufgqeItauF3hoJ5hNqh6rbqXOCZmTvjEulrjki2boJNOxco4zzY4XOh4RbODJeDBOZUe+HD0S6Tn7YPktF9TQzWs8qRKTtc8XaCCitJwoyjnaP3mGHkGzUxA8yazRxdwvQpW0hj4mGPQppR17eTDuRFEwdckThhYKIH54eDGHWU2R0yNYCrEGGFCpJxxTt948aWg/lVsVUiv4Nh5g/d/aDdn4+JUTL1qAdRYscekVeS6wt22c6KOnNp06nfsf9OTIP3aXMPJgQQKS8HJJN1djJo7dntrqWuCBCdX+FfcI/8rwqEOolVcsipxL9gwUtc+8J+N18RyZJGMCc2YEgjQLGF9xkmw6ufI4BfM1Jo9npEWBxvz/W7M1zRtOBNPjletozrWD50VTsKGxXzU+f5PnER2TzB3XKz9k1kDQ5VRxCZ2xnrRg7nw0B/tlAqObTx+PCBTEmS/SmD8lF5yQ65FrfriE41m4dpAvXaYho7iFtoTZCvwlz0CnE0rrwL9RLMAb3CbUk7PXp6RWEz8SdbvVTPYOEqX+9PIyZJfoY4iszrg2ZbMAjcXO2x8UhwvGN0txpP2D4ZjJdRvOxxFjy0SR8Mh1K/RPJtZzUywyEu2a20j4K+hiPIJChUv9tQrZlRusI7W09BBZctPA0ZCXMOO3YL1s/IPZink1T9a1fCqEQT2N/w6ywcQCTGgM/BCMgrQ2DZMVa6DPCVO93wRbE7SJQ2k6y71rkbHnEw+jgk4R1VO92/bjHDQn4awR2tCN2TzUgSWwsLDwgU7dijNSsJIj/8HP8PdnHH5C8NpkGeD+zyhOd5ZiWKQLxcDO4w+jWQANmbmznyMmFtC46cmZ6DcemHqBfzlwWBgCHtvHHd2VUChxwi1cehNHyMDb0vzQMHEBJVslGOrTZnKC4NgssIEY7Kd2BbbV3G63QtwvLt68ePrs3cXzF/949/r1D28v/vbD678+/eHi+9ev//vi4jEpn71AYcV46cICInyJwxrq4u7Ab2kjImMiHY6nwQeeUBKwphQeWvPE30AJOed4LXFEDGK/KINdcfcX3bgsy51L1yTduCjLj8gT6QKNFAB5VoZfOjHpxlUZhql0jdGN24p87kZjXJfRx31dYMk0B4hJKYnSI0o3buryLzzyPzbelgEt0QcGGliWhys9JK8sz5GOVSCSZflXLru+SLsLwF4kYNLJ1HjOz5ThXzd6xZ02rYK+AXk2+JTGvgvCKfuZrFdLnWrRCXU8TzPHelLkDd/yfhuXlgmVXKUQrCMqCkQiZ4xbRR+Tyw/cO9R4iu0ZZY9in8KSQHEIlg4XyXIZOaDmyxoUW8KIM9u5D5TlipKmjEEmdnH4wlts4cbOR0buiWILFopx11MYbS7a22QB87UBurMqi2XQULBY5d1RjwLm+JHqDtrKcZQ8QgycPlRWZhig9GPGnipDqwiExJyTA9Ilv2Qk7Hyc/B4b48TDFybUdP7FlRVYE6vMuici018c6WloQLKI9vbT3YR/gjH1s08OyIgGJ3Ba68AoC2/BInVgOTT+YKhyB/RkxNAYv2FgXcH44P7ItDsjlleSZ3I/W2tEykp+l3n2qNvpDnSof0u3Iv5Gji+/MP2X/KUZyNLxpsHfmPELO/8b+6CPgrSHbNW/HVgbKVlkjECi6kZrRzBSGr8wtZd1hHGjn4DdueEgpupXzH6KO/cARH+NH0t1qOcKJyH0gJqiKnxnb74nhw/jKf/zjv95y/9IE0R85RY5Vttwo7+KbZwfwBqc3qJnBsztb6cLhjMVTxQ6iGel0z4mqNOzdf4BvWie8RUveVTwenETzo+922d032VG/naUDRRsjZ/YzltN3zHpCC3uzKCDxlkxqahOubPiCIcE8fCCfPgueIClC3Ljs8oOLBug8ahnXhgvmfGcFLf9C20/lyLhqzLo9aXe0I0fmP0d2JKNpU4HYKbxhtmP3j86fnRpfGLyLBqGAczZRctcSc9q5EQnXkNdwbVdVIw8o0VlX+BQzByDbdLVSAGwMSazfmxsJusJqjZ0y5nihr0nnXTEQqXKWSU5fpMLmtQzQZ6vySzdSk/cqFoLb2uhASvowm14FEtOWixvN23l2Z+oC+QFHehKGCFyWmzp5nig5jTGkO6sLxfxi5spI6U3Nlhq5mcWPGBxG7i0NY2n/LgKVh9t43tKITvU+GfStaStX7lTvMYZfcz0rtqjWbCStUcOAK9CbS2PoThnp93NxQUNnosLPuKmZUL9tqG3QK2iH/AzBwY4edhz8/NvMD6WzspymQH65gXkWuqETIeFuA5SSAQzYLXybvlE5ISXdC8rAiaBfW7QgjhDg1yQCFoK2I6Pt+g/ZcQBKcAy+rNlMt4Fnz+ff9gauBOTHzIPyCUpaxvwradn4uy0RRs4yU4ZHbbSoQFuxICUenKfT1jg/NAVp/6k/u2ItaTvvX3NYB0kkdt/o69E3zvwJe8J2JeYJ28H2M/wA2aIFBj91NI7AvYFgkv/f3uCX1m/fvsdpl1cPPvh5Ysf3128/PHdizc/PoVFyfPXFz++fnfx89sXF6/fXPzz6Zsf8febtxfvvn/xr4tnT3+k3J/+9ubp8xf2O47j9aufXv7w4s3Fm59/fPfy1QtQfpAObLCLvZoudQ3f/gcb/YMdH4/yi/B0Z/v8gxUbLq4x5Q6Vg/vWO5fV0JsVi2jRvTMwi0D8DHaXFTVT/NQdVZU4iTZxii4Fwq3IkTLwz8zWgfv58/fs8+fG96zE6/dftI9Ke4UVO1TxAk8eaFMkc16DcXrINkpvW8Rgk/GLNAsHN09CQ6N3AwD0CtOXay92V7jBNY3FjgpadUv3Rpy0uKEWTWGajfgJizgXa9ZsoY3GOp7xb5AnqpZwoN3Y3CB3lO7SOJR9gzu0bX75qX7TxTUQ5fZeYiF6qSgNoyppcBoBKEWaZ4AE1dUNCJBtqNzKuZPgOaiXLIdr9e2We5s5ozyvHj5scEapm1YPH+4vcEdPlcuDfJU8U/apfW0MvTzmUsDvDOKuPU+kEzF0SKddfxQJ3Ln7J/RvInnCIUbWEPHDghnDaujqIooPMMDHnT2wIx3u20+b31zI0iNd673/3k8lL5W5IxK53JZaZUcIdXBHNcBFryDWsRBr6oyzhkJDWCm7tOZDH0cL/cqgc1F15g8P7Clq1CnOxHbJrFZEzMSMy235dMbdSjRvYVXueHaFEUxQK/T6Tw1wFVYeTedM+IqLMw2dEHrQ6cLtyy5YDKl7UWb6xXuEkvz0ECQ7yXJBREHB2x8grnQFCiddPq/AEmuzNRJ/cPQm+8huDceWnt3ilCg9JApGjqXe0IlxP2RODp/Bzus5EhghoESQv5qzCXA6ow1OzdkGNi3SlKs5gIJWzgF6PdqrBqwLFg3E1Fg3Yu5h7Nrj8bH4HesPUjIjDGyA7mV4TUf8vLiImDdXvkDzw3pQfCOpeEAIfxO3ElAO4Xn0wY7hH10qGylDYhg0OyNyViQflZb0LbP9xOfOfBxhU8lCQz/SNNpDezR9HI2mx8d6cD79kGI+nx53PowUZAExI0yd8l0jNJxaP3zXBroe54kdoa8ZY420KvdDYpKFJJy0LhT398qGmHpF5ZYZF+Ks9h90GyH33cEEEGOYgp+Rcds2fuLnviE3ueXdQEsONpltcwuQ5yo1XmENnDhY/2CbRX1vhNcEX2YU0zsiI21j1QiU/RMCB8MiB8M8B8MPfHy5oxC39oRPmrwTK0YTInVRmF9ifIyGlEV0usBrhiil+BsE7mVmNuIH9f8Sl861Rup14saRmDCYP3VZRPEB+J1g3H1bx+QFQBeZksgwLY3vSshzaNy6hi7NwJAvx9zBDXhNcUGzqpxBYGXc/CW6Sd93GZeMUyczTtNh6gIU+RUjA8RPwZr0iw9T9CMDaYWx6AqGBxVjMagbi0HawZEYk4Fu8LEY0FiMSsZi7oZNdh0ZoZmRVBZtZQwS4dv0E2nbRAACO5tjBDq1S3HIo+9AHZpgVl82wop4C+W3ssc/+x990Opji+lGw7VN1nvyrlW9qwQtPwM1RtNNi/Zq3qED2g8urPmN0lTbBLvVrr/sWVEy0i2YPwy8EOeAKgPdbgSGe0b7P2jg/cD0dKC+AY1cmHI3YnxzzSH5JDomYg55TdNonydXgjPqjEl3y8zFmrfsLGcIpsU14Q8Q0U1Cci1Ob8nAxBsmd7u1MZ2ZqB5k0rcOui/F2EAwCu6hc2dk+lbyKat1lLnspPa8atwqX53CwXOmFRnSI7pnugIj4sahMBXxdQD2A3YfqIDIosuSfAEEUyMPKpKcQsJAOxtLP0ao45Ilbj7cQJ2nqM7G1vipf4t+MOJ4Ls1LLmImd0zAarHq2lDbE2h8X0JX+BhWgd8UJytsjP+OE2aCgKRCoI7JB+XehXVMnAXqUb2mYmtp5Z6eeEPXyS8FzsbSASKd9K4NXh3OeH5O1HPXCWPjSNEGhfuauTu5Ri7ujLR8t0akZoA179t4D9AXGiajcBqVFxt9TgK/qBjTNVGlpHAtjnGMutE/0KNQTskxzv54tJgdsfZGOARbTdMQnqLAkwK/noGRIG70oAGCF30sB3lnb5Aki9xjxwa5GiEqYC7+SS+CGvyKLY+clVhY1g5Vl1hf1l777txLt6GDoGd0WOJpbftG3EovtdrnG7GYtPztB8431Be5U0B2ltNgpIssDRcQczfEBWRxGVGiqFQn4LohpDL+bXJlGRE6IcZLyN5Qjnlv/T6lOOe7ZkcoxmvgJxJ6AUqRdpBBfYDoLkpWnGKvWYXiK0ZItKv3phtMAj0liOLZMJq12TIKpPTU4SieCWe7nFTlKeRAlCcLliwZ+MCEQqOysDJXrKBhETFasCm+hvibLAb0glcUzU00gUwdnHlgvCg6F28D0XEt7soU8erynPSMvCoVgISrz3EE0nqmlikpmMqW5zza2Wyf8gqkiuLFfM6mcXlZZbTzpQKfTtABXEuKKtMllOBJqVNlcfoWM5MEkasF9NRFLgl6Oe4iofwMrVpcFaiUxy9n1ePh5SwZBS+XK/QLAb30PXS6t0vK8+BZUQdNB2McCt+DwTkcvw6nc5WoLP/BAYTxPRqgIvh1qFdrUEl/VZy7imduaoHXK4yEGsXutLZYCqYWfsNm6ykLdwiMgMrKSX7lkC8yT8U4r3rzwELhJuC3/vTFDfdye0vxM+rJK8BnCVWmnsrBpLpWYzFxD8Uem6etbqs9Nv5tboHB6ot4BQarxCkQgzPihcW1GpsxCdJqezx3hrmsKmpj3OBOA3Q4fSOnMGUa5zcP34oLfD46o+C5jGNtbrEIo4gPVHrScME+chneAjSupNeKY19QgYlFGxEB3uC7tMPGSh9dJvcUHjQukWyXB0R+5y7ZkxgmS3R85CSt7cuWHHfKWdw6e96WwvDdrwsotQrdAMN1/sCumEcUzex1obrHYNcQ3kLTpYDMKquaGdQoP7l+r022lzDfYxvxYs1KJwDhmEANpzzcOJEs0H0ZMoCaOweApT6aJwzyGpExFwYXkNvk9ZnbrdxOlt6ul7LlDnaBufXl9nIC4Z/h9SPrhnvF5sN3CpdfufvH+AkaMMexyEW4/dgfSedpv2k+efLExI318/DDiM7YHLyGreuYgMYnhml08WLtKPXuBWrLA3Mqy2wZTCjjbu4mt4RTuEyQPyG8GAIU27CCsUK96gMfcakAGbYvWsKb0KZTARF5OLBdbM8ofByINkZ258+N8NjUYbk0BcTRB8Ozo2MThhxeuqcmP3EaUwzi6z12Hz7Er7Ux1c8axIG1gWCwsAltDwNuYNrUQDyUFil389PSvmCfWjjHPnmpOhf+Mu2+CDTAS7zQ0ozT30m0RmIwrEJnkOvi8kqJe8nSDcOYS6G8RzPimiIVfCG6LgIlXjepkD62GeUZCgl2nBt4ht9YoR942r4Rr3abCb/J+53UDJJoPLjlPvowjOQIusV95BtY2dzQATND5ZEMqFxT+IBSaG2im0s2RKfkMTt70LYeNPJ6ofn2saM62HsN4QFj+5kDv7hQkru/pErs6/RIN7LNEmpGaktlJ73M8yp71bvoNLFWb4OPcjUV5/o1vzDOz+Q3XMc/x9Drc3smrs7vxCEAm3N+yr7C8AZL/Gdhm0aiVbukVQ0x9eG/fOb0E7cuWIOjQIEJmNm7TJP5NstEwtOFxbISaoZ0kVQqSW5aoYCcqQkcGPU7n4wNh9l94y38UmbOMBsGlc4XWJYtOGeNct502RtKWLVQlKzkApMBnR8xfmFpJH6ot5liI1vllGWuNfGwynzazAL66PvQRurSXn0J652fxFwPzVVzJGOSbFPN/iG4TjJ6asaPKH9ektdV87hDFoYHFOdvSc7PsHb5K76zCZlJ2Y4KwT0mSzYe8GpLxoDZqsXIifs73Ht7kze620/Y589mp/84v5s/zhbShMO7xt8Iu0JvZ9wRi68Z87U2bSwAGgPXPPj2qEZbfVpIV2MX7uWCrq/BYgmAtPmqeGFrrFsgbG2gg64Qzr0AiDBZ9xHTrX6mNakDwU+qgVYyMC8y5fz8nosIjHQh4iGZPBxSh//piuCrXREXScbJiu2LLZ8qL0YXdiaeKTotSFPpwva3mdqFg/tPjqsu+TGEG8ZjzkCu/X+68SKRgOwKLhceOE80/enxP30rSzqzuwrpTCU9riM9Et7aRbmL1RhYBcs/G1Is6/x21nBspzVjnoNeFQpIEg4YDMKz4NixAhAMO8CmiwZzj4CmqQasgvbbnX4mhlUfksz2SfekZw47XTWnhzmsl+vYqd1nXWkeTW3neIobtmDjLI6PDTm2LNfIrAqs2EgMAcsxsgaKNTUS68VqmlvDeRKcNVSTxgEbZonvZKA1klxij2kFsKRYYeysoS6OLEZn3miCOM1A18EyVPFNhU1k3H7+fAX2TIlho4sd2LR3ySXvXy7zZmhgphnXobMqVTV8YFyMip5EVQOjwpc3I3Hb38N6el6+np7x3NXO9XTu1YWy4O58yyXkzHbtbsHvAkZXciTf/ZB4CZ2pqZb0unClJc7tdDlnYyyxFSSuuB2MfYmelmJZnsSSd1B3OSCnhTvX/65Q7ncMVO+WB6p3awLVY+ggVxcOVK5QEOlBzoxizrqG9GqgEx0/BjWPAjMP0Bc5c6vcCreFBx9EBMAxPnwp44mN1QjXcTFSfFz65EdsjceZpZ3ijSTOpY74wdSRpcTfPVJCFvIMjCSHe5vLVXyryXiD4yhYspiisvCXF7ATj8bH8ozreHw0zq0Iv2Dtxaj5Z//19vWPLf7hzm/xmrkCJKYSQH90zI7h3zvSHyUuFMv/BNT5nQXU+fqvdE/tdQOjHW5m1mYOWiZUD3YzDrFSMslnTYYClzcuv4PENwwjsUjtKzxiHQ5P7tY8ZjjJxkyb3CbBVbbGc6j5Gfz3A/y3hP/+B/57C/+9ssDKWFltA0b1DMQH32YSrouzuuvl85LMkE0x+AMaJWOcRIsQQXKQcUFh7mH5Pb3vRRUZoO2Vk7MWICG9SphE+EyAs5dv8a5TtricsVhOLiChEm0mjwcqqkJaX30h/BkfgNw7kp4CghbQsAFU2mTtenHT5bGMYap+lV7qlRF70HOEVoXeLQYAJLc9D/19RMQVKJUZyb9ErSC85GOZe4fIohG9v3EBffTq0KtFuJoW9ZacLKVz9hxdYlBVWmybOs/xFz5yyy1u0XZqjaxOqZHVSY2sBzE9xwFD4B31rW2i+7TyfZr7Ns2cS7tDB4mJYZG+pgDcSoZ0emVMHMtR8Es6u5p762iBZ2IlhvySYoR5rRWZ7EDuEoN+YVlIw/0HvWR9izAxAfjw76w1b+hFJzBZKekPMfXRuwFJECPPnbPpLQi0hvNyMGtJJy8eCIowaNd4H0TMFKDmPXSSvhX6CCPhaOjwgK7QMMlc8QnJ5fUJC1KsX0MK4YO38Zd455G+WmN+wQEfCwt8v3g2XDQ6Hj5kZ3FugMZpGIG8VyQRDt2kVNHQcxEHxwG/Ej9OPY4aEULPdGzChClhAtBrLwkJBOW/TePhkucSmRqpnc0xY9wh4gpGXEIujpX34MYiJAH3bowSm7t1RKdPYFPlW6u+JvdAYcwhTc8QIqgVjU+4kXAhWQ3UMSG85a9UJKIgsELH49zGA/0IRHzhIcseGU4j0zg971q5X5vwDTy1L8mbLG2EH/hN1bSta84Rv8hllMlhIz5rxHaGYCO2i0uGs+q1giUiQFmxHPKz1jOSfF0MC3rX7/mPb+3yy+Is7X98C0+vYZfE9O/gl+LHnlfdUu+lqtr8MFKYlh455AM5ZGRVP7trU2lkovUrazZEy42yBlE46Nw4UEc6qsIkGc0zesJyxi8l8NdXAiXQBmpEvmsKRMzcyMFFAz2lE1OYUv5WFnUH+d+GGKssRq6Ld3ooWJ+mcCB9hY9McCQIWkzI1isNVhpgZP5VWAHS6VeczRAgvhrqMnkT49nrN2+JUKgnTkYukBC6wBxUa/IiH11yIPywssB5UDjg8JE/FX5x5b3Bl32/0OVAeftayFS+UxLt9/vo5l+FN9syrYQq5Lnw3IEK0Ke4OvxOblotzKagU+K6gYbY7zWd8pCIeEsVwBOJntHdvIlc3dI+AR19CenjWET9+PLzJ1wY1WklMZO2HAypOaaXpknFiG+6CViYQf+0u6kZssVCekf7hRkJvczXhXwO/NJN1v6RIo9IXIlWVCxH1PwjEtgj3vSj1p+QRcCO+hFXzoR/03wbKxaQo7yNkoYJdSIjtDEgbtaKMKJkVlZeBFbm5zRVTMjGNC1BQzQ5DlJLZXJESQpSKgTsDMfi2wYzElxotaAJMGUZRGmyrH+j0G+FRkpfZGRrnW51i1cpZRgr/R+odH8UBvTQNAn9gkuhPIEcQDgkJSY7SgPfICldto3HoypV8/lzwz+2j8hizouPKhm4cjk6RpGg68EUQVfePiux/VOcxSFYhjYmtBYIFg4OHL4lOkGhFEeQsGaL6MT44YT6+o5RxPmWGUswbaNj6nWQEB0ZmeEjOCVnBX9mCGpwTWiQGk3andGvQtNktFXr2+gIyMy8dgNjqGKMneGnJZmC/jL8JRz+nTvp9O2gAaNuhzJNOfAsmTLj4grqyImOuDpM7Jx0/z5KFFj2YtsRNC43jYvArfzKFfPR3VrM44KtWAZvlfBdXTG3Y7BnjT9bLqImywtgCYXAeM+99NNd7SQAfjOxn/ibyQHYAy3tBwaU8A1ZPEWx0kcOlZhn8bR7+kiWaRbQ6X8yfIOVGwCNUmP6rME7lL+tw38nQq7T8z8ugeR1J6qTV3l14ivq5K6q9U7KJqeqDlTKGKshPjsTTUnWVrh79m/TXOW21aEaq2yMct2VIbBWYTkZhVVr/CCnsvP+HbRUjWLKG37JTjleTX2M25T4hqV9JEgAmyWyj1qt1pH26MlYi51L0GJ/wmAqpfZC2TiotCG4/SACUBRtiBEKzw8gJH71xPrrjgS6sJYAU4RCFZayv+SgMUJ+zyf8KfDcqYImm57BkysiELlL55K9DadvWazwKE3MckkBzpQHizfKF8e0ktIEKgqTC1lajj4zRThA3rZBcau3bb46wyaVe3XT8FfSFiX2za9h2eyrQPgUfpAawW2+uslxiZOjE9XpZMWe5IaUXGV83VOqaD2fT/MHmpkNS4QM5XUi6eE0wRNxNuORPqKKS2GN5GIUYq69MRrxi0MJXPbOkUxeRyWuiqLo90GkXIvl0L/f20fLcm+pFc9d7PCW4q+QY+hMm1/vxh0J4vuIJc767cfxSGfiMUAjbjbTqIrZ+yv41DS/GPAE5mGxUywjQwq/p/g8xNcS/2/JX93lj1vo1huKFZUcvgXnzgcbcMIfRHtsAmIjyDtw+eJKRBKJwpeVZu8goqcEuoO+YeiW1NBFJEmw5514EUkfEHKd4OXH4u6CclNlFD6W2JsmheXBqqExWC1G5dncqU6+rZJUyyi4qVgc4T4Sg1VKrNFBvIx1KhkpXk5t63kfKHzrW76Tth+bgbGwgIiT4HjBOTYFo8EA36FsoJ8FMty/Y5i6NWMew41kyNct6iRXdpKP3ZTpJCf72AM+W2K4u0jycyQBuKufuZKKUKHCxTa6utXAH7ZD93uwQiTD1VUfKiVye8YzSY29lrl9kjuFfc533uk4lDskidPX9GIyxk6hqCqvZJAVAw/L+NozcQL4nj8/xONLCpcmBavDI+3BOAdBvGIeiiaF3OYnt5LElvYdHsDi4tP16Z6GeGql2ucnRN+iZjAnp59onLk5U2iuuJOe8brCA2PxcFByjKwcH8OKe+qh00tkyFeIeBE3cU0SQUz4ITXy5pLFz6H4ldA434XBUkQweemXuHGVYJ65IaMoMq5c8MuwLMHslh8VYL+Jzvo+PaJRLt/qSIrsN72lsmaW8SZdZb4W6eH/+Yc04IDwF2lk4sQncTDlZayG+qZoivMyHcVSMunFzCQ5Bb0Q4Tfkow0wZt5cgZnzP6sGpPGtGKODz6kLFwYKxjhdN9T3iK6So4RPV4XXmmB+99h3ztL1XBaN8IhUPvUl0oxP6Dz1Y6hUSCExsZJt5ql3ffPpymb5h9fFkGw84GGkMp4dLOfZwXKeHfnnzNM7cxjfNh6BafvAbzkeTZ8wmekxhTeZe85l9LDXPh3So2a41EEa8Dan/D3iT7HILz1Oc5K3VMHWBH53z4Q3Vu5tdLoiyUHMbnqlNzu70mXX5OEwnFwTYg2mvCiWL6g8QJY4scIoX9zOaCtsW6rRJjmyuuZvgqxQsov6EIqzrMfOzz5amDhVogOchhJA0UrRCXrJn0tQnDzVgXSTDk6lBdyNiNdox/ydYbss+uVdKx4p7sQskQohkj6IJEx+o5H0NvelPAkfcaqf773KN04zJDu2+iyS7YriRvrcD17wRT3g+mvGryRv6b1c8qeml7fpFx8miJ8+Rw6/Ukr4kwdPMaSukdQbZtPjEd44idwJHoFu79dZeDFYNAUaEsqhCIs0YJeTtb8wdKcRJYRHnPCICMe4nhj6lRdLWh8R9TwzpEvQMjOyo6QJKBEiRl8k2VSO3kEsVegdrL8SfYZPFHU8iddLr1Pj7MVcMhQwihGGAGbSaRl46U7pAlj2VT5cEDsiFjqfXKmbVgGFli5/OI38tIjtiXwh5/OB1/mFFHrPUcaadrxr5xYf+tKg7gU3aqI/aQkaeQWB7Ae0DHCSJdNmHXFv19ybgpX0EXmgpYCw7pcZlD69N8zQeVbOU9ixZxhdKfPgdqoxoH6pCfufP+OfzkD8PeF/B+lr3HL1xGWHZW9r2y5XM3ndOMISUkpKlaPD5KyPa6q3DVGBgXdeRar6bG0Ci3fJaArLUpLo/j5OtvwnNkb+HtDzKkxg+PyZw2Nwvw4CZZS91Ec4EQgMANjHWVqUOYG8lOSUMtF+jLVQaL9qmwfJpI5wQl1mG5TMZWkbMk1LOyhFUc5p9a3XB+aoolZ6PZoj79EM+KCNvrZCVNO2Z9nA1805+6H82czzxE7D8AnEATViAD/y8fDqLb67yjm7If3xlnlzC9iHt9Iyb01KY5Lkwc+wD1HGethKEMgAGJocgZyhviIrfiIr/IG+pGzC63MTAyYgJor1kDwGkoxplCa/SpokyaJxoSIuPsya1eLC31iUtzqxKnHRsS9udp7wvwMrsdMTnTASlz6LOa3MHaT08qqqlF4oT1KQWnK0RRDFpJ2kBi95UHWbf8RR2QAjhoAkYwfh+75LsB9A1soeUVRLnDVeECTebxRFXyxT2UU0ehZP8iZh0gVqMI9ZAHhzAcWlIPP3AVmF0Ke/u2kkNuj2zKBbsmIAZIoGMnJHYCLhbbHw+Bh+tpMI1g4YUQ4YIH4DFIkLmSIiSth0cZjhUssIm02Z7DZDMvsxOIwrkzE/aTN6lCccooR0YlTVh88tRcRUrkEW6hufxUfR0KeTcxCq/dsS6jr/2/IDdPH5+C9/kU/PjT9UxNu1+EX8dJGodFuh17IHnmmAgbKAeP+9lN1aGtG3BF/u9hwb5S5SP12KYTSW76eM+fB6lWTIp1RExi9JRvqIish6mWbJZwV5xg+FjB/wOUGe+dckUz72IjJ+TjKyD7KMt9k2ij7TsxevhepPb1YXroDIYLy++vSHOOVwsdfSF8WQz7jZgcvZhp6qCWE07WkqGWlnCvZ/TLnMrwLxlv+0TJVbpqflPo+A+1HCNTCeuYiDWF4AD5BkhERR+rulJc0nvtGTXvbLVGsAHpvW3hnUsbwxyoN/4t3F75L4t2NL+WjQMwM6MoDX/CZpX2znWkhTavKoDY4cOmHFGOi43TO2Yo7i09LCsjKMq4E0UyBX9QY2FieHTX5vd1uuCy7KdEFWes6eqZcsqeHKSQ1PyO0sPMuYp1ByVDLbdc0K2e/0ZAYF+xSpp7K74wO622xb6Tq/RqjMoaz6ebIbkFMOppnIJ+21oPAYzK4KND42cjU29hUYXt1JhY7qDLLGQj9poIx4UDa4pOEwfhMEEpM0M8bvFD4ktsclChFPHFrKxsEvyzNVCVpjRRd2OhaZvMlyWVX8z5IMXY3QYHYqdG4nEZO3+J6MJLBboW7N0xp12+knbQ0djFnyygk/JjV12xU6d6TG3WjzP6aIuGH2reyd7cIsVqE6chNW2XXvTLiLU0tEnEuDHhvJcyTp7k2cnvq0H9v+yG82daWWc/9DbgQntcms7V59V65OrhR1kgShZ+r2qngEvP3k78t8+Jmf05loFawwxjm+EGH/7/L878sPhTlMgf4OV/9YZkWh0Y105fw/VNbgf/h1l/9Vfv99CdxJibuWRt7fl8fHslC6XSxLKviVFcyEldx9L1CdWOBkdws9huY4uwEx/VL7Eoaye30jOH7diBe4wa4b0MwFrMro1x+XfMOd6SMpP3LrWups4XcJCljqP1jeQPtOz8Z/mAVTcq2A8f+H5EVomMLojpLMFIHLaQFuc/GPVs6U/fzmpX72XzPQL9bFu1xoFlrz0dY1zcKFcrFNBSHjXzOKpZb1KZWuolcYQ8C+eqeMpPHSiReYevuuGOfn3XaLa7c4+CG4ZuEzAG/gbvsf44a4WYlh0uUTK7GBsZkisIYp6oO/NUC6gaEJYw015Ntbko8EAgfCQvyIFxnIZyw965sgvBQ3VVQzO0DZXfF0ldD447tW5s0ZO87CAqE+lwVkZbaykQwPSI/qhMRoeX6DDCe2wBpE4QEyKEwZFBYYhKSFQFdOBEMkIG3cO2ocWygbYBg4tMA76I0SGJ/YWmj5398pNbxgmdOx54wHNg15lMiNu0heh/WCS8NJP/EA0wjSbzw9N6L0m4auMU0TLsNgvTK8XMKzwPOcFQxqY53LeeHPRvIRj1wkdzXOe1sE5H8BXRi6sUhM3s7OBGp3WSSjtRgbbIDFDGgW/IvUwx/xYqpBBMi/CYkyASjDV1W34eL4OGXd64R1zaYh+bdXA+5GNxLMz95ltHl3sYWlMjYnm+5gOrUsmx5gOm9qNiPCDN72bMY0yUiZkYXwEgjkTjZvDXnwv/aTcFGYBvCaFjR99pyt4oU2Z+Te7QXX2icWBpU7MZXb0ElvfFTUAn9cZhUy3KV/m7wxgzZHRZYMy0i7nfRsVhVgLAP6R+g0AtMasVUrffzhG3L1JpzkE9E5JWWDY2nGbl6DwfuNcEZsmhnA+NjMQ1Y9lqwiwAKeE/H4WBw93m0VAHqKv52EEk3C7xQ9hZ7K/YvZIoleo+MyS91YU56UlCqZaGyBibWENTPFYWk8eu83tD83nFjTz/RH+ggwoovkufmB1gnzBZD3WJZMmaPB/zmwqjkba43Hjh/4t8tgHT3Rx1YZ+F8Q8C9r/ryR1bbaYwwPJBr4zfh4toDlxXyRNvAXlhyr49H2apEGI+ITwHKBb9Th/q4IjiuYIA3A0WrBz5wqhMWolzbh/UzmcGh/an1vwH/cPEO1nLzo6tqb5/gazhIURLI3wYMVwlomEwmFxzRI/GYrgqToW2xQ+csWvvJC+xG98XNkbKLsSxpZXNvEkRPWcB4GFVA8wEVSGnKKE1lIbvjG+YecMIU22xYBGQCin2Eaq4u/GqYUxoK++iauu/NRQqY0e0zNhmVoxdsfZRzKK/xdHPNJcNg1DjgZcBpGsJvGiRK+U0pt/IFGa3+qXB2j9SaMqhi3yC0wOTFeXuI9iTyN88FcRKLqoYge3Aki/sBZqDxfTiO0sOA6lzpWPAD2QQxS5WBlCxLaqhH6zFMr4xrAsTiq39X/tbUZY5807ch5+NBpqV2dvPmW6416dNm3Y2rJ38o37WoxNvDSZYDxvKfwx6SA2xFMvXwceXjQvfLwjXacb9b2VPmk7fbAduz2yHnsJQFfHnjnzgfQrVNvPQNjpJZGfaQ7cpc/eLxOcazPgzvgCPAYgXszSDo+f8ZH+yRGnXtFeMk63wiSPFj0m49tB31g7eDhQ6Qe9DUSAIjloUIKMXLAZgv4BoECy90s0HMJasY/+izAYzEBbbSfBJ8/Z+B5EGWcXohhoOk9UPCNMXoI4vAeG/RTeeBcFd2HD2cKf5QpjgyHmT1LEaqZ2aeGsvd3lfEK01eE05cx043Zlp8FpSwQe1DbNOI9zmYmzUGhgcZt5fSVnM96dsNDR5qyHUCYfPUzsCE83RqPd1Ho6Yayl/KKZcO/KlunlZt/T5M94/w+HuT8P/bedLttZFkT/V9PQbldKuIIYpGSR1AQly0PZZeH8liDSi1CJEjBJgEWAFKmJe3V/+/f+wz3wfpJbgw5RIKg7Kpde58+3b12bYtIJHKMjIyMjPii/wwje3kVBVpD3Xtv0C2cPjtim40GrfFIYYL2vUCmm7LuylocvZvK0TbKMpXxg24oXgFWFavmpVav2jw137fVO6NPplYYnbJXUe7R24qCzzM6AC37CJXVC5IA9SZahjCPaaguHc/LrZDmKdVhhKV+Dhdy7mndXBLmjm4u6Saw9JQBNEa1lGHjq0o6BbhbYshhFWqXsgCri1pxuvAnhK0LFT/LBmRfi6VNZLjiOYY4nmCIj3lVPkYQNrS82u705sFcicdDEL+xkJERLguPRehzxjzH9T4yIYovZyGMbLHVHICgetjfGmz1j1D2RMiIMNuaoWYl9oV1g7qWteZoYjNW4iotPe05i146tFMGGLq5pXDBt7AVaisVk/bWFoMniqsXZ+w5EJo/qSPt6WndTTOfbU9P1TxTkFCBFGnvn+lqxZb6aE2pSs7GIruSyJwrEzRjUGcjbQN6NT8AuhS8QOrZd9U7uYrl+7vV92odizyw0lQescrk+7Z+v7LORC7LE9TSjuWQ8mV3v39xAefA8K3uitvWr/pGMRFUMJGhUVfowytXXSYkBl6jOxOsDikypnRXSXraUBJWVw4LhlqAx9AtWiCJBqUnrbr9Wq7MKJRvujTNFGQR9r/IFgUVRJ6KDGMNMIEp2IWThX9+0WgfFqEdk/ZZfqajmwCBPqEFK3GerUWCiLDdkw+tfI6XdifARZQW1RTsBXjk0U9mC35CMe4dyxWFkE6a/ifpg4fvta1fGi/QY0HgrKJj3nCuPA/W27SY3lKfzj9Xo9RXrEkexf6YJANYv0I98GD1+vRrgYnjemDi+ApgYqF203uSqvsZGe4ZlGZtiSQ44rN4Hbz0R6MAwFI1s6tgSTj4zv1v0RnUADX9i6CerwERPiBklmcuK30d/7UWH7x5I4Bz/s2N/qwVSeubjLfA08YIcdk1iE6T/vqNwWk8+Ii4D0pQec/JsNBVwgFn4IDEnmk3N7XwyXz3n8feru3Z/djFh7vaW3Afw4BoozgVhOnqL0guaiXFA6U0tXZ2ZCHfUjNYEHNYM7JIDIjNwUxCeVZaOOIH8eJtlk2IVZRZhoCmNnAmDt1Zln+0UBvqYmGlHKOhZd+TSuGttd5OpDaFxxKz9dHwjXjsh9MQHW8/UGxAz39+Kll9LaprQpzDAI87LtUIrs1q2m8zjPusr3A3YAiJvB4cPBR6T3dOP1a0IPdOuUUWBpcOMdYiwLkJx85UMzQ/0K2X6c8LOOc2X5Aq8Z/qWp/ukmxH3jv3svv7+2GbbHbavd2dYLez3XyC1X//7PSi7V207Xc/yBu2zRs7RIUbIohYaSS0zW0bm0O97OggFep5x7XKaNyomFTcqZ7XOreULGWK2FVl3DKF3LqhbSdMOfBTmzoomfBmR0UK6bR3lM3CTvvGHRU2pH1XZbvTuavz3dq9ozLu7ty+pXLeunlzV2Xt7Hbat02zsPfaJGWnc0MHItm5sXPnjq74xp2bt7WI2r57u3NTfL17d3enc6utxqdz98ZuW5VxZ/fOnVttXcit27dvQ0bVsN2bN2/c2BXF3Nq527lxU5dz63anDR/bkVLPWga+sdOB0uyo6QTdkTs3dm9CaWb2dIKKM7J7687t9l1jsmITtLWRikFi6m9XDphV9vTmVKG9L2LlZGGg2ydRahwW6gQZX5pXvItdJ9a4hSjPUMwzLIXOozIOHivfE1gRKIIWJPDDbkmZfQzvMoNP1TMZpp9F+ZSfWCTMN/XQ3dZnoILWVhPf/SPy+SnjIH0IVIHJcFzGhUSaXlhmKQY1oV+Z+ouIcNDSAkvIubxsM8Qm2XKKK8tRP3KK4oAftYOS8+KfBIXqzQjjr+DXESRso89Nubld+tE+GjSjAm53Z3Mz3USaBAr2emWQ2JH+OZaYAU13oDf/0awOJ7RWjqa3WVLttsDHqsBy8w55KkBjdnfsJTzyPcRnHJqZpL572v5fv2egi3QzLJ3oi8DoHqFdBIxGZ28v70L55H8MGf+R1EQI/DH+ithDep0GFb5UbmFgHs3QNBszrOrfxJ/+Mk8qt27Gu/8UP9ruVNhQhe1UuEyFqdTzECjzX8dDtjuCifwRmygY90/1sr5/urcXdvyN5v1Tw2tRPXv/NFSD5FgdPa34ueJtVdju7nb20266teUZJ+MaN5NfY+0tLNcULAi6wjXDRi4u7iLDrV2uMno2PCuU7gS/xK4Tkg5o5fBL95Esv/5chfBEAaI0E6Ai3KWs0nAOX3PUg6UWdMX74jSeTFgjMzxguSdsKyZcXfyDMK7EzSz8CaSdJsNhnCroE7oLSMNs8x+pYBRzyyiGyCjm3eJwfgT9GOCfbZbXR+EEnkg1qO0DsTBM5HvbOTRtvjfSYWHnMN9KZTjCD2fWPmnWQtLcDLc19e96l8iShpc5c+vfYvLyant+xAkJ82zts9GuoYKLMAIGDD0rpVHRb2ZrXKWrFWYd/qPsSsaJhgKVeePvnJFHXIfVpAu7lC/SzZ1bnbu7gu2/it1YrCuVdGs5fHc9a082ywvk7Yg7RiATUIinGL2t97pTL2581n0L9rydXieISyy1mdaMMIwsb8WB6AoZCVR3jJ0gDp24bXcg4YajLaQstxxj1/8FN4e/th9Az0CqlF0zXB9eGbGzGrWvfblqiVKWAkXmp1Oz8yti5nWdFzhBz6PZlbs/UkUrGpIFZZUwPhjdiqpDU2Z9PX4u7A/1uy5h8OhwZWYFYeUJtCE9TI789l7SKuAjlN5qcShWHeKtYWOOOO1Q5sVFTv0gsIqEw6RguNkSOiXl4rSUh0DgN7H//pTZx/vTvbj3g3r4AR9iK9T23p0GP58GP5wG74XJDCJiqA3y6bQ1k3GiQFKNw7MkHWZnrXiBVsMi6BUUVkyNJjsQc5uUcjVSoUK5h88hvBfBOCgpFT2MqIfaXOLwx9Mj3zz8IR9+kQ+/nYqI2Vlphl1FN8di7HHXIQby/CaPxFQ7D6eHT0+PLi5S+upcWfBaQIbS3DOyc2hqZjN13ijCnsxQOogrbqBOk9KuymYF2Bh2S7d9a7xoS+OWRkWie9vT06OrnKqVT3Vnl//udup9rXeNv1l9zYPyr/puCy9QRzc+jqmj6KP1BFVcCLvW0BGgNPido/KeyDYcvjo1iDDlxQUnhOenWcKYaW8QV7oIKGIvrHebTlYj5sWldOedUwXx4XUoaUNsEUOVHo+PdKh56yiq1sCM//r4d6t/EM0QFRdN+IQvqMqajg/jFc+Aaw9x3b0mTLJ8GTSeO2HIZpM5BjJQgQ5Y6zmbn0yS4tTiWzGgGctPDbpmJQVy6xpaFlOlYWnNo6WxOC2SfIyR7GN2DcvSBxmUHx9MksFHvBjKx60sHZ5MBpiAbq7A7rvxnnbc6MYoHo+ZPUNNottT1e1kfMjYm0foTpKlGEF5HPPvJ+lsTrGHEHToZTpZ4m9tboq/Sfer16A7ctTeIp4Q/OM1RH0y+vOo0acPGfaQVcUjq61GzSiGYiPQRNWePhxF0uEE4R0YDBl1qQpVKSJMpG1Ca6ISWo0nKrQdlacud05QSU3EhpBHjb5UfvdbjZcI7HCWFLFPoSpsza1rwX+95itMDdEAxInW0wh9QjgmOdnrZljdFdTP8cq4qNz/S4yMusT4K2Mj3JvlXn98ynaRxRiWbm+jHeiEjBM6QTRuwXEIv+kVtLIhE7zlXxVV9DXDVc3dF9kREHcg5rAhwZ7GVk64b87RFAxeOGBKqQ6aDpI1m+KihHNPV0PJro+v8XGhS8Q+yZ3a4jQwGySlGkV8Jf0kg65FkIwVdiSujsWesNIL/2FPT+EB6bA/ZCCE+0mOoQQAGuPFquyI8pjd3NxoM3ZA8yMiH+v0rRROFbHU4C/qh0jDTHh4wz+Fg7OshAF56kfMRh4NKsPjDGhtsQpSwB0+BRjoDoUxMr9JVjR4nu2DdBxtQ8/pIcoTeMDj6Np6Li/10ODdiciApr/Sq06O0L96XNy+X9X6qxpv/eZKi/yh9NNrWp/Wtj7/e1ufitbnflpt/Ys3TYVtJzzs5LlXG5aoVp0gzm5ZrZaelM2Jap4KeFvtisEuqFvedKXsx1cZr70pV1yxrVUUufqR8SQpVKoLOUFRgkxZ8In2iZPsU5/F0n4eDZNMCpUHpXv38GVjc2noYO22S1ovzABlKC50IMxXIatzrKE2NGaOM+fcQ55rOzz4xI9CyqAZ8xqDcujRiln72DVr10invLFgtAjv0jV9R/sSmisE8d6K/chmxTtQOLteUbvwmspb9gE+OoeGkDBR05qUmlB5W2kHZCmzGVqzYlBfWUjcOiZ5id7F7J1hT43l0aXkPmf6LLVR+UwTHhFhz0gagZLFutVaFAVh06AOucTe2iqqtgOVQhRqnjER0F6teqia6KEoPH1QIFcNjLXk1OsDVaJP+ygCfoNcgmrAHSpnXEFcFC09vs0qVM1DR9tgrJcHY381RGn/99/RFGtwGuUHsBrvlc22ZyyCmp1b3la/0b8UhT9QhwAh56klQXKgI0iJV/MxbLSVG4NvCx0YimxhaL0TvDAbwrC9w0kG/6iqyCaizuAEMVDxYxWXtDC2JUpww2ryjGwvEL40Fc/NYhYPktFSZyX7ClE2GbkwyvBKvRYzFVvptRoPoKhhDBWXZ3GcKvOV6KrqE9lu6h/vCCLcdhHrTj7XGLbBOlMOW/K2RYLt+2hSenHRv2ch3xAXgvRA/nxM4FzmZLY6m+8rLyb/1Fyy8Y+YSSr+XzKPC1NydRbfizf/G8zhhOZQmOeVrgmlXyBPJZvuft/PKsFV4blm+8JUJbU4aVqK6IHcnPl9fEOYBxSdI/NqZBqdp1QGjRnFBpifTBPc3ukJgwwi9FPNx8ysvSALBSYMyQR0D6Optk9f09NGSM7++h3w808ktQfmvUmry2bamaq/+YaxMV3buns44p/wxsJtqWhi2dOZNEO3n5VsKMDVRBsWQ6/CUDc2Isgo3msmnJg5SmpnM7Gz6flFhQCK2k+KGgIoKgRQaK8s35AXjmLh1dIBZxWWnzVkyr4/TvOi2uZFNc2LRPNgeD42oyqBRp5GLSENsEGK3SCPI0uVkaRKjXPinZOsoSV0wqEgCumjp8EWTT9iRWj6CTRN+QVLrWriCTCSqYLOJw6fLS/zXo/wWbUcWdv9XHZ/YyP3LS0UVpQI+M0KFeV/ExOgQc6qRJB5Pg2UMOcr9Z267CsvxFIS+nu9FqW+9YOROWjQer2mDQuNmvs8Tt0oujpVexMdTFsHKsnc9dhcjlhkdJOrSG5OmlrfTpo6bV1cjHCHHI1rNDgHHGYcNgC1R6ngM7xVQTnI3Sfxp4ZuXKvxU1QUVQ0ig7BDKoh2SWqCyBTmM9Sk7XHZ+61rGAAjgC0GdVd5Ni8myzdx+SRN4/yHt8+f6R7PsNWzulbXNSEhsH1Sj4lyTaGNIlP2p+gKXqiA39xNq4VjbW88xCYS3Lt61k0arooa194VHArC1WeSRk60r0C42z0ub1/HxcMB1tF++7quPuW0Y+UPK7vpc6tHw03YyO69/jff0JKqA+wfNX7Hg8TWNdQGS/eeF67CgZwtOM4PkXh4ftm1LlvtbmICaXQT1Mwf9q/3t/AGE/WDyoqi3U33Yp0LzVuScDWS9HU81qRH5iyBv/UQKJs0Jy1MYKchT2JOV6P9Rr/GITKw02ko+B+d1rjtsWw7dRdabvZsNIbA58KW6XN9SW19mvGW5hKPcxrlM10aJnB0Exg0pSxeHup+cgK64B3I6Vhegqjb0FPUxdIlGYyCdJvJMTgHJnrdsjWFpiYz9EXeyHs1ngDkAEDrBs3FJwnf/Bj61HIuiM5RnkdLXF19XWafzMLhSMjxK32kRy/YkJXmK7dQf6bSRjGIJtAjFZq+WjUdQ2Xdl5d/4rQwrTkt8KT+FxPzC6fR/yo53/OnFfbzyN39vmbMx186oTUQICmCBn31weyt/uC/1qSZfv4bj2WeP9ZnaiuIKGFL3n+urNmv3dlqdjOz7+Nepju971xMPZFa+nLDRqcwUipyTSWYioMRGumEWgBeEeBqpDerga+8qBGXhYOYuy+WMoyDENS10C5NEK49UbIIcrnlyvBh3HE7Jn5jyPGJZijUGDHrGql9gaPnfL3T2dPu0i6wvi3IBvwhm9eobEwRVA+pi0olVP0wP2wfwUkhv0xBqkcf/BAPDjze1eEhYyYsn1BB05KMz1N1X6PubczJjycnXxG1X5duNDnY/vJFnFOsoNCqr3X62yjRWA76SG3GxCR3Njd398iHmcw70NTjWRyNMHM1bb9zc7vsYSNMOQiJUTr2Rp+FhrLfaPS38B9UVMaR25n7MuPWFRnfy4zbV2T8oVyDfr4W1EDdW7gOMgxm0L0aSfavoYSugBXEGgTvKuzpFXBYF8Lgy5/+qdoqpuB0KSvcQFwSPLZX3CBoPX3z8kWLDyywJdANkiK0/XJ7p3dnv+z1zylS5SWwiXNyFNZ4Wdu3EVxXvNrqX/ZR1aAL6N10Ppef7vKnfUmHP1fujDo77e2d/0hlYB99JX0fudUW9Sz30IF5DXjquSu8lwaIxQrDfEI1CvfEI82Ak0Lysj5oJPv59p3NzU57j4T0kLphhiXZvoNCNyeWItHzV9q89V6nlCpFX6V/rmYVniHyOkFdFFk4JH1XwFdKsWeuG77/778fKkTvZus/vN+Prn/v18a7LOX1wo+l4/hRuc7U15SGVK8iJqYFIgWXEm4oIoJU915zFd2/j7/7amcwfrP9Q/j8iJIdjPiXU0+DRIcWPtvr9fdgZrb6+0C0e/DlvoY2e2xgzVBjqJysBcY/+kiktGlshzt+7FF9lXMdbldMbpWxyKlkwgO41t/Kt+BfumzCwETbFgtkB05qOOjojdPBESuDzk3Kkqgsfnsfbd22CHUVkaNpFfX9Bv5V+DXwtqlf47u+hzUG/S3t3IOrNcXVenm1bUizrIeyhkE0NAKDGdgPq7xIXV05JhzPXYKzMQeMZkfwKGwqk+H2jodNDhwGJakKR1ZS1k1DWfQGx1z4tdQwGxMkU1cBs3F45Ed0sI8oUB/BRVRnPfKUilLvsQai5TkcSSOYSll4ZIBfgKdsh/pxK9M/gAjYISba6of9rcxYtCZCNOjB/O1Rr/a/6QftvdwmwJQkKkZfA/HPMYN5+Q3NfEPkMSmefrsvGc7TykDBAkhCArcEmUkMTf2CiDxjh5zASCiQCsXZ7VDs+AXTPQxWhif4lWJ6zQxzlJzDz7dC5qcwRohmUWDbMfW9TM0w1QtqM5sgZwNsfeIl1ToHjFQJlSaHA55DbPPAtNmz9Q24YBpfG6FUqJncGKcJjmIUKmNZGsMJsRcvrbYCg8tEBAk1qSART4ilRGQ3z1JhRIbwggq9ZCtUhA5bCjCnSmiy9SSdeeouqELShZq7JgZM3c4s7hhCDyEyZOa2kto4sDiR5whMhOSwmpFx2UrEJxuEKQx5l52QnjcnfuF1C/gxgB8aN2silcxWcz6QyYPNTeDqE08wdEoZuCnNnT21k36MlwXkN1hr7ouBfbHd2ZtbnE3kvR4lFpVErwdTgGMPw4XkGJ6fwxqDNTXxB0A+wNL0y/7lJazTZkK0arL3t+ZE2QlRmkgmGlb4L5Uq+lvIdrIjv2DZIar1qMDVWjPBpTPBsQWpEi2IVSXpYYxnCaoEXS7ChDcdojXJnpwExMHZUin7VuZBkB1zB4AQ3/bhL+v+e80IV1qNZGhylzUllLYEjzyC6QYE5wBE1IhMUihgMGLS/1MlJ6EGiUq2oGishhHYsfTApikoXqrTF37HvzqeIj9IAcaGAiCZRUR563ogH6gvfRHLrFs19/yMx2Kateqe8ItTrzrjajfkWF2FOsdWBhB0TqF4fDbYJ6ouWDNAHr8gEBAC/nax7QZLjeL6XYGohhJ+7qi4LZwaiS1dfTFpZwvamtLqUT2NqKdQ+RbF81Pbna5beT3R6d3XiTqwWI7UkfjOER+HGMoy0ckimiT+kL0YjSqlXjWAWKSls2vm7q4J42O2j8Sj0Jk1O8ikZqUPgKEmhxMUNGnusm2DI7k1sLJIez+DA8BW2JcSJj33tybECAaXeWhXeISsSY0hs6dqz4jgYWj/wMWU4LmI7vlhyG1gGecLE1+m3skZ1Uek9CEXZzJkT1G3kBUl6kk5HiQbs9PzFwKcIdjAC2pZ3VR6l7xPqXG3tMGB3xA0FM6F0d7KCuh6WSjoH8UY/hJGJOk1J1shkH1GQhWOxITWaILPwFfNGqU6Ea1ypXyg5ImhZFpHHlGuVSz5dRMBG+f2tvI6SeSFSxQmyN4n4eqi6U22mu+ponc4hUyXvA9gw3FeWWkRMT6vT5lFmPR8S/hA/Va68FX9b5gFxBgmXiJYObasr8rVIGwluhMi+8RZyLteruIAwCOOxTkNd4CI/DxygQ5h2zs8CtANUQxPgB+XvZT+qhBoig3bEQ3gdFBVuQXRJc6gn5u4sEZzEFqN62+oV9Cn83twVv/+vx9ubR99P576cDIVR/DrLqslUPmLizdjiq0ArCcoL3X5y7ERPkpPA6CnrehtBOyS4uXw6KStk3lZZulqepqd5JVUzz+pL3ZGGe9TSTL7oiY7IfFFQxjzouirx2Gy0D9nxIZbExjJJ2U8hYLvzctsMMnwRkG3bThZ887DqIsq7kNOEbP66LPCZeIv+AY1s/Qm6q+MiX7Fg8LvVwZIZ8IR4iyVsdIZVF9WR0dnmCRX9haysYn1cKiNq4csLKwZAl2uDb+iPjstp5N+L7WhICszG9S+urjQZq1sd7HhFK0mjIpWvzFcfb/H7hutZDqD43dSIoAxFUftXkkNMdRjbXrbT4UPearXuFZAKc1TmQutE7ShPO1z1Ml+OdS/CvRUNA9kZ24yxVBxVCr9b7+kLrC1fXkaR9ppoBwhDLNbUf7nix9kEwoK4ZYEqeuag9fnlcwR2SToD0yJugDqgH6gVusH6s6fbjIPgmzBCSarzPh7lKXm45NxgQgj+hHv5/TvaVxGpo6ktNWnmduANKPQDcVfaCvSIoUIUoHIZbNl9+UgcWWxUvLbR6fPHEyCc4jgRmifZnyjYrPSLl2sg/5pR5HR6Y7+sat/3NA/buoft0zVvMA6ZqntmF+75tcN8+um+XVLtTSfqTJz251PkicTtK8iTUVXgSZU+0uRLD2y74fTQOUYWh0++6jXkFxblYWlFlzdyrPrW9081tBlynxOvCVK0G9hXOrYos3OLbPZm1ewUc9+fGngNC0YQ1qHj2Q2PO5TlJfJYKLHJSqSof59MskGH/+YZ6VOGMQI6aIehrCEkokuZZhEk2xsHkwm2EzVLz2H5GIpJiUZu7NNTiy6RpwQUyOOsn2QhDCFzUL/jNO59l2KdOWGgPQHRey4Xc2n0yjX5DA3mU0zcE+0nk+KEXIzdHs+TXXZf3mBrW7OioxRarC5lOiAhh1rPoCt3Gav388541AT9lAso9rtXJEmiyI2a1Ue4WyRyBFVX5KkYt+74ko9GkGaWhss1BNcFZba3s9yQHM056Ww3Brv4Euhy3NVGaIMvBkb1xwlyfGlH2I8YLYUYSGgDX65KjN4LJun6q9ai3izDzPnV71/co4jx8Wry4kNYOdb/QtSTsG/uX8wRo8j41pEj+GGxseDD09PoTbEMeY8fu4F6txhTd0Sbe76io5xpNch3P8s1Jox43iU9lhLk9P+RmTPUZ2RE7KKot+4NxyS6QTyrX0ffuA63Ud7lD1iqPt4xF1mczT+Gcb4QOdhsmF58PJ5o8zjWCNBcwBBfHOSZ2dwoEHcr8rp+gkcod8+f+ajw8iADWXJPI1OT2jtsvdtsd/6tvjG+n1TbEKMI07RUkmEo3gJ3xbQbT/3Uz/yvOAr6xnGBTDCYZSWprI/URWalpP+3kxSYiLRx+ZXwidEBzicgmk7QOIPYQKFP1yl/dgy3XAlUKMGIi5wlL8tWt+8idGQCCM4ZmN0p6dx18HwGJAbJgfOgS2gAIS+9gi82aK5pNKhF5qfNvv/jeLUQipI0g4ELtARvbtAveEBYk84hJwaQs5xdSlCRs/cgIMuGdgnC68jCBmnMNUaL15w5+Y0TeubSPz73998b27w1k13qXUxV5HXV844js5aujo7TUoOFvl1dTaeRx/jRgG7I9kxDbP0O6VgitJlA0rII1mmtn+DUSEz5ziCRQdCMJm10XoE8TgfxLQs/0yHHCLQ1/QylhWqnvKiJGN6mntgk2S9gBEdKBX5pg7hSXA05/ysTMOMZ7lj6CQDmRZprffix/Ea64FWmb2bzfSljrQlGKTuPWJpb0q2t/uEINaFtdbc7uzJV32v92Fc5/37Abky5P+guLO/EhLWgnnTacKifSP09YNkSLM7jaMUEno45AWzdO7iy7HfnxZQPwKJPlAX0uXf0ZoFcLUs3waxZ5R8+vrWsZmK9gkVo2zsTDrY1I17qq0pCK3PVxqbQmOfIx+Axj5X/KDa2DdugxT6OPsJ4FqwXK6IpwkcFghcP182rn1bBNDca9omskWEbIb0Hgxp37PBeVLpmdVMihfRC2hf7wXay76o83zoQ46+AmtPFPoGm65qtkpG1oOiqAwqIrEjDGzxCCOjxzQ2P2E1P9VW8yQdYb7lP1GXZ+w0zeVPGlpXnYsLZaCR9whTwBITDlHAWqxJFpWInQF1PMLfkD9AZ2j8u/pdatTnwLvtzRPW0764eDRWKGm9NWWnQfN1rDAasA68eUo9FbTQ43rTrf7sk7gHmqR1Rqz6rmvD3MS69qFkDM8HfLaH59jNqIqfRjME0GyM8mzqDmsSIxi7okVGsNf49K3GI5iR+FOEvjo+fxaen8NRY5ykr5PxaRk0kFVjwVuN7+Lpd5eXwMCNyfLTN78og9PSBC8bgbD0WQGUINYWFOlLD7VSs7FzChwo1NAJX+RjYnXtJbD2NsrVVHOHFYVn48MEliYqozNgiNmevuzpZltbXn4YHWZHR2FijBeK9Vf4BSoNN1LEYCvwsq2EP1xVgtUUWE1x5HOYM6P6j6gatNU4CouuYyNRhGT0YUoYYAmD2hIKVcLAlEAXVAMsIadbqjDHq6dmFBbw12NxGcObZGGy1ff7W5G/McBwYiBuwR9cpJmOjavsAkqMkpTxmlUwPj7a1UdVhjqckz9WHiunoOa3hcfzT8bqI+CdZLUto0GgIxXlQ7PiCZp3A/FhuRQPYT5GG/ysEdGNACE3KDFhmnxCRpkjxBh7yKdZum1TBDVrNkIgY0TXXc03/YZimZzBfE3uAQXGHsOAArwWgMfOK4xm7jCaubIEe4329nS67hM0I/4kuNtLQ01Dpt2NFcodesbvEu0la942h6v7eYVFDYm1Da9gbUNkbf598i7SbRoxhaNlyOjIX6l7BLSTwhsgH7TEJiljhMHT7hufqAbBsHEx5arF3uYmfZT75WEuAdbmxkzCEUdIfWZl6qrOB4VKEua2P02FOo32+wxj9RqNS1puj2CKq8/bRT5YSQMKXklD/URUriSnVvk2TQpkcNvjyXJ2qnUBG1XoaCcwzFDKe6/HKtgrnDkENJ+VRDV+1ns4mcM4vpfnZjqNvDNyk3KvU0BHRmS54VWsmuLw/orMgnAcfMCOXTPgNYBc914/uSdQuQitr5KIy2+CMZZxgc0QADBHZy9o23/QqtXuNBNsGg4m7er+e60KUPEf4r/SEke4w6QexomJbeloefBDdeTKf2agdMk+RoBVNhpVdxeOEvwXm+zVqEVnqby6PDzy865YiURGOZBWysaOudcFIaQFEkBzFRjlWv8aeW9eu/SU1aLf6OPFn3WKWD1naszLJGIx41v2QsXjOpzVWGpQ2lUElovX+Rop6W+byIMD4VLng86evXz/Uu3F3169gIJMHWcdvSof86p87K5KVmJVqImMkxmgcpQNUCzqs3JEJ2Tzsr8mmg77FcNRFvv3CDPTCsrS+5N5Lr2j1NsnqXpPTy/nJaxNOA1zMQSTCwXA2TtF/jZBJGHce0/mJyck3WVry1FfYZTReBgPv7cnrpOlRbd/LJewFcyFtz1DX6o7ZL41HsjrNw2FZa6a7zmvzT1y9b2rqJFuVHGYt2ZZgUYe8WsBN4o214WPdgRu2oOY8LfTAcgRq6dRt5owXhU4e+iXy4xCN+NqPkbTopEeraB0FXPI3aH+0fKz+qo0/7myqiclq06AMydjIBD0VUe+rGsy0fVWq/vDpKx4+n1VLx36nCvfwAFMxgSXEEI/kudflmIOmCefBDx1KiGwSsJ8dduLI/PUNOzi4tdqszlLwmSXxjnfRtWP4IMkh6PLZGncEG0PEg0EQCda8rfDuMMlOvsTI5pqj0uUKaj1kyz7OJ819HVYpLRQjf4a3ALCJJX9okYj0+pfEZONM7jh4xDoI1/AssUBHM0R8ZcG3NhoMQgDCGXJIhnOo0lDSRVye9caiLpGJWiEklaOq+lGNSh3tb2v40GcLBgoFY/+2DwTI03smAlR6oh1vvAfH28xXhsIEqXwtxUx1pAsNADjOhZlVCVaU/KldkIuV1lhGvmX2uc27PO45iB7TkP8GQ+xCIxj74PWrDi8l/gqbpLUrHEK3rN2DHC1DrOYqR0WRjZOYS+xY8HIHXgGxEYoP2oaF6w9IU0okDwCrDfO8BIiKWlAZrM4YhFG3atEeOSEHajMpnaAYaOaxcCo4KOosFIkV61pU1cWDdCROi2pLnSERRirkpUgID0Qern1aPa157TOohui+1AZr27FeGbd+lVnFW0kqqEol+bIgvspXmgrNfHDYUJXVT9HeWovbXWmH7RS233tOAM7SRruV5scuM3K45E5wHA0Ic6CBp36uthqsG3Wy3p0UwO+WRmbaF5mJE6Y0ZCNMjgM+rE0rwx8iT7xOUOkMyFJUD911/NoPBYZFmJYsCmvMZ5poVOgf4ieP3kd84VC8Tr+Y47hZMwZEBouSpspRnpvMjuNdKl46HkEfO/NII/NLEfFMh2Ien+aREvRkzwz9gfwFVJqgqETjWmDmkH7ZI0XFBiI+/hTMkCm/iRVP9y3qKcoY2wCRRkPzN38i+w9Mo3I2ElwDBttO5Bl2jIgzZ5nw7kZh7T6HfAb/RV6toEkidc1htIUjrR+dMY45xkx04430JYGoqkYlaSMp3RDrYdOgderzoKsM8kiS+9xLsi26kaXXAEoTBebCk1YCe28HWJktMqp6DuzN4gdDDVUakFUD36/p7+nikkRDwQGeJYnZayYoeI8Pnvvm71Q8Te8Cgiv4XUAVAM/z4m8LZ6ld9n6Dg4tJR1dypX7O9PU36Epv1/dWM7S+uabf2VjTenzgs8k0OBhYjaJDOQprIqUdFiCed3Y3OQd9VJV7r7tqe02aBis30txg2JGCP9n2TraRq9HNlZ081ic+x2fXe3myqCm6jaCgE5XjC1dHlhhdFewxP/Lav7TWI3iJm4gIbMlrhMXSdfMi8JwBzIRqecNqNCo3FOG598Wl71rRKyCvHoUcVdZmvABDuWrHDaoUklIEUIqlafqshE9mu9NMNjA+JTFVAy5W/i8vGQU3siKrxoDjVaY6Ms1asS1lrpUN2JkjcbqtHJHfQhSLLtcsM6KFC2JjzcPfkrxhkh1laDqKv9zqqv8K1RX9rqxVn/1kPF7aqRBJQkSlo/L7SCBjxFWxP8YxzP82oq0X6+bMiSxfRKfRosEwXG0biz/km5M3Svr/hVf6CD8nv4zXaTv/9ZOiuAOUm3+izrEo5+g1+t/iBYRWzAHfA2Kbr8P9XaMxxQ4RzXICJTOliJ/493rZ7w6ingwh70MjgdwlAG+ifHsv/Mc+IxjtE0SgRIcyw2KLpSP4xKd8Ip88JCH7+KCw1MhXmWWg7w4yziuVxGrHKQOW/uWQCaFfUlPBluSjVuKKF6F9lPUBlomlJFnLFswTJVCN4m0kO5k1Wi759JCGQOqo79Myng86DUiI6SvPOpA6mkFkxNtnNB/KWW0AzQmpF8q3SLek/G1dLWMu6kMh+WlofOMmT7iHb+C6MTXf8zjfMkYbFmOrkDcm0MC77zW33rITqDeVv/a0SFVf40qv3ZEKL7tbmlBCUvt9ZiHKbA5HWsCMenInpWsg/CHQb8XA42G7Yl7VU/0CYuFgKCDxvPkE64wplp9uclP1CQGXy5sbHS62+TOasWT0crinftLNClL1Gwl7vSsPOrZSqqzlfBsJTxbfJ1ZMzA8Jn5lJDY336Lv4iVtlo2oa86SCCvVD56spyev63yjTOIDJBbObm5MCWVyYyM1GIFsuCdx80+kKUV8bOxoybCjGx+HKgy8Tbfx3+gLDCXTfDU2njvX9U80AxjMm57/akxG7q/GfhxeH/vXx/CTvatgdeJS9tg8gIculkOHy7eCwv8pdWNV2nhk0gNZmP52NV06FJfX5UyBLoF6o+rxXCtRA/l04Jyr3AhbNWnV7M8zEOcfwGlsNaU263PYi1ZTarO+m1Wfa7M9ZGt/GIqN3MBn4pW6AX/KQ3LVNzcL9KSvIWLhj6GeDPniNeFGbujUxpTc6OAlY+yMOlsQCnWojZXhMIWHWuACyaYEyaaBpu9oV0z3NGjRqD/0zfXPmOx1DK4ufqnqwQIIu+iadRAVIUtwU0PnZLMismMiJKC9MDrGMN0aqwUYSag0KOgLfdxLjnkdBvBD4rhFBkyna9FGsecY5ikkt1fygFVu1+k28+087HTzvTDDjOl2zlkj+NHNBTxUdozeunQ4j30Qgnqd7Vw5jsrwKE5Qy4/xErGmVBF9jT2F3Yh7vP2qJAqL1Oarpc4ubZ+dXbTOCjm2ZKet0/zdnb0w5iupDuzLMjbrmQ0NIqXftyJZWJ4+pLZaZ5emCJTsIomAoN46JuEJL6kwRDOlsOCB0QjRPxOTaBdL+XcalXD6oDB9YaJe0wdhxE/KI+AtJ/LtthfXAZYQ4Gx2RJ+h0VDZQy/bIEE7IhPUEItMige8En7K6UInHoZNs6vYNDZ7pmBYibIi5xgqq3m93lkavFVdSgpsVjQm/eebMpvBwS1UL7UzxOumwO3yz2dckGqWjL5CJa40TV3kwiBXxrDL8Atueb1qQlO42ouOwZqf8zUcXYPKV+iy6a8bvLPU4/Axot+yD1c2tfJdbyVFNnaAdvOT+3QZXG2tfMeIn2sngxoMhFMA55INvfQhOydDA4Oz9NKTkSwfiGW70htjAg1k+jwbJqMkzt/gpthbTYJiAowNe4wxHXsbG8h6ArnoXoroPQ8EP/xY72oGHEQ4mD4/tu5+mrmwK3ZX5x7ShmearDJBnhfHJs9MeK9NcaMa2l3SGAWsU1luyCDy96pnET52SWQXg9lDmkxmfZAPfgeu39CH+hGg65GCFGpxap0E76FkU+2R6TbBoMPqfn3ca95HEcv/fKwcIYwY+MRxfsQzCDaKuO3n483N+8fsBhF/AYXxubWaen/suZ7ATssvLjZ+gnLVRCP7xz3Qh30lgq3lmBngexL3YtXWylDAcbi0DsS2N3YAKMRC2RqU+eTHmEJGRpNS/UKXXfjpUfBIzoAmf5yBbV9pO9rcREN9/KWRWc2wYiKd73iAPQcLroVH+AO1n5kslyutXTOhz46xNXBYjiYk6nzM+srxi+blC7PwQu676Pejg57J3xXTGOuIqmUuWLA/wMrlqKtsq20kLoForu0HN8pjay8Yo0lNfyvWAatw49R37DLwLuxlOrk1gIJLfeRukrMnw/OLQHqx31doE31jX88CjRDjJC97JIyGXo171/E/bYkVwNngMD8K4HyAiArLIR5ZTbhNz28LJE2Q9VGhMThu2hw+yjD0g8Eb0Bgk5sLPac8IUl8LjUVQXnoSGJmGbTZk/A8LSKxHE05rFDXZ81ajor+2i4yXlmqwwba0mLfIX98BLTXfHRM3GpwSF8dO6Atp3Yf7qef/fBy+47Un8XCthaj+hgSfUMuhm5vQ7J+PPU1yh0ddGPYSSvNjnxQ0ng8Hvyd4/SGo9L05CypLJLbI6jWx1T60A0sA+QmaHpVfajoKh7qQjA4MWIqA4DWdsAF/IV2VoGyaeH+xD7QT6GHlPgrA2eos0FFM5JbRRH6uZOYVpoEO3PmrfPrY9T0i/1MUBDbI4aHzPSR0vkermphVIGgvIEjgR1vzj8f007G5EbiUam8CzhxbJC8nvXQD0aWhhI2LEatFJiisLAuNVWGhUAofONpw4DAqjFzrdhI4Q+ek29nQpn544Q/NwH6gbhoV1KY3nRpF9x9m0oHVqB5pdrPXn/d7+kFj3lg8e+fIKDUSLbSSW8RGsxi30FPVQfBpqDSBLsmHC3I4Rh4sHNq82HVwW13uvzoqCCqqi6c5gwikw9FXneDYLm4rlcdCfYyM95CK8n1ju3KO3wLDykYjjONYbseXUEt+GQXcblsHFPaGcZq8c9TsiQR9BL90FYLwqCKfU/udWKi/VMgbCLhHNI6Ri82GZTSvG52gxK3RSeQyRIVe0NdxB7SMpZ+biArewm0Xcj9Q8/+T2oJhy2uufYk2dZ1bHgiwjgz7mwrhE9uIXRk61OrP1yQbHVsSn3GW3hU5AlZgmzkvQ6TtlqZfr1uSDgKPBnSAQJuSJ48QoUIRapexp5T/uYlkxETxMxVO4gap3E/zeGRxsBRtp0qbknooHTpfMvAb38NVW3a5uiu9+ifEEw1gYQK1Gqd8Ek4oIJtOKOIoH5w6SWU8cZ7nufuMdyxnWT7UUBhW4iFYP9fexV4mCyCryt1a2uKZQ/1fLzXDEjhr9W4vhQRn8ru/HV9cPD3Was6nx8A/YWDRkhwW9dNj3+5hcNTKSyRzEFZfYZZeHp4XmBjkLTeXDzKmTHyYDi9RI9fM3dpRkb6WFvVtiofnvTe6KAoyeg4EeJrldC2St+yDzz9fMm/Rb/jRpz1bfWJ+c6r5QDzBWfUXkGhgX/vlmCzr4S/IbznKb78eowDHbSIBzt7OAdlYAU7l0IOoBLiSYx9LAa4UAlyOp2SttXkK4o6Y9jiXPPrcgJWlhxVCPlrxcEgP+z/HJx+TEsTlo7B/pn6X+OJ59plTp/ijlKhRZa72tut0ulb10QPtma9kspbDKdFPOYTTep869J6l1/HCKTjEyEM1O1Sqej9YEIQvIVOMUIOGTRBYGLkVgugSw7JGfgrJVsIIQpzMRyx88YIzST26fQGbVXLWIgNDUkD8RH7HSk6ZL7a2LGJS/5iAKUr4k1rTl10E3j7G+Ja6yFB0Mcmt/LguVlt1tPlUEM7ONGYotdwC+a2Te+JDlHyOFJS6MZ9PVKR5IynyQ9cG/0uCcqtJwNjepeG7vZ4J+SHAFvKKUEn9g0MQ/C1tNEpicTQn6vjPx0CRIsrMci3kcPePF74bJgyIau/TgoKFKe6IQb6EFJpLDQl7eVBwFGRHxo5gx4YjPGwfySgIylj2eMFC8Ikh3sUCBulkwSa1Jo0jibm1m0Okmd9coqjetByFQeN0XcuF84EGv5X1LxeXNXthkTtOLRv3MBLX/floFOetpEB224wN2n57BYlcS8bAYRFBm/FmgYrR0Xxry59AXp/gxrkKP9kPPy08jOtEXO4w3+r//uleG/9vIpcgTAza6wAdfVps9aUzJ7qeFKewM2hHAWOmgqAfZF0vcmfK+JqntAXstn+kbhPlneAgF2FUdGQDEts2N23/7BuMWq0flOAufLVzG96zGtHB3K/Z0Asm4sZ5Gaq4C9w+xPPOGUbs5VRD7I5Rk0P38RcX/f/5P/4/RLmhww6uQQYB7TJ8uHsO8gdhYRB7R83MhGLCaw6qmjF5G9/vi/p39/OLiwFjnhdE6gLcdnMzEy1Xn0OTRBGOT7JyPztMaiY897ZgfLGMIw9jdKrWwVDiIRiBZlIEZUZra1SQo8u2TxtHhiTmNKu3Gn6quYEh60wyDF17r6zCujII/UbbC+xZjxB9BUVDe2CPRn9q05yMyJkFT91DhIHu9fdhLPa+Z6TjftCHUTGXI5eEUPyFoCIIUBtG6orrji+iGfg1SxTdF0t7R1eGq+DYPWhJk0JyeP0gsrMc4fhRkczBJqaY/U8LGOqMGDKG90Ueg3+PF1hZJfLGpFcaY1kYEhRVQWxvEpV6QenZCrEIYI1syfFFqoBhU7C5VhcWIxdn8NySwHOBy2C8peiwY+emyxT0aSGMS31eNCaLxmXRwwACyDQpYsXK6a59XpBaZz4ZJRgGjV9FoaYbn9e7NlygVW/8JfcjOqAi+0uhaaZ8oPQmJsAi1vFPBEzVpfW8EC3I4w9sEEpAu9XqYWyLLK2pv9KA16qUhm0JvpC1GzJeMyF6jCw5Ry7K/0ST9pic0pm6CRLRMzvnBOkDiGeOxjgVt8AodN4q26AvUopsRQ9YF8VkwekOkKtAAjCxnC9V5eRXI7LgKiIbJJJqKMK2UEVpZOZ+02uE+43zS/hgCx/gF1O4a//LhYwXPW5JZc102js39sxyEwsIXmDkJvpGLx0u2JguY9niSeYxXhdQe48PiIEyEe26tqoGmw2OyV8c4NLx2s+roTY22oRQgau6YPGAVgowEURDUjSFd5lJNtdbMpnk0a6NwAur+/3KLo8e5NMZ2ZkPk9FIFaMtoTLEYkuXsgDe831oXkdjqtOxA432VaPeLOp7XDC3UF8TXvilcxEf0TZU08sXCH/1n9dD5LFqBlgYoNv6Acf8gJcFbGgDpZ0jM4csdGHrk7B2QDJfDFmiRsc/PLAPqhmopkjSeXxJF2C7e6EKL6jjqTtxq2viiRRGBBjYX0BWKAzB3wGXRr+UeIS90jqUAf2AUlD6oeePeKNWoPQ0cKWntR0tSKQprEjjdr3Q3S5WusxCPYPXf2GLLzx//qU8A9Jho4wzB9ZIGCM6wBh/eaShR3QybeVHfRijSXh4toa2M7/um56SAwKgKN3hCTbSbDew7At/wDzU680JjNri4qstZoQIMORQsGzM0/gPdB3FmKbDOMZIlZyg6LrVOABWn3AQ6WmWfGYFIIgMlWG1m6IlotXQ7QM3teDQ7EgDKan3CnuMG4iGh4/UN1fP1RdzDTwSR+cekttAV9539gtO1puGoav1M4VUWD+o9gQzyRBHb91gwlZtBxIkBiiTRIU3C8+nR5pR/2DBxKzGWrfsYG3LnEWP7FG7UQmgEzpb/RDGm7d2e/37aH1NGyM83+j1H8cF2+nFmzc6d290bt/q9d/mUcr6bsq1c7dz4+atds9Gk4TUnfad9u7tG7fvQBlPhugW0n+JNuziWngkNqi3cEhufly0SCcZlj78jNNhmPovFy0CjQn7Z8p9EpOAy6L5KPo8hjkmWG7LKhWyFWPoyrdR8RHPg/k8bUIecuxOB3FrCgIZzshJkg7lCxjmj3D+DWryNumVL98MYB/Pn/PrAgNLCdSP3ARm0D1FV64sTUmeFKgVzoGUz5EHyjI8Muz17ULHUovRBgEdIMsY2CBdNwGtPZizm6k6PioVVMbHqI1Qh9wwyqWBCYSjWXh3ACtCxdfwim14qJRchK2b+0UPBLcSBzvKl9sTRBWDyZ3lyVQ8d9puPpsD31Vebg+j/KMoQz2Sk0RfRcPCOcD1Eg8pKEU3d+bXn5hhsofTzP0EcZF6zUF4eG+BwTyAT1Yy+BiJqu35nT3NeHpNKGbjAdJm1ppEaVxsUlTMNka9xMgj7vj0mg8WBKKHJ/Hni6+g3Q8LL2iabEX1deRVaHvg162ROIRl/v8gUliulHJ1tBsj7Qb5168D+uAqao9hlegatWdLmUzjN2U0nTUjIumHCx2zqdCVr2TlqlWyv/rdv6saoXA6dXVueu0lZl0mGzKyFK9Z4jwZ+koVIGYXNgRTodWZgzA/LI66kRGZWuzAbAMoR6FOk+zLx5XJB9hMi7Bkg9z310R708kwvUURjYUKuqcOFOaVF+gUD84PZIS7quChZD/z2whd5scrS4uzo6qysqj0J1Gv5y7ZWN9A8ZVT6rMpXHA+jBe4CIrgnJaFZgQ+IgN/DGDGxBIJYoXB24G9y3jaN0ZQEB7AeJAaJxiVATgLAs0Ce0IgS1WmXVtBBhIMipu0lBJob/T1SyVBl4HaHQPfXLGEEsf1YexsBA6VCSJc3RwwNtbhkbn5ZbzEROIlqmMGGgAzHXXzejpyJP/C0FGxno6KFToqvkhH+Z+nI/1J+beQTf9eY5KM4sESpgP95OLRCKVs+gQIR9JFjnThihN+ajhu/Gcki5SwV+vIhNBG15MJmkOwyMeT70uxgMLndVCdUqB0MXS24baT3g9uVlLczXad3PQneWkisM3Xc+pECkvHguFuvMWrEjLab6ZhM928vXunc/f2rZu7Ht2RXy04+HnvqzYA1HTAvjwFmoSKf/Df+2lts2vzCe/Cf3/DWc4eIp1+oen1OYUz4prGf21LHur1oktXdFTfmvW5hffXP9ei1JZdXQy1bboyv3DxqjJmXHUbTWybJyWAQw1Wm9Yw39Qy3+hfzXw1k4yJSZZfySR/4L+PMdBJ8N5hmDnBpkYJirGNh8Qti4ae0KB/kE0R9OFhDf+MaF/tJV/PJgWhrGGXMscVbNNkk6LdG2cutX9eTxKbbu0XiA3GRPX7CTqu5fMZ6u3xtqchj8gqkyV7+I6HPajy4Voa/ZdUYyh6AzXtwh/LHFodZtZLv4of3EuTqcLTrVlX67v4dR8Kv628aZddHD6BzT18toC/7LDZ1VY2jxboPYn/bm0dhcL3cs2LZN2LSL2ApS/f+flKlBN9SDcxUrv6MA5EhXaQYRI01a+M/viZSkcsBPVRmFziFg8HzZc5MCkFTmz80wSThOY8WWB7Yt/8LO3P1P7M/WcLimnHR1n66egSxDHE5hGj/lBUq/RIoiX+R1QkCRch136EcrK5CxlSreR/aSjPVJ6aiLemkV074s3c5LMgyajo8iMTcaerBaWuF7G245n6BM7Kkei7U6yTEYQtdcbY2aEr6Ej43tsAKiA2LZIiOUkmSbncfLFANoK31Xg3GtFFsRsDUx9cdjE0s3Aa9hM2F1GNScLdzvaj02ZK5bQYfYVQqxEPMyQjZ+05TGCWIZBpoIR7NNOhMQrTi5u7t+7cbt/t7EB/vIon0UdtubQ42z8+Uz6uB2fh4ixs+2dn4fKMqZ3dXvvPo0/JdD5tzKkZjWE8K08b8acBgY2qeLKIFn6KEHGpBRhXsG0NVlDGwwkeyCYTwhgnZzA0UE2Gsc36czKZcGdRSDfJD5Ihp+q7mUkCnI+xThTiBTrUcuAZbiVh5ivXP4R3pOgHCO04K1p9r3twtv/mDIb7QPWYultB6/hnu13fV3R7pu3UJw28eWzEjPmByH027ArWyoCny0aENwEE+5FxiBXs/lAAojbYa4BjsSxiOP8y7jtGY/fFmjIBcOPWaBKNi80b7bt3Njd/meMx0xprxeRjrKg4NeuqrCmoXC0IoSNkATZOiloGAtKiQp73NHl+XlR85LUZ3ecFNlX4J/ERoxcHJo6W8JuzNobVAo3XwucFLq6WwlZBG1yy30GBrCvYjLDhsNdl0BNje+R4pYngYZ1AfCqv1olniKviRtsJrS6Mz/A2/fPUq/um0wnIWuLR9OpsNzh0WecmZ3+9NvuKR6P6sYEhmIElokkxbR887hyyC63h5ab9nKbx88IwN9Wvn6GGN3F1IO4vDDXhbzTMVRk9//6iFQ2HqH8UDm1m+xhm2nTQT2Abtjw+CnVwatyelaLbL0KKXO4P8C+6IE/gh5h4vFwTs5gzbyjURLbVEAbzcOCM7U1MASKaVEa8mkJftnhhYvZLhywl3EDfwA2AbJtNFvGjaJoAD2WsAYzToOI7nBLOJ2LqIWujcAZA0Ci7DMIJEu7c7i/zcNice5Si547DdUBqbwAkEJTqCV4UjNGEqRPa2zx/cHGRmz0QMgyREgpRGhdW6MLqrDjNciHao3ry1vEsWmIX/KJ1bGxsOvRy2CTv+gIoUput1teJeB/cTqSZDUFPlAFvmROTqhITz3zmD0gSYnXIC2DzBcKkzdOSXjah6xNeKCTqwMZqC8vnqPmDNI+sXnh44IMXOatB2FyLppiJIQ6zyzOgTYxdJDwnhcSlAAHGQNb0E6/OlZu9ImX2xCYK55+8Svm3Ya6hBR6gX4LUmbTZWRzdptF6gssZHaC9ynymyx2JrEpk5VjqCupAbkP8jdbm0ebHSbyRvprH89jNw0XZGqbYbIWYUMxPMH7fI9xf+CvaanRTh9AdHDr5uRXn+AOSGvUHdvOyH7jXOuF2WyaTl8RbOLqE251WR+E0QIvuw3I2n3BT48nISdUFWQVbKJ7fYPw7mcBB+ETCk3SUiWbWEWZHvvohyz7ivKrBeGwtkI1NAwlEDz+VMUgjMGobzhazLlcT6xBk+iiveLVbPIeNJroKbsStpCBR7UCLQ9LRNXcBdKywr3iuOaTDrzHvowg7RqrkmKgDrc8kITtbtwarijWWlV0LUvBOnWF3IiGadzxHsXwy72g+XTXxyjzE1RTIYykwdqSy1AvQAspdXdWuaOJP3YXRJoQmZymkNWSd1tK0Z8rVAmFnp33rbqd99/YtwgozyykWD2jTqBIn6plZkcoEz+76rmr40wqPiN1neC8ZRiyf/JKgFCzPoe5LFqQpiCM1UgODUjWUXSvRcetTCYny0VezCbI8unNRQwIdFNNJvcQpUHw4NsJFqhipipxDIeBGdDod8W/NV2PxgCVVWUe8koSkUGU78UqSoUHiHbF4MG8cBlK33XGgy4rAo8LfGhky0OKMolAU2tmU63IVzOiZWvGavkJDYHe6q1zAhOLUXECSHZC6IjhE/lEkx9g41SUR120wFSrTiZLUVJJDULoGw0l0QnXisNqVeWoj6InshFxVpj9qQdleqYVU07HKWl/paWWprXS6stQq/XeWmvKEVMCAiPHmLLz437/wakZ9dQXVTcPqCoJTjABREJpixHhSd6twYqATaXeNqZv3KGfZMws7XrfGKE57I2XhAXr3ZeGjGerG/Mzr7dxikAKKbqF8/ynWuw6pgqHaezu3g5tcsAGG0+eR+1MbL37c3O0QAm2CeiC5Pd6fKsVQgdhSfBK5Z768j1b/2tgUu+4r5JjGh2mQhXf85CL8YYH/vlvIs8zzqQWHQf1aYmBtWslwQ/hIVaC4f+J4YDnHmirgkJOMlnhJfy0ZXiPFBhTT0J8zDCheMKD2RyD2ci4ZVuA72QDUQIybnR1SMOcXP1fH5LkzJmJln/PlsCaRoO2jCzA6+FfSL/VQPnEmobNbPwlPaibhmfvl3fovn9V8+X7KHPidmITk4ucF9Xq3TQXF1YLere2zdnDk2DizCOGY+fdgkuEaZvV3zCoO7LnWEayxIi48TanmuKdI9ickqk7bwZBsvMDEu27aI8rYcRNfU+INN/EzJd7ymR0KyIE+XXHrk6LjoWlaGpvYlwq0wlqktj0dg/zXbN6YJB9jOH+PshxB/eAYHn9CQE8delzr/QxSLxJ5Iym/KxrKJwAIlfR3BByNl46s5ZtSMFwMOcNDygCjMBnwwRRrQJWlUT33CuWWFvwxxbhnBaLek42wo5CRh+yX016T7aeb41hv0xcXfRV5CH1d2KIaOqqBrZ3QHKqjEUYMhWGAjTqayABXQu3Z63tBoRVlsQ9MMe8dx00VKF6P5zffEIQpDZMKTjmNy9OMSvu939/Ktq5RXJ0s3IFFEWqNCNMyL32M4cKAyoGFwjZgyE1EVz6ZJ5NyG+Nv6uYVXoPQ9AcTWNPfG9ZPuTXwUuxkRy0tzHfQgNErtvotDA7rKUq7FIs3q1+7Gq83LJylJ48euUQn+mz0Wqbs11q0MkegmdrVj8kjnxUMZfU4o95dcZIp155kRIPur94CxdDd2z5FjvSs9CK30vfVXuAnt/zYXAbVfvVDblEggBveEfdH76y6Vx7nZEPfrY7cuHlDS1NAZXoBHR4FNlGNqbk6wSY5nFGhhMQ5CtGBQQ3hZ18d1w5kKHg/wchXJnYUfOMmXMpW/2y107XMSR+Tf1yokJRSPFZq72apojYEsc/GhEHpFzjFwQvCy/V/FG74GPFeEe7VXwnAIdXI33KQX/5YHD6lC8ZfFvb3rwv/1wXMxy8LB2nITAl9+dvi8BXfXS7t71L8vr7wr0Mp+hpw2Y3htVLA7+7gvVjubXe6+Wb4j2Znbw8d67bCjrqx5Qylt5WgpLbb3jMiXLKdfHuzG4XNfBM/y6AMz/Hy9/P9/TDzk234J16GkMcWdpFCRRdA6ssw2orZKovzROKVoOI/iIqpw/pa0qoiaSThxE0j0/HbUqX9NLeQQDC5vy66HowpDPH29tPFEY+1uof+pT69az6+Dh/DUP6GmV5BJhpi9TE0tzY9rk8XsEO5xWak/l1fuOI+sGK0Gl3E+WiSnQWlBDz6RdLQ11ACNKcEOQ6bW7Z0mUQfAmkHW/T44qJydWc056wrP2VDUQyY/VaF/oowlrEMrAZH8UJt2Rj3vCgwGIOYnFcSqUIpWoWxZrTUT/DrfJScxDksK81kArQRxohEOZ3HNLYUJ71FSx3IMEwYrecRyA/P4mgUlJddjUcQLVtUJkVedS4J3kRnDQ2urTuKXh7oqZZnWUnOdRFFCljb+77XhQqq9e8jsk5NemgRfKLlJXMnHB01Kn65BatL91xzq7aIGJoepsZ3+oj7haDkqO1zXqFSp65NaV2TMAo88sG/a+i1GxAxTAHmQwS3EtnhZwJBmE+G5DEoSa5xGqMb0FfRHb5ziC5OFNEtCRSbaLDt0QHY9EitactiyjCbEap5y3ZS90WymzKxu21nL8rHBOtTmGkyKYedIyFZymSfJOw8jJZdJkphVgHrQKGd/IbOSSAyJU3Y7BTZVm23YcwGkQ4uye1WgiHCbW810W2WIp71KTYaSqzDZEiBxxGKimNSThKKZHcPh5nvixhtAk/9JnxmHo8RvAcNEvCiXH5YvdJPULJ98+b1NmQ9oDwNo8+mWEjBN99sN+6p9n7PxTROcsQyAikWPtd7OsMjNWB0Gt8ZF+HvPIzctN14j1GrTvCsgAhWjWIOX8Oh9/f+AzR5AAm9CRlRbP29/zwqT1tQ/jCbUiJhiJp7fyApGIlkqk4daIAQD7EGLKjBIS5LDv0EHYMO5N9hiD5EFFUlaesDO6jcNyzkoYrCxtVhMYg7Sm6wGTabJSGUwNNoVuClJHQcg9zAAXJsIyPg/GFxOhgKPmPUE7LfQB79zTdPSpqFaFJkYirsTJELb2Ti6sT6ooIBz7DTqjtoLBkXbt1AAyP0/lWWJFmE1hzffLMmBIrhqNvTpKBRQfkfDRX9wVLAHSUS1lzcMQgg+4pHkwYiOfzxFI25SowOAEeBN8MmWVfpgH3DBMZv3A+eNfsM89xHGQ6fJhm89l1n9GSU2yjoGtSEY+hNT9ByEz6k4GuV7xZw1stMcCoM8BFwWA8E6/l8pq1bEafnWfPz2WF6VCmABUgqX5uYug2b6kCIyTQa6xbiELvf+GsaqMLVUOYyG48nq11nuOJpqcKI9HEUn+ED0RkV/gARqNB0jf4qD5vcDbeRm3AbeTXchjIYYAAE37Wu6Gcztsv8wHU4g6MCZGDbNLzYauN+Wv3QRuPAT81TzcePVM+efaFnCnHlMg3tk78aCNaJhmDCr4o0BWeEWMkCSpJca7fSi4uNdojgnutiYl5c3Bs2nS+B3ntNjAU9Q0nPAMVAL3m52jn3HQpAG8osfTPIs8lEfwUZCkqg7Pb9w3S4kgURlnUuipJhqgaZMyUA1/AYT9eERMMXrtBp3Jc3JEpvnmjZPV1aa8R02dVqsHQpLlXUZcquvkXZDYoleuwKAIzGzm2Vid619TutdoNqoEiNT2JByRINSoY78dLaOaHj/2NtR0Wt9R+r+HiabeE1K7mTwrpHeWKXLRN3bqPWBtNgTm+SBsfcR4apiRiuQumpUB0XF6+GVmvhcD4Po/9swJimm5v5UscPypeEJ8onPy3oJCjKpHDkXRFl8OgXJgak0bgi9wb4QRDNKrCklyTtoLEN953jSCj4turNI6Q45xq84+CNAJjARrzGSqfMtNGezgtbOTfLIHEqGYPYHYqDSqVIog9Fa//Kc0k3X4bQU+iRuW9Ao7rO/y4dwt7s3EbFRr705yOts0RQ+Edv/UdvlTU2LDUvgH9L+jdd9mDexfbrUADb5q0iAkcJHmrxay40WYaPQ4nmmiUmkEO2NOa8VtB9dqDHFn7FwbMDotAWyC2TJbxELXzGZTu3TQWt1EyfG3vwC2MhZEsmcGkqPbAtAElbL246eiopW5ht/kZKIvRWrgBqMa6wTjxsH3UfNmM+fvkiEkTlZHOPpWdDAagOLTIQMUXIcWWLWhXbSdpaI6U7gCtvOdAh5gMBfYZZSSH+fyXy/5Ml8m+Lb4u+3/96wRwP6lJrOcFlM1uGI7Wyp0tnXc8TrZw8a06WqAxXpsMsLdHlmZMUpv5Zcy5zvmZSz93MOlUcmmtfatvpmlfD5YqK4UFcMls22h610PIC4/GqMiba6Bsn3gSiG/AlOy46lPRzq4+wn81TG6CuX9cdaJRAEUm0RYc7RJOlNsDWOKs2YRnT6KFmYqXs1Ie3OAuC7Y3MBLFa05ign6+6iaDUIi0sNgmnseyt8fOA1xsMmu96f5QVQw1IWe8qUnrqVs7YdGrB75LaujKFcmcFfsPX2DMbpIcUduxIUCALnOPGZSYPw77+XdutQC1JqrBhGiaEwr8KzxSt9URLCHcqMK6YtAJxfdWVDl6Vip4x0vCjG9FJUzjuKPfJCLImXYte0u4ODOBgdwAHUUKYUoODc304OIL90PgI+YXj8GOdzZuF9SPygca0pw46k8JB4OKiyUaXJsrhZRQWJEpYyKNEwxDc4SBtJkyWtfN1ZKqf48YHNHYY4GqkC2JUyeIKgM20cRazKQRJW6fR0Ly8SmOb2Z5GYSbN3oUOzu1pxl3k7qm+GDyFzc3ElRqtq5ubLmRHY6GV2MbgWNjGWHiWZuY2JnGG3RAI4ls6smpmIGoCS0U45prAMk2YCdvIIMlAzm5mKUpB5KC8JSwELglB2ZTvC/QFXWRmpzVRH2Um8RI+FtvNVKyk2JXKkhCD7+EpzGnTRsSoD8oq7ubOjZ07d7wIT3uW0Pjdzq2dzo0bnm23nre2XWAON6ynwzespFZivWLCDZIBr6I1Kq8Kn5M5K7xQp7Huj8fQOGnFaoBM6C+HdzRg0ocFXsaSxEuILKbfmOVUbx1mkQnC+jv7l1UovLoOkqvek0eM7dD1t6ZH199ClxLDGy5Xzg7AfEs/ZndK5UN1EfJUG+9MAVJjdAw2QIhiorFLVxgORbPGqlhjGs+hXG3oFyyUuNxqJMQx1wzHLX+mhKm4aoHreJPKxlWDBx0nwnp8uiroqM9I4MwQdJqU9hFJkBMtJcI0GjmnBZIrG3RAM8h4BT+lT2x074qVSd4Yx+UD+HyhZhGvfphcsTR79DKWIKslD5MctnNooKrCghpkwyW79+FtkHL8QxNw3rBRzn8Nu/sgzptkjoKhVGFSmh4KXsukOVo6MbYXieNZO1oaTymaF/widgQnlaBDe7gUQGaMbNZAZpi+Qw8B8GNMZiuv2VLecca1S+7/7OnqwhCVVSNYZfbarhi81tq48kDHevHzHsBsEIqeLdlXvKyJEHuSmNt4mk1SZ+YBes6dLn0OIAi/n0cztNs7QMvuoC3jGNM6ZD7B38JOOIbjZCs6oWOAXZmIZ4aqgAEcZ63up3EW4bSSNQzILCNgzTjOmBpNcNSXIOrExldWyaog9yYD8tBd4cM+W8VjSxHZ1SA4qIbqd9vbfnvfPn5lM0kQ/rubyeBw42XzeCl1KM6g0mg28WhqURcSYUyg9ko+lyDoYvvGHescUxrIB/If4Tgd1lWyJkt4uALQTdDc6tSE+Nzd1MTJzPGctN1BJzoVA08iVJ0591rVtljX9koL+EpaABiYk1y82dm53Wvv/wR8v/nTMjxZNj3/0TL8tMQr62e4mCxM/OtleNBEa7vmb3D+OLiIDjw8tuUH8O45KsX9J8vwzRJ7W46aqNSN8Q/uRO+XHI3h/rL3fkleLoG4IleffcYN7T6pD2M98pub7f3H2LjHqnF/6MY9dRv3q25ce//nJYPVy0aQju6VasVvlOHVUrnb/IL1/ob1CrAFrbjHsfHOxdBIwzxXiSsM9mpGiDuptPvUtJSa1i3V+KTu+KR141Pi+KSXq2PyVa36e4bmgVV/fjQK2I9LdIQQcBKCUp1cjo3gxzW5ttxs97DGP8IfqVHCk9w25Ef9LeeRLXlOdbT3MJBV88dQ7uQvbAH3TO33luiaJQr4SRZwb+mU8MiW8MGU8EHLZMLHzuZ7bvLhmnGa+oxqeqlmFZlqxT+MhLmqz9jLpWjQa0O3e/hCjS2Wt/1y2a1CZm7RZrnivlH6L5EABOP5/KeLrZZwP2lWC4i5n0CGWAh94OPcl/49+vePMJbBKKkJH6y01YTfyFs/GBW9/0C8fcBvH9Qo8H/Atthh/pEIwxnGd4kbKUcrYcquV9PZSgoi4+tTrLAstZvM4CSUZ7U0hITDo+7kBNbQ/CScDKFZwxMCkSrnRdBXW1LfZ/tQZTMFQpMIbh0bePUYtwxFYpOTrS20eIaszceJ/zhxQq8+VnOyvT054a2zud3Ze4zWTT9rDrBUxDw40edL73x4YnnT8ETHYJAxIFRQ8MFJF7pG38+xc8OT6vUIAQbpbRHEDK8Ja++wPPKaUnX8oyNBHyLmyrrBUY4RGO0hUL6664dJbJk4QkJkyGt6pS/yQfyz4Ee4r6dyX4cOpBhViwx9Zb0UStMUa8JVQKncXPQ/vaI4FfXy0vNzYdxq+crsxGh2RSBSxqM9aM0w5MHwACWxQHCcp2pgjZ/YWXN24tuiMLQzJZVUgnMO+tXWjc1YqZVtUFlzFiyWlYMvFhfI9f2LkJ+HyRBNE+6dZPPyXUry41CF1QjIx5pF9iI4PBIl/JZU/KB5rP3YDVCifLnMBAijUqEy+oyLmlzuLK1/bkHD3hWxagohdGglrWkThRILE7TJETbhiTb5o32dwsO2ruglamWuek84x9WbQevzgsJ0ocEHSQ+dNuaqBNRwYxGtxgGGc0aVtkop9GErWr3Mg3PWKRzB8OSIp7JljNdw6n7CJxieWQkn4wjvA9Wl9DZF6SwTvLibJCc5IsBCMWQSRcpzxMFRvOk49dmsQ3hOkMusifZ6DhQukObo0s9PMAp6UswmEQU8Vpbn52gPpLEuEoHalwQmOIsvAfpixTvKy65T+eF5dBYl0MMgujzydbCZDYea8MbIpssgNHEo+ElEYNErPbjUA4AXXN6lNkJTJSqbM1uZjRjPQIb02tQZKKPP0IS7KSPEA8lDe/O10ezzuz7FFuyx1uDavUZeCXxDNIRmynw/ooNw8FVm1NCl6IvjpcaCgjbAKTdqkFVnMlB3I6RjP0PbWzrryzrmqgZ06itI4aBCBC71nRlUATSEAHUD/WULztEf4wbiDGLcEI6tmpMhrO0CXsTlSsmA+CxY1kq71f1OzPe+fR74Pjao/50ek+/Q9ynIa3zsbAAi41bqULSxGAfqPRA6OcYvL07jyUSBhNL5Nc4dZc61e7hsySlMLEVUmaYwXMt0sLJOWw2KC/eGr/5NMl/an8Tqq4jHYppN7aWGucPK4ESeyiss6XkWDekKu/8d2gbzXfN3NFgRlDacT9Rs4LxmOdqk0VdneVJioejVJa7Mr2GU5NKPzZ5otvLqfhyvxJvSWY1WrZvW7dip2rFho/H/Yml2o07NRn15+S9bq5f84pcTGJnfTpDP/3oiQX4EotKGAf754yTM/acn2i9PKU6Y5bKRAy6zpoczpfYF5Yegww0pBR9FIUnYbB4/VJ/RGklQc58mQLRaNyOUMmhaoFYbfoOWDfRpq/EsjlCxnOVx0Fg1HlDQ/MX3CDZJKotosg1fbmcj/INbxLsTscdfpz1ehPv+4QQlOQqATG9o9Nb4lRp3ZKQu6TPea8J4x2q83514jmASRywl/3JyNSxUJLZcLQ38aQ8XJTj/cqLFqV+U/Ixtcw6LQC8m3mn47oSlmscnLgNhtSkGhcQZNTu22eg1HxlYBvKfxw2E/XZUCX6qo43jNRvKT/hXR4XmZ/iBCYx6Tr7D+EhqNUqgX/QJA96hT66xTKMc5glzOS5FaFbrJGCQc2yj8bFRP6QFamRVG0+FmZoSJZ9aaAZCyeNggGjHLs5nSWQk7KfKzswNeoAHU+2f04WTddktt7fxJh6PUCKAr9FfYrLRB6mgtxLRLzUnR/euK4qk7QdrLh0vbfaBRYms3U1s6IVEKzqjMD9MjrQlgoySSc8ITq9+5vGobw8k5EBDTrgpIQ2hGaojoz01g4+y48Nm6fB5V0a+pk2qsLGMVYBLAgiXJJA+L81HeTTGjbGvRBqTYO9U6EKTEfUb1GCfnMRtt6iGonUND0x+VBNSNRPkcd0s9usnW2HHf3ViOw+/8WDk+XA2eXVC4AmV+7si0kc4FeCU0G1IJx4KLMZqLOCB/owZpvRPfzBVYiGcKVio047ebCoBrZ/gZgGrlozKgKUq8TAqjLmh5XwO52k1lO2aMVsLvtluPNc2VINsllgLxmu0T1wDMXTwMRqTiznyoRbZFOr9Dbaw7ZN5OsRNjpuGpSyxDP09MBr++f2H4tN2DoJWMo2vcTHI+Qj9AsQ3him9lqSTJI2vkXe98KqfF1ogVSVgEC7gvl+OU6pG86WKVKfZMdMiWerx+BH5oPM7dIcc3OO6cGY9taex1R4uv8Z5f8uNZ9v6kCVpE6nT2+pf9oMY/sBe/GTEYAdxlBJigtr1ES9goqLEY0+NJwJt5bhJIKKBwfVwsKAnkVTNIMfqGi6paCxQ6NURw1WzbhSdBYTxn1PKAWED9o342u/mn+A8jTj0+Bc36dI9+SGHTumv+Mq3IL+Vs7KOU/aluVBEPI2WwswSR1Ct128LSSB78Pj9Pi8SBfXaeJnj1yB5O+NOohX5won9gvBmKQiijhJWtr5pkBGaAqhsflt4feAAJQ7qf+EuQan7598Wl3vfww/uUEq7i6CI4RV0NXfoan4FXY2+QFeJoqvE0pUJ+LmefN4spyfZ5IsjXTt5KxP39YXhsH1bqEFbGbDZFQM2cgZsdMWATWlfskJmkzZ9lCjMhaVFu+oa6OumSA3JHU3foHdueRoPO5Uq3bRpIqrHnpA52Gc+t/jG7H+XW8jYbq2EUgltr67ahSVOrKJdUntLxl9QsHCxF+gEAvTwyJymUp2UyyrSqUJQ9GOD22m+XrkJipoueIeSTBENvtfE0RWg6GJ09Wju3tjp3L6NgEKw9+CgcA/yvVTk2sG3uYce2ObD9o07NxE/UMx11hSdQD3WKpJ0Tc2OhFqsgJGUQmZmYf0W+o28Rxx9Botk6yptvVoFSrkKBaUi95GHedJUcCsrBZpsQuhxjWsjBaOmpxixYu9NsblzzqgEKrMfIhIlxkr1i4irBblYIzt58kbbBZ0Jw+ji4gPFVvYM6FEkD6cR/FfF4YWjbkRW09rZRnVWi9q6DWvHMq2CzjgD99mdkStKqxnIyVfM+w38aZ1/HKAWHCk3xc3sIrRQbjcJR+PdF2lqlVLMXF5c4O3g1/V2boDooiv6S/5R92WbIPt/FqUP9XlN6CpD6U+64YbuDo1fqZOm/Eo902lYx/3+Vqm7mP5NHey6zbRo7t650bNVcMteGqS1FGlZNqmIOKJXapsWh3Agl7V6LjTnU/8pIuyzr+dHAQP3zi36itE32Ge8T1brs/j4sLBxswj1HEHVwP3RjPiPKby5uDhFvB+zKSJN2Sbw8U92rQKcewUg7tcOgtRvV1Vlxmd1tSzuEZxsCf6De0VlSc7201SXgJmVLSVk76qDhMHwqgXoV1KhL0ma5Cd4pwQg35ULRlV/ChcSk05MosOpXCSpu0jSmkWSri6SxCDDUdXoge0rvLVKRYbMU0Pm6RVkrgSYpNdMcPDTyuDbzQ2GHgMfcpUViralWB4uMn42GWvqSJF0KRTKqFKXIt6UiTf1VsaivsmWsTJVy3aLoVpLhLWFctuADKGlun2k6qonQ85OhEgfMCGmVUJMawgxNYSYrhBiWiXEaSWGmcDiNwSXuwSX1xBcvkpwKKwiGBmOPkdHIDN2IDysq+vWZXH/Dc3lV7FWLjqXwnMa0KOujbhK7kxCCcSo+0o8paySYfwVBU+oG9QHyVqjlfq6hicBfaIkEMrBhgZEILMyheZMoblgr5XBq+3OXHfHEGrsbFr5WhKN6orTzcvozkc3EcvL64lUf7BIGFciITLFnxUyzVfIlPJLYhNkSu8qXg1O5F0BMaEI5+JiIzV7QPcKrqUnfKZ2OWUpkVYYbmJRLpTfHo5CaCOr4knuTYwoGhh0JPGss9BGrkNGnFdeOmrgFS3ww3TAl62o9j3LjLrLusGSlyYeBUlJ3Gr8iEo2hSh1EjfmafLHPEZXMbrfsFbuDQzRhzItlpLk6ia7xGuTPCsKHQyp1XiRpduqFFLgoTqGAZdMYxgrbTifTeiODZWbw+8x2tAUr0+Gjf/5P/5fautJfBotEr6tEU6jpJAeUIvZ+5kv/EZzjCevVbetaxh9zolKA4tMs3lLCprIhOXRcTPxM7/wB/bUPVGWXvxnxn/GYeYfh4jbvOCD+Nicko73NLpV9xjvCcZ8mN0/7jUX4djns7MXwG9zFsdqlsDhE3/sF4fHR1A90ov1ixjbo+s4XGh6mISn8MmSP0G//83N8ebmsi50EhaN/m9RE+MtH3vQD611CpfBzJzrl/BiCW1cICUeQx7dF8NYuKTHm5uPc/gJJc2xqeNQRq7uVsZgDCJUonvm26Fqcg/GpgfYwPFKA8eigWN4MTasUTbjEmseh/B/r1r/AljTGLjcsWnDotqGhRxFGPmF0FjYiMNj1gfFzaVk8McBPXrc/sVK+xei/Qt4sbBWZVgktPthBOxG3vBo9kehni/d8RY+O5Za0U+17h73Hmon45xwBpSCXfln43U4vyszjN7VXUfwGVI7UPoxJzDB+0vlrtr0ujMzPhvL1hB4Rne8tSUyeOcztQbGPSCqmVpEXgC/nTUQx7QIZv5SufPxOoiNT9D5zC6EWXisF8KCpjCOzXcLmsbZ5mYcr1kNM54s+CZDep7r2ZqEcRzMbdAFjNQE/0BluCK4e3ItzOzcQDEk383ctbBmTGa0JmxHfTuKTe7PTHYHGztbaetMNHUGL2YrKwMbRStjBisDXq9pzTGskJmPS1G06LjaouPKAMM6Oa5dJ7PadTJ21snxSm+ORW+O4cWxXCezP7VOuNvGVa1JaguMr2W36FVNlcL5uTfFB9tufDJXkMLorBlFzYiBgzF4dhhV9GpGPnFrMgJqVCNesBc6yFaRIwlGgdiOqG1Cl3xOAha3l33oMI+KOobdUTlY7X/bO0e7PKN3RpRpEC/91dYXUbNAXU9hD+VuEKFIa+IK97hN41Kwwrkw/u3G6zavaBEnpEVEtZI5DkzkiGGk9xot4sQj9C/SIl7ZpX+iJ7L9VIXmOCU9SP39paAfBEK/nzerQ6q1HdAWo2+9ul32eVXtcdWgewG04DOGBdNVXlmZ7a2RieIwQ9eDp+HAj80pR5HhgGKPDq4gw8ghuRsYjm2NyhReD9wUN7OrH6XcbtKauR9UVKKFVJp9/aQWqCkbyFF0ytGjhWNV1TSsLmMYNNJ+w5eWI/EQq3NcZA5wxyYDbilwtoNX5GRBYw/PA8teZHytld1fbfrKYiGy4sDfB6qlnDJgFZFpALQM+c6g19SGTW0R9avenEBBb20Iw4DHDKCa5foO+Kj/xWIm9SUc9dH9q/xUhXC+9o6MH54oIajA+0lzUqk5eBC6qxqnZRLDIWSexiJ+4nwChyWNMRun82ms4HmV4TBW0pjOSzIuTGBIMeADHZKyFM4uJRojop2ZNk2gk1v/Hv5u4WV10yM8KLL4PWy1WsUMPUuPIHGmClcgR8IN+lfloEyoSsrw4YmWCPmgp4mijC3sD1qCFA2ESbRHR8g0LTBeQvmJgAoHLViEaF+yQVdBaIjWrFwD8wA/j2YrY1uxn3knTTKAqIGPwJgS5SkznUJYavgxtcBf0CrBwJmXYmNfq7WoWZJ6KWYRLky9HMmiq15nwdlJsUYfsGItqmosIqkAi1wFWFSjAIusAqwHi7zf34oEJpDmpLd6zXpuV2VMGOWNuVmBlxtrONhf3mywBh+ZnhdIcaqqSYwcEcjVJMI7bqEZOSvXuartp92nvMWgfez1k7CtHCKWJqNmQa+UVWmkLGdVxANlSVpKS1JGjsrCcXPnrrI+01H/NOhNCFRhxqrL8COZMw4EWXJFgL9s/XhWbR4H5qTNNo+D7oBtHnXYm8PBUYviJgij/HO3cszj1klfWctIZa+nN63LEduunj8NE2nFd+rYXFAAGOsGtZEai2PYhWJPTrsPmy0jrPd0uJi+3m76q549Kpb2t0XFKwPn57+RxU5jT7vdPEMviu/3W42f82imIByQXwy1eXXDyYmmO1k6SsaoFsIo3hhtMpq8zIEtBpVSxasQmOp+A/75QhY285FZ1FdumrZn8Tc6XiDhIMcRgw3IgGjnJ7C7MlxDFVmTEB7Ql5UDlLMH4CRaTStOIwypdK4s/3VGxongMO8HMOMnQEaFAoUYuM9CFaaoYCUqotPqkPyHy/U9Mb9XeqEAXGxKtUsYvsV5r7qHLib4o9p2iWYS2dMhAWUE0PBoHBSffBUCWMWdUiXwkwUlEWdHYyOs8eBEVx2trjT3ofRct3P2CY8qm5sbo0+aqR2QxFhZEakOA9/UAd19jGs/iQZqCMnTLMsHakA8doljFDdYO2TQZo3gVWG6K7DJuglS+TuDheKzwPE5zrMGlrHNMcqKVuMgo0JzZS1qVMMPkqEqk+MdqdFsffONEhZVEwgJJZtMsjPn86CB4IuJ549wO1d8qfnbZnJAZ7uDXvNtTtstLaKPOW84GH9bEbifWNMnhjBB4yD6ldAfP1HpCL6sPsJwwiEV5r8kE2yaejcCw0kkLQ3C0l0BMgxCqSc5NbAa1qaMlh5GknEBOIBPYjwmEwroVcx3cwI2JXKj18rqVzAJJXYgjI3Miyem3NNEx5tjqCkUYxVWl2Bq8LZUxPOMgWYCjhtJi4gid9p11NJBtdctpq6OVt1LwijMAlSV0KxkiO3McFAcptrU7n5S2k9KpUbA1G4qWU1+BatJqqwl0rwkX+Ulecv8vqwGrexq6EWKo+mMnPUQrg4qtD9Wrfern8lARm+US870k/aPGJ44QLwsukgvnoPISkvTT6HC2U4qXGqIb5ALJaq3XQ2oWJ1+hD+rMl3zlaZhbFMhYOzct0xeSqaBk+CAut7lP0yCBnsvChF6j15g6oA+mzv07YSVnzvEXcBztbGQO1NB5Vn7vjIZk6DQNVY/DwceHSRcWMkhDIAhrS5qwuchdIu7ghCSaqWMQsZ83Ny+uXvrzu323c6uPwtHG6FKJ91wr3l9c4TcbRQ0c/ULpMANwinAk8b8BJo/5eNNpe/Ual6Nbd7NnIVYfHEhsiJRCbNTmJ1ToEiYMH3hORXo8YNP6BA6DaemVCX1TZ2T1fmUcOOxwGPIS6fwsT/0T0lvMSKJevOHhXd+r4l+5SjCO7mMDArvO8ABCT7XH4bHRkUzDKduHMb5p2CkQkmrv5vbt27e3L190dm5w1kKavzxauOP3cZjDwniZxoey1b5tQ0//mLDmTlBYV0aOyYi3fhh+Lp5fgkfTz23Q5NPwZA2wEskIT15/sjBumN71Vs3/Jl8vtO5u4N3TYnlWfbmSSSGh6OjYMYGyyNP4Z/PFDGNvo6YRNMEepvR3zcn4Tyc+YNw6AWGWmd+dhGOiGGoywa/+P/Ze9Puto2sXfS7fwXllegAVzCjwSNphMuWJ8VjTDmOo+NrQiAoIaYAGgAlKib7t9891AyQkhynu897T3q1RYJAoYZdu/b4bBPtrc5c9O/svp0AmZbhhJ+dGEzEZVTwrkZWtBBny5bfnWrvEXYzMPY1aP1pnVXUXzINotBAqxXv44Mcduyfu3Os7iYu5LWayMMFcGE7NOEsqtXmW27Qk6lesj6S1JqiUgtfLSN3U8t+eyL9oRDVbTETB0TQRKbzGDhajuwhxuioDyLNjpeK4CKX3CiRHGsYIDBwxACx5K7HzrvjFa+Lv+kNj6w3fN7tnnlHM4aHPfOOZxz2/Hk3zOYVUQcJbAYCFCkW9MznXfXQ8cyAFjGAoOhmaOxI/36e4AMIqJhgI+btDyITB00fgWfebBbMVBPr5zN+8Sf4i59OZ2ZaoQzg1X1a0zG9Tdi7aBuFJsye/ClGab13+Uudp18K7ZZtVtvbPe9qLfmdV5GFbPRqZXc+NU/+G3oIZvnTTL0l4VdwtBP8NLMX4ImgjXqzAb3cfsGefMFMrueSNxlQWJEDwNStLP9JpYCSNa6mtWTmNiBgvswssqEze7MJhX4V+Ef5FCpdx0O+5x4mSFiIu23D1oFmS3TcM+pkNRB95DMXDtumhsnGq+Qn8V2a0SrKcGPQKXT6pNmUXB8V4SYzwyenuUKaCu3pWZ7AbKfbVKH8aaGaUp1Q+c0GoFVj9s0blaj8e/edpNIefMIaGu9mdQiuJ8YD0N93M71U72cbG8G72cH72Ueqryg3+q73gUSltdczivuqcDvCZ4z8Aq1VNeFruhH18Da7xf3w/axbyGzkNIT2i49wQqFN4v2sB4oPA6yHxcbWxqANLD/t7mz+nKpiHSmWnR504U+0Mbg2wEqn6cIxS3C+FtZeGMrqAJERfYW6fY7UgmZ7zswX4AyH56Dfy8Ib5DrBAwgjwKZHJTlU6A0l5uqhO2CEJarbrSfoJEEvRppx7QoEH2OAVXzX2+mYc2npXU3oC1S6ocDbEG8BAX7Ka9dardYbBxbC+O8VgsvyZbzzxjf9d+3HEp79f7/pv2sDMjeYZti3zEYlrZMdtubB+rFUJzoe9yiTauGAMWSU54+dK55wowT6QQwH9Nut94QZA7JDOkoR/4jLi1stEoL8oXbVtK8Hv0vZ2twIf+kcfyLwP5m4CZj7TyZu4JRNhPbo9cv2tEyACE6I4xHhHSYJJltyuXKJ24O3PaDXMV52y7Y5/Uhpz+jxarx7QNBEGsgPO9woahFAFFJ0W1G3xiAWlC5sbiLBG6F+uWB5HTJYVpsRCOKUqoqQEfCjfFwbyhhDpexc2xKuQrOcO9cjwdtE2GOpU9YjUfZBFu9oebK6DP8Ok+xf2zYbhbEQ+5XJ4PYuu7ZT70DOIEUZdV3mpgsg5kw7DWGI1/pY26d5m4rycrRLb1C2LQFopOgwRIQwmP4zXEdyYtC4gEtwRq4AULIKTfymhemnM6suWeWYaR3aW7mPhlNR6UQhTGskZ/Vb4sLOgCB+ihGvx/n06LhpMyEQyYS9FwE5KajiPJAX4dQwgz1MqjNB/NBkCWT7O7oTuhIhgzA+ZDFVZ0z79VdqJ8uPpXjFsFXC4V97UWtf8XWcdbqHCBRRX4iREC8oEgwOptmsIiDva9ckl0Xj7rW9DCgfPRFk6f09GBwMNiorjf/jgC4mzkUdjsjlIfUgM42smHGBDkKip/Rc+MfXq14vw/Us0hH0mPX2chZGwQcQS+BMd4uXsRsNyZ/ghoP3M0TyfAo3qkPdQWoJvAvCEzLfRD54gBg1VwhuaHi6IUYCxYeImG7wgJkuxlV5D5jpRi7TxQPkfw70llLOe4MmkLFBZ3B/sAGSzs8Dn1D6bOWcgTVtgy9fEvp98Ff7mbX8TepU78Oso4XFL7POL7PgBdBZCOKrNCrBre+EA/rxoccJHcikXpChdm+GhUzC95HKNvGRWLUhyvrNNUQJ/vZO5I3lBvyrBEdxaRvkxqCy0eVF9x/OzOzfS+DP04Q1QdA/nC0wH91sot1wX/hwJmo6wQcMitKgrFkE3wKSjzOl0v5yqJQBRBTzPhzWQSR/OYQJhBu/HArND5fxOSj94Ss9vFczsi2J78FLzHeHZfw9fDOD28IPfJmZQFKzzIE2tHn73tbmvTu3YXENHUldrXHnvUzUVeMzk652tO0GQ+DSuIXtEPXDgV9SQI+QcuCMSEfnfFYzRGES4VkYPCEa+gv7/3AmqmPbRqS3snbeKDlLGAGz5KNcBjMZcBok5Kitmxm7t5VEBVUCI3qjkD3a/gMEwFNWiD6VYllaxoPKjcA8HvfR4u0Hfxz2PAEKRjFGCX0kw8YuZZEO3vGuHgSfpcI0nz/QH73PSndyON0AkddoLoXUZrlLW7CxfqKwkdbhOI8/20g/EYpkMv0EZkFqMkb8l8xYgQexfB1C90j9Bpj40RHNOMwhdSMAFhZNEGukMABOKZeF+eYhouVEBQjYVjn194a/54Mw5CM41TBHkYcYx0Np3yAS2CNqSH8On81sItjPc1jfDNfvhjrzRXG89ISkESAtDlPCg1/cg4NGOQe7S/B4CJ4H0vY4zyeiiE+KaE9P6b28d0RwjcFXTfyuyHFWRWRyfUyuZ+GxbNP7SvmthAMvUd+QBxMC8JouSKWuSegKf8E7F3f+7zM4JoDtiiQgtg7vzVSMS2RASWs1Bp5ETG9UI4hReT4Wt1TZz0szi3u/YuZwpyLwDevhwHs1s2QOYEHWgYLHBJL+Bw13sX3TAqp4rvv3FlmZLODbejuzgeu/KH+2fb65oR3sVpEn1btTFDne9SQ7u7G9eWuno77dhW+bd29ub0mD93r4L6N0yC8Syu/JTBcUsq1ZTrU9nN8vRAQW6IRpzWcQE3IZE6NbSEbdwKZ/5y97kiG+NXiiAfis5/Cr1Ts+y7SDWX2lyeKvX/RHw98tFuGNWt4PjqQBvySdN9hpdmgksFMMzGjhB1bkIfv3wTAK16vtWq9gi1wSimNNFGhY2qOO6AlpStLiBHdXAXQiMfBeLU/0h1pyjYRYE1EhSncG1kd1OtMqhYND6keSw4qQ2ksGHHfcY4xUUeMUW6GSAYfCAQW1tXb3nrHu8JOOLNDrLy7zzvkiL33hsAvtH7sCESwU3Rjo35FnxDFJvsgUx1xRRH4RT+TPivu5sUy/Gg6Gv2aSTP+aIcN+aFjh4TPD8yXhryl8I4C+D5ji+yHw9ICqZhryQys8RucHIfOtjJKky6TnLzOrhvEPko804p9avyyN/KWRUyyFGdX7Xkb11n7R8b5USGzhRtWbkeGktdsRjAQSix42AbtlmZqSXK8Ccw7Y2E5QWWaGGGX6PKOa4polFBZLWBEH5Pyk2sMf1Hu+Ujmnoo1/2ifRpCnTKmmX4zROsNJQQGdrZ3Phc9RE1euJJg4+qt8Cq4wQUnPwwdawEK1D9QcjZBCLC1o5EBhSJuD8fP505nNxIuemkKLk0ajIhvGEzOLZQfExfHbChQ4zbTJJlldNjZQtg20eynSCuiZVWk6z0zyOJKqgqNPF0gYZTRTP4QpRXAIKyy1j8xRhRw2D4k1lrsVnRpkE9lFSbdxA9jbQwbdirBsbgXHKVrkF29UEMNJDCFYTJTPL7ZhGPAIl1UlgehExBrILK6am/pmRv9hWO2VclqrTUDjszojPQuyKsDlIFdEPUQjXMa6SzYvqaJ3EusqcJ10EBbNe4u1JWzYTDksDFe4DuucOCrdu/UcDby03aD3NPTyK4Qi0/H5p7kaEfqnFgq6oF0k3szkVwfFU2s2Y6vAKE7OGjR6fB6Kqta2KtFveZU2qPibptBvmMsxUuJg+yiIdXmmX2EXRvlZvl4UGPsA4RC+QwX2LSreK5S2Xa8Cu7ot1FG6k2Y1JkR/BqVbynAnsANigY1CXVlTaDIwXh2kYGaGfdCDiqEIzMllGkfpuuEbEko+MJpVJAKJ2DP8ZA8+aYuSdCAMbhmM3DAznEcvY8g897+VsfYin5LDj/SA++SKEbEz+16J6IQLG8DDa9OM1I3AltgPB9P3w5QjYx7QQEmlE9NoZt/lDACry4wj0UN4z47b1PUjMn/QXM3wsGMoAtSlVCZFeXxyQDGUbwxCIDEb2vcrdSw8Nm7pvjv2fHQmsnYxaKsM4xHrAkd9RUzuEM0qUER5RSM+oi6sqXv4CtOzMi4IhJvQ57+6ZL+zwXTzikRjx8MIRj9vi0z897JEz7JEe9pCGPezK1RRa8ljRIX7io0G1CY11REtlgDb5yA1/UoaeYEriwPBQxxv7gmdm3domDIy9SjFVenfHgc3YxBMLB6iJqqqrIK0DN7+iUOeFcRREhphGxwDKHIrTZ/+1nD5r5PRsKkL0RDnUAFFrZNBd1BRoorl9Vg/uBeYvueIwRyMOLHcuCBUT/Dmst8t0g8iIqd8lmnBehCY7Nv7V7PGRxcgNg4CmBswiW0EAB8D7jSXNXbkH5kDKPk/pgNOipr2wL9n6igVi2RXSz6JJeZxXxpKh9JaSWRUkRfZI3JC44S2qhIu+kfcYCMG7nrKU2N+iEzZFsYQIRC+/+2g2n5NLw/PruZX75ODFpFOUQ2s9M5I7RIkk9KrQ4FzDHRyZjyjieCEVfaAHDy/CWzP6SEuXXaoXf+P9fjDZvagcRU04IDTiK1ek+AFrhGI4hYfpJTp/M60RYRZ+5UJKUWAMD+TpIBUyZxbs5d40NyTNgiMKscQZcBcJYLt5827wMvd2Z/PHs+DrELh8kZ+LwneLYOw2EEncPzhoDHDaBiIm/hSFT0lg++8h5AwJV8WGMSGtPZpJ6RGxY4CusiD/p+kKRT4vD/FQ8l4BUae+cwJkvk/xvI5DMBCcCVkdW3ae5B4tIyygs+CpWnAQOttGh/GknM/z+fyN4Ux749ibMCBvfXeGJt/+DIkk6RGZdC5BKWmQaUpJBPSCSXP/tk0VzecgCpobSyMOGjprrEg40YDaO3dvolZobTFZ/XCBpifbVK1RpJusChXVNSM3AS5JhwwGfEFZJHrmLR1VP9HEA861t0UUPAqxLIrRx7AIRjkF7U1yKxRwqsao0IIM7DbxjLefetvBgHveP8/ixzNWifrYMc/HIKWAGrYqO49yM1DY6A1ahUVhJtTTRQipqmJIgRK4JOTn+qriIwy4daPlR5gct+0btvhiStiF2yayuvGAPEoNO52RayFCusnUhnwhcG0KdZOCsnvY29IUANBpwUz4W+0JVd5gUEgWppvlOOdIPBps1/JUADWNbBNDZdhrlBkiqwudmSGYHLmzuHLIwkH+rQOu/WDUiNddlydbFZ7Y41vbJBRQPbYKxhZUxmg+2SapU8OMYoXin+Y1vG1T0s8CsrTAY00okD1cOaOx89yM68cXyrFoL5uXWZRzgKjCLKQr+d8HJgsnUq2vh7kDdHqM0Yw2P93lyC0RfxiJ45qCGEkMtg9H2geVVO0Sy7ISweKKRJxUaoGGIhek5b4qht6BBbls1dhxWlYYMoQlRuslZKO2+t0oJvtXe1+l67XNF4dYLgr3b1BgXBFyWKlOKBbrybRNpUBEwQx4HwhcwJTFj5wCGhiOPmFPsjJirfVV84ZZtjJTKRXFUQU8s9lXOa0wGNBNvi66OUVslWFkOdEYw6lEEAVexeGT9BCmQ8F14mTkirfCdS9FkI0YGu53tZUm9nKE2ugz0ZSykht040weC4rZReop0SctJETOBf1d3Fozqb1PVAwHHNewki09B+S7J9W0wmsjeIRrurXyaYU4L9gilZTk8NGoolooIh4xGpKgpW/XDQvqFpEUeAe9ur3cQCcGIofh07xGRmqVuwBUeNS92EbbeW2t2jEIJwXwm63N+4adH0vyeYNHOoJ9HBVHZoCDQDGVw6BKqnqMVGWoEgMasjESS+MdlnGRTvjsZKGoSG5geFoiwHxUALLGXSRXZbv1GuvInGHBUKyTxqkmGPSWtI6mEby4ShKun5KPODC4ItgmrFPEMjWHggkSFLSWN9KakWOsxJJGxG6F7ZE1VBP8q03RfgZFoSuCi1r+kAc/EPC6XeIS3rOrehGYlwVz1n1E/d/csrVQ9wcyRlGnzqEzxY7rNuN7gE5lWHbENC+W0vE7I3mfSXJPUb3BVfLI4TOLEG0sgLvfMHPiTAaDz6tqrH679Til2kCialAiYqNQk1LOg0bqImAHdB9qBKgBMzgCfBpgHsQD8R0x5TAqqKMnVqeD69VtqhuqZdj9nEsBleKkrTRCgQlvgIyWeHNGtQoTywzU8TLNupmRB8SlMytk6azmLjG8C3aLyk2JCMmFMi5VDVVLZYFRNZZKdFVYnHAQBeie4pxwYj72hUCX6BPvktXbdaai43czMgxzHYMuz6vJLsJXntRyuODQ7Ug9XluhinP/66GGfEzD4hx4Y3mOjhbgD/scdHyXk6LWUOFnuxxnFR+itpuG0cRj+1xfYkWlOvPWvn+BUADoTg1SOhAn+2x2OtnvpR3pMgGxpzhvaLUQz9JzGu2xQszyRYEhOgV7sQ82P+rw1IzkXOH6NTRuQ0CroOlvlXEfNwn11ULKe6C11eR2RP4zBfYCxX3QQ2DmXQl4S3obcfQ0jjT8WvI7nM4p4c0ciPZWguoeHuZW6yDwoYCdWn1xpglkV5RF17YMqfu16br83Oy6/JxbsCbCk/k4p3A0mBXYSfy5sWqJOhwa6mdIkagIKd7NLV3L1Vx7Tw87wgFUYFVPFtNFAQuhTxEpipGrmlgUYm9NgRkWd4Fd7YE5v6ksYeCjJxim2vT+PhA7V3ENY1f/WXcHvJpZW1lPfUXWvy7dVrk9DzI9bLTH2wqIGnLTihf2ir9s0J/Cr5jLnwQx7ENU6oJhMik7oLRkJdpTDF/QMosKbdYmkwqL+DoIyTSkGCGbAuokwUJe4njIZJSb+I2xb/QTVrjPK1cX1kMTQhJp5+78GFmbuYsgR80ockkC187HtFPVSSczqsyzhlCY2Z61F7HaGdYeUngrts0PF6VrxKDrKJ3fIq8I3Jg0jKEu/V5D7yvkGVjyxLvEKPlWM5FZkD08bIV9wkTe3bm3efvWbTR3Uqk9uHTr5q3t21u3bt+VF430Zlo61YWbwlRSi25SuVhLbXci4Pcg+cgeeKn18fWuQXn6Tm3CM5MoHWpCaz4CyAINdZeYlzKzyAIajgmQCuWJXQdd1ZBEC0zlo/LjII8yXT8+FdV1/1dlpAqK4ETLFKD2PPasDS2Nzz2mn0CGH5XmoP5yeJHjuhPNwWoAWxiJXb/Hg/b/U4OrLju4h5aij5haO5t3RSsGhWIKDUqowP5v3725A1R52w/eoO1m3yXL33IXYaOyTZPAPgRDRmupDrgypqqpXk4PfuhUHuf4Lzhy1jwJKnTQvz7LMK8+KapzbyAY2KCWx6tt8TDDsFQEHHuaPKM0As9vUY6NkdibtxJWNSggBlZZwX+gvsB6Nh8Bb5MRPM+HeBMKyI+YUziIFFDw5cvvUig2nnASJwF4jjlj6rIThfrMVUGrNQs69GozUyboQremhuZEB8gRxi3NBZoiODNj6Uwov8IA/x10ZBeRcWSmqSiT1c3RvyAOc0msdTItXDItkEx/MyUTgpkwlbl3//PmCd1nNy8e+Xtbt/pQY3HhAcsrVhXwj6YU8bRuDq7qhcOVENbIQCvzOAbp62Dro98rQDwGzbehPx8tUfu51YEPqzuQeA1Rlom3LLev9vYC326Usfnyd0ZvpACYI1flkTDvhWIdk5oT5290+Rd7zf/IPTqubU7+wb7pV6XluCGd1lO/X8I18AeeHCTi/Mr2/5Ut/lFz7hkhyugB3byzc+fm1t3tm+vra94P6yAw3dvZ9HtuaFPV8ZKa9AGXpyQUiVishGKxEmuH/FoX/cmTXvm9rKORf+To1jzq1G1/Ze9EbFatR1QPvrlPFf1G00Fl88jBWBkxPeaW+CGHY6FuRLxxw4iNL003C0vNv5y0J138J4wYJi+6/+y4F3WeHYtAJDTql2jUL6VZ2TLqCyMzYlgvN+qXwQm+GlR7quol1dk4TD2Es0fzPhbW0PFvHpbdkXpybOrJsdKT47qe/LXRiBqbRlQBgvg89WLEtp7wlEyDZEp+YIZu44uFvKhsvuKHr7Zzx/+6UD4ibUOTnqGFbEXhQdNkB7kabel6JlxXhf5e/p/tmZB+odL0TOQKsRKnosEzUTZ6Jsr/P3omtDxRWjX3ZC2IW0tiUBj5pKCE3CrKYh3u/SzH9HIbP6Vp7WQpPnTMikDNx5i8ExBTSaEvv+5rm8XQ3B3yaMNHgwwNlwbbogZVtMXSs1JJ/XDUOsll8F6dTia+1JIIv2v8wq/7CzMhUQQMGCovh5A7+Y5msuO/oZOZ2cfascMZszp7zEq6d261kmJpFb9qt3WNFYk0G4QYepsgV2nwGZkOIwK3FjCK+zkC0ASwG04TWasjVi4cSurmFB9nkw5k3AhRU1csgGFxM4bqBMgGzNPpCWEk/apZtnIslSqNle3W2m6WODkwohE46tG83SBdJ8EBZt2bwdC6dcNIvNz4cGDEAB3mMPcRqMtAlpiGZ8WK5Lrh6Ls2XJZ6X39KvR/2jbmK9Us/sI12stvmqpajNCnegD6dzrqm/6Y6R9jt824WesX6v7yt+/d3tm88OQZOcWPL9xVQi7ez7W+gN23wabBRbQzefsIyyVn4FpO2Nu9nuNIb4eAZXLWegS5s4DN8uGfhb3i/aqX45N6/Ab+o9XU3gxG/ZsxBwzJPLbowY9dKFpg1BE8iMPO6mc7YVlVSNWjw9k0ukLojqoUDkaIrIzylirBReI4lzNFd3dVRDxgDVwSwKUdFUh6LmLdi6rGZEtiQ+ITmhkOUxiqZsqjbaIgdLZNkaEEtoajAQCN6l6NEUqQnDGeBcEgZLACKAakMKgm/UpCpNhcu0OkpPhqF6UvbyaksW10Zu3Sw8zFcpb6z91oe9QRNgUeiRgwg2Qe+CpYKFziDYJijDU6kowo0HFL1lUVIdoa4VzJL4imGJ7V4Bsia14pGKDgpu13QGibxOKLaGRLNS8NUEL6Z9L2zORBoa4DOMOJK4iDmfJfi4gQlN7EFeY+RROMk11PgVe8Iq0GnVA3gcUFzT1EQqUtW8mjSdJUGVBfnU+mhSFBYvurR/11GvYzi3KHNt77O0ynrUvB0GnGjpesK+YdWX0XeCQLQ7oHILYsgUZhJZ/QiBUkT6esMllU1ZcwEkQbelGrmsy6msP86MwLAqnr2SRCHWGovYzAUO0kL9evUSM4KY1SZ46BU5pV9Sc2bRjLE+voZ6g1rWyJyV2lq2J+cbM+ZtQ9cpyTQfaboPiO6D1TFDWhWx/PaUrspRU0PeSrrVUsQxe4kLRGvqDTov5XHpDxcVao61nVDriJgYbgAEd22lWI3hIlrorviKnQXMNGRC2FV0GdtJhoCP535Ew1QzJAzqIanReQXLzaaSbZ9M2CH48lhl75WHdGcj2O3jV17XDYDTivJMQw/zOcGZANeMKKWhZiwNwsRi2WzK2UFGeCTLa3OYjuGKRRJVWcxAolLI1xB11f5++VVTksBKaGVikbsdTE3CsWhO+1roCn43Aw0Zem0yB4UzGNrILn5YLklfonN/ToBlhoBzzWW60aYYw6ZRJZLmgoayBtcm21kVrmtwqOEkbc0jl6QG/OQL5mHAXT6KKkeAemeii49gfOQUKYRHeNBiwFWeaMI95MHm5wYl4KalTF0nEhJViIVVjeFjQF9J8CECiH9KH6Jix90qNoCwjzWVMs0sM8GCwXJhCkwA8BLEzoyyH1xACS6WKmR+1C2OUtJTZkoH+BWn8jCJXdi+dog94PGdbvoqWU2eGNZ60vV3CCs09vabMtKjBxZKdSwFsUWtlsvo88gu2DdNSzlJuwNxZRKRI0i4F6wVnWKgiNLp3soBExEidFwmGn5Bpolc496sLf2PEMARWgNP+FyW5XWZrVdUokYcRXLpCQizGh7y1uOiNQW9FbcSB1QMVPtd6/6D548/nTpdi+6XzTP/WYkBS+hCmL2pqz6GmS56i8BWYaVXv4i3JVlmR5l6MUfphzXysbVtOT3k5UxmcBPhGfiJbM4mVQaRk81/r9KRlIppnGVFz6X+JTyo67liVwtGPbbSUZWibdGuTOvkoMWEVtGGHNpZQPgzkMNcoBCri/V1gJlXjR7wZ2EZY93YMwAosJU8I9IwsDAmlE0HVc0CerxlB8Pw4oiYYmdZKiG+tlB+tFkkfQ9gX90KIcRk0tnzfGpuRZs8v2xvHYN/j8IRn3CK2XkPyU0CYH9/mBj1N8Y/GxgSA86zbcLEGlCFWTLrnqGvPyqjJtAXY0yB20Ql5qeroqE9m8MTDg/QYgavpG8wvioQju89lsKwsoyeGd66oZoPk3I0I9G8IxBuxji2eoD4oKaiM5nhoyC84S6PTx2mlxpulY9dcGsZaFAwKfA74onCcifPOVseNc6Fc0baX1lXBCYJFfMw545U40eDGl4D1qDDc+b9GE/P8jy7Pwkn5YYZCHyhBqBr7TIAnvnNC3yDKWJV9FJYlYIlTHXzi3dJDwY/JgT/TENEpf8KNCdNhU3Sw42P+r2enDaTfiOAMTlxxsDrCJDJrvHQfF4o9goHgfZY79j3LcJ9zk/IxhkVh6no0pm/VIY8WMRHWRxLJJdZRaxy8tqAzDL2Oh9Z0RtC76Bp+ioj2cBrHqc9HY9+dFn0X/S11AHGHjGSZWkEQEtSEwbYkt/tUkhyEghEJlTmaGY4vTn2bssjqZHxxXd1S2Ap39VZNPHuq6diuu7LuDAVtGzwC/305MEdomZPSrrwJni4CMlK4uxZXpsWW1siKXa1Z3btbvGo611MOMOBjT7DwUdd1QtkV6lRSFZkPMbBvK6rPnWTyOPUg7xRdNZkGnjXMK1oYWSlqmaQKHxksdqbYPHJTvyTQCtz6UJbxZS5dAgke8yQkoe1ESJjJyETUIuT6Xeumk9FxZxlpiqEjWeuksK68Wjb6RpYC8LnJbHXiGH96gU/Vss2GSRGcJp7qo6edus47lLoeaWZOJd9bWSaaR2oJL3XNoxevBJeN29A2SdH/3O811WH+AbHK5vDumT2ZjZKZDyvEyAjW77DWJsh/Vy4zSReAEYfkjE0lq2Xp6Pqhf7l0+S6jinGhmMCWsbNrAgQQocLjrXZ+hJUpbRkRRz2WT3bg8OkF0qxaNwiy3f4p+lk1aayeDZne07t+8Gb47X1/+YovvSN7Ng1SlQqNUsGmINKNQ2M3xoWpU/SSlKPQ0wSOMpYh+cU7xGFhp1j3SWSoOtf2eLbf1bO+LvvY5M+FVRNZ+mIFJmNZTQ9fUHSBH5LrwXPo13cXMzqGx4Y/vWnUDNAtb1ux2IFQe9DSOrnx/2Mgs2oEOjbEQHyGysQUl6IPoB30KyAzp7NqUas4iyvrbFFfm2tzsqbsnqyVXfj6iK2uQl8Tmj4nNS7Ak/dynTdIFvC3+r0U1kanYUPmMZ6NvNMHx91R5rJsbqDNaGtXynsaxlFWsRBQiyV3TU8sgLFR1tYK2YpV54qcWpFwVIBPgy8qdJtkZVFyuT2PScoawen6+vl6n3vvAeK59OIcAU5Y5j6xhXvyKZFGRJIarhbYdjoYLGOdYuODxXaquLVcLiWVaBwsPAFwM4+xD0vFMsfJb5sRYdd9R0SdvEkQL1KtPCnKgV+l9QNk+Ix5rmxjwzVOUX/j7YhRFPxW6IdzE12qzQ5boYzMrkgrllaPBsMXy5My2rgPLWFFI9jcAndCWZVYORqpU9wkpvxH/7GilfSgb6QwJDV0SqsNLdZaMNzWftyk6KsHUj2EW/9tIdxqgu2E4ZiO6Ein9J2kIhYU+dj/DpIPrY2dtlMTKq00bgFLJZ2+xqMkNVeJg3cuslDC0J03Ug2kwH9iVIqplFqgmRKiEaSQ651RGHCxU+iUxJI1iTpxjViEOakpaRZSevfcRHrqQSXSipKAkDzUC7ouyJrnyXNW3UTG/UNAQpEDdiSe5BkmVoxCmNmAvTyZOBTunGQorNbwPWZ/iM3ULXdRfMy9JEnaFieRrrO5/huU3OCcz3ifBrwjex5KfzqCzRgnuANCk2xAOU4hTAJ1k4IjPGRhZkiOiwGQXSvFJId9jXhUqZxdA0+KE0bCz5QfkxLOAfobnlYSFtI0cp2oqLUBXjyYMIJ7oMn1PEr+rD2nG/5wnkevw9Fp+APYLEUq6vfyko81cdxsFLGRaZUloCzopZEdIVtpLQBt1gau7aULqRTWprTxDtArEYTKORYQ3KiFiBRWnUEZzsCHuEPH3rVsDlgsIs+FISFEbwxOwZhdS+RTWM9pYAeUJbGJqCcWgYjTES65IYtRUlsfgS4pTpYi2O6ZyRKxfZFR9lKXjRbQ7gF+I6umczLycPML815PdKWleLoq23ajWScA/GjXvpog4bOXW1NXKAUZJ6559n9Banh2hZpWkOQ67TxLAtfSwGoKBGePEKIH05R6qgy87W5p1ttREY61SNkY9BcdRrytTVd8xhGJl2NRWy4CmArQk7bSWif9cgWByb4rcmMqK++PXTaVqmh+k4rc47r06DT2LEL0n4FELnJxIYNVZ88MkVVheYFX3CbxlwZd96GVBGDNRQKp1Il86dm9g2yDCKUC27oE8sYFKouKI0TOcCrHMuZoe9eggJIMp1wpGXrv8rkqnEm4qSqAlZA4Mnm6OHyEW+LhF5t3036e+r6nBnM6CQnzd5PpahiYol/YJqk4sZo2739U+vqerHo4j390v8ZpGQcl+Gqk+B7PCyeaRxUCPqFs/pGmPA0cuDV/gvMBPus9lL2S26o7EMljJkC45KadNiko18z9JKx7AKo4nav1ijVRGlqtr0D1GqLueq8z8bEgq+pDoDJHIQgL4iC8yqzul5+5MQBn8jY9gEySGqJx4bhJMZhBPVqMZcGqIH4wbQxvncYhhUTfQIEGAhV/xlOz5EsW0zUX6Jh+8+4oecwhT/3BrmSYnBRlFMrpuoxY0wsgi5aWjDX+fL15Wv5tqNlmql9WP587UN+/sAuo+T2ZOMorO2ZX4Pv5L/bzHoqAvtdnsxCOAO641wA38nwhgn1xHTO/y19L7i5Y44CCXj7FSKhy6Ev9QnfJARhS2OpHxEB444exIzYPiha3G0pSquoAWn2V+lVzlHh691wO3gzdLtZJoRf3NizOwGgRmurVnMtWsw2/DG1va9QIstGjGkxqOVQZN6Tf5Dl98kV+GBsNd5JNShP2mocB4V5z4KONUEBlWeU/afLtgmcUGK/Z4AIMvMOhRfdelq2DvoOpFV5D5gtBPteIrh0V0WimQujO0SysAtNYDSJVkpi7qwAYrSOWKLnIvork4mq3BYGJkJ7lkkJJRWu87BrztEHZCFVHimF66goo7vyIHPj4zi3XpWU+t8RTW8soxjVagItqvrbjcqJO5Jq4Wz7bsBJ+ZyE3ZIk6t6g6Ks9nlJWjcmi6TAOo6iNFtlDJL9+wEX1Dh/19ePpjhWLA8nmF9G0ehpCMd0YnBAzKDdpPsE7p6b3Mb0H052zSInefhDwipxzjlj+CdqK5KSyH3GpTAPCPEyp1gpUHrx00m/i+arhTHnsrJS1DYoNmBonNyGxiFCe4qWrpypLUC711YQiW8lfdPHwO+FoDlj08oF27m5vY0pe4oUF+oEk6sLO4r4Y+Hwx8Lgj9Ya0FSP1SzLRWmW2xUtmRK8wdeeOScTPGMBpZvSAfxmFviSeBFb927e3brtq3JTMunedicYV4UdfElKEabFu8FVQUunuqswosPzeso8hRuqiJefsK/ojfV0aUM1DL9pEIZH613dyG9GuEjANR3owjuvyWV0lNjOhO5R/yD62IyefP/HsvWT4QfHUsxJVOhku0gWQpfODrR1SeEA6Bh+FPPSkH4lsNMwRgCtWaLUYbu1y3WLufp2cyNG8EeEYiiNgWCaNSIHBz2BZHTYRltbMXyRHEXxudhu76MCQ1SUVGXoQF/4kCaFL6Dkc3xgn3MSvfoMBqdiBk9FL+oBMxgfzeUQx9SJltlo68GbPQGdzSV8MIZ1qJhga+sei1QmgYlReD6Hsqr65Pq6nKGl0P/ckxuiJ/4gIHNXwLaVLDQKHQusjRRNLlcysBTLDSxZs4HlfWmXV7YMPpeon9xQezfjUrcFv1IWtV05kkiNJLrMSKKmkTy1tqywp2K8I5tT17Y6vB8NPSbIyefCQzEOZBbrIkmJvgg/i8RYCxn51Jeh9VGQM1kbdse1zY59dtsmxiiUBSjSk+mYArPYss3Vt9l2/ig53Qd5rhSpaDFZflm6FIbQGMYA52j+b0ILj9HqGpPVFd4M0/0ejx2YY7S9VkFMSjsTT93cQYw0D9+ekvHZ2JHBwPiCFsvMzBTyIiNTP1Il39ao5BvQ0Zhj6IinjzmGLkN8V/1Yb9B6lp+hvyWgtApOTKZasDIYlWdCVMg2queiSTHHcwW+nKQzXJnppJVFJ6KyrLAooqs6L6rSaAf0JmTawMAzneMbp0UMq120VG3d86AF92GMEnAh6XxweQ6jU1KScALaLvqzcWnaCsQj0h7mXmRWxXt1AoN/BJOAsUtWGW/CrsSXide0MdRsepIUkpP1QKdbMm+XwJ6JHOyZ9orWWoMNOQ4MoGpg57xMJZcL4Bhkg2Ta5hfpX5vA2yuZZS7GeJEYoWa8/WNJIa+ZE68Z+8qpH5lO/YgE2E8Y+oEWJeQqGKed+0G1JIpb3eFG/tIeqdVVUZGkElZYfhcULi6IdAnJqMJh39qHcHa3P9GxJAt5lWFVuybd3GHSD5Sosyws3Da166R7GETD/GW8V6l6RMZ7Na9XfYbJ5wN8sOytAxJ8sOSxLFCqIl1/LO060CiLnJyQ/qPC9ANBUAJfwGwBN72Kp9V0DnQ00BG1A52apcJlMSARey7enmQYUF1yaMqKcah8NSngYZOEcIqe4giI+zp6WwTsq43gM1D8awCEpEnzcqs1nytfnVGP4GEyyoukKfYdT6BxGItaakakVGSHJ7/Mp1nleGA2SZer39b+9Anz5/BEeiQilOEJISv28nBQf0TzvMYo7Ia3AykOlt460Bv6smHlTaMx7149qNgZlPnkBWNb3iUvbh6i1fiykdYXu3mMfN/q0Y2d0fEzF4yrqQPeuHlEokFfQZ3M57H6NNYYvQ3cR6C0XGmT9AbL82FgAy7ZOPBbN+0LnzawupRZXVQL7X+XldFIKSnjdJTE5/EY2IaCrNZIfaPcKDxfiihlPEe0ugiKTdnG4Fpmn6JeKUkieEJGaVYK1A6sU4bP197c+bHE/127puOvjW7pQj5Ca2q3Xrix4RRffcb00MLIjc61JRrRlEZ/Q/X/hn4T6plTJdb2BjDX11ogJ+S6IJ66Fgfj2jVMPVi4wn7DgRQJzR3Poyur+D3n4HoFhwTfNRAKOsw08OhWzqfFj6WCSum0hk1CmTQQqXNHhdAYJ00PTgS/83feje89ic75yAG6OsorOHAoRpLPRdkUHj4Yk0NHxB4flLQNUBJ3LrXTkhN9xnCAPphgoHwyxPtKfsAhfedpUsVlshL0+ccygMNwMgaabf0SnUZ9gsZpxdi4PuDzbHze0nWdaYvgHUCqLNENxT6xpDxuQ0rFJ5gJpYcu40YnAgJSi8MozkXMNXQYAbDK2rXGmai5d5yH/v0TgDYOHm0a6+HqmTCjJQwDEM2CIXDXBmYK4+agIiG/C7Ag9UYa7MXdMZu1epOxLWDXshutxYZaGGu18GJLkdvW3zMXXd0shBvOtYKtlcZoyquM5vvavcTqNC3F1QZYl0S4EGeTKFAf5TGSkmRz4nhsbAjjw619viRlskdlwFGtx001OS6iUhBsi4CHKJ00YbMpHaAaw0djpOnkyUhkVgryNM6V7ILkSFLtmvq4tiIRtHE+loy03fyDikplkYPsH2fHcCawPVhzEOyyYVsWhqJlVuPRkrelRKnDtlayH7QmmIAaG+mljaGE77KTuoR/RQrRzeB8PCSZBSNMSWMEbgobREkiog2HjGyRVLbFR0Rjt5eL7lfvu53/eekB7I1U/9n4JRIjjhOpPGdYvhFeU3IiIboFcOEnZA4l8LkVeaj1F4wSjG1GhzIa0IppRsAnNxj4pMRrJ9MqYjRBhkFhPoTjFyh81Lt3e87Lcf0kOS+ZctG/NPkec+42VuMqK6bFoYklStrf6udFbda6e2H2suh1DBogLT6CjQf6s2JEbg+vv0eWIcslg1hCaDlAV2gYCUDkNPLMyf44nTD9IeOl1hVUZLEsLZnOLnwY2Md1FkaGljzmxt4nFYWxW9LMSlFEWo60WIWWXtLIgDWmRxnoOg22pNoLarIMCzowtRZJLNEh15pNNfVNYNt0CikogEZTLBcUOq2lqquh5PExgAd/494Txm7F7qWVdnnTKK5Kpu/bc3AJ62LzKJZo55z13ih5iu1z0aoqHCZzMQU3HbhLeGGQ/GW7L/La/n3dzy5j/lvW+yXr7HTefvvVel4bOHfei6VR3EhXiHWAwXz+5cSLfb8RN4NM5QqupObUEIAmtTXeNVSDsDHAoa6JrJkww01gK2ajiOZQ1z9kPzWUB/QQgwAEImytEaGkWdYPwb2Jj5eiQKmDPYPBEQjKHBxRUFPuOOmU0ictaLnpAcl7n1Iv9zvo3VPG6mKZHyAy/ADREj8Akdhe1WDHp9UiI704NEzcC2HGF8K6hHXDA4e17FzUv4DBjiW2MT9EqaQneYnITqBGSS/VIRwgerLtF7al4f3y4Q+RH6hb2Pz3Qopq4iaRYbBsnXBdlrG9wFga05iKxSAobaNY2u4/6j0w7l5qiW8MGWpyGtgno5dLRhBc2h/RdId3gZTW2MzSGz02UIueoQliNaaLeOg/AOayW8f1WYLtEknSkdW4djnOg1KB+lTP/gLSssWXJleNFZS1s3kXGH3lVubQ+Y66PkcUrm2q0EUdcGDxQLL/D0MnzqMbh33E6xn6ikfGdOcoVByvO3Z4IUUxiEGNTTY4lo5gnJ/pqp06lmx0+u3bKhg6scgwQ8NgfMFuM0X9y2y6ZffD3hvO5xiIkcMxOyO2FZDTezgLRRrnxKWFrqSRSZ18RjVeB+1PoP3RfD6c9bymCdPMbYrMbVSnPZAUhrP5/JDviuGNk2CEbLvnjf9JvvRfxY3++S2IGdD/9C53ti5BBtqBEiO/QdIZGbJLDqwi/nf0FTjSFkce21wo+CQi4nKXEwFLIE6U6zGMgYc42QYTzZaA2m22FBtsaWSypRG5iIEtjRC6axVb8kaSLw3/RrDAv48D4Sk7ZS4Rm1woFlwomDQIuss4ELGskxrLMt5xgpxoPjcDIlUoV2pU1zhOPfsXX7GvYTP7GiL7OmlgX2OTfY2JfZ3A8L6pE9CL0QVrU7c+LFuVJjuFd/kQg8ZbvIIGF1w5XmDVnaLRZRblpugDvesvttQse3Rrc/vmUrbYNHk5Jb5aPGF9fWJdFM7XK/Xv77+ERnIJ7nvSxH1PDO4bA1sc/w+aEmbyIHLGYRSIdApg7E4+WBDDOyj6NbZOgr2E9GzDfLDMHmRB3Irsp9fn4Y0tlU6Uha8PMTK3Md6QfnIDDc20b10VCNiUyBqpp9TpCHL+UYAaYPS5HWVuU0UstIZEphHLfBwVvS4zZFLbZLG+nmr7M+ysw36twvxe1RoTGDsmNwjbLRZJkkoUhgjmZ5kI3ptwzJ2L0WzFC9pWX4zkHSNWSEUhNCN2ph9OjxDdV6hOkeW1OhRVtIy6cmWt8ldEVREM3JbAgJCoZ+1+kRh4hGlad3a7DviaCUnUXTKMSFghRLsxNfLitRbaqOsthK12GyF72wJFCyEJMVM4o7+W+rgKO6Qpdi1RcMUqw+O8f5A05MigRehJrc+IxG8u3VKjMEGXctuMlGEAyqqhWvWzzR+M9Kd6hz/1D6pv77AZy4ywyNwc9dEot2eg3hl5n4mR9/kByMrIYvrgZskmGq9gs2Om7K3/KwsQMzWZh292LeL9fWXuazeHebDOPEx/ZZwEzJqrcUJCf/DKkMLiSiuxxGYasgzeVsebqfzB9cMZpb1BO4h/RoBUZp4tIpIYb9zZ9o3fd3aa0nDT3gPK+391+fTYtSXpseU/lx5bwsA4Pbasp8eW3yE9tphA472d7U5znmxkol4gqoPEywvSnsdTh7ybkhgjnfYtU5t1YmO04LSmhwh/lAK742ywSI/KyP+NJDgAiRri4AkUGgXCXFiz9EvJCcRGMj5tgZKhEOybz/oqQbpAKY3IIPiDja+cERw3ZQTHVkbwGE43OyN47EALJSKxCXpRgPgeYz6qPO703BkzGsmJjFWaKL5FTAUMf6/w4mDZBBuZozgV5fQQyfAJ7gFsxPgKG3Lz9r2tzXt3busASthUsDQpQXDw0qTqlPI7Kb6b5IC0ccEU2keYGsnbepqNtUvl4BzlLJU9SXk5Ox4WYVcsTkNtRCFyuw6IVDXghwj91pFIOI57kYKIiBkTIl7glBs8NLVAO0xICL9GZOnVCExl+iKNxZpZZOu3t+9t3bx1exMrt2dLM3uZLDNFCgnidglSyHA5MkkKAnlhGS1keplUCwLpwGRhGLg1TigoIyg1JqK+inXbjay8236nlEXctXiYNWMqmGC/f9hIJAZYRMNIKhsmQgBCKJQIo8qqg28SHnnb24GAZKKiFczvNs0z7odLokn8UUeTUDNswUpcBCgheIKqTBCUnGRcgxEQ/XkQGamQAlNAdLoUaBOr0M0kaMwKZAFK6aD7ZKahZkhjyZCmK9coNXLWNRpNjPwkBsZXCn4S62maapKM9cepos5Y9Xka1JekxAAVyU7i+lGAv9d2aoGPrTgKOIOR55sQEMo6AgKclZEvMAwiEz4ArRDGVxIWygRRAb7GwOGHR2UlfBDAVMqj7hjhkSqY4Sker/hJn7dDUCNj4FLANmH0cZjDMkRwIyLfFQEykrNDguTgeIExCKNcQ60gWEkVzAfSfloec1B+DX4xkDnhMkHRgVcUrRmaUp/yatkF6+I9UkEfBpxGc9lgAN+GKRbygZEARTnFrFMY0VeKk+zAqhAuMYtU1AIwabNUr0AzX19/ftqGKQXhAUipZDeL2gkLQgtT8BQlwVMUoVcugacoHHgKZ9tYO8yFq4gZrgKJjNk1/snrcBXGJZgFgquIFVxFTHAVEgloQskihL2qh2T+2DPk7HvbtQ1NfUckurwB5yL6XjgXxARTg+/VAS+swttVLJmrgllVNdTNAkYGzIy6zw9GaMLkOXDA4rMY1SGJZyiRUXStQ1nZSL9Ci+ovEJ3cKuXJeLESi0oBdugKpbGdJ89oMK54qPJVajg9afkQiPosKoZlB5ZEbhkJJCy+9qmYVHqChdewChFsjCpKx6hLwJ+XyHhTUiue5MXnXXRWgIjS8fK20Tysa95WLfJqGhfUK2AP5FQJDdgJEAy0D6c2f8AXAaNhMlKvAp3NqF0am3WoiBgIWzIxUd0qdzUU2ldXfdKCjYZ8Cs06jVF8AfgSyp+nSTR+jTExAWoqOAZgn4bKUoZaiew6UHhisZ+gLwC2s0xu9IhxSIWzB6JRuX4+mx/OrIMTpJ/18HwWyKfLMO2J9EysbMgEhiUOBzA7tD4D8f1QLpi8MMUwJzhSP4mA+doNVX6UYJyv/J5m0raPtoq1WR+xO5Gj0SdSjjUeuywvIYAR0naVv8jPkmIXTihPYCToNxA+uO4yf9Ud4u/m+510pMH1H8vr0qIWiapRxOspRcVYMDRE3bfwkX/6mWMVxtg9QnDlxlTEAhyBTu8N2AXZaafP37uDHKmssi1ulK1yOhqlM5kYDLdTECwPBV52uRGIGNLVndUWygu7aYX9XjcW7HrQui5XGz/Lpb6OwW/X1Upf7w0QDbOxkkfZ1KMrTOF36lsZRmrH9ZHw5/NIgRairUaJqgwqMYjz8TialMlQXhA6dM/ry31zyenXg0WOc5lRSnQ8GJXqBg9L4Oj1CBam8x1Zx9JR2X2lA4AG+tPPKrGMt0U6shYTfjSWxBMk6zuLU8+vg5fF6ejcbCvUDfHA/W6EYM1eKlcQhUY9fvFdD09cWD5+n3DEBOLMFoWqIIf8cuLlPksPoAt2y/twFCbZUXXcLTc2fLhh7TgiQGQs80lbsxWp8KIyPE48HRpa1io4wFFBZTjwHVJAieFaRtGZIPZudtfi9jDPkq6+TE/ia2NRy2Ws3twdb2wsGjfhgxb6I9CZAaKmDoxnVA17ga1p53W2HR/AzEbTMTYYU/BtliRDDD4dV+mE39CQNElR/Ooeed5SoVA4uosiOuddipbW0CFdKaz1PJImpAskJ/R9vKLcSnTpac/7AzWyPPz91O/kIL+sFboRtCDrMz3qkDAi1UNTLqTKigKpf8dPGhXn9XWSWkHs0nh96qF7ftOP9B5lGpS2LW2qUFIS2vrTbJosRKBapVYZu9xVQmho91i0ZCKZiQu6gUQV/V6oZlQXpBRtyrlSGBDHv3HAZyHI1xJkSder8FKlcZv4vVTU2bBL2fYlWEtECAIRusIK9oyPSlUPzXN7+R6mtRQ27eb3d1N7fcPULPlgiv2Jr1wAsoGUe7HAp+QIUj0CGDzq3MlC9j9r7r+WnfjGLWE4wn8EoJf9gCU+NVmMHJngOy6JXIwtMsFT/UnlD3Bcj3lN/Cbcr9SVw9FKy7WRuKUBfUEwp3Q+3wdl29vv1w+h62izELdSaDX7b79M00JkM6MwNbgvMYrecPW14ueBwYrSkqQt5FlYyScvjjign3hTWvWuYyhmypE+istoDbYRJ7mMjTq2puvPiqcJnfAa9skHf+7OJVZ04GXrJjqwTzWsbZR0+GIBajY+Iu0A6JQxUanpgl0WV/EiwXJsULC3STklhDGEBCPGf55UutQSJmUKk6LN0iyGyqbnRNcAFtC62v6rzc2apalNavAg9K8p2mxs02jJpuKlNEvA8MoILKuKr1ekygElJs66BWtrxvxh1JRVYn6saEHwy8qq0jEzql5i3EJbQG1gvaBRLkjv9NzF7mWfhh9gKIBVruIOF2e61TlDJ7P5082L3mXevLXZoTcroD4rvoX3qv3AdselPLZs2ZE1yny7efNuV/IEHWNdtDm/89GU3Zrhjc2gaONWTE9FyXrjJ/P9O1ygZKUl27JZM/auwSllcSsy17lRf4W53wrDaee8wrK1G8bxIjQ3aVdWpuVzXs+ZtOYRosh6SlPYU0506WZUsS+ZRsKUJQQEifsLutUa2r1Os+1C2Uiofj26wE1hCE2gDQsbQBfD1ZyHfe2MgFrUX2ZOEkt47qSnmnOmrlEqFUYn/oyWKCYPcUKRRUVbbWAULOd0Dcbnlv6qlHdHlW1wwL/FEzc7q3flwq6VYdodp+bJULU/DZPD6dErlJXfJpQHrmVSrOHytvAeFHCfKHu4TyCnhJHndC2Qbb0+yxCPhj1W7HgR40JeyPdQdcewMr+p3/ajUv+EX9Qu5UGxNbsJL1LUtS/PIk7LRYzI1ig9TApxJhjW1FD0z7mQtVGsmcHL6K8hd1SGLCIZupRJMwO0WA4DGZoaBn6hMkrCpucX8qDRRTtVZY6uUDZWAGKyP9iA1eVtDKMkITw1Tqyq61N7hnC4um3MfIfB0wxOQOtK82nZktI4zqM+xNQJht4h5XY1yqo5btfCdLtW0u2qa++hBX7rzp0dEFIXrojhBDgShKtJfxjMJbBdRfEVKqOikJ25JA0CkNghPZItcJkWdVZ28bvBh6g2iy+0WL4XqPApBg+RVldYoUJwtty6cxuVBvJxSWqiO5+jK+L3U/Sod9WBLPe9eTRv3e5E8iywdloS/pC6WzLBij+0NakCjUoms+Pan+A9sC4hVbMuVIEgWLOnwoNYBehlzHRFuE2uGUTOk3fuTWp6kzW9VBgbITE8idqenKC6Qm/CV71yWulKC4Ug/Lf69ptw+5sLbn+jb980xh+C6C+eM54RBQircDAIlhQ5TkwA0r9OyMGiQUjPCuAuRsikRp0dR3+dez5DiVXHmI6bxUkP68xjvB3WSE8CudlEXdCKEGhKCQqKdlnKFEDIW1AnQDVIGFGgSEDrOKVE0E5rsJFtgALxAt7XSsyWKNNW3CoAWxEqidQKQQPtwUaltSU+TjY7dg0hJXJZVJf5sg6bUVBGKFNATkWtTsVTVRpLPbsDFE0W/gtkzqSRRTEyjmJ5onAeM/jlFQG6taA/CaTsxEaFkdxSKsdFJFiIEIoue82qelBVEeZ88ippGYOFGIIQL6+vT/D6wen5RxRVNkXCGD4mXxm10/KREupEgSNVbRgm0fi1A9yH2u2I1y5sIGsKBxLIq7VogSgwIzS+VuFzuU721sLuo+hkFTJMGXkZs5kFnWatJCrG5yJTOWgdUpg6XD+vjklNkzUMRedNH7xdp3CZT74iTzkGZjd2VfDQJFxKTyAkZXCRGCWz1nsd1KEO8+G5Y6TAy3gvFzUPB8/2X77AGuQ5CjWP8piwTunBTrKg2lLknYZjIi1KTmO/nHMajrhQV9YrDCUeZIKs64szMZR1DW/szLV/2tA5F5IBU0g2ykUprqkS/NQ0vdRTt6hUJLvNCLZvy70tcwHMknKziVcZBeJc9kCxm72aIajz1Cm+9PvQa2Ywh8AUjrW8jJWk3NZ0FxxxwG0rcdOQDHH7jhwkKagGkv9TOqydbqThbuJx5J8ew/FkyRiQ2VFRkXOEzQzfDYkvNt2JQYhau/gVhYJNv80RKxxljhVziZSYXkA+PA+mI/FiOMWf7GMwH9FfYdKf34GLqbIULQn4QopzV7meLnhTkWVXaPUqMs2ctUhOUpHJiYnaVGq4ygVLp+57ebiW+pT0/gMc3kumBsOWcx0niTHU5uTnPLsRzm6+pAnEH1g9u5GcXVlHxdzBHD4SUSYEdDmiLBcPzfXIxlMRhAwtMAml8iSMXFEtX1phT9ALnhByRX4dYuSq3yvogY4un04/5FagOseGNxv/gfBENYankWHFhQX/Yd8ONUUykURgMAh7zW83r3lWF0sFESTW0uva3mEhzf9R5mUBBjocBc7NaMhL47R6CwdCP85ZtEXKAQE7IVCgMMHQ9gaSkUohzJ9LMnYFJhTWN0lkL1hCz8TCJnphNb/YUoVslRlEmrPE9YukmQYBXtXPdtORcPo7S5diSwlfry4jqt0xRTXrjgsX/W7HLse3govYPTSMGZKT2EY3m5UGVzO4BVftjpJtlSOgKyQAI2eL4Aw/yaxkd7J067Lw/doqZKEHMh2GnJ1UkYDhKlGkkXhUNZcjFf8RejyL/ClXzNOSe6uhZQZvJIgidqRaDVhPC3g7xO0lz4JZochANjOA+KoiSgkJDbqGSWQkzh2nVVJOohhEvIIAelOq681FM1LM0aYEiceHlCDBnqPmirm1tVIb6s2l9BB1Fj251O1qxSObEnbUnvrN3t/aLnehNc6pMwyTcHpuCk8pVYBUlhdi0ZNdOC4O6XIbw/qTIdWaBPl8hnUYzPPLuoHD/EMq8R7Vg4FlrkAhNIRU4iFJzYSK7SinQiaN5JbKYx0aqKr4lPDg5KHXzaU6baHoUXRxo1KULlGKyOfn9r+oZxOlqrKgtO/bvy/ThVLf6InvX5WX7Gxq1nZRKdxoWuWoQ3CA5CRCfyB/jsc5Ve7kwMmRKnnrcuiCUhNl7If8Fg6w5UFP7SdFY1t3794FhW6zAx/u3Ny5fbfzVNYgKtpkBnjFLUj0QzR3C36mf9eRdr1f+q9ftflLOjr3jJv8zkCU0dztH6SYNkh/m2J0fkuTs31VNrWhEOh11ep1UQ10jxE0D5ME8Ty5VA1ohteFinYdi4K2Wk7LLT0CLhNav0M8H1LZ0BS3gVnOyRHM5HTzvPfcWmsd9/xcTjXb9zrC5GSt78KybIg8zNY0QyfwiH2bIB21vMEGmbY2BhKukAPcdTk0s9jPpYogaVfAkIJgVd7HTf3LKK7VsKWY0ij0OI9l/T2Dh/gk/Ctn/t6Eigh2xF8Khi4LShvCv/M5fe0nlbwCH7HijLDwKuvwnTt3trduB166vrNz69bNm2ioZdWW7jMlLXT8goKnHr67dW9bxbVMpp7f9BNP/u+H4fPD4P2hsOomOhWTO3BHT8hEuGRTqX+t0U45HyflcZJUA63jtsc5nZTrD/dxhvb2/Xq7RtyNO+S1FxOq+XWFzqtOnohOVvrkSAzXp7Jl3965e5PDxlXR5J7KEul8QSFex7oHTzAawKCaYz0Va09lPG6iAq9FLI4MWuwYESM6crEjw8qykJ8MWOdRMe5oAFGuGbOCa+ab1o+ukvkrjCkih5wKYVfuuQ5/tpzvncL66piBsHuV7FrmRoNXTV3LMNy/MkLEs6aeOBEAelaPrID0evvGNaEzhDpxAp2h4SZFPdC6qE3Ke1RlGeAZXibj0UNYDSlUB6qaZzfSkz+Hs5spILIKouP1ZUmY9OPIvZpuiLqlzktVcmw3qf0cprwjsd8q0dIIkoLupaJ7qdO9dFX30obu6Rg3w0emYiXdmcTeAHOdRmNr/txJ7coZz1Xvc7P3ueh97vQ+t3rPV6jLOI157c0bIlXGmtocW1FTaz8ColPDbEffabaNKV4yr9L5nVjPzUE/NzOcMP1S74xPKxMopAvtF1Ft0XKfST1BeDmkCi10Y6HnSrVVqIWOKnIUqyAN2/vh/qCsBJmt3tZyVItwSSRN1XRZQIdYGrQfDFHBQPmjT/anTE6JiDNDdqQwa9wfa3eLgAWrzqxkMfQTyoqo2fS8GNWVIcVDdszb7Y6brgrT3Yr+BheDJsihSSwj6kzn9u2ODFFRljXb7eIYpXoe9UsnWHvc5AgjBVNtXAElg3+YxJwq73eiXlQHy5HPV7XTG1rgV9ntdCguyzbvieUzbxf9Ef5T2y4NDGefF7RuhZZ2byNOTlGZ8L3WXeTy3doLXggZplbc0pJH3wtfIrnasEYTw8ZiQCN+oziR8nsJpF1rR1U2A0fcC5QAd3YY0EEYGZkeMzba4cwfT7yUarYm5F4zB5gIil1c4T3S2q1W5P8ugFgAPtVwEShOhcyltA65GKRgyJFLwkWGRmzHK4CHlbS7ReEXqjGWCwZ+ut9BMYELuQiP+au+9+IIEZeMsLLz5vv2jPukXOcEjJenR4NLvWNwElXHgwtfw41SoaOGm73BMD0dAM/en8//GHqFX8fbeZzFuLJkJ4xa3BLpgQ7kk8jf0rBHLS6vVEogXef3soWI5BkWL20lsySeVrI+im5SFNpiD2wbS45iS4Wov1QloGhRvY3oSGaC6ZI5Q2h5jFUCQFr6KwUpv50XRz8l2Y13/Z+GeVz+9D45/Al9qT+JufhJtue3aUbIIB+10yxLCrwvHNzn0f98/3//JD4NSGrksj/kp/Ei02ljrUGC2Ni4BsrEkZaGbaO2MuKB4GtadvDeBZwKS+4hSA1hvoWG5EcYAekUfyFackQfQv7uEuFlO5Wu6g1hmFBU0euRN7gxQPX4xhae1GRgs7LzaiZqUac9lVX4UiC7AtGaETlcZf29ico4Gu9GLBrWSIos1jrJEW/BlZMRKYhWBZ0UNXV11aAq79N4OcMoQrl6cCCA6/F5YQoR4/wImvWnY753dz8g3+HufrOxCWPxkTphdDy2DFHKjzLkx5zXiGjomAeE8SJutRdRmD5yxxkguHrBxVqpwBLZ74F7TicTMfQxIazTeKls38Hz448I/3PwBf4WXU7myVUyT24le+RCB781n8uPt/2oTYWXh0zmuT4sdMoO3QwtgSYvP27fwc922HtuZ/LkzHFrmTx5PZMnb8zkyd1MnrwpkycP5eVF7mbyyF9MRWVhVfmFGROM+hXscRCWCgri5RyfaVXlmcrgnUwr8VlueU5mgfMEOF406GBcXtFGo+mTPJ6WMhxCpLCcHNEdm+qy3KPoQlzIw3txWcmBZDspJ6z0+9acFIbUcRuljuQb5QvDRaUwJ/67hA1KcHJkg8yQ6kQKlKlEZTWo4TRcS8+lchWF2blyl0iLVGQlOaRk7y4nlPhWXCb0ojmnAX0aTk+u3PIiEQwi4QhTjDdibzw8OZ9rJIm1TYoYluVqn0moNVFnYT5/MDQfJ30CQQ1TSvQSac+YRdXojlc5uhEW8k7JGZ9dwhkPQhqc2nwa7cM+wxUCYSaQo7JE78UybZmSJbKaB2mpUmllP4REKAq7TlCM8QWkbIvCH7R0vkSrlDAyOoYTHbTSlMweWqwEG7XUMzjJOsYQ9sdhdDg+bwg2FLTrjsrlBro7wVqyPBBbhDqqbsBL0tNUFPXEpfpuu1KuHi+UhAh/LxDCDZRAnUNlpZW5RqUbYd3Q5MtMfLQiULyaHYotgkrqmYSG//jmP9zDboKcn7oJRxX2cSnGo2lltw0gDihiSFkya2SghdW24yPQKtLz3nDWDqiyb1RWkO8ifdjJDk6kJK7mA0keTOJYagarEB1FabYiQHbZHl2WiXTRHq1NVEOyEoeJI9wJb2XNNdMld9v7O/oP7u+63xv0Emt/R9b+ji6/v1XXv/v+jlbubzPPSUMcrt496bfs7/Rb9/f36mE3Vfs7/W77G5Uxub/Ty+9vufHeWPB4MFM9lRGS1SbiXSpbykIpKuABc8Eogkxkokj4SjaINniajGtL5mPpHRrn0lytS9xO8S1ouxW9WvbeC9+G8EkXvAP1Y3JMmxZ1FiawwC3REutMhufVD05YtjciS/xlR9HfPYME97eDDPtOsPLx0FsRcqj20+07W5t3796+WTOw68i4YaqCmet2eM7Z3Is4sKmWlBrayafG0zKT04JPjgjtSpxYylTPp4F/HIMcirmpUpd5sIuAJ7t2pQjd2iqIjCgksAStFZAP1MqKla+DOY3MZbUXOUx45RNX70MITkJXkB3QrusXiGqaOI5qA6XLAIQmRC4/eLq+/hSVhcKGLNOJ/Ra6G/mT1ZT0jz3/52e7Doo1MSQ9RslPZFT3QuUNrImgCpywSHNDE8rTaBD7cZm54hdjkK3plMctLOMEXCgj+xeNebQWafYB357WSY25+fb/gxNxo2iAiqPZweUxoDCvNFmFCVDX8yIjKdRGrojIF1FQNnBDlK/OjkYcaEaviwhcxlpT/2siUOC6Uecro4ckBn0R1mqNc2O27tqWyvcwc0QyrC4mQ4GNPOZELo+GM2iavxBnNkhsVJTIgKRDMa4XMTF38G+gVzM0VhPjf8zrev3n8zVQfZ/2aH9EdLhFwZn3aYbxeT58ms0IsSY4nemIO/iM0UNLN89S7XNbeHu3ldOWj+DPzWxOn7IywNykHzoeOs1npeu95aOk6GUmKmtNSGo0M92uteN3xLjsgEcD0p12Y8YInuLIylx/9GVl+IbDNgsvOtALmWa9BKXo4nfUFqP+jjXGn3Zc5Pot54k3OQxsAripvfWufz67qn8+W+Gfr1GeClo2bCGbtZB5YVHcNp7/bwgYPBWhX8tjLnSqiBhLkKzfvgXErrBfQci6gVfuzJHxLpVuGwIrnKCH2itwJyW0h5a8zGp2W4SHGLY9fo3wwDumqmq5OUqK7xpKoMnIun9cJGc42VlyBqtARlVYBkNvNbx5UhEVS3ZpJQ/rZ3z/FWBDwJtIzrpjDrDKeDWp7v+Tp0ZlFexFjUS5pOlV00hoaRbUiBFBaKnKVlccTeFCSf+yx2EDI/2OE6g5sdreS7mlcs4Y0FGaOZ1fxJx2OjYHsSz8NW6wX0cvqj0FrGHZ0famBn6z03nTAIizV7u22TGXyeqkXqfVC2Q9dFMN25isw1gX47FjHPU9MzGhdG/Pe4bGkl0h3z/EqK2O+KYf6atYPfOhsxj1IZx3fkx91w/uytDl4lxhLZsyTaFjzEUcrQbc6YpkdV3VBG0OiErZzcK0O8wpJDZDSlgn/LyE5AoBagdHxhmBJPdncHn/TKQGPoaRvT1Ex1z9hi0WOmQiRVNWmC+i5sVN3SgUHdifER5aT3w9E18HcCbzaAYd/LyXlUlBFibj4ovoPJ+KQQ8EGIFoPw9VJPSg9SGfCng1tGzCNentLlqca0dpGKIqOWHVteJxQi7tQOKyTTNZactDN2BOyfx+e9BRsQvVcZKZ4CK9wbVrdjkzhsvIq6Q12Ig2Bl5Unmdxy/Nb4c9YjYsgV1U/o9YbBrzAMuYUXhLAw2lFKWktflTDd3OUizkkrnbGMHrpyUkyTIF4xueda9f45fzar9dablujBNjFo6iK4A78udX66SeaQqydFp1F0B7mxNEvVJEaETbgNIK9FYrfX54/eLNH5cKwmTI/SfaGfle2BUOFjwv4v/Gq7rVF0DrgWz/6XbzvddE6+IhotcYiYa4MApkKlyxMGJl8rl17kURFxlgj0SEas7FYA7+A0vQwSOEZLkWnJYN0Cjohh8npT6DFff7pGH+9gY/dkI8BmVnEg1AjRYBbQc4W79I6lDL5j5mgOMdOwj8cJrhSdrbh2XEaH3P0iUBJJPK7MZ20fywHzBkY1RGVWNzIC4p/8jKCpFgs4ohyDvyve2STk8igJoM7U5xIspTCYSmp3jIiIcBmKanFUhAfklhKEUaSpRQGS5GQ+kUbTfdBGeYw02VV5Ofd0ky6UpdX8p80rGDa0+DhISFcls1cCAQawejE/BDiyOXmZ//qzP3xtzL3R1Zug7EG5OCyphmVLw3Gx0BObXHuC5inQZGMEJfTCYaYz7G8IrBVWXGxVhHTge5UfpgfS7G7qrx1gjPXkg+K6wLSBL7EScnRcMCSeBwtqjMvxNKT9Oi4aiUpJtFiscLDhJQtVNBsOZVip+SvJpiQrP1YNlZ+XCLeYiVHzI0fSK8RYg7xNK7V4ppXzgM90zAPfP2/YB6oI1eYB64f+hgI93HEQHi8NyrcG4giImtzwN7QBPs6dgsPLivE6tngep/FrpIijAv24MawVya5B99A7tU/R+5LRvzfR+rVP0fq/6k5+DYyZ9EXod0ETA86XJD2X8eIGBwUPgjEj/vkFOHTZz7P2seRfMAn/hkNh/J7gA+ro7/h3F+6LfxO60GrFL+IQgMkSCKnZ2nhMFFyRpukDnKGK3lQCaDtAY3XX1B9tk+fSIzZy8igMG6sZx2t2ORqqz5Qe1wcGcbEOXtJcdNaCrx5EOJc7R0GAhWVD0Prmn73n9aBCBvcPgiNnEqpu9b10/ppaSqmmx37NxaAisKFUUSwA4/hK2VQB31T+c8UlEO/v0QMVXZqYY+Nt93pJE0J8XBnctZ6NSI/XAIz8cuI8GKNezMuDeiOQUOGG78tdHRjVStZQAvh4yagtaBJ3UWhcjoJKy/TxaNxXWS6r3sPZ9fqV8jAbIfsOX4ZKHUkwupzUHqyI+ABqrRGe4DYVbCzXp9lOM+gy517A+EtGfhuGejBuyyRrAmabYlw6AmjhbOIDJuNorIFu4nwxhslRR5rXUaGaYvwvLfJyPPl/kEnFXfAqk/00tC8kVz/jFHo4w2U8QYi4tVPvLIOOZpGAv3R04nkbAXnSaXRWjd8Y33pHhMwpbleiVgZ8Uu9a/Jea0VlXISNpG9Y2Kw7fZXxKWuZX7Kroszosv7Kn+ud5hAzvSS2MetNrGtuy8xde+OiQpJilb20nWe7+clJCloLfXlLxkPMRVYmATKpohGBGOQgyA8Z1TIDXSQZ3hCXfbPgkgFwk3ooO9USX+uhC+oe5TokOARuNLcbzanRwuKLTy4adTfhUfNA3+RlxSP/roNNav3a0ynvqo7GLU44p/T5O/rzbd/K1VbcUHF3nfm+2c3uV7JuS7ax4f9uYRsE1UH20ejEC6dgnDzWuka6/8OY6lm7DRn5A8HaX5QM1/UrhV+s3/H28u/441vf8Zdhemw1zOaOObH6sYfWYzjJfM8d/GgEyvNOUo/9Zh21LBaFdRQ28wySnLAAtkbUmPiXESieWRYHbCAfBXXxHt3Yl2zx3RVm6rY5a+vr05GW6eR1A9/jPbXMiSndLq/4ZUu3YK/ENd8s62CWb+FSepco4dJNRO7KLbGi8PG2/rh11654Ux+aiLFzc5aNUfsyzwUrzCyta4PShYZ73lYjMwUQPX9PGxgVvE4id9/iuk63/dTS76qeN8YquQFIVBKQFG6718sYUTRrgB7NmqBHMx+tTCBUsNiLQIqYf8yNY8b332sdfZlG+hFFN2ZtFrwxFWBXxprJHALE3s6zeJzGn9dU7TJ1KfyEMW3EQwsQjCUod0vY2G5SkCCvrSfvEoEDeq2FY96YTFEtXi+hjl0iJmuskU1xKo5myR16mZ9/4zJn9eWB6Xfm9DtPyIqZeH7hTDy/aCa+2AdDoHezE5cE3AFW+yusjihLxPoCcQUBpCJbKXQbhdUGsPrC154czZm1Dyg8SD/ClBKCPJfn+oseEiUWQlnUnZSGS8HdR61jECcEsv53C7tuqLgCKlzlQEQQOw5oEQoDtVdBrlq3y2ChHYxiK1EpMzAKdnaQARjtmWDJMp5CuDOrFYjJsk9Pa32Supk1m3uMX25OoYXL/fdjUDQp/mKd6GaSmCssynP4aHL1s/cDvUUdPDubeKJYAVkyRgd34iMsNWDIar/HHncxCT+rAsmf+7VC6n9YOFuygks/3AyAan+NPVXrXNxCwqWujKHQ4Q611g2fzVt8E0rlV+t1ch8iwu6SCnO3dKVgvQtr7tYy3B95ud8teD9iGdn2aZqcUTy2SkSL5nO6zfqpSzMX9OGHAMaNrlAgrY3Bp8HGgz4qDw/6Gxv0vCdlgu3tWuKJAVSiFwxE+fm8YQ7lq/1uQ8nkSE/WD0LoZ9lI136SU9PbtSVg12jU+YYeV/P5D0aP/SXcOBkjcTIUmoV2JKD/RGh00hgafdlu4TsCs3Mq9lq8xRK824xx6Oudae9FCgPKSPiQEkMmRBFCNLS58xNCFo1a2KhKuMb7KAV7Fdi/tLzjfd0qjAoqeUYsC3WUY+BNsCUwxDjLM4wv9v4Q1RAZImZty7fWgNxs5iIYlcHHSivU09TgxgqKmsKRoimuYAMtdLFQXczEPPYK7munaGNRs8LvYrA897lHS9OhfqdBpPrdE2sm24A5xjI8yMBBFHtMzfgde2wLjUTXzNyWUZIYvC1PkFkN+2CUOZek+rqvVMjXfcJFoOpMglxe97vfSM6XoGZ7heqErNfMVQszpiPmeILXKhBOKaFUaAWHY1g6jQXmrXAbw/JmxvIyBVIaWY0IC2sxI4uGUrGoYRRE8iOiGiHtwur2qVl3dVEyoAo8CUsJBEqBs86i2WJBq2OTt1EzXnMZm7pruxuhvTEC2xRHYfZe96W8xlPSgYXHqWLoWnNnoiee7+lV7WSWwhmgZqphr6Z6mownaTJQ63gMDRCWrLUJ9aypuSwC6JGYIErBFw0sm02DhsXMfePuKZi5unun1r4OeBlL+XvlPrjqItU5JFvHNFhkeOOWxS4Vt3T32sFHzU+WTAecyDiMbjM7jf7OofbduEBlm4IEpZg5XIJ2iALdgyKq7ydtm2/YTvUDtKndIOJp+0Ziy5uJLbIprFxJYbrPPbtvnaVrXbqvNQpcjrUcSoE+ShYtURatrKWtbFk0tso1Cj7Ki/Ogfz8S9lS+dxxGBw/6H4MpCqix3/XGJHzO51P6i2JOSVIo3kx114ahNgLdZCiKaTsepxN/qIqJDcNxG8Fy6KlROOUvw3DYPoeujNrn8/mwPaOPM/x4nKCfmL7zR7x4lg6rY7pGnxaLoYPWOm1Hh2VvGq6N8UPHG4u3wmCm8sNYtz1VbY9V21P+BG2ZbQOlWHi3eKWrxry+DrJ4LGXxrJNJWTwFqV5vmpvzufe5r7UO+Hzw0Q8+91kFUA0UnUI24ERD+KZsXxnbt1oqklbG7s17qvtaIe4wYUlYVEVecp2R31WuyF8alVLHWuS/LJ+9wJrMoh4ZVmqygOC1ArcVjRYMDi5CO93wtJNo4j0eicXLa77opKkEM/Sly/tK7tk4TLukYUYhzFYRlEHMs8S5kJoOIpxxIUCiiMHOdf8iFi/mcAmTn45N5b0OuS0c4dpnYopaWfgnCxCVLz2MUtYSXxPO80uslMGX/YPqo/+V/uAmZtuTA28OTa4Odtinwgjo763O8hq4eCaQx03INdJbMEKqRNgowo6SqQ1RpX+oUlOjoQKW0o1MQa1n6XjMBpMWvrSl30ohPNQ9eL44x28cYEJhodMs/TIV703aR220tjDcV0QXuYjDpEhG6YxeFA2HMqYLJhWDWEDuqJITbBcvkuo1QBcsuj6z1XPVAimurLC9pVM1nCK6DEbbIN47oXOVWAkU607E8k0CmxsWvsSFt4MYh9+LmrLQiIhppKP5/E8lKlqGotHYLNbcUjxqq+dV9SSPZYlwkst15PNbOz2vHm9SXS37hvyeWuHWv8vX6fft1DP+VsG4GsjoY7PSeOgaEg/3w6PHIAX8kaE08Cv+S3cKvC5ogXzFFOHm8878SoBrHUJVNm4JkmxoXnycDRdCkukA8yRcXcub4WNSseC2v9Gxf5Zmw/ysKw3LGLwkW8N7ze8C3hLxSIB0jxJKKWWNtQhThEk6zgsVWhOpS69HIyBUcsuPEHCMpRT5jX8lw2ShnDRBrj6yZfJrYWCSt6IFM/BNYN03toIx/jOFb0P4/yhMgom42XLm4SMn3RFG8MznEZf4GKnXrJHv0IvDciPyA7wrn8/TJXeN4S44/EemU2kHT9SNcKTBp6TcFXgncNmAZVSH5yQcQX9PurKbML0jipzmYR7ifE9CSpjd2JjCBzyAoIt+gFdzvIp0i9gNY7xKL8Lg574oOC1tkmynHoUTeHAkKpKQ/w7evijCmJASQU6iv3y4CpKLicbGgucUokr7fC5JcpN+37R+p/HM9sOvtMDJEIELO0mgyPQtUg9WMTl6jDXFMqxlzafl5u2bGDqeBb/1ETYrzHr3tu9sdhAVuftb3xY6wt/6AsEjMSrtFpabJwo3u9H9QkYURBsbPpI1HPIH0cda/WMXUWEbbyard3AyBm1YV3ZVRQIE+JYVUrMkLbJYBtqh3iu6Jt9mghEufVhnuttdVQ8vCiXnuGpSJQrdyMaxOrFyA8MKFJh0LjRUbha4/Ou+E05worQka4n4CMI1wipjhHluJOgjrgnPsvQHZYY/yMEl37rVMbPBOtE6EoQJgPMZI+xTx6eDihDdKRYpW+rayUKD9eDBd8//Fb1ISr/Ea1sSRq9QXmMBwPjs8YNHAmWRfMj88eHrRx8GHW7H9hMVbQRjJKjxDKvuLhaWb6sxuvG2dFHxHNzp2KGNhQUHVKBFh5A40KbqyuKmRQrZsGuHBZE8VSJ5qswfqW3yKMjoVDSYPDZ9d8B6JZwkV4IkddK1Sy5pi1Ifhb9isswNzv/5boiLC4HipSAe9C6tVTLHjSAct8iVpBfVqP4xttH4/+S6Vq8I8il8gn/ycA//lFcj+pdjKs8dkO4xQxLfn813Z3ZuJE6ucaPgjZkVFiAGl60Kps8ag+kTFUyffe9geqUWPEqHL1GU+M+H0WdOGH2iwuiz7x1G/+8f/YUB9M7ofQzlznQodxY8OKTILxXIra7wwcimqH7pZbLqnG3d6NZF9f9eivxvyez4D5Hkf0tSx4U0+ZIoMIjJ/H6JTAiTeq/87GJRrt8GXvwIOwHc9hZi1bxExiwDeuoiSBU+wr5qFo0NeHgSmJmXpRJbkX/HAp/OBq5WZwYH7FnhM1J0COWvjTkQW003LDgmJMN0sDKIfTNVUg+MrAyJU5h0I3yduqgBGMojBRE6uH6JPVU+8nZHF5GQM1KZ3gg8wX6LpazdoiugE3zFE42Zirvtg9g87LpyMNEI1jUx89uaBrS4cA23tjuiW19LeyXtQ7Y+NZ9Tr/RVf97E5CLaP6/duXLCcRLECx2UBUs46Ndv2dqxb9m1CTBx+YeFthFacLzGL2X4dNo+TLOhJ0thpgjzXPq+7+Iy4LS5L1GhkHv9YK2UHolqGfqRuv1FHw4PeCYOX/SDvX5YBt6LfogW8LW4B6950kc/sqnb3L1zh4LB5uGbvh/s0eApaTiz8Tc274fP6d8v6+vtzVv3v9yArxM0Tz8PvgCfkHO4hwopvDNe2IK3GfsxRRXJ2OkXkNadTvMtUmoWDS1WddnzXp7P59jxB+cwG0ei48GD8+DPc4x7qGu38kVr7oUG4Es1I95o7NXv052ez0fy1QMSZwZUTTRFbfYN1b/98zyMgpfnYW4UeLvAt/CpHlBh1MAaW9gmZmaYVqE0doblwuxRCBymXlE62rkblG7LLctj406FYd9YVP3OouGdn0ZYChI/HWIkfS2pDgNfl7/O3N13Ozq9sf6e4xFow/SeU2ts/qUaN0BVkiWmiiNr5JJixVVDNzo1A4Js8DaBwrnchx115NphmnCTynSzA1SAjiSrhgH2P1vS71PnftlzcX2xxFF9Pm4sRdi1ykrqrUa8EZ6haDURhC9Qi5SlSl6wEARVJJ2oRWkocepNUSXaNXIG+VkOcXyNBl95SSiz6uUEgZ3FaaLeb1Gge1G7zeCiWZ5B9d7tg4l9aduJDpWazPCNWQ0kdCbvMGFCDfAd06z+8lihzLw8VuleTzDA9l1GPqVattqS+7w/jy0h4dUxaBmvjhuqqXAZFJRGC7KmRxx5aBYoytg20Wn9mA8C9AxeYBJoomrgWy9A03mFpwJwv0M9K045tsxF38N+3LjRMeQSOCBf9MVxb3I4bQK2qgcltSIPZk/ekmDGpvdf8DD+0O9OR0LdQ4/yL33rNR/6BAykB4CC0KdJYN4jxLrM5YS/4CEPDcR23He9O7o+SCbzzdbX37KALnuJrRF96q6o9uGTmZb5oe9LkW00gt/Mzlr8WYhr5H7jLFnx2PDSjzkM/Rcd6gTdQF8XtDMZiXoWKncl4ZSUpCF3JWnKXUnsvnw6wVXuQLtOLx1kL3vylppOP1CwcsO8mq25pq2bysR1FntnAsYUl7ZPSxvszwyqsRUYvMuTFFDadi5mB2Vb6Z3v0/G4gRusrz/g92DEReN7trc6zde3oQMhCJwv+j6mhTdiourJgHtLNwe9FjE8JKmxttttSbGRITinr7q+WmJcKTBeILH1x0bN5+YTlvCnrQRjU6toVjlAVvxq6xxCb6qC4URnJzSh9xh4af9M35arQ6jzyG6OLuimBmEiSaJBaN2Rm0Mko2zd69SD76RHPTSc2dYhnJy1HoK+UylyVfiOdqJYgrlr0PldBGwNnPaMn4wWG7NcjCz9vizUcBxlw3FSSOzVxMZebSy3YYAwjc1MepqtbtUGieExdMdT8RWi2DZDdYgCSYzTARvkzTF9f6b56TvF4/+Yeu/6wbO+bxYOdxOgRmmWlseIPJDnDKNG6NdoQDtMWmVSrRoLn/jPTTWZROWK4OG8gsRME0Nq7BbzVTKilVeiK1ZvdlPt00w3NmRcdQJCBeJsFQfpR2DdJHSMw1xUW+uOtWgt6G9sG5Ewsm+EF/E4978CKx+7p7lywFun8qo7nQwr+9amw0S9gsP7ZMraL/3wP5i0BrInxoOxYEJrSoMMvPIS5gRQjUtWjcVhNCBGG6MsWMKaGXDuQa7ZTm5K71gK0vi64IKpVlDwDqhTPpdplwD8Omz00RgjhdjeVtVl60dX8GGZzu44TGyPVrLCo6WPfbRxrrMd1AbPL8PSCvEr28kpVVYsLb8+2402u+P7pdwHY7kPpmF5MP7YnRJmC5brCqcUE7EHHxeP1TS8Jq8294KkkPnuLNAqMUG/iYt+QCCeSltmL5wjmNRbJtuOhyd3qSKO4AyHsahccbgLrXF7fcF5rToCJv52RfUeD6P4c2mAmXsU+YuR+cP2cToEzW5X3bXsBwr24AnuxLj/4NBCz77vgr/CGo3D3/vBtw7spjBluwvqeIBqB29p2oMzO1S9VrQPL+/1zaDx8PfhEswijIK12I10XEWdryuQEGJgQ5ZYPZ9jaJFMYxUxAFVajZMBSM0xxkyJUp3lw/P96AhldE/c4B9sfgy8tRKm7uCH44/45zn9aav4w3dv92B0L47wIpxuD6qqSA+nFTSBkYfoMBr4HL4bOwVQ4eiL28dJNLRzrWEI7S/TpDjnSC7kmnhT6+eW6BMs16sh3EYyK3UIjpJphVmLVejUh0SczAHTxquJx1+DwTG67ILY5+DBDTiK8cp8PsDGSd+fwm6d3h/L3TqF3UoG4vHB9GNAoFnGQKk5DAQSDWkcJv4WDgYS8xYvwGy4LRTJWDYAH22YXLjQ8ISYC36GvthP0aWG5+IiL8u8SI/STD5Nl17TJbsN4weYFjgHMdoz8abBlrRIHS4Wjeuq10essJk5X9p1mZMqMlaIvgaDmKNN7EUSFy+9Tp/1M7pFv7Z86hcxHSLQxZiKwWBDXW+YU9wL8mmdIClnEa80PDQRoFLyQfndflhebWgAQWFvIPjvqaI9uPIYL9htqMtN5ABMFwRENXb42k8qhwz44j9CAo1SOnQRWWP5JC/QjGCbrAjeCyGChylH3bBE32ldH2xUG4Prq2TdGrNYmJy4Eg6sPTgp3ky8caD4smGQlqHz6qnPeGdWt8JzHTVk/L3MCNVzcW7W15/xYW1z8bKWiqzOQTh5y4ZwGfQ6YYjwElMZwovE0uQWKBiGVWPtLBmabXy/842iRKkmgISaS82CbVwjnvG2H7wl0Vb3Ar6Pr9SVRKWf+F+rRiChckTwuCvdHQsaR+KW/BWikj0wgTSkZI2qU9Zya2IRNuj9RTYrXiAMagO+dzKoVQQ3VFvSKHQ0A8WstJTmESEY3cmKbeI4iGCaG8TQZRJOPWJOBMiJQokYSki1GuGNaZVGYxzyd9N7mlIml08yqQP1xY7RF59dYsHd2Ikxe9wfIjk+3RdwLyiT/t4Pzyde5ZZ409MKN0xNEV9vjnJFSL8vezyduMLiCs/ZX31BU1vB57GAFWyIkxjzQGwrayz2214faPeoIoVdjS9ZXszOJaDfcYs+XF9/in15TtAb8LYSm46dcIaYJ9VtwXxZQyhD7MYfNGtSK5SYum8oEMYe3w1cqPfNqD64jpWelhVpWgu9pUu9ptPm/tqlAl7fsdfb251xuKTOJGikF/SJsy2RCkYY4TABquju9cMhqBq4hBP8+6IfgkQ9NRYOr9DPGJ0wxJTGNSyRjZkpIy7ReZlIh4QiHdQq8uy63sf2JypYlo5TEKiwfJvxff1fr0471pX5q9NgbWyeEFMM+eATFZrGcI1wil+B6mHQUxHWwYEhMKwseCN8/5caxUiMIhg8SkvYKRlWg/A5UARam/oBTsxbeDl5qMeXWXgRASyqhJlKt3ndoIiaDr1175/bJDubnUvq4ZKrPMVpridaDGsM/ilM2Pp6VHhDFQQ+lEHgKgS8xj6mJo996CTuPiXuZHMidLGYHo5LCjm4g+oin2dcbH8aFdERSs3k5Q0THVHjdHqxirjqkTWJ6ShpzhtxImuSS0bW1O/TdiiKrEmuGFnz2opXYAMdWgzXtzUU45d4Je6TRjvYWVTrNzfv3daLChfhwh0T5X0ZUgEG/S+N8BAd7H4eq8JEHPygqv+xwGaDg2HW0Ca5VzD/0ecsIjtKyMC0Nr1CVtcws+j/Y+/bu5tGkr7/30/hcFiv9KB4ksDArByND5hwmQkBkgAD2ZxYseRYIEtGlxiTeD/7W5fuVrcsJwFmL895n3NmiCW1Wn2prq6qrvrVSnPpx1gkOK2MpXxgEOMDRHWokKtjE/u38g7R7VcEDiMzubaazn9Q4Pl84L0jQQLRspyHohFr72BXX/v9QPj2fzqojqAq4LiNbrYtQ8662R3vLia/DI+yYxHbBz/vbB53+yPMRQG/t47ZzcI8MQ7ED6F3OrqXmJ9EEwQyv0in/hC4vHu04WwcO9M0QlVyh+y07pHgD/zneOFcBEKMcDccEC9B94c2U9bQgTPNwzJIxbfcgesiBMF6oQJj18+ytJxagzvRnYE9WCCMxJINz1s6Hq/1wQ2v6aMeL5oXc9AAzo3wXHnGPqAFsLKE6Hj4nxsnPK3CYdLbQHAHogUMh8AXP/bBASLPf0YxcyEg3ExNUlCuKetmQNsOk7ek7HeauPpOxdkoiWqV95nV7N7VE9W6crHVt0xqQeTR4mpoiLZliRDW+t5oor4VGF6FYApwHxEN6oWlrwzspb7aS32FcZBX8FUFtMW1/CWf3KTJEytRAX0EWlB4w1gA0KRO7viUY/ghHnhaMpt0b8NVKCA13AsD36DoWYRtUA8cV0gHDsx2ZLt65nlCt0BbVDy3InguyuD4VmaA3hoMfs1CJYZex11fyavRm3clr+b4K23vLFYccu0ZnJqOuDI+4or4iMs3fLJudpRVPxqypehqHg/t6cXs7jKEoIQEv5n3ivbJtPGLWw9c2O6fHKBkswfETd6n0ybw5bo1Sq5hs8VOAyoxgnwTPHZTA+679Kh2qFSrNPWaHW9N7+/UsMilqyxyKwZiNRtpKA1MImzy0AnJQ0dvesPLD+qzLEldlL1a3rxS3AR5LyF5LyN5L0J5TwNmfHWNJ/XeVZ7UT+I6pO9HXgx7fOz7hI996fR3KCMYQaOwsvYrQV83i2cUXvjQBRHMuBzJWBUpmny7is5S3Jy5NFRQWsE1NKlZHE2yHDJy6OtQqE3hGGRbrQKAVrv24+rLtNWnxcD87CbVSkq0lbRLdVYDoGFgCJPu22u+et+lOmpLjs/E9Q6vCsoovSo8g6zY86lV1gAkpMNm+WNN5bAaLg30wiYprUJj8uMVBqnl2Jr4W2Nr1Cdr1i2jb8PVITbL5frL5a7wR6/evyKMbEP7zHA53uSKAJMVkSWquh/zFIyII/nEkVLkSBpu1POat3fDho5QWu1/vjpwmjb1J0ub+krflV1jW2fc/X9PLvfwh3O5h9fmcpfp1NXpx5eIEE3l5UFEuAxVvgoxGqpty7YH0w1yRWb35oYRE8VksV8ikWdXtSLUW/E11mGVWZheMj51lwU9y++Bzn9/CyE/fr5v4/mbmWKFESsa8mdTUdUnGTgpCMteKTz6GgrAo6rRSnKOQHKuJXDBwfEFzA5h+umJHR81dPwj76N7vI8+4X30OXvnPT5vMst1S6SehpQpdQtTsdrClGLDhGG5MJ20iiu36XqK6o3toj4EmoWm3Z5k5O1aT3MTOR8IrtogBSdob23cA951iKk0dxrgDG70dQW8tLn1S2+86vtHxwjmdMN21hpqxvEyrCFtUlPvw0H3w4HXtLBWr6qrgKNqI/QBDfow/58PBA+qY5X8cC6L5EozB1oRBqRjrzZ1DL7VdnTVByWS7dUfrEjHSq5gbcn1rC1bwdoywWm/kJRdY7A2Bc3keXQuklIbZ3ujBuGGm2tfBEw35iSHhkVzZdUg5wS28oV/gpHq+p5I0cSNr17li06cazWxb7oBkLgz8pYZEDuwrBxg4GR1gIeRmplSuVuUuouzU6oSG9ulMFJA6aONYwn79kvP+kDGmhHChdIiQqwzPNvOtQ+sZAMj23Y/kI3J5XqW1ltQk+r+zAFQ29NoGWwORO5qfJax6nrUXPc/OGDXDNXWXdcUc6cGWRsj6DQHZQA5tNtVm0YrRCnazJypcez46rxnNM+1jOeX3qtz521VYG1tyWP6z5UxcISq3QteeXN5+YEgS7zlUQYRO+RToGg9pHNYPJmCGlYd0xYckI5Jja4aMU8bsdG1I/ZGv6o4LEjUo7oZ5Z7bvJGDvGna3mqqCwLtBgYhaFCMt4dWIIGTgdrgsqguV2zJUokxni3qYoMFo7724eBHxShbbinL05fI6UvoALogPCx1ROdcfZZYGGeJ5lF20XDY55OqlZKqlaOqNXQen3t6UjcDP5q1rqjd9v71VN8kVYsUKdXZ2TO9edKe1/PdtEm4TvUUcrV+ccUfWZTeY1H6CYvSJFGXIFF3I+rHnyHE+iwcfo8YXZsRR0i89pUMlAXNwsBbb2abo6t4HX7Qdkf1xV8roS9/aCCMmsYAVi9qYAX1vmmvruIHctnWXl0sT9QVFoiiZoFIaVnktCyGuCxiXBalli/QUMcagmZwMfy5WibrfHJN+NWaAK1RrQdh/8cIViDgDKi3qDTOZTIkqrb8+kj5yyTtGySNmTHqdcVI0rkkad8kaV+PCNtCAkkdggVyYmN70EOW/Dp1NL+1v+ItSRjGWwucRtDCC40VvDNgdc15fH2w0svgqQrHbbR+q8crcky/q14XQ/uazwqbl6UZaGkVQrEHPRUlgqLd/jrFA3hYnY/wxx8HzmrQcuG4ah6trmrPTb/bmPeMXQj+OOhe63hYff6PbzivNRFSrwMz7UH51wfO6wNv8/6DBw+2Nu9rn31NuKTqui5ucDYnOTAC4NTKGrGwnaYMNnYDqEpkZKJ4qYH8IxpqOGu98KeYCoUAuUkcebciRlvd1+j69xXgIloCdGGzq2cyvCg0cJFukHK0sLBm1aFFvKI7g8Khpd7X2vDZaIMRgKrOw+4zA71B1l4ZyXqUHDt8mtRFFE3nA6LrwxaPmKQ3cerLGqImYXBpwBaNzkY/31/JB35bnXzjN633JFokLFpkLFpENz4W/tn9LBxWhXmHON+OcV67bPRi+5JPdoLu5yVv3NVmB79uduA6nBvX8alexxbWcf2ZLO4zpmwhMogbaXGVW5vIXHsXUzgZ73n/BLnlPbX2Bxw9bR712lL7fL2L33VHrgWJF3jGgkeuIGNkWjbE/30rZtXK+GP1yvjjz1sZ9VVg88R3lwVggwK7DZS2iojqJPD+X0sCH7RT9yXs6wSxrzMQ7yKvcK44A+gqVOlrBg/l5WX1QeE8rFin2fVnUIj7f9UZlExpTEdPkV2X9g4iq/F94tBX0e3S2Ge1sVdKL+m7pPlmEjaqgmxWiM0CqlnkP+Bjx7AOG5/htPiYQldsk6lKjIuIXZRWGMrbF28PzIwDWlol+0LF4qf4TV8VgotUxyR5HVuwSfeX8Su0JOaWraNB3I5VmlTh8/D84GR/52H/8AT/39l7+3z/5d6Lnb3D7UE56K166HLqDgkYEl5efkVFgN3KJX9uSFEyLDPKVFuEnKkkTM6jLE3Qni9TscBbo+iszBhzQSRmaUHlVqfTsRGiVsvKWQq3YOtDO+ojDWT9dvs2JY0QTbvdXr/dZQbztXNYRzhBgTpDJ19s9dsxEM3nU4GHENp4VnTCHh4B+Xrnl5ckjh2EqMubjwgcBNjc59NqbUDFS9XGgaUfZBalRR141acsgYQ6Yt1u/3z3/i8PNv6+uWVfXj6VE/Z13P063t72Np016+u4fffvd0F03aB4k7G3dX9r8949oOi+F7IJHn6pahYKp+XkS0dMggFBo7nsQRVaMsmy8plb0xLQ1tNtohPAqJvpIjnd8l7AmsispSgvtDuNZlVx+I3ZrEYzzmZVaOgmma1LklmpaWmHs6WwujIPn1N0OpqkSRxpTcq84Cw/wDaCMg5bPHN5B6jpFBPjfpmRNdpCKpj2EbEBp+Osf3lJP/p9Snw/RJDg+BXD1DHQm2bGC7BhUEmOf2/DIHICw/chw3UaFMrfoS6cje0bmXtC73W73bdeI2Dxm+RTks6SgfNpRgA1oY25wWaSBAuvD/uKXq4G3dz3ExwOHgUDSNka/DUf2C0S5FsZgvllnL4oiGAsaenWC3dah2krTimrEOYsOvUDhLAhTm3ZLcSVQEy7KAhbWN5pjdI4TmecjalKPtTy81YQ5sMMVlOAkYMYBZ27P/1EsMkgAJ3/hGAAP0HVRHfrUbLODbyFblV11XPTfTmD1Wpd2fOg5N4lVeokgWRd5U6y8nI4xsZhbilo1oA/iv3ep1+tSViM00DFTZ7iiE6Bf7WqPIQjAQSOUD/0hc4tG03Q4rDsFYINFlIDvV2S64MkRSYcjwnHetEHFmQ7D5EsS7hRo7YwMHNY6osFKrKi/qXft5kMzdDPgyotgh/DOAZz7AlmTYBhwVBNqOE2q7uvjVTUoEuDDILhblLUiE4FFZ/0mXzP+kLu8k+7hyhgWZh5TcuY3YM9skzUZGF+LqCfyZS5gLjtDBgCKgiDgeOjtHLu8DbkDKZZNPGz+XqMHugosS9VZX3D2zoh9fsuttv5kXY/ZPfB72n0DV+tCabU2MyL1qHhd3/Nqq1Yq/kRrNlPNBinRt0//5r1avW7mxvaTbzUr9cDP/s0cAe0xAbIrNEXx1tLyBGhvbn1gDIJtmERfpmimWMXwa6QojcuL9+FHH3WO+WNxj1nkpUpIlMv6QYpki+6zKTAMx8D1WPdORfcoCR6hTfrQ0e80zlqDadeITJqkESGtOmgxUVsfDocEtSVlih1XgQZLrvIm81RfnPWDs8vL/1tLwLW+rTfe9q/0UwfhoiJIzjDgLL8PXPeOmpsmqb4unecEhgCZzOUg7OJsv7appHCB8dnyHsKwnQJlrcfDtPzMJuDPuufxmLs26ktElyJcCFPoa/y83UpONwViEkbvbySSXrql7vhkkaac5ouHsJ5ZsEYZtDOp/2q8Yj0QlnDMDdPimhP/S5ndMjUvKz2aekSohNtspmT21JaIfeWHIcFsyrisGBLhn0OFgx4NF4iwQwx9crqEbnEELc+/usDW1Xydubt9p3dPrS3silau30pPMKvzN3t6yEKUB7lFd/LFzQRa5uOT02y5Vx1mSAXcs7y/tUDZ8gVRO8bYrkvYDylYzQOq+C6qeC6ed9E6dhHsDkJwoG7OGbWuyqxO9VS9snmWbTvbf79HjqcrJG5F27c3/r75r2fQQDFO7bGMoO+yx06aewQKqwRsoXeM1B33UjWjOe1cIN6iv62uKft9GvYy8M+DPhSRFAsujzqu1fAlAhxiFH3MOU17cVlLhL2VBqM3N9eYkMiaArM6ru+s9/HNr3oO0/6zk5fZg6nf7CbVf4ufXDYOg6U8LV/521/nXjR5sZ2ypiCZledNyFc0gyvqZzh0PN05mHyUuQZaVk8I/xDb+fQ8g2sfGipamdRaykoX1laFDHye2orRg9JKve5mytfrnooIBQWbOjFaENT3vBLM8swn7Y4pRM4I2dqX4S1Prw8JB4wqbnvOmPP8k2XRd9hOzMyAmt8eTmhQHLgzZP25v0Hv/x8bwMPItRPGPEzTCE3j8N8HILI6FInCE7F3XCiyVm/+vloDroA/MwFwuT8+cQ/gztHx87Mj1AsfJJm4t7ahnbPTLPpwlovE64kcE+ShSNymTlPMRQJemA7qApOvDPoYN3vDro8Nh3vxu645hwvk4iY33XGCrhkwoAxd+44k86qZmJw68R7I3auCbSpI/EoGUFy4kxQO5vgHOhk7Pe+Mv268EByA7r/SNzHit9OrTOowJlUpwhAvr7TqD55E+tlDcgS6Y1P8RXxnDlnK3vTG7zjJwiSQjrFNAvPo7TMWw8pRhGlJ3dj+4xHpoe/5Oz3KpGwhQCvBwckoPNMg0BTfzpwq3fRD6r2PqgR9Cp/bsVHZOXUXVwTgrFTNuDYFvaJxUteSE1jwUtJS3Jeyvx4MtxZWQhJo6QVk7C0RXnmNsXfn23NQ+H+3V/uCV8UPaYl0T0f0YEyzcIKIdC2awHCSRUgfEcedCVH2bGD2Tox16fIekPpOc8xiSU5H6LR4/cTy0cxzRaGm7VNmZlTXi4o3lmeUtUP2rkDqmWJyrOGcTqKMxdV+kvOiqlcSDwzAXrtqEG7EcoGblDCKTFhqp6l/G56TMFCvqolgS+r6KjCe8risFO0vX/u9ekPMGI8hxI0JKQVlO+mUKMU6Lx/wtZKdpyZn01kIZsSY5PUTQsBz+fzbgX0WnQ3tqOudCO/u7n+ZIxBF6m3ub3tdzGHJWY+jaD2dCF8Fj6EHAuqEeAQTVjcsbqKiWgcgcUiuhHUHguz12sdG51sLZO+zdau12IAWUSFaydGq/ZvPmW1ZXOac/vU2wBV+TVPZnXkMB9aRs5MPn4QFb5miFMtRbYwcoUolcAo7s1x7EJNMHkj7kh+iEN9yre2Nn7ZuPvg3gNaPwXe1LIli4pJH1ulgyHzAoY2/DRwOhsbd/kf9WiAqkBN3XOatIjKZLFcWfXwptUptOXlyuSjm1b1HHb6hmrwdlMVrPcloIch55rNWacTpoeNbbZlgHx5W1hBYqAyYQ6xTzCICCQVEjirrHEZKnWR97SPNeJcrFnZtpfYKnKkaD+4C/LEg/s/3yWBrTco0IKoKbeGrgsrBF6pbLT8yqssxMU3wMDYrY3Nu1v3H9zbFM8o7VdWThHP65n0mIVq9ftCAexGvegmumZKewNqin6jXqk/XyyAxG/DyNjMRJ/2YYCElzsp6Bdw+QTHaGPbezVvt1/Nt/fmvb25+wrEPrz5FW5+lTe/oooMN7NeBnudBw12YYDh17N5D6dmy3bOM+sZlGIfCjc5FSuLH/YzWGLwMDu18cQvEnHsmTP0Hs2dGKp+O3dK7/kcBu9g7gT8q08EQQp6ho31vd05zMT+3Dk8Z0BuT1s1QCm95NeINq4IWuBFcCvv5b8mnB7Ndsk3qooh+FXkixp5cW+Qg5KYBJoFZABTm2DF3exmRh+opA8/w2FZROcgEwwImMFtDe4MYTNPaGJGjRN3szcXkehJ2ROWAvcqMpbdMBcbDHKAhJtOIljq+yG05BxUBBfq7Pv50Kfs9BybP3DJF7U34MuWNB+54sYApgkE5lTKogEb8o+gL9JeTLCbTnpso0pcK/WCjKiiiE/YISIDdEIZoCMnCEFajt2LIDwv0jTO3QuBtRmBWA7yADIY9xn/fYp4Fe5b4EZxmrn5YrFw5LTBGwinh7JoZxL6eZmFPHHaA5CzkGobilr4xNEfDOPQz17w09wqQfd/NYdds7PpANFuOPtzoFJeac/E/bdzWE3OV3G1xwxOHtAU2qYDa/KzWJPvYPm9m2+/mffezN13cxgduPkUbj6VN5+KhfoH3PxD3vzDXKiwIsRCvS0WKtpPYKne5qUKTJPWatUEWQZW7Bu1YgNYqbn3YQ7LdWP7NS7Y33l9wsdocX7GdfkbLuH3czacwtLU9yBenD4tTh8Xpw+3gI0QSUe4ODG98MZ20AtoCQe4hAPMOvxroANBWSNveNVidW64WIcrl1wO8nZ0xWK94ZsOs6LsGw3GkVju5vZztaV41TuOL0Y3blrxP2/71y/u8trFXcLKTa9e3Ony4vZ/YHHXONo3L/Vo5VKPrl7qESrJT+ewNHkh/47L/ba4eD2Hhej8Ia7e8BpHsb4SIGGdadIkLDRcdXc37tFiC0/J4HJK7+gSJrxlCJy4QO//cu/uz/fEMi2qN/GM1rC3kOL28pD0hLohxnl8iHFojP6yrKnrmmCzKs9GKOwl6PsbDkr4zrTvhQ6I295zPAKW5858EH4blBiQ+Cd951CIIjt9NJc+7nviUMB5STdAuEvRGOW96nt7fe9F3/vYhw/s9r3n4sV9Kvepr9SnWUZH+tNzNLaFd7fD9QC50FfQAIbQgnjeJ/TjgHKZHRSEW7/hBOceJqI/7QQR7H1ZIPr3jplJjt5JlWg/EqL9e27C184z7/cv8Ae03D73k+rlp2djbOB4LEQujN05BaUS/j49RXzgEFVfGIyTvk3pTd8Zd8/hLvzBB5OD3kHflWgVnjdITz+ijxpo8ipfGScC0XEreqd9d0zjXAjh+nVXIQpbML5539nJoT/vKExIThQGA8n4/XZ7H92Uqv5PS+VIUrkUKH8QWfnahmvd1o1Ft3vnX8RDfKLbl25fXmqODz2s4/yLC4q/+uak+iaMt/yYGHr1zd+/uJqLyFh/52H1zkPv9oHuSnJGZpSn/colAX6H2mGfHqGn39fG5AS/BcNZouEUdN/butH8drtdDZTCxLCA3NH1YM362G9v3r23tfngAR2YrVkv9BuXl9O+skbkpTXtq1NfLRtiaWbZ+ND9cOlFfYHQhqMHOzQOCArS0z6G2sOYk/mefFDGMv6lctdg/p/l3Y3ttJPDHRiYD3TmDOucOSIu+Y8MQPNOLEih9y4QdwpEgYf9ru+i+zDbemb45Um/fpCcg4o/9A778hh51hcHGkDxxE1SL+ibpwHaAbM8rKW/QO/VWOvJh+SxYuzNSBk0GdAhNluEFcBe+RgakALvqSWlkWcLWIezsoLFYs5tfijer6AQBeuorOhK9kOEuHEYx8Jk2GcU9Tt32PTxAeQuJPbIQfL1gbGqnk1FA24DG5vRjGhojdgQdiJ8rQwkB6X1WqMccfoq7IY63WRMN9EN6MZvphu/Tjf+Srp5xri5d970FQmR9afaE64hpCpvBhCTD8TkKCoa992GyUIb67hvnPhrxATf+IB+gvaF+Wq/VGmpgcaV1x0WW0O/oXabfvT7uGx5uJDUvvSlhwaMAdnaCxXApJE0lTTvntPdee3ul75LzetZDc2zXWtFf6EZRofn7J6RMmmIAXxthqmk3mvzeLZrpMJ94IoVjBSS9nanVgoKthHmweeNtZEUR8C5ClzCc145ma+9YWXDiT0J09qNJad/LfaR1x4ID6UVS6T71mltqa6GXqfkBLBpjtCJD+gqOjsTaQvUaRCelYKAc1WeghUDPTcJ63QlBZ6aBSXDg61E43g3S5AWhAE0K0+Tq9q75KzZ+wLfc5FR3JRZEUdCbpQRN4qAOyWKI/WWGBL0xXZTzbHwyxJTgj3vFL2I6rzpoGyOX6n8rlGe6hUeIasPyRvsE3zN2o3YG8687+wTlsxSalozAa1K09Dbwc+7r71CSwWotQgrn5WU6+f7K5w1dxGEcdO5XOGgtdvcOd0lflMsxg0QId/lFO9da4JA5BOOPrdNh7nNa17rsOMbudiPai//7JJZXmwYIfuBzlGG6lkZwV1kFfhu1pBxIZt7mZ4r1BWvPcUduwKWmg8ZTjP0Xnu76EyP81l4Jd3GC2lGSUhexdnXUv9pJy3yKKEwjxKEpCTPbuTh1EeUjSN697ZNEp4mMCe6wOwwS5LHeNUyQsvlmpFy4TWsmaJ787oKhXb54P4vPevp5SWO8rgPgjJI2Y/7dekZkR1Ao8KnjpUJd9bM410J/56Iv8B8yFtM8wzWI+gE6MNdLCP9bui0DfXfxyVNiO3ulAZM0Y5O0MKBy+iAfUGvon+H6J88sjQC1MLqHG2XgiUSD5FKThiRDWe/Ht/7lYspyRIGsVtl+dMO4zS8PliLsgz89ELB7FSBLp0vpOh/Cb9Gfa2jj4XgBF3kDpzXT54Ipll9SuZn9XAUHjhm68zFbl98ZSguZAlG+HC3OnWV0TaZkuySO7CUzPJOVgUkdOuVeQmfCajQGf3Mt3ILhzlDYB/tzBU4e1LLNw56TCGDRWWYYOUH8NoLq2EO4bu1eMEu7XeC7DWw8SudSpwJupWsMkhg0OJX3NX4U9kMvvWhT3MCev4oLvPxbnjmD+d9TBb1pRC6vkVmAHos6nyT5P4o3I1G4XAO0qtmE/hxt9ogwwCgkv335pkFfYLeyhOslp6k84KylhRNiFDfjhJVg4ny8ViIT8cm294UJqz0jo4VrY2BPY6rvKBjecJ/5mVH42Nxml9Kk5/wskMPOx6KgcTYPNOtFmfKanEGbc1z/wwkkkFeoF/2oHdAfy31yHblHfvYXkylEXFKRsRJgxGxZiLkw7tGYyK+UETTQ6ABN+4N1Bld6wlUSZZQ0SOUDUcwvLJXmp2yROOj3/NvbnysKh2gK0ijGdIsc4VBUisoHctpSsmTFWcUlJAYseCMQ6LkurNOgo8zzjoTOutElFwYF3hoHHYmcvDEoLFTqxyVawzfJa5nsl7HjUZu47kewKySOW4sBYRI5yZyipBO+rgeYR2Gk2kxV2EA1wv6JMRVW7Sx0kVoAdfB0Q3+BEMJQoptOKVkiX9a4iQVHvDa00RtWMToKhjNMFfvDATyeAZSRjnDo9WZN3EmM2/kjGfe575zNuO3PknuynwVeepEj7f51MB9baGRFR3KW3wpfHJohMkdeAYKWXzp7Z47f7C/SCyRPEbis0uQhKAyzLwZbXiZRxiNCLgkStMd5FFNQBroZGI6A2W2uj/SbvTIcs15SjmdNfmcqXuvsijNMAHNhvO6tHbGjqbYC7ny8BDamATpjPPG4lh6MJowD/DrPYgjj1Bvo/0Lhdibfg8EKXFIeCj8HaozrtPMGiISW05OtI8JeCv3NOa9efeXB7/YznK63ge/XF7m9kWOgW+gpIkEV0Pvt0ln6uA/3tsxDO0H58Ol5/dJ2J0q/ABYNtDM+QUanajskKrIF4ts5r3uQ0N6VnJ6CTSWCQE6mHkPQfl36p6N05nzqnSelM5e6TwvYYSch6XzsXReGN6rhDz1CkfvCf7zvDTC5B7KQD+5gwvZMpp10kTba2gtdjGUZre0WOzQaPkj1bIjhvggsyYyAq03nLkwxjtzmAie1N/6NN5QAlaKZid+oUIOk9N2yH66ojHZaRfuef8M1ZBoLkRrmjUYr9KZdlk7ZyUnYdQAdIejNd1cLmrQrhtOkLRq9DMjrKi6llUZdxqPlWR12oDukesXDleIYXTw60Pf+Rhb/gx4ECxkYEYzbRZfCa8veuN1n179wGbGEKYScU9nIO6mM6DKJQLvNqakRhoHfS4zaFyocUi2XUHnIuECWTYFrT/DPFBvDoBVPj3wfud0DagWVqms4eGzA5kU4cuhCEj5kFhLsCU54panQ+TiCE9JOOY5pcOFfu/7yRlpM5h8GzMMYZIhw7O33f4jsfJr8C5zdhmvXFZewzu25MXDDglDsF0PO7Dp4udQomRdH+am9EA6H6g2EV7PAPaZ3M475l3g3dqtnSTwXvjFuDOJEth/cxb0ZLaHyj4XeHk9jbHsgDPyAjwNFlo8OvBeXjIbxWaOyDNUfo/7M/XMuyiQwwdQRO9zWlfRAmdctU4OwcR2zngU1AD0xq5WDJ5Aoe7atAP1wUW7Pf71jJz0z+BNrFPk1jjx3sMYO2PbOedfZ0SGJ+02HidOOxnOLFnpEX/i8nLaAblsnGYiedQJOXRXt1+ORnlY0IOUfuIjIhvxwrl6ge6q8ueivJjtuReI/K1EWqDezDsccpkVFn/UkZ9AjD7OYvAwjqk4Ki3QX9hwMWCUa5hjMR4MixvhVN90Lap+p+GZY9QBrGFBKBDkLTD18u7Um2rpFLr2VHdx31QuAhehSAUzdeJwBH86+TBL43gXLkA0n6obh+l0YZNKItSGnEfKROkXNwkKYaObbwdSacml0hKGXnCUH3dDEBP509oXvRDpG7689BQ+jw+hRYsFpoVaOz10vhx6p4dCZVV7ps97ZkQsKQNpXB1GFcgVb/c1JvpE54q3a1zxjJaIUpEvhHwgItp30BPocN4lET/Z9oCgrOy0l53eRNhmsY5cReoeNI3C95XlFyYDF5ZAjYlTipVuc+qVP4GFE+duytRS8fCrpscbYuMnM0cTDpTBNmwWDWCawpk2j8/1eSyAxYmNUb8pj6J35t2d5ZkUtfN0Ftt0bHTj6UxML1Pksi3N58odEHtARacKjCAawBlNlBPhzWjhRz/WWv01GOM1HAWWqf9Amy6JFbBiZyhj0nb8hWQRIDlBaP6sq8gu8sqZ0wAHryO/dy1/yUomdIbMpE/fVvdH2g27B61KZq6QeUDtikTT9ktCetTjKUGCQpeY2UzYuSR6pV6G5ANWYK3f+8Ka5l9evqdo8NRLCjQSZbqZ3HkxVuaTF2MQhNnwRXgUGOynM0VKPctndFYVcKlAzjF2ausXebyQihOFt2OXz+dmY93a/2zsDr1D49YbvLVj3HqHt16Oa5HJWGrR1FjrI+gioIDmGrT03hjGfW+MFuyaUk/aMcIKFBmJGGyrMfKOJ0xjbuuv6QBN1As6qdazJsgzankc7SCciqPM9EJxqulLikHJAUU1uEEHwT2Kg2KipaCY0oswKCbwQEkpOwSCYHd38GdaZkOEUCxZzHIClLYF2yL1S+hiFAwTe6MZyHugX0k9WUPdkYp2WTkJlASxURlkeafe6AbbsWxiAE2MPGvDiY+CY9sqeTikEBlWkWKiUVZkd0F5uNtuo5UVD7eJWE3SdpL21v3Nv9+FGtL2va2elZ9ShkVo2XzWO5/dueNa57hA5qAvoLghL9QiKDFCcQeEFBlNorHd3VJHu/EuFD4F+V+54cJ5SdZGFD9BYH/F9ro57BS3ggikoeKWcwGipqsp+zVie5+WLZBhWv5wGOY5MjX5ZmuUpROy9VBR1AVabNtsISIaQ9gsE4ewAgnT4ZyRb1pxClJUhnfPI4wW86EEMFE8na5qPy2L1hBo+1Q2hwv6VWXoATYWRldaIWgqbEUFSPQjPPtdGAg6++L8AlQaxGIKgz5iK4mgosIWDAlPJbXHTrFW+QJq95niDvAExkjWUQUItYJZRaLBrJN/iqbVvoFpo2HftHZm+pJHZ15r8LBF5viDeTKU8B1s9I/ptL62A8H4kE0N+t2awfigyQXKMa4JDk+9PBbKiyiOMX4Qhh2t8whsMsUsoNk5v5TDx8dZmmB0YR5O/KSIhrnDprrW2GfAIuhR0xc6reej1hwoCVrtoAMLFvZpZamOWTZa/vxWPgwTaEIK9fjF35SVEF6gFI8IxNKhjAVijcM++RsIJKb1hExRWuIQJZ3gBMxUlJ2ufecz2AHEKWiCO06KSrz3ZszRg2/GvyY94PQJ7LWIpaSJaMgMiTNlpgTne/GsGysrntivU481v6W9kzxHrz5QEWZWGrOWgB1scVamXMyvPGhR+DVoMA0yRPo6JcpCuJ/NroRAgIZI61vOWBEkh4Hk0c+sHTS8ZaeaojtEWS0GTlyyvPZeyGvxtjf8FqyI0gxdfeXD3IJAJO4N6Izr5sL5D9S2GCoTICvySj7oklT9W4xJIjg0pnoUoMhMzx8hhuDIQXDdwHZAXsnQVW3YZT2egGFQy4cRC/A44vFcOYfisE23Me24FfSCG3nG78Oyi/DorcXgTvmADgFrXbvCTf7bKviSWfgUJH8gm4AwDFI8hVFRjV9mPTxDn816fdrHpKCX2S79BFJDmttcktVepXlxnby2qiDJSv8yOYkj8ishsYJKFDx8UsuCBt2cNCOAeohloAQYTedKHLHxaBv5W+W9WnjkCwGixFs6zS+8l7ll5It3ttAJZO5b8ne1qxDg1pZwtNMY4HMDNwynJBS+DXdt+jSlVaNlzpHBa2ZEsCx78bYU9kHdr0C6SSikTR3ed2RVrtnoSQPixmNgTOfiXPYJCBHE3XQCAAWQ38mMnIR9nHPT2oHqgvQMXvu9T4hgGWzAFyEPY0jDSI4En3IMv8tw4FCXx9/VwD3MrYTAOkJCLcvEIEJVyp1FC3iuERppgzDNYjMUJPWwKPCIjeWgoT8tEBZLnrO1pmPUE0IpqCBCmN/CQ1yEaaODM3kUB7Ik4ovly8djKdoCI/gubfdYdBiXUBH7JcAqVwdx7OE3STPcy4HqUzyAFU0pBAyY2DnWpZhLjXBa0D48e0uwz1GOX2yJpSCSLnf+8heWt8RBtfuXvyDUmQHD/KzmnM0B3CQ30V4oM3lfGI8IbzCRLtwCfLCbERJ0gUjQ7CIAy/UM76Cjrmb0VW841RvAjYlEMPW7hREWG05EyHGkXr6pwzFgWlBgXeS7m1ASdfRbzQjlpoLBv6Jvui8RzUpI8GZ6+PqlV49wb6MnlAplb3v/TECJQMiYjV8xPBUjtF8JS82Tufdlbi2HNNkYgNef225SHcJs/IoxcxjN/VS8/Xnl27/T2w4CZoJ2U3eYXDpmfthSPQDiYEWupegoTjmWUpE5AmA6JM2T9oCHiSSDomwzy/zplEHwJOwlENg7GHeJm4l0GxAdF/QxaHKufR+kY1+Do6vqQ5FT1Agkij9B5PR+bV38pdX66X9Ec1VjaxX+z09/Wdjdv0A5VG1QMUmo8WlZTKEf8PgvfLidkD8Ctw4k3r/hihN4nwQQGI7980igdcCizVozamkehthlKgICHzzotHZBMU940UJlKyABsX/r+IV8HUH61n0EbXYoXgLdzm+3E7L/IH6bCBQXEeNxnx4bQSjtNkos61/722/JL65C3+sJJCZ3DzH4MCCJilvwY2MZeu+dUKwKpUJ9DtHjPfQeZyJZbm3PKpb3rKeGX2gtdzeIroWZmAyYUjbHFWM773i9aijwhof/RhOm8l2JNnnXlcu42nKjegO6kf7xSPu44Vb6d9eopwbHbDzrnFAdzDauwHF6RZyjVQo4J+mo3ToFoQalN3Lqrrw4QDM+BdV73uAH3cyblsbusw6juHQGeW9r6+e/b22sTAEpeaJAao5IBgCq+Djp+l5yeekD/2XpYWurF61KceC325E6DxWf7O1YkfNbybmWouV2YegQ4sNDqc+lStuiV0Mlej6XkTV9Li3hrWFgl1Rw9oKUHloYToOC6h4eme4d2M4flEerIbkqPhS5djYYUAoEsI3KzQDqMqw67zXKX9voVth95CBpPTu/fHOOGxhGGAEX56zy0n1V90T9w4QIppVcLSmBj4OL9C4H5G3ynw1xJS4374m/PzMNeH0CXWX5WgXBDpzHM90h6THDsxYS06b7mDFaVVjLTO7P1lFxjCbA0FlthgLN928gNLH/FxAzS1oMWCosIohCpAG0EgeGFuB7BNgOq2YeFktSleTUUPYcNyfco9ZZxsflAk8yoUxXmKb0jq9ZRNBAkUVYWyqbg6xctabTepGSHQU+jf6PVC4XCgOpKCB64aK0dYTrD4LWUAZZji5aBr5G7aGQEDUaGbw22F+1nUudRoVDno8Zh9JKBBKx7TzUfRhuEz2tlAqunsKHiRqatPXX3BQHvnP/F4LvMjXk3ycCZEIcEWQh2ssV/68SAZw+baba3NH2eoH77osZklMSftGiA18oZ6CPMyjghe4L/MulYEt9Qraj5dCZPTRZ7rHJEsG93Vd441V1Q0P7DhSa9tpzaMKTmX3xHAuin3KVvgFYY+Z9nGlO3fQGvxhWLkco9tfPkCLCEWfb20ZltUIYelPEdnJ8uxLCYTOyNre3GQXq3tZlaN/ZtNc3Hb/tRe1/Wmn7nzn6CPuVu2dP+3256fo9/3LL3Vj4IikOIc2loEDiriP9UW9DFW9QuczIgbHnuxugm6xG1r68zMxQdYpgx3hZv33XJvxYrB8G3PwcHpThxAkfc1DWcZw3Nc4CSo59UffnywLdZopXFzDtMJd7ymQYwrDuzriPtwNkA1bo7c7sbgXBRkbERBo9zYmU84aNQ2kAG4xhjQSyavF96XJUkWOE+XfxSUQKXkWxCF4AXc8cpguQJmBYUCglRHPU6KKF8JkDIYdtv7CVIR3ixik7Yu3OvA0dODqoUk8ouHeTfKSWJ6+jZagxx18ClhWy9ibGhao8fkxzPrprAAWmztCLjtLj7hB6ur7Zs6ycJXg8hZW+nNhHLOT9Hlo5eqW5w20C2jRRhi89JFrQH3OO/pj2YVhvw/9vUOIOCSQnARIMryTBsJEEKfhCc+90BMheKCA/vxVDXuxElUyao/HFuakPaZdSByRyVaAEK2SVpL2ecGL1pdf0vA2VLAy/9mc2fZ5DEGSAsoo/w8Po6pBYngony6fCyfKpcLJ8KoylZOhW5oEYoNkg7AaWm3iwTWMgl6uhtvJ+jamVsfVNY1QsDaZTLK4ddvX6VuNcbGnwpxV7z0+99BQZ+RKHqS1GOe03dk1WZytJjf6QAJb8kfHsDbc6vSB+V35W1ZZ5t7tqBtTqAA6dfffyQI7GAbqEQ498ziHGgvyxTtjyRLE2Dui3UaMHl5OLVQCY1ahjb42ewRzkp05OMxEpZHENfVFJBPsoESgamI8NZR638YuGlVInvmWHcdxChD+48/FQL6Adc7F5AYu6QNezsZMEhtyCOUOwe7szT+39oVeeUhQAYRF6+2NnX+YG2R/jefsvv5Bn8f6YULKR1XuhJPbdmQZ+GBjn5xLwko3PFI0zn5ym8cC4d4qHvn4yEAmrqwcV5kjoWp9gwAe+ONBwzhLTuBEE9dyZmK0dlFigrUG7nXBed2EbgEeRRBmAFgPv/zw+vrwkUujwJ2yHhRx8H5SDbkpWF/gv1cr24OUC1YYJ4yXZboqW04cF6C6nJej/g+oZxntUNg4f2EcqPCfE2SEqb8MTS3ZR9ZUVXMopHEoHR4KFyp2Y7MegurhHF/JwnsFg5RPdEQHtwtJt9lVGdYSBIIU1jRSwIU+g3Y/9wgdFPkXN/UJsvAhZjPY7N3Q4U4WLNgb84XBzXX/RFS4SoywMv5INpMgJmFosORFOJObZr50/5J0pt+0xt5Swd360Sc6qJvl0SOUIXf/Qz9B5I1ocL3TzwSiQFhtlFeCSHgf1Fri81fnZ+Bwvl0oaUYjTQNrz0Kmxfa+S9zjdWtiQbi08So4R9J5lPhF2jY5nNFps9c86iiSgelknUjLXt46ikpd20/V1CZOSgdzjIGiCJCA8jjYbT1E4cFPWTUCHEabVi3L0gPHPfPb3TlEtBKapcCXkFgsjiMlSY9vdsYbOKHD4CsS8IRMDNjWFrqdVTGCKXacv36CJzr+ufboBYZen7VGVKaemkz8WiPiMowC6OLfpMN1Lk8dhHJ5hKBuhuslsNnjAfuuv+a2VgWIroracUGKbFkfvx8cEwaSOasRNaRBSsfR3Bicnp+XpaRwOuok42wM5+CygQ8gtkuITsioZJzITtQBUz9ttDM69ce99BLRr7LdS0alZfIz3vWOBLnIoLGeX3j3YIgI8ryRJQUNwCoQFby08ejs7hiWNf8iD7GzZAIRLFLOtqgCG4Ri905FPPZLmuMvLCQ4fHgHbDv/cIK4ivXFDE4k9dEMztqFbVMjQ2Bg0RMpGQX1LH8dPmZEzZ0EFRiCE6nyClkLD8zLykknN8xJ0x0lNeo68aLJAE3wlJWHNIS4GwXTWkhNoKo5LkZbDMcVJIGiYuoMBAvLGbByGuN9bEUFTZb3qTLEXIqkRVeyKpUsnyVDOXfHoQpz7ItMXTgLArhHh8dpKN1dXqtWk4W8ZEgULCxnrRUV70+Z8NFs2azi0k3Mev67M3WdoYl3JiIWROGUjMf65p1jxqkzGzIBRaOG5Eu/fs5ltypyA3dS0DAy9VGG2D/l7Q3qt3U5XfYq+IquD98UBPXUsNyxI8LTAbOZpraMYVcQfdvBrP/NH7/OfLfn3AR5N+7AVyUwmLX+BPLyK71iQ2UV8/zTRpV3hpo0UiUZaaMKR2hpzb3hOx9cMlpArj1M5JsMT2D5CdWTFa2TwKZyjd14+QJimPtbq6UkzZJkAM6C58qqcDtB5+URbVQMKFomgUOzx7wEMw8lyEdBwqMxpXGbLRTjAl57x1yhMXFzXyg7jaPiJ2p10QOosUtwKtsym++UXUYwug9NYv5ykGGtWdY2uaRFr19RZdUXN1y7PQ9nSIYMfAGcrsa1jo61B5p/JNsBPkOCMq0LVQtdfokK7BNavWoTX2jfxktmQvE5pas6MjxNvYt1TlKM7VSMq5qVdy3q9l3plreKcLRWJ+JvBX+/cKJLjrU9GEzjyR1TPF/x5rzTKMdeE2w/NqU6ncznMagKAeyGi8tCbG2XP0kI4lAieKYrHad78QN3UBkjc02hD3NFGSdypKELeqOZH3OH1smOOCKtocP9xbbLOYMbF+7wc1C3v48mCXd+F+OwE3lpJqitu1jzGbDvTBtl2Rl7Zyz0dezG/M+jLQci7BkQFup9OulOTpY69KcF9eGPtNHsMV8juxmsESYR/tu6Lvw9APFDb+0j9ssbel8SaOiO7Srgi4C7OA7g/5rQpgWD4GPkmOOHGdikkZIYeR63RAmHVkXl7EEpxlZpYLmzOFYXD9gDkA2CaxK9pqKqVLMZOn0iQsLVCMNe1MnDHGXLOjA8Y/hhTys4Y5V0W0UFn7qCHu4hARXMCbCAxyE/x0W/j40oqt3LYI2yqIuqwuQt3pV7kQkOjWhab3tCMBB2KHeQdvefy607es4ZN7SlSFQ9LgPHDHjRpaIv8PppzuQfK/NCmeFja2DAh2OVlyRNe0kTz3/vY8KHQ7F0rl2HymcgmRpET4xOgmUGavMCx3CW2BrQpb+wQG3SmYqwHnElUH+iG6bGp4h1R8St+olctblWVi7cHuHhysSZid0h7+sQb6neg5zFRWmmNnemdAXNiwo8HcothSEjHDeCnMcTexBEotTCsEVmmqJlc1QirYp7vDLmqUlY1gZ9mVQFUVWJbxzALOagevQka64fOaSDmq0I5+BJYKayI3ClJo6kmMjCLBPB6ieImJllzhbLZgw5ntqQcVDtRfN/zJyHGgsrfQDq76SzM+sCeKD220hIGLOEMomRaFhQ/Klw0Bqi1DGyGudlPFB7PHkdew6+nJ/aZ904kmDnzniUibvhtImwmemuctSGSu9GONfXdy0v+Lt6BLW746TT9ohqDNzM/iNJBDyakTKxMhqailsL5rvYT2z3z3pA8B+vZO0OjKzTzSQIDd0bTpaBMT9rtE8IqzeyFkKtO6gMpBS0lH2G/T2D1n5AAiqHpQVRgVAsOVZGVIdH0byfeifMeanP+OBEBb42SFDyFUr+d1LO56bLNhxM8HDW2U11UWZZ0lIiCb246txPKgxEZTahrZyiHfT7RMtg1i42qLtrIznGUX8FbKgefHC7yeOCgDyGIcMz2gGLe5CMOwBfzcdqtv0l9qL+zAzdXvlGKNA31lwSCu3xvMRfCNZPn25Pep4QOi2Dmmr4HKhjOrhwRNMrC7z6bZPdOGt7intld9LTcPcEXMDswnQsMPqWoiL8FZXSOlw3v9TA8YLkZ7fZb/Na5d4AQ464VnXiR4594A4qTQyCD6KQXnXDYnAs/NKgA5+0JH4aeeHM8bp3bzsb2SbUlz4m7nZ5Yc3TrXrEnz7U9+WRhO+e9eQdtmN65C616SErNebX9yIc2ygRQ4PlJ7yOPs/uC//KAU4Ogu49IXHpOjACbN6+ad0LN+3Ji1Yo5QsZi7rGy4Sdaw+fQ8BPVMidAjormFqLqKV6ZXjPnyorEokxlsg4re3VRs8UmmpljvnSOXFTim5Oh8BbWz8ZDcpIz3OcxXRhu4hHv3pEQ1yIhrvmVkBahkEaeytGacu0rk3wcjQqLukNOcI4oVxjlpDAnCtlahIA8zulWeaTEYcrRsQajLE1VoalhtyQWnZaFSoDf4YkXfIQ7Jn+Crq2g1PngQgNONYwccmB9r+hwckDaaEi9roD88FfWlUaLhLbIyjsPTbPGcKNWL2Um4eyMgoDgkDm3NReTkItJiKtJGHqxE/VAGIQxTtCPMJZjnOpzgbBQQ8T9iQiZrKGwnBBZkrwq5PCnYomwB4N50FJoRJ/qFH0gCHKaVE64at+nC2QcII/68lqJCEWVDI64jDr/fHcG7X93hsa/UBMqKNS4RFS5OOzV8pALtkVRm+hEhZnRa9hkWHenhclFInS8K3OZqpwwy/ws8+etGfqEDeRHBmh+zcMCnct4O6awCwxuNl3xMKBhUCYcEBsMyLBbYnRDQYpXUJXMO7fwxPXPbj0D/P1JrZNGdeBRZzDp7H+Cq+BxSP4qyRDB+ZIzB/YTdGYN92vlcjc7W3TLhE4HVKROlFdIhJeX40SmZy/qwg/a1Tt5OSVjVN98JnAikRTILRjY5Fpj/MCth9oAwDQOah8ZUGpKYffDx6K2QWviJ/4Zg8cJi/vzgiOKZ9JzM5/iPJxGcVRQFOlZ6Wc+VC88CBP4KocNp2gdASaQU7xzqbCl43lrkgbRKMIkllkrKKcxuY4GDV7WSAARtR2G1487t7TV19es3nS0Sgcfnyj25BP6xYp72VF4jKHgGkKydkq9tmaFtUPb82I9H0ObB+Rks/SMzFIrHrFG1fhMiFR6Ow7VYQS1yAyjxYODpUoo603FzsnhfR6HR4Nz0H7XCxUgzAWPnaJHIINuyGhG+buoGFuDk8OTgY6vqzbmovkIhPgQfmfQq7WJBnkwEFHdVAZBdJmXMipPcbRxjBU0thD5nyq8tbrwMPbzHJng0ebqykAIohFF/z1ui/ecxhUUxKMnSBHH3lL7dX7+WPDztU3y5aotqh2JjU4cSm4JuAQwfl45MzvS/bh1BsQ7GPkgGQ86/0j+kYiY7VKE8mN4aMR0DZSeYhAbBpjDDLX+miP0gHjcardbxCMXDsUo1572+GHLbSk2t1Ae0LcQgLuB6X5XX3zxJVjd9BpFRuAXJJvThvKlGEqNUnGO8qk/DN/sP4fxfX6Gy6R2c/esVzsdE9hUwk6zd2CZ77BUhYzXdq9806oKwjtRAgWfHb7YJTcudaUhVeqOLC/pwNOqnXYeUn5gga+AbwP3zD6V0xa5UGuDhXmcp9M0UykC/poLVsdFJmVO29wwDbMh04YvdzWWysWWB+QxpnB95zGhzu+G9MfS/WsE2m3oDgZ3QhvEm2kMI2X9MXMGfxlU1x/gWucBD835KjzioA4NAy4GDfcw0DE81YFjIhVWuZe4VaRqVjXM9jHeryC7DPGV0zSYszxkSEt4fDaA+2lCdgdlLNFqTMrJKdkqtXun0RnGquNXoP/qQ2vyQyAHYoX4zPBGNM9TYJEhoYD6i97/fGOArdDt0/7pc1hvX2QhuI7oulYuiKQRHAQOac9G9vUo/SKuZlFQjMXvcchZ5+Ycd2DWxTzYjWlMYOzFPiA+BIoYD/paBYpsX3Dr6KGqbcG1ZUP50Swc0as86sjNsQ4fxhaFfX5u1wMQEtoWoJIehiIYsph165ZNEQgVcAlKZX+FZSFZr1gBE18A1up++lgeDQQYO0j3Z+MUfQNANGn5ZyCztNDmSU+SsMD4D4LXGEVfKCLEaYXARKEA6EgoQIhoE4qNZGaAzv/ohADiB3FUFKKqKApieOiaZPaqM3C/s6P/hqYBrSQ2pVMgdD61wSVyynl2DX+8FSHiDV56mealh15QK7/yCRY3hf6eJez3muu7bZ2ehYebK2x5ylXOZZRylWgJ2wlPB71E/hQFew3gOkMKx4YdlYYPR7Z6gZUMGM1t0tJ+xVHe5jPTXzutN4IKfa0s/N3G93/tDGy3adzQdbwDagH7d3CTpQOaHO/PGMPxedYAqSAASHLYjaMRBhWKmloU/k2JDlFj8akPLGBz2Yi2mMpZONda3hHxO2JzyoUs7pdFiuhp6H4zx+UXgs6HIDUgEdGCyqIAFBwCg4mkIV704Hfswe836gG/+F3Nxh21EtKxaX488+c5oWt/wbSYHMikwvCFM/QARbzC04zfvLXQxAqq8b+FYvwatTAFKAKpExQSSQNBIcXoFnkVrCkPPfVb0QS4G9x5N+vxdsWNr4rwRDTUgW+sIkwUleSrT3EOn95oDm/he7e4czyR3Jyrp9LXBkbSYBKGQY6CCwwjIoUEyMyj4VgOcRVVFiXn6SdUAp8XV5AlfmGnvtrw5ovvXXFajTh7VV0/2PMfWn1Y3eH3rsDq5e/uwg+tROtdUzMfymao5Wa2WCwoH5HLWAsiSr/FdH4L5yZJWecYrP4IImtMBazZ932Eb9ByvNXRcX80qUcyk29iHyA+/ND+hJTRtNBxQ65ts4OP/rmfD7NoKqPd0erPEe9/eygIlHgzyi6GaUa6vAcaxhgZyrC4cIi3bDQUlUjJGDxqmOWoWBZ+LsO8OJClpToqqvzHPyiGM5sLux2Kf2RqBa09nWouuwrDjCoSyBZjCgzJtC+Dip1SM7E+rqjuRN75mz3QRKEVzudL8oVV6CZdofoMOPcwc1fM+UvIgvKhxk8GJsNqLMq8Rpbkq8aCvKIHBnOQBWE5yKJh9elwxWcn6pOT5s8V6lOF+RkKxFmSIf9N0mKa9NlnTRMNxQfXjGl8HNC7UF+akJubd5KYulKaHAhHrJvWtWtJvyIyEjdVhieL314fns0uVRngUXJGcfAHYfFcmid0wZiDXKpvCIXv8nLNGpycjItJjOeYmW0A3t0aIIPJO6vqV6YIwdqJRQwuuD631el0FgPlhH0e5dHKGGrtC+swq+tkYlnHamhPogjsKKHkM7Tj3OLUVl7W4Y85idbNqGbvNvvUV6wed1K2PmsmbTwAuLrX+HG/Jz4sjMa6iQiRl3SPAnlC4obqSAYdW5onXLsr1onhnVBSahusCH58by1XnxdIb0NRSGUjMh9LLyo6jDFu9dF9JJQ+klFFjGzVQNOBrtOBnPOE/F71u1+QKJ5pZoYbKqKSjTTxmybWwh9y2WBhcpmkkcvsHVivZ47+mpPYSz4i2tGJGMxpGMc0MJqryJlW4FwbRxySfdiOslzeQXB8BDjbF9hO+T5smFGmBpn8WrTaJHDow3g69jUmc1Ni6VliEBpYLNpNV3HorpjyEB1PsjU2yb2fHSUYpEB/l2WwW/vhMEQ4uqUTOiGM8pRWBhIyJgtzEImaBdptWZBSZUBMiUZkHw+Bc5BRvdPaYVsKCVLC0E6oqRFw1aFEB2Eqd5RBRRxmRpoxvt5Q4H6hn8UR1I2zhr43yFRYbCLgVAY74S9UjYQLrLxzCz0yxHKI43T2BCYL9ogwlLYOgjrRqONV7M8192nYF3J5CUTBoHQxeafrC7O6qhyhIyKbwLx8FQ3RR+J5In6YT/dh8osQm4CBspo1Zi8FbhCxIxDbCUlFUX7EqfSTStIXaVAqak3q76VT9dYUPpM/T2C5hYqB+MFLYN/q0lgJGa+bQLlMQ13qIvQn2qhERTg5wOdAqt+wNJaF58H1S8L0nJa2yoG7toG+Dc11rm2ukQPkv3n1DitiQuuqHLvoa8XLgMF+O09pt9eifM/fA57abm9uQ69/qJnQtgNqiLB0k6/bd1gsZZt6TR90r2qi3pppOmX3dZDTDOdzDISCe9rVORnY5Qs1mZX2lYeYGQAXwykWrbYbX9xvfCcb8nlB/R1xv+md/aYXVpY+GKezpdI53mwqfRgVDZUXdLexPOogS8VJMamVnsSP8C+XvY1lQdQ8xVvLJXd9lFeMkjHeWi55gOeDtaJ0ZlgvG8GK8JvdKKRlRQOguhXlwizGeRsjgsQCiTlEw0OEfBohpTC7H9NFtHRwRAIUpoaUQSaVbyEQvKYECJISep/726wieEPez2Av/q3BGHILjTi1WrjtrO6z8eH5Y3GesCPPH3J1+oimLLGXV8cPsLtlWhZlCibY2k5kEqfLy+Ro45iOoNC/U/x+iUdJR5v0m/w+xe+9gZ14Afs7qhMvcn+Gr8PIvpwlCmM/sa/lnUK7UhCzjzxEDFbZ1q4+ubzmdO3/NLL/Wo3sujPn7zxEvv6o+L/djvAnmkz+DB2zUXfUP3IT3qgxniYeYd+QRTCEGAV9JMLpKBWMyRNMChGPMb2b8JqSnsYIXJZ0chil0Npyop5kfesPXBFp6hReWMGEIPClHnNWgNqkXGZMA6SUWcwYZd9BqOVm2699IWuqyWsanirpMz3Ej6BbIIrBqOliUfVh/S5Sw1K8tM9IJDLyAxmso38gu1IEVjxeuDvXGPSeckQTrPkAw+nRTVKw6CA6N4RW/nl+piIhlR+FL/6qR1JriQy7RDQ5IxmPM0gJ4Y5E+QpTANF+8B+fQgN97GxiU7Rtjfh8W2KQJUf+scjRSNxRdMeXOw16XmS1YBS4eYD7fFQPUlHM7eqNSOfAxZ1bjJ5ABCk9Cwr/jBw/aUtJhCMCoXRqzDlBB1lYGoOreLNcg8JgjJl8EzYRLxZRZScXXcJU7/RLFnIyo4woIJ92TY6Apnd3UlgDGZpAcxQl56hjqmnKMZjci2S4HYPgcCgAJU9aPWuZLfMoJUcZzVppzlomZo2s/jA9peEGRHJuat4cKouZeb9uUIvNx8Jm5De+JAxzef1LNyMOrVf/TjoxoSXElGdOWVHL44IDLD7hX5+yRsdATRH6bZn7D/vBE8RChLOJJCFuLtOEkwE1+AL6sHHaI5vjZ4+iY4wc5PMNMeORmHE1IfnqCUnNh5VxOIMHtZ5HFDLJPX8lOl54PiY5dDRb8tpa5qgdQ+5me1genzA+hroslkZKedHRWKVyrNTthtHyYeVkV41WKkcrXR6t1Byt7KrRisyHFfnWx/gKQs6bRM6Vb7SCNGQk3In/KQSJFMG90WFDjsevKwk11abriZiu3YK0g6iuH6RT9lzCIR/ikH8ULzSPJ8U3w4gfDY+drDaeQ7lLEHHz8YD8/R0nBLVODSlCiztlKDiguqZnNzF4wJXACJBXcZrTI0PNHWXEL3l0WBVy9c1VZ3xREKbKHIpxqW6V8e7rTE95t2t9nWG6u9rHyHlm9UZu0GPhR2gRMzqllwhBI1AmRjLPK9kh+XTFR7j5tPAYtMBX9v7TChwjVj6XVUDomWLgk7DwlTADAyjl4KyyzM5UZRi3ikZPHq149RYXS2qLl6ktXvLb/a8VM+Jl0tWUgTIhxCMcipKHYmkcSjkOJY2DwssShoGS6hcyfGVEwBrzFTXmssZcjawSbfKquXra8mWsJpJys3+llMtClACBQi4vtsZUZipbFpucspKeptx7kZo7OZqSmLQ0GFObIux12WmqqEuIPMvizsq9YugFan6z5W9dXopxnkqERMpvKUIYRy2ytYj839nRiJqMjR/BTNVrG+E0TteEsTmoLZGR6ATLeogIEiAAGOFZ+d5U5x0sI5pFIrOIGgqzVGyWqouKZuHSLCxG0iyTNlb4tqloXm/hjYXK6X9cqBQ9EbSA+dWYEArQ0aWrpAJAIMwPcVMAICQdMSHcEzeR8ZgCcDtrqiWr15LVasmMWgq20r5BF74lrzgjUo9ABER0oxGmyF5tHJ9T3a4i5kRWR3Klp/A9NBZyeImqk/KLqiAhDjORF5whVvhmatGXY4T6Tzqtx+EQkwuchsUMbd0iBFNrSqseWMktltM/Evj8cTQKEeBXZhY1MjoIC6S7yoRZ1b5ehW0ObOcN4ZM7azDOMMzPvmWYWyvGWO/Kd4xyNbDo3iaH/H/r+D7j8X2JIm0qdLQStLVotYpGZpIpKGG5N9IUiyGZRpwG00m7PWw2lixvE5WONfWGq7cIv9oifLlFDO2FUiAzbJAPe0OE6KKkCGaNWqIvN4bhNXqiAPhhpjry/NX81yyam0Wr/pnFQKNVvRVPlGLpc+dA+QLVMQWNcgoNEJkx10CJXFsjYEyZZYK1x8IpekfH7mBA6IjqZkaQONX16BoVM+e51uc5YpGoUV5SGAlr2fJjObT5ytmvdqdG/Sav8JIXSv/NuE0EJOuzFps1qriRnGr/aiUXwSJ8baqjK1Reo+jULFrvzLUbbvQvV35Fe5UOHNFh2OI5UgNsr6vVXkr1qZQQoIajSQMFTGCYR6spYKJGfHKVGry22azdTuTsj3j2h2r2RzD7oGxPhc7dpJBDs7wpZjuXRDC9VjOXr/Dkag0cKY181Kinj67X00fQjamppJO5WtNFv03l1BXbb1I/DS34JrooQeUxKSAdjBvoYHw1HeBjMRLjak67StFVcxrznMYNcxrfZE6/Vf/Fz/63WFLjGo00a8MEOFZNxlnDZJyJkZIK8fJ8YAmhJp8JFbmakZJnBKej5OmAP8t1lDZDIE75j/zYVP2+vFSaOHfM0MEJC63qx0lDP06uJqqTiqhOakQVVF0IuAtBUxcCowv8nal0UhJVB3JWlM7/hILJ68heFFUsTjW1oGOJbJapZ3gI/gSuK1FHBNVr2EgEdHBRZQ26WDiJQmRgQ1qi29EEPBIfeaxEVKgAFQoQj0CjOgsLORa0vYEIJKmvpcWI7wZ6jsPagWxR+UbYTR4r7Idheqr4sIFNp0q8piJUAloi0sTRzpw7tNtVDiwwblCJPwFxyuHXvIuLiZ+BqL6PkdZuC72CsOI7rb+Fk78tFoyDwwL4bwd/4OJTia9AqvAyD+Ql7SywsCmP48qzwALPAtPaGMC18m1ut1MJouF3KIb85cgarK8PbE7jtB9aKUIZZXe86I5/Z+AO7mBwe2p3oI8TBDDTKlX+DCnnD3pCR+TQnHo9Cgng8MwZrN/eHNgmlKB6voPPJzk0p+nTP1ZZemcw/TKAQR10MYHm5aXQl5egT5gmOJI/I0H2EyXWkTgFGO+ZIX56oTId0DF+F0Z11owJoi2e/ZpjEDm4iBSe6CxYbw7d8wxtRZrfxeKuEIeEO60UAMSGyju/2KkFHYhlvZBeKtnaVV+4UY01yW5E7o8Ft54cW8Qn+5wAgAQ9NSpff2BULr6p0VXq8zXVJBqFb6plqbNXd+/Rf2rS/4xpbpzY5IYT+/a/idz1TkjfXfvfsBI05+WlVXHl6D37/41ZUOAMjQt35MrReaMdb0hpJEJpxFfZ41MYIRUzgZkjN7r5tsTf6+YgnEid+yg/phhLczO5wjKwfMhQqWq6vVwAabnySsKdymsdiV4ifqkrxgZTl4w3XX9F3qU3zZH1KcGK6py9WBbXh6vP8oZCsIhJkcVDjVjzy1z2iIPyghjiJUe4oRNXTpFrG+gy1lnlwlfXgSt9SateOFwqMSfWJRKgl+otxG3SQFVjtCXKVBD/JUFtZnNWKoRIzup9J/biXiwcV4U7YIVBacUe4WLFttPH0U+p30sdZz9kXzKVoe2QPN0wRulolINETrQmj9rp1qGKzeHr3XBkFninYQ7xnWcCeUh4xfcb495SWLK6gyZd8zhU7a0t17pb+sM8j84S1o/TFob/rHM8vCBZDgKDWYVp4vDvJF1Ppy7Fid1yhvVB0PCaVBuEdoU20xMdw4lHXntFzEFVZWVOFujQwPJODkUyGzyEFT8neArbW9lpY/pEI4a1icfUUir71XXH90M2cigTdPNqj9VqHy6tdkQ9/dbVHq9a7cOG1T686Wof/mtWux5zOTTWd7UL/IfYAqYWGNbYwlCxhSGzBaQUYfCPYK496eWfLuwraH6feYOk8CGfy5jFK7AyWbqCK2t8oc6DYsGDGmZOO63QSveR3iqftuYXaUYa34InTa9owcXVUsebnGlHVaBuNVWyAihNb0e6pIDSS6L+1Kx1JZramjUUIbMER4SwdohrzAXETfF58YS/Ugdai/8PaO2/CGgtRqFJzf0zXk9x8zK6CuBsicZi5eI/NOFdKsqs76zxEl5JtSwYEtWpbmC5ECpFL5b6fQEJUr8tgEAQX6R60FRHw/vq3WqwRN6y4vCqPtESq7pfW2tyvOv5N5pGXwMdEK8Zcf6N7yyF+z+S7JUfhPLBCr6p4QLIN+ke7UcrXqpjB/zpeAGPribS/wtR/w+EqH/9BkJeFW3uuxe5F3Y5eiH1YifwItQI1eIqbUqMarAZutdojxh+mz1C5mvSjSoInDyUmZyUcWK4dtXnrjRxmSYKElw9EpFyMtaopFENxosh5gnmYneqNvUxMQXKBYG9qC/9GwXKy0RBoaPG3Pn3DHiDucYcfjZpDe3Ly81f/6RZuM6KVvsmGdPMgb/ByKvY/7eCZeL4441VwimBA7y9kqt9kfqslHi/rAts3Ss2CxWpv2/sFypQ/4o3Zbx+7U0Zrr/6zf2G1657h2P3zXc4dH/1OyKC33xJBPBf8Rb5vNZeojD+5ndkNL96QwXzryrPMf16eQ7pX1VeRPbrL4jA/sY3BHjNsAKviQV4Tfx/4DXN4DUxSGFfVy2uWtx/XMX9x1rcf6zF/cda3H9cxf3D1hUkrGytbTrfaG7J6+YWq/TqW2npfT1rigD4enZUytDcUoXJ4i/UxVMkCo2fayJtDrKsT84VwPwDD03XQ2dcWAFbY0ozrBbull5gtokii1OY3kGv7NAPtzQ3i8B2Plk5sEiovGQWmvdyt+QzaJN15zfYQGUCWH0LXWqWCGbecH62aURID10f8KAM/CyCC8XGc8wWKJMt8x/KvydsWbl41E3JBhQ7rIMvFtJNYGPb7+Cm2m5fY4NqtykxBZKf85LUZEwWlluRXaWM2OCQ6qg6gHgngOylt4WkT06FvSF9KtjNorWpfCmAYPnWln7rzqA1uFPQvyGQ7pIHhhq59U278zGNEmvgtPBw29HeC6szae3Q+WmjU4gSFRm9U4m6yr5buYCJoCc9wkNzDRO5RDZqTV7b1Jrwe2DpoBWwRAj+AcgSiXIHpPwozB/NGWxX10jlOUXobTgF/J94V71rgYgsXMjsa3xRKFsXeaGAwnAAVALcIeowskqRZgRnmcOdoGRSIWkXhMF2G4YzFScoKbQIC4lcNeFOEqDTw2bjd4f83dgbcoqUw2hCaaviX3ORoorF66HZrABuGM3qltSGgG21Q+Pj6R2v/B9ruJ33Nl0rX4/tn6zhOsJpoka8vp45xR3vl/+x/DspPKk699NmeNd2wjt3nM2N7ZBbQ9lb8Uo63fwUQrH7cnEl/nl0hk1CdppwYkLKi9v0oEOaBFCLoyWQEAZcuxe6P1eU8llPh3FdQvvqtd8aaLy1eyaXz/khL7nn6s78sL7ETg41gn0vFrdIinZyqIRZ6ZmJUVJm7bx1XPkBlaQE+BruPcKqAuJiwoxn0Ds5dMOqHX9op5xy5L3PmHmonnTEdpKj38fHXgZ/P8PfwtlDAApKF1YWeDicVNV+qDK+hRRhoiZmTcseFYrUGFzK2PJEhl5SdEXBaIKZRyb+VCVEnobDMiYCy6BcPtDyDtW4kT/l1ExIi+Fw4hs8SX9YwQ03PPyyfuW7X9aX3kY5YPmDdLe5bHV3s7Ox6sHmqgdbqx7cXfXg3qoHPxsPlhsag2y5fLdhhMR9vbuKgUvWXhHO63q2HT2Zipj3JBUVaWnJ5AGNnpys6WEdJcd4KOBytIcrDkV0c/fKQkogW1lCwQKZqQxv42bGm5IAIycEaJUrixIiiqitaTqlHIWDHibem8Gat2aHINRhZD3+ItlwbVPzawhH19YONR0e9vgjrtm24hvehv3noPAnU3cdSLaqIhkRKw1pg0qBdagMXfYFOyKHeiqrbFSDUpEcUuQVWBYbZPROLcAj6ahDFxxBsjRateDrMyyWZ0MEfckw0Tb860rQD4Jugp/QdE/e053vfByb6jIdVaxVi5V1CFDHy6qCOQ2IwGjSej5UPed9ik75PI3LxiOZdS0EUqIQKJQ4w+DhKYxrXxB2P01GwKMKnjcD0Kcrzo7Y64LzBebI67Ukmdb3rrGedZNWoZKyA/uIRgSmIvs3iV2HKEetLBxh2IcvtMBQh3oTaQD5MGjA29d+mhaM08XXr2AL8WPSOymJgKoAgddhYvPWLdmTWy2knZYwlws/2iqXYJXvwW+BQjJiEP4kbcn3O62XqBfPIjRaFf/4GzRxAhymBDYgoudkSa0uVIQ7f7MX6Au7mrGImfnfOb4renXr3z7CqMqptVSOdLmQDjdDPxhUBYIR70wSYIoG2tIzxY1ECasuVnYwY5cbqoTnWDudrS+liOOC9spPTMUnRNJg0kGCVKodnQQI9iA6xewBuLTNpmLyX8wxorXtF3a+QDUE9GQHkwakh8Aa4G90SM8wj9ZGvdOgxp5MoF0yqCFbX1e2WXzXF3Xk4u9Q/I3F3+zQBq2lq79SHtrnU6s+HIH4IYRQ23hlBC3EyADzFZw1B6pKOBqCkwAnnVGU5bw2un5XOrT7+oBh7KKaoa5/dBuZJNl+D/r7z18dDuTV4fvdHXmx+3zvd5AB0G08XjaQkO9BPg7DguK19SH0MeA+FZYG7E0AW3fDCCBB2AuYoQUnRoZu0dBXJDExSCLshhVJZMskkejTv9krenDnBCQIaGXwOMrxxMgT7uWdgK+d2jUZfkABdq36g6WqLi8HCInV6AEvErQly8jnooDtGo29i1uR3lx03vKSamd0tN94oOLq1+Zr2C7C7sqaVkOmrwalom0IJTqUxI5bpH/IWaRz8Xco/iKlg7oLE5epiaumbEy8hiYO5LTq/hndV7lQlc6EAHTS8KebL3rGE2sg5mHg8Aw5QmXyEQLSrc9f9dkT/qwxelqyc62xuhw5F3RXeMXR2eExYgOq0JC6sVK1zO4VshkkWDphjYSKGk5yoUHn9wYDF913Cxm0oWUYV8y56oSmvX8ZmTFFoc4PRLO7bEAy1ke7DaTbTydTdOM5wIbC0lNtxabF6fDTwL7YsUBsKmzgCqQpq82WGrWcqAuTxvi4W5OdHI01sMVtv43C2aGKW/q15cMmmQQYgS9GrBXRWa7aVLf/mv8qI/GjAsTeEWH4ai9Q+4zy6BKC8flRId1p8CipBQN6dhZyiiWyvB/4Iz+L5DbqUyZQPAvARraqVgqQgfxTNJ2GAe/QfpUJuYW+Gy3qeOcvMlYfvpB3ZuHpJ2hDmp39hOc9J3CzMzyLelHgbf194+9bd8nVDjjq0I9D3TJQNN21F1X6VCwh8qNqaXK0GZdBj55+k83SWBLTDIu1jhTTLXQeWul07BeNueHXGu8BK6ZPVPe6eKnVpYsfByM9zszrHxx0QL32p0hwlMK3cAfZ+uDOaZH6SIMyDOkn76cz1BrUQjo3iIikjcJJNJGxqVgfPe48Ti1RJ3g0/OgkzzQ4EA0lG2k/jqCL+xjfRhNUJU22eRva7CrvUBZVUG6JtmXJbiRtmL6H4XldtKxTLtF2G3/ycSdwa+CoGe1bVsUkNd6hfbgn2rnOK9QVKxVd8ihk7jCdegMYzwTmJwhgMuCGevgoBc1yYj7ne7ZLrESbuL7kPBXXZoYo0q+bgKlLjHF5uohHLt9e8e5y6uhesSqHNnHcbiOJJDW2mzSw3USyXecbe9VnD+albtH9G/RrKN8/WvHoWO4ljVT9TV0Ll0ldkBDn76ReV4UkxXhYEQyLkpk0oeia7yc4nKIaRxTuUV31cVGUS2OprlwYF75YL+DZsUHj13+9WPklJnntY3xD+94plziur5zrdvECxRExcomRz16xQWWMTuo6gXB5hql2oNSwcEPHP0U6mqY87+SiegpbLjAxysuuPxhFX8Jg4AzjCAaug39e+cV4zRNSERZHT9FRnM7WKJg4j05jvj+K4iLMjKITP/909Y3TNAvCbN8PojLHBxsYJop06m5se6gZ4oAhm4OLjNkc7nvTbeg4e12H8m4cjgp1m8IeND50qOuvOIzImB+hAAHMq2LQQOJNHD7U5mCHapKC0opaYC/DKKjHL1/QddH5cmcrvAe8fy7+Evt2CsG7bcENG77drdqMBjK9JY9H6pBEO9dRltfQVkejFH7EZkFhVSQwA3VYsiPBk0wZq4U2yqCFgthpyD7FfmuPD5jIMlf4GmwS5jtklCM0bxgF4SlxCawsEbYTlsg6rYMSk4QKx4m/5RgPksbnhHtEkhh8dWc0wkPh6jMoUnGh03kL1CNKLzgO+d1SCl7w5q4/x87y+wPngjrhhgsB4vgQyK82FAUz7VUjgp7J/imneEfvi7khJp6GaqDQbYMAIFLy/qjLhXF0mvl4ctpKGe+fXbGTgPH0EUsfO5qVCbkv00yQ37NPp+7s+VwSyAsUpxGFsTstYQ2ug3i6JCzDcAxTWGtRAmJnw0g8Z5DYAzSWiwEhC8kkzHNoGbIG6kJhDoUUbGWvpUWCMhScRnFE7io+e52MReJT0P30eg+wDpzB89oHrq+UU3IMUxCiv7dyvI9aYAtdFRjcC9N61KpZQQGykhRRCGkAuWEDeWpLpwMKxUGt3JeGNa1ux0G2C3+Ys1UvfaKXcOaX0doVOKmz4rlCMq3qezjS41srvC8J/1iYZroC9gNjq+kW2ZyKjryAj9RNorMuONrS1WyrzDYDY5fCvTxRvAL1hOqqU82Yk8J76B+R48eKMu9mloQEP2IQdpwpHAjYwUAcgUEObMd8R5bgcKa8My3zsSWLoPfv3EY/pVyIyk4orf8qYBPl2DKfIsDS/Dk6ZuRO6W04I5DYR9tDKbGPpMQ+9YYCknJt2kGsNXQw4kcTb7py+6Cz/4m2/U3k7jeh3a8wN78Jb36Ftvexp9Idb39qTW2n/PX9oX0hu+WlQvOb0i4Fgs0kAjXx06iDsUJQ3nbE0EzRCEyNke9Kyo7hXtqTd39Ne4N3PswTrDTEQcHxJG7GQwQKRv2peUsUQ3wH0ZpOhvrbkbyCjcbKQbTWmltZEdRS0k7NQufFob2wj0F0HYeJFaFzkZX0tPoOwqKA3cs6QvNnEqHxyymObbcQr/gI/YzOtijSqwWtymqFfAsUbNyCczcBhhrIcwdzPXijLlMEUKuobcQ0x1Vpy6RyuwmWmANaC5OIc7fk1kVenhZZGLprGwscvY1usS3dkLqFpMLEC4+KYwcNniHthQhv0pnmYRmkot5uhTmGVnBazyIfhuvW9AqMXJoygZBSnGGjfg/nhASNh4aVaTkSXmJOTj6Y0L5h5ZszlO3jGGcHXftIMKLGKOczG6H4pWkbUctK9CmUyGAUVQ0vsiTl+NVrvvaav/Qa+/q1xBcddSnqiYUbUJpNPCmwttuqlHq4yAnoToEc+dpvK0MDZDUwCTr7Lcl4mUy+W5sRXITUNqgxurzMRcvQrCpB2jeOZRkvcmQBz0ec36OkckZrLrTUOFjrKVKyvrBW0bKHwGfWqqec3gH3h9B7LEyjipe220O0EcA6wrzSF8DFHVxiKXpywueBjEfVIhOlmhfHRjfcnkpiCoGYpkfhcYcxy63V6/AGbceWOEDJ2JjF0AcpWrIY2dxSNJk9ItWm+lGafXEbPqEQES9YcV7jiEJ0Hp9m3vJCWx/cCe8MLPIwtDWj8wtNfrhA4R6UvLMsLacuMkhow4CuSCAg78FXfpSpZ3RnfQq3qEAaB+oR/KZ7cK3uwV8SHLT0LZUkcgLUc4adeRKdhpkXij6lpxSWlOUeX4e6NJLXHDpejZacrEpUfZbFGOEisKa5SzxZ9XJTgp2G958bolgNvSk00Js4JIUyJ4UoH2J0ux9TECGSHJQnfeKAbtu9CxHNA7q8+OWga3d0jnfEr4XubLZbO2MlU8cAeKYKxg4NQ8HQG9yxwt5gE/bSjYHtihvya+qBhn+kDRaJ95V/rdjg1je7mbeLkDrdyhyJxsiwwRgZojGSwpCEv02BZ32xGG2P0nnt4mNGj8xfZm/yUGRXQrOtRK9pRQv5dQ2VaGS6OqHVGjjIffJypCl2plMqomP9mC8VvEmF5pS/vb5m6gzOsTjUz63C7oEafxqXyADQfcg47Xl2fZUgPfOi4OboUCo3eblMVr3+ThmF9g65vxdyUT4XpAnsQa5IF/Z+eReEFefV4eWl9eoQd+fJVGezeG+zy4x277C7d4hyS3VGdJWg0U1kXzOt3WiZ4Q8jk9c68LSyY1DfYezvS4sx6A90NiAqrxm7hJMF6mzA7xOByokvCHiBnAcPR6WDvohzZAFLNnmbTyyrwTbKL9vwpVFGJ6rfNW1Kro+0sCISIcM2tqnz+GX/zYudvcOTVy8Pnh8+f7l30n+5d/jw+d7O45NH78Xx6tqab/su7XJdX2yZfPjmi8F5gAByTKA+CLIUMVoQxdp45C+zSrX8he/h0Ts5IcD9TeU8vLhBmw74mzKgTbyKbtvGHDgop/mXl/SnvsPJ23hM3xWd8r0CkYvx5KbWvzXuIdz7GfkI/7xb/dx6QHC9zGVUv9e43/6Kfvtav32liq/q+6v9nf7O4+d7T3uWVdBUtNtr8IuGwSYb9wRznPnONGQwOmLSUHTTtQ6AWGAZBRjKkKADw+HEOZxIpDvZVxvzP7grW/Dk5e7uy3fNLchUC7IrWzDCFmSiBTsTb1UjdPr9bPpJfNdCCxk4stGsKtwhOYfhYWoZ13/cYfOtU/SM++/vkLHXXbrJivG6uK/pwhpb+a3GVsXqfs+3jR3hvea8BBLhE8E+815PgVnVHxG2k/65P0zfo7rMQ94ldWvCNXidDWn5InYXjxBYyx+ChCyfOM8RnqxpowXupiw5vKDo+KSS0ZzKmxHU2zTb8TEXhtwJkkrihuY6LA3ATrMsDuwdojwAi7i+/awJXiW/iJ/D66h6HiJpQwUwBMeg3yzUB9ChXts5F2oCtaH/8K8Y+ib58T8y+vJoqpOlafGCT4WUi2nvnTwXcBNDRljYSyQrhdslUhZhb8aYvjaOOTRHABzAgqx0mifIBjEm4/ge9L+umhIZcFArI3yS9qrjCQ2E59nOw8fi56OXj98PXGgSslUMpqjFfgoXNC7MHmg1+B7yRKNUotf6otkKg6LuIKipQLdHJvxd13Bq3OwqYmJHQ9lL88O4LuqQd4SNSZ4I8h08Fnu+9+rNIRmlC6YjiX8goq6Vf+FaZksvDeH0rbvDy5cuPgG1ot7oCPSQrrDW0E398HowuMM3ySRTrwjrNr3XuDrc9G1l9tZy6sorcspGH8J6XA8Dk7PPthFlSZAKiBwmu6x86rtaMBxJLPU2wYRTLldzmrHt5hcoGHKahUOEucAYNhY3ML4sxqE3ayVsEZxCGBb8Lc905ZU3GIiYRbphL9cAu1mepxlGVciK6NZLuqXPgvGgoSaO7hZ10IX5Nt1qHjcBAEVUes1wNL8vglYaRx6xjGyHjG/QMAwZMJoFN5o6Q5gzoi9Eb0ZX4M6fOJaw7fjLlMCYKCh53ZwKlzC7yTHSR59VnStWGKG8cPWDoioIZWq4OxEAhlawW+M4uK90EVHOMu5t4jDdjItATxMKNLuivUYLls+0ClbGL5bb9ssPt634wbYlU/O8DShb+F+ri+GhFlPTWDzWi6NHa11IJls+naBC88dafdH0CtmaNwjVCjvssFlyPyyyOeyckl9ymTXhNl7/mI2nRhV8uacHDaGVslGcGTx++ULI77t8bIYZm0G8Xz4/bCrpmE3N9FifqfQo7QqbWhf1eX3ylGwhqaIraH2TEdPuigUm7v6iPOrI+7gQfvSFmJhCzGch/OkJJ1z8nYq/k0OzylTcjw6N49qG89p0KuM1jV3e9Jlt3uOdBEFxMxMKl4XorEGGxiRF3eToSQBiNHltHHt+AzSu2ssGPUI5d33OQybaTjKjWzjIqfBMatEU0PtLT5FddtjjVwaIL3YeFfOBePdisXDFowNx7Kk/0hyKtYCt6ZKXktwcGQngKDk8/n/svet220ayMPo/TwFheTzkGKIlO5NJqCBeMiXZSnxRJPqqeBMgCZGwSIAGQEq0pb2+f+cdznm770lO3brRDUKynDizZ/beiUV0V99v1dXV1VUPGqYwMopwRmxRraFUvUf4NSKxoKcYNi+hRPpa2HMwU3LipnS/ybqKtlZH8/tyfWKvbMkzisqDj8LglTorCGmrqJN+n1whBU/z886dy0pN67eEiW4UbMmLOJ3nf7BhYeXVSfU1SlbT4MhuYCoNiY2GVGpX35g5NaY3bZjyCMM64EkdcKa2Go3fAc2hmXXacytYGVXzLdQ7bRJe1hoTlNl3vqmqplvBgax7ku0yew15InlxgUcWdTkLK6NIcblwYLM1wItrrKy+71rdNWoQs1mU6kLjSeSUemW7a/JrTZ/B9UAeRdN8MDqemYxKZeDs9u0MxfGzFp7H8yLN9pOTFPlL9NjdU8czfI/LxKK/ep21FlmWcgJ5I0eWPVh/zY+Y/ictcN+46masifJK0Tl0BxneGEeO6i4HEChJR6EYDr7LO0FmU0tkyhLU0OZwj7I8fiVj1u6TLMv8YqUyErVB4nMD1jfJcj2lJUCoRo5iRizNxUQvSmclIsBAOnZQhqsVNCsUMj2UU31G768+11HQTxCtrp8Q/vU6B3P7r+gRZAfrHkHPDXoEo9X1CL0A+2o9grn9k3tEnRus9osQ5BGknERFmihOGrVjQFKX8pgkKW1QAdrhV6UxtxX17ZCcWmnXUr9f4WekgcnSGM2sy8G15Pjn8bvbt3Pkt2h2hno7YpMjW6tveJwwi5wp9HbBBi6Rj/qX3LDOSdZ3QkftFzRKYzVKyG5y5gmlx/rvU6OwsVgAqxMnPa9TtHUJjU4ovVWAlpskQaSS+iKvfvnK5jNzw4Cm6PeSQT0JY9LYPU+gpsN4QEpBYRiWecs5mEShEsGU+oROTmOmb4WxAHpYhKWKOq8kYsW21DzpGyjac4C8muPbp2Rp9UvOkqS6P7h/WoEX4//Ny4o2D0bSBu4xFp2t2K8ybOGA9F3+E2Yd2eaE2VSOylasqOHmyptHvGdoxMcb75pbpVKViroV472eJj81r9cway383RXd65lpsFIMfGVsOyzqYicnN3hvbug+9/nVUZoMJvHgFHXYkH4eDWAxk7CwCJvFrPoQz+gg/RyoGdV2UEEdVMlxqU4u+rHkKCrwVTomsXU9GSLtKgJLItqCoCi1bx6CNrWGossvVhvU10PFpNirLpaXlRbEfFP5vBrAXXxLuBX7xPM7zqKJ75KcjPvumFhv4IvRF3jGqw6dTSO+4wfHBr8I4ycUv+k97pIVrRjNSIEb73hiPIkAOQWnDs/gHLUTDwtrF3C4a32YRxnMCZbjgRR+qR3CzyqagphT2UT1QIXHHpS4mWOj0LQhrNgWSdEP1ft2y4TVuYGluTtgIRXj1mCe4UO65gMY8ZhPRCR1Gtsbq6s0dOEQu7Sw9S6rNtFrFm5VcZBhR5J5kG2TEWMyGNUkUZcZJWPRXzUwkAgPVd9ywImlM2swGKnSCd6st8Yp1BbxMQnS5XDKJvFIJFgzGMDMl5MrV8GQe8BVPUBc2t7wSMaAT5BegSJxDexbyKGpDr4ozneD1BU+NF00rPCcr2igEVDXMXjwK9svzPr6PsBn+9gHES3dFLohrl7ZX1zEEM3sG67dtU38JGLT7f0unP8j9Ik2QC+kXotQGWwD7xDs1XA2IytsD8JWbwa1SfWtnx96KUt4tCRv/0n34mEXdZD7L7vSCi+ERCEvwEAKDrww16NKq5B7xl6fJp8XmlZEoywulm0UQxG3N4UdPQQIfSknVFIquaHTy1ChdRZlBylgbUxsAy49qCi3PoQ5swtrz8PLd2lYE+/Z4Wil2JS8FBM/+OYbx1l3gjtHM1jfdwLw3WEfTF2x9burluWPOKV+or0VH7WQTL0yXk4esfBejiRv0uVEajmkqZyIVroN8Ry+vvCIKgkMJj8ZZ8mZKopz06r4tghcwGF6svQc0nOORBwRu8VZ6gzjE+gaekjNNTYoKqGOhDrP8dVzPoEGAS1HVpZK8Gm0bLl3Ek0gp/Q8Gfpw7Y/04dV9g32HXVvtzbI1p3FCFgK4Vf/OfWkgZUvVmIOKIujOw0tYdVPtzllYlj1XTR0XpaljRNg7NBKruJqKvgZZc9X+dGxde+5C2kc2SCDGKRkMAx5Aic6Fg+AwHtJ84V2z7Qjp0eIx/swR62hWXqqjMs2ARjfYsjfHiHeOcvMr7tzxEqBaHEXrYAQoNGi2e2PFYuJrTiQ5KrEbkp/Ik+Jv0A7UeyVqV3DHLLpJWZfqNap7sS5AUVscZaVCfENq1kglaKhMb1Yn2vUqlarbJo2qGcFUwdK/Uk3zitOsrJHFJ6qyWeTNKl6mgOpfBlq9LUwz4+zxjOTvI6Xt9ifUpEY1aLVg+kBlAufuT4b0d8e4ngpUl+7iZoltM14Lm/FKWrnEhUAw0+x9ZyTqmndfh41Pl7CffXIrd8Fu22ybVzp5bZmvZW2mAp4vbPLAqJjs7lCrMJdqUg0LrKGIRuD9QXEcjd5BHQ2yQduPJt40llJPdFNSlHUt4CCGyX100PHXHxb8/IlF5WwCPVEEelRHoG9lLak7yjZe+TrPYNYqlq5qwgW0Ad/vXP1y79rEh12zz3fMcT/GW3djfphj/dyMyHj3mLaBdzAtjIeH1m10i7AiLJKipOQqRg/4kv6TSf7z+W5l8Cn0mGYXTuT/lJomesnDwG8ZFl4do9AMhyQD1L/F5yCarImarJiBq+jC1flr0tlCQuKwr8xkhZozv3qxcHERVZXAauvFXDGYQJmnDx9Nb3uGtlvNgknYuGyQcWBiirwdr5L90Sp9jaYFUf6i7CSLrL7wH3bNckKsH2rY2sr8Lm3ScEYQgjtGiYj3WNEYRWZu0mhZWpTnlmgO09QbEP1+/aM9vMBJ1SqEw4Neh8UldV2o1h5af65pEPRmeF1vhrWUTkhkCUmeYKurnQkrIsTDSsPIKMamQW/AqRqolMTorBA7C2A885reU+43tg1b7TcvXsVKUrmmlACtjo1W1+Ca2GpiLI+3ieSxTt61xI2w964gcBRj4DpKh1f2Z8gdRsFaVMw6/jYqI3kbjnsQab9L/Vg27aoRX1k/eoGWaY0XzqucQCBvrRHfBhrgqr2xgjTeeQa2MsAwfPiakjfvB9lxVj68Y6QCZ2I4b29speWNf6pu/HM/O07pEU1Ot7NA0dp0RtEM/dx6xhiL5FAIR+pSexI2H4iJhxHqs8bjqHUxjbfqic2WS2h2oYaTalJT75MpEvp+pqSkjZP1gwd+YZ20o8oRmSLYIFRGhdwiCiKX8bTtKxaiD/oUrH3GQzZzZ3vU9U1VrxnhrafhDEYXgsSzFetDh0gyQiCcZWL7LKOTlkcU2saIuxhpcaWMLu8z4SAwSzhhIXrBEahZn29ckBfCciNJjdxIIk+x1hqimjFE9rhohCaMgo8mauQiq8KvGA3lTcjUyovDfZhwT0alRkgrB9ToFgRbqR/dSeUlPj0FbqTNrfyBPCEPm21uYOodh++alzXX2Qd6GGoRp+BBa5YmJAEkTMcHK3QF3Wz+5IhcJC1DYyLvVdjOa4l17d3Smlyh6/cTsuPFyiFL0yULFHlooTQgUvFr5huZtcwMUpIvJNJG7FLWAS1VFw8TCeKR4eIApcq7Yr5GtNLqWye6YkrnBalMQQbAFI06as0ZbJWGtN8lTqDqxhyKlgnI56MRdATfhhbhyOkDXZuMcmKKSFI2bKZ136EczCwK6c70bIyGb9Ql7POnLWefr7zOGA407VAZ2dGGaog1wBsKNYMvN5jDUq2q1mjrOUVm6H5BozbhiK9nMaHcoEMxcnPM93z6TrflekQwrOrCv4qlvbZRFZjVyp1LhL1Wp/sZqTcroJQQBur79u16hcPl0FKJ140usrRQSc9pkp6RZSAYP4PDRdefzjyJYZHQEZwYQ9L/pLWHBgCjDaNSN6EqF/o1VzeXMAgLrEO4yuhyQpwo+n6QT/8cQteDwzTiC8KBqF7mqDTKHJck2HI2doTmoJOlXKVT/ZATqnoiY7aYU92z8cTMFW45zrO0kJtJSo8dYzcJWXKkYyhj6ZRwuEA0MHROgEibZ5J4muYF3wgrNdDDGPVqoeqfjqQ3dRAZZTgrk1EV6LDWPLsffVfINjdgXiKf7UmmQEZPE2kxWWI8iaPMDVp/VZoc7ZmqryL0TIT++tIZShq/EhT6ZBfRknISvOaCo7jyHoPzljObzhGIJNIORxYjtxL/+J2nysV3MbSTuAEDApdUNRtQ1lgE4HBNP6WRQG2FEhP5r/D6OIDORaLtjp9YKhFpsgZt4dsGXlgJx1l9J24HNGXvxJ4KXVnBIr1ikddXTFge4r/kNHWduz8pFaGry4smI+kJj5PBZA4r1flLjld1kUNWQEXWQAhmmkAsLDEG54RlV9ggGG0CMattRymEMEHdU8Q1LtnkKh9WtHQCxzdEAJnh6mhJi0E6ZCzDDdeLhfEKVMFEK4Sry4LUDpGpGuGVJG4KKPHA+VXR0yCuyUfUo9PYrPSdsaP8JfcYq5BadHOrqaZq/dVjo1SXmanm/3esoQef27yZx/95BB/ylUOJHdS22IW9sEQpKs5dVDxv4uFUdlkpz8JbND+r+ycgMRcPD2qZltigWZ31wRWtognNabBEychRWgLyq5vNzaIhYgkqzMP/BAvlUjSlUVYCKVsTF2U78M2c0Ri6JAF8atEpTCG00IIxo1HNx0Jm+KcVpox+UGoiOVIUqZBNjTmf27ezm/XYKo64+/v3fmOLkulRt93crO9aBvvduhaSN9wV+2Mbl9X3QdhhxF40dgny198m6TC5U/LWotrN6OJirUCGjrEWwbdmbDr0nu5BTdIHnxsQrv2/1SRufw7ZqDZ9fk7xOyj/E5qLvAyEjkzSZJ3tUNLzLkFAuyy5VnCVkC3ENyIchzYjNoM5DU9lr2H5SCpC2h393la71VavjKQqhQxUf0kfmOuKdJXayJY6yL35Cqqn1LTJJmWUZzqbkHnaz+GM6499XNWb1Av1+6zqtNifrVqbQiNA+PqXlphS7E0eslegFlmpCFwICTrYhh+XxvXDE/uZlXr3ZZmFaEQVhuHHLj7v2zdeVx0a2UB00nR1cbG5sdH8G94zkloA5RcMMYwW8SA6iM+jySEqUjOs8lSD2pvNv7XuGRbyPkqnlEawokFFlo4E/aCjOvqmRGn+owZByMMlkGGknI/ulCoaBZl2LYiR/GrGt1LE3OaiGqKgjvifhu4b+6otuYoDy/XOWOjFpFjWNqFnp6js6ikGNSRKs0WwKEdmd3IF/1aKrN4IiYhaZ4asL5LdQjr/6guMT4WPckKeIf9XWhIztgZs/0qPq4upyH9hdlrZV15Sw1VOVi5GtrTqkKLKjEKTMt0ZXu5ceWUS3uh+5CtdjJiVvxQN6zTSeSmCaIOFM6k14jNY2JQwGYlRzL0kd5p1w/6xZNuX/Z7Y/X7VNWhy7T1nYkk7vqxgILPO+ACTisYXSrdvP8KoVoSmt/GjRLm4QKdakg9M9QrMAqy3t0bPiawi60qJWvOEV/CwlKLVoC3DLWpYUMud90v3TtHckmoRPrh9+02X29IAx+a9v/8N7bb+7eduU07L11TyjHVp7qUZoxA0tWx1z5c25AtaYqC0n950H/x9o/2h27xTlG8czGTmRfZKfoNJFGaqiTC9LT/aFq689Htcvsu0m6pGGgGA2Fb7p7k6uM2aLjFe3/6OMTZUfM0aojCP6rm+7kHV0W/q8dJxVO1roz3SFyTWsmYN/7oWa8byV+vzrb7FwCse0TTyywzZoG/FFCIsYBaLMTeWX2ZaP9da3QWeel/4tmtIniZNdd+GsNddeZ2c6Cq8VYKTialqLrrqeu7ml3Ghv7EV/qifE4TqkiT14+Pw3VYjtQyNkWKQi4u0cjdCOx9pEgiQ3II+CQQP4k1GzVUdSr9mfkrMAo71uouXRLF5q5nyPdF1ShaI68R3KBcXGWmtMHOMaROj25RYlD2r4c00+qUZg1pqrsDAWX2gYGBUHHXN1WK8crUY+SsW3ehqMfJWkkbW1WLdLa+xaD7MVhVU81UutRuVoW2qLpALG7y+UUooUe13B7X0sA5KEZBnz4zvIZQ1QFmzlCtjm8fENPOfd6UAmAD9cHBKryYIgl1g5yV3Q7pCpYcUkh6oaNNpXBgFqqwPsjjF20m0tI3w6HwWs3loRIC5/3PUWN+UIYd2hPhGZ/gkTCLRsQmIYDLhN9rDDjMeOYCG9RAoxwUsrB3hUBgJqSALchZmU8OLHWkXxaVYMOkFhmzY1aSLTGzAhtSfVTu8IHlbCuCrT0Z+mrN9AARjfO5nDE+TF8kgnAMxzwfmWIE7BjBUQGkvtpVDUpkUqD1zyNOiHAMDajUAFfySjgV/ILNDq2bFyZ4bWcSJovFLXbJ5iW+pFNb5ydYIdsT2t4yBDVuX8qfRNI0/RkPuqSwvtZFZna6Cse5QGjHPAQne3/ypINWMkehq5sTNLdbJOoz68xE+A6F1mzwIxsthJjYrG82gbZiwbJjKZ3+e1euN94bGSRHL0us3VRG8HAWCXy480qQa4mnkwn+8uHixAPiF/wrQ3ahxn19dKTG8SK/cEF8aKI2QuMr9PmriPY/5EGUObSHQUHchD+MnebbWhrrnO5G0GKUgBpgOX/OMQpSNMiQS3ljHVLStdLhApQOHC0P5m9UntFU+HevzytMxzMgj1Bc2n0SkKBc71Xp9hS/Q66M13o/xIVqT1RBjVZ7B8bbxbEwKtW3mgFjWgO0mowMLW9+wLiLkCWXb+Usa0Pkx9t/gAczLjNttEm4tAXE7q2K52BtB+8ZjTWeshbuolnK3tlb8VDMqxukwt+yWzpBpZJgEFpF55BfRSG8py2vIwYCFibeA5QtPFtjP+U5CicXzJSMg1fSMXo6eQLoBWnLIlp624yZZqQzipMx1J5bl1vrmm1LUPzPbgBX9S94KvE5jPEYZiBcJsolQGxfswouQX3LNwiUd4fScSy7xeKj1k7Mqi9ALV2wJhzZDtMLQ048aiGsf4g0L6Z0LJ06gNpPACbMRM7L4pUioexm6BOYHykcg1QH4aNjGxrgwbXEOSAZ+iJIoyxB1AtBry7KS3RjlYpGF1OJeAewgsivZXL3O7IfiMtX0lXQkkgzWyjS0g0etoV6YFePLKPYDKwXx3Jbh9rF2QPgnPxYPEljDhhY7KVKK9qhgrToUKDoJMBS7lUcK1ra6eZ+UEpH7/qYi/ncySPfdPzY3vv/+u2+bW4WuPXQBoOcyyKMqaK9Rt2h6o5KiOVLU8KVXj9wPVHphmqEue16abBRUTEuh4fHY0Io0rT4l/NjqbsEf8/NZsOjnaWtG+jHQ4b8ce3GZSuu0oLDQw6SxUXD25QU8/qICjKjYkaNdVU44RQ3WYkWAZlBPPent7SIHYoAps/J8N5/Syy3Oq5nBPpPOUO4kZDskjTKmpPSK29/evr2++WN3F/b+YXRONl1E51Fc6rXlRuZKE7BWwCp3TKTblu+YnPusRM3Y5GD/ks3PXi0tc/NSp5vHEeRmkmH8AnCNLBSzdFZIJy2bWLvw73lVihJgW6lUfuBv/vjj/c31vTGJddlE3fHmuwugjdLb/n8OLiOy29t4e7sRdy7CTpNUfHcAYzzu+EfjRvPOi45XDBsbqL4a5mdpWd65v0mMb2fzfjvHyR1695pebk7u3CPYANXu/zqjCJfcWzjSXqjZXZVxxoBYqX3yw8u4zHR1jFmir2c9/ra0PoZTS0P7Ak0keKmtnCZVy7q3K6dy1AMdlfYP1MIuIjkqqx23GYmmLKXGCxWFwvRQGns27wvuTCKieNZs1cxo25jYI6YVaMQjlKZ/8yQi3aFn4U3moJbCFfT1wEpvHs/EzKJRLiLPiJSds5yekhCEDmShSEO1FHVuRWKrT6fLIh2NUDCLQHzkUh58cK/daa4jMS0DE3muIbOlcs7VbUw4PzdzGPYnljcLR7CaDB+ZTtF+lCghJ6n0iRPTl+oyWFWnctPVmfhOo+UQSQvtQ2GPvPTOVf7TFAWnyqjk16Fw9igi7Z7rPiCzw+JMUQIjs7pOYEa2AtEZ4/Cz1SwFiPJINSWPotNItSSf9+Hkq664zNEq0vlgbJVLkLJbyWv26yKdAHVjlWt5WD81zBgLiqO9b/Q00XxyVDMyN8BlFQwgU41KrQZNPrQLoKbLCXSP4ecI5gAbgScwu3M4Z0V2RUsw82SMOaMUe4T52EoyA7q5KKvFHWB5pImyuF6Ot/SMtaYy1N70n8eF4Z1E4SIy/HjGNucbXuKa/nKGs7eMLvPISCCQMokClIlgbgH+Ua0ibeDmDDEyOxtHejJR0WbDCGA2RUoy4whIYkmnPZZOE8twQVswUWeMqntpCzsbV3rY6Y4ryZ3dMW93OzrkhYQ815BX46pG0Rfjy1WIofVuyqRuBTlehXaWvDttlbtw7fhL+/ursasDWo73+Wrk1aE0R/toV6ugbgl8f9g004/SQqMn0qstuQA2Xwno1OZm9NRkah/WjettkdVu8dts4o+iIj889H8SC5bP4YThDdMpBZLpYSC80X20BBQ73ZvADtAG4qHMAc54bOGpo/bBvH0cv7v0CuPk55OFdAN0a8Y3wMhgbVULuECumB+1qvl6JX1TaLKU9JGsb5IFbuQDxbZB0/m0RiFcUZ0+0kkwbaD7lrtemcRTUgzG/JHYfYrdr41tzB+JfU6xz2tjWxNIKavWo6tummAiIW889CAfcPMbrYsLJsN0pmWuNdPKsHOhs/c6Rr6da/OtkaIYTstH30gJyqAx6Vc54NKjCktfPb+aJb1b9ORBiEC0L0vP63W8qKUnqF94cUEPlpmlbN25TVGRedN+MCtEqBCLBRCLXz1rusP4EorSKjXRdGVyPV2pyr60Uls05El57tZRbLp4bXPL1MFUXWRbG6VpdjVweDIwsUZTEe3cg8i6MEK3ygdG9KgE+XUkC8FCG3hwif1s6+2oNJlms9Q0D0g6khSQIS2HfDJCFsL3wdSiz4elgUt1daS+jizoVt7wKb1mJ/EkIlHhPJ+jzjrv7chHqWfuD7LgjSxJahEewt6O/D9UXVHD8bWrXB40tLYL0mlXxbWeNWXwZQicYcbxCV7lapnGUgfpVL8txPmE01ubUTAUdSLrZbGLt/HLXV3cCWJQvE6UTbjp9a3APgX2VeC5FXhOgecqENCcusqdTZuIqQyvofVzqm6NyzaSJZ1GdaF4i92Li8aCGLlHU7xRJrUdvVwY0x3hEDbMwGdpNg0n6grLm06bJuNvRCtud1fOebt4rvu9WRv4BvLRGbLFwSvNU+Gh1jKECZ87m+/wTS447tHTOSUYtWZpRUMWyrSRAbJXWr20fQgR5dMcnqQ0aMTyFijyDvPBuw9zbd2/j6qghfPSRjtBYRG2Y49ZyqSECB1eSCW3s0ulLOIEzgEfGdnn+OSZ9xrbhBYpyC314RaGBlgY+QL3e2P+jXkHt6bdmPdpa7aNeTe2JllhzbGi7PME+jz58WxXdXqi7t0z/2z3OHm3lVlTLyLzmPbUY72AgF51LmQtBZJvvAO8Yybn8W4Op2SBdCXo9m3IQhYvY+Lal+y3brElFJhih4SPkM+tzcSsmIhRs4h1COJN/XGGswglCz7ga0uldU3x8a0rnvTiYoTV1ZzEVLHlVLIQH1/a9gbwBnJ7oIyuEkMzRB1fZXnN3E9bZbQy9ykQemuVKct4EFPwNNuSmuZmTR9ws/y8jfIOPIkznMQZTOKmR40whVsWiORKtjbpqcZL730irKJZgTz9GG/moRTqcNOWLAdKzMYnea3SXtV38Rnbv7CUL9F4KRKsh8iDaAfTMJmHk8Djk6L2m7oyChSgKhct3ifGgllhzRsCV4l3b8NIJ4JXaKplrdZcNY9t5BuBsvntJkW23Iqw3fNsoh8slfHEGTUogveJtRaRYkaik7COSPCs9qUHmyaQEUsMguk8iLCtl+WELAspBSv1I9hNabnWFlXWaFVWRNWRrYXeJGY+H+A1XEC3STdJIOIoaAfXHAYU5LW0oeBGZWRYq0/7qupeG/mKGl+bpqx0/awy181yWppRpRWQhBO6GDYun/s3iHNOcSJW19vQRhkglqZZH1yhoBev+5AGIyoKbTyQybaWefOPmotDR5Pa/A4NH2kpDbVAl6FkAytOUxnpq8FSmaStHHblocIfrhO9bp6QXQwgI6PEqJWVlhly+hrUowId6z6TtTVHrA4T60IC87Hcm8pb2LMwMTXyxaj8onkpK63XO9zd7nR7O7svu8+fPznqPXry/OH2k97j589/6fV+DOblQ5fro0KdRjjLsn0Z/acpkkpHyMyzJaB/fz4NVhDS5OvFo6l/AhO2M/XxsuVs6gN613YMd+V76At1gjIto8TbmfpH9EwHt6IGY6aWXHyj3qu64BJxhRMj7mldXJw1IZpx2q4LVQbnIPx9XTiKuA+K3hQOjRDlaW0BWYqHhww1s9aF42QFwgHDD64IR/YyBO/V1jDNzsJs2COVaN5+bSWVfY2m9+S68B6+OoJIh3WR8EANYR/rwuj5RdN7WBcWKrsfTe9lbdpoFA6WPWWTx3t8VeE9EqTp5SjElZDhrRd1UdHQdc+0KO+9qouWlWJcEOWRjhLDHA5hp/N+qR0LxhikD0SkKj9M/e0sC5etOKev99HvTFu9XufJPprf3H/W3T18tg2LZud579nzbu/F0W7v+WHv1fbhM3QfHvW6j3ff9Drbzyj04NHh9s6u9/PUP8NcAEv93izeTH2bzi+PCJt8RKD1pk4JpE+GTwisoMp7PUV5r7f0++vUX9/0bk39hRKpi8aluzDcieHOxmjXceyFYy8de/nYG4y9ydibj7d2I2UkXcsNpiNfLGcMx97J2JuNkXKYjpGZociMV3AsQjk0k6YUWJveHozHjEVGlLg3Vl1Qms+wtXN7i7F/3YHRW9rhfJekQ/uV1CSA9CaOJkPv3A7Kog/zKC8OYFspvCM7LEnPvI4NQrYQE3XqfPokWkQT78yOtj8lceIi0qfYrh3hRR5lD/EIA+Ou4+zacSrn4B079El6poOeV0oHelqHnVLYJB1525VOidQYU8eQbR3vvYzTU/k+o/E6GPs33uW8vbH/NET91JOP9+89KJ3tl5G3L2FYnSfifvLsnnc49u/9/TvvI3y+u7f57bfew7H/7eYP397f+NZ7CUDv8dj/3nsx9u/f815hpO+/vf/3byHFI8kE8MoQzj/NVpEe0eumxv3vmq2cTjL3mt4vYz+QeU1idreCO4/G3ocSivMuZ+jPJVRTUxzypgwhYlASvC7B2gIph7wtQ1i8WOC/lnClm0tCbpUhT8PsVJUcjcoi0nDIwGKkpUOTEdmcot8YfuEoWQDCQMk8FGjrp+fojvEhBDoYqaMrC4dxSg46QIGDL23BdemFI/8wGu2ezxrBfxy3t9ff9sL1j7/9Nt/Y6Gys03fnO/58z9499u6x997eHn7u/4Mj3//HDn/20Lu5R6H3IK91/u7QhyPf2/yeQjsb7N3bRe/9jY1N9O78g9Lu/cChezsd8u7ssXdvb+fdv1d1f/ttvbWx/gPV5uE/qNgNqcV3XOz9PS722413f7sFu1tKQ53T70NcooORf/f4t8T97bd3d0feZISwOf0O6feEfmf0O6Xf8cg/DkgDS+AFcs9ISCB4540oRg/zdP96+8effkt+K95d/Mdv+cVv+a273gKmIxzjUC4BVQFNogLp+BB+iniA/Fh6ndpH/iz+nKRol2WUoyUWhxg3H+aoqoVsr/Qzh2ergzcydK9JV0pA7E/wb5Sl85kzRFUQsBYnOSpjgb+FM5w4w8KJpn0yjwEYDCYwOEYqG3CSrCkQ8pAb8kscoBqnEf9i5PGmM77njO8742+d8d+d8XdsHwd/UAcNlzwGVzGdwBmAEsdTZELP5mj9gq7bnEnMmhQmcnKgB7nTMIN9JXJQ1IR+UK0RCpOGeMqGkxHXO0m5Mo56D+zwGd2Bts/gOAOBDhzrY6I08fylHlHnkYjH0EW/Izpi6IUMHLmmUPzSYcMlBfVyAacieWPsYF40XAX2jcMqeaDdpPzIKeBwlcEe6swnzhkMzvl0FhBPqGgEDsy8JY49j7nqaeofKQ2FVHXrpTFSSV0BEo8YJUwCwLjmA9HbZZbTH/nLERLZg7BoHAc8R4J3Te8cKoDTocCeZ0FY/PBozZwM/hVWTkewSoQTw+QUzoVuOBLaqlT5xQAuqQpN0n5Whc0I8JDiG2CcCPvQWAjdnhcpCiAhdUdhw8lVITUqyDggniJDLqbjPYPXNi+9Di39M/gNE8DrRB8G2rkTTcKlU3pJfxHJs2mQvDwoIXvxBI+IUQnZJ5obHB02W6PgeAde+g6gKOJSlaBuPMWnd4oUtIYVphYOVTJsB6V7m6xrs/0mDexM4pnpTSdpZvjpWZ/hZ0WBBuBApHde18DeGLDDaBaFZsFHKHJSX2mVvn0c1BQEiLSmKMCnfVIkAC2m70OyZS/tMSBk0MGCvMKn7QKh9j6fF4i5DIiqfQk5QqrHAjB2MCBmvk+ik8KsC/rNmqDfjH+Iz+vNBAQwUxDATNJNZ2YC8JrRwUuR7S7nXsDNQncbenb1RLBgVtcJzKwBwYj1sZKaoCvpCXpttSgjnAerlcN5UFesngkq9k2Sq9atQLl2VpZUlJ2pUfpqrWoyNhpeyRqirtT3qgwYbmVAea5kwCV9tga0GsrE5QIqk5ZLqAKzs6oMW01OekFoSDnlNUhNaZ0vrSudr7FYdRJjudowWrAVEC1ZG2a3Yz8BqiNSa4N9lcWhgebs1kALtxBwZX0Y4NUsrl0hHMXua7uOZdsqZVdaaK6Sa3NYmY12SyvZ2itlpQ41lavLvGaqqgBztVxbwZr1wgH2gqm05rP1wFmsE69OaY3lLYidxSEcDud5Za1gNA6oLDNaJJUQWCU18QFqRtbFIUyXVrPmyo3GBtm1riCqGrSw2vaanNUmpfMFgM5Vr/6V2AbArlYF/RmYaXUAalpXk+8Aa7A9fD/PsddmGZwSOiWII8ynyeGcuqP0qJqXEFX1EmKUAZBcpydKUMcsYxHtup8g6yWPB0hAURIb/Jg081BqO6CST5SViaMMqc0yDfTAcoaDcjKJziEafh7CeRNnF7ofZemZOI/GGWpN4ah7k/RMomtqWOK9ysIZxoIC2gH+7oXTGA1BopMVgx5FBZ7tcoL9EmUJq7RNCjQZNUdUv4iyDA+9CMTmawePBnuLLCoGY3EjPkXXyzCLw6Qw3cpaUJSb0E44s/y7YV5s5+AygU/wUhJqbMV8hvcY8cAEKeqUYK9oYPAYG8kYmRidqrtM0GhmjDPB8qt8sC9N+NE0nEywxisBMtcsIFdABkFqyGPxz+8Rq+2jcKbn/iOYJvgM8uwRzZcRjHc7wF88y3V4oTjKj/NNew7TMw7pyhF4G47fNsRMr2CYzK4N5gdJoUro5DSwJUC1Sj/tBQKBHMpg8HAY151j3yArM/qjSn9w2KPre+mQlt7n6nNISSCilVb1hWRgdaDkU+nCCpQ68R2ah4p4c0HEC3EmgG2xooKSinSmYvGh4zgoPVzn0q+qTRAhxCS+3qZVAmODhhTIG1AblHYTdYdVUgBjUWmYoL1pmKGtu+OAHQ9Vc9j7hBvFnkNpGvu61EBJJS00fFxjA6BqzCDdSNNrprGbOSXeNUcHh44I7qdx6S6j56corJOf0pmfHPL6JiIfn/XRRRwKdMhxH53lQd/0vSGfHI/RuXKsN2NTXY2sqI5GZlDL9OSE5xA7tpPBmPZR9u7ErPJFAw5C2rbFU44oAw5TersDuc4L6Vpxqe1ZvApfildtlXhJesJ7mnJinZX7jURhQaiH0ThcxESKrwJVMhuKGcxY5yESF+zSs038Mt3Ep+abeHnCqZQy40wvzwoTouaDwPSks/xWMnvaoanthyiiuY1PsnC1a48ZysppVDD7zPB9UqCqwtmH4ShfJcZ+ITCcxKNEvFAh3OXjk6UCSHTk9uUqMnnKqOyViEfR5ETFQ3cZjXzvRKTtqVr+plcPiwmUsTFBaoBMGI+SlZsM1QqMO34FrDrfDNAjtwpczcUeQw450FPP8ldaemBNQwtmt/XAnJJ2jlZrD1am5yq8tqKVBh+sTtiaAJUTMuR3okHKzFbIxAYohGBDn0AGK0CFLGxodxwPThMUbOOydqezcci0nOk1y1EwdQRCGNLJkgSdiIklNnp1TC3igXG1R+EVTKGBxKa2IcKWtoBKKMACVnjM7zxAYUU8CCfbuITUUkKWMhwPogn3Vl+cRygobPqZ3fLOOxvDlnOEllBWW1qGQU9NgPSkBHAqk45RuJfPE5ded+TfbRxvr79917w78nbB9x/TfP2ut4OuxoP2WdQ/jYuLafrxIm1SvLvecwxbp2in4FxvtDDtNji3fsv/duuu9574/k/p9xnd0h3Q756+DG4EVzLwc3yUQUpOr+cpr3CQFa8IjlHRufo+ohsX8DzPhqi1gf3GOVHcQHhjKnU6Iwfvh4vIKQ9q5HwWjUINf47lO4rodYRIdEpCUjlhUBLHJCmdkmJ1LPLW8OlEBq1bPQ11JuF0ZpyLnBSGPy6WrBgYfmGVQPtymHZoPKVPJ7+zeIj0/sd9uh78mKZTfKUyeS5JYYqkQ+VBjQSlO0tPo50QbbpmoelnkkEAT1EUagKzXwHs9DxUT9OP21fMAgh6KANZOnnswP9Et3qaX5XDNKfU0/wtto19NLLs1GPIXh5FduthZ68M/DR/VA6X6aEhYsAhZf/IGO9XtHyuqiOHqoaC7xft47bqCNbsZWjHmMMmJBefylOc1PbSqxtZgqShDNBdbBKjTW9/5Afjopi17949Oztrnd1vpdno7uYPP3x/F0Vc6Ofpk8B7Uhvv3sbGxt18MQq8w5FSQtY4Biw4QCn7DkwpZkWzf30ggHfecYDXt3uEmU+I+3pM2e9+mMcLgKF7PSIPBhk2uZApg76UfRiKuSeF5vOwd32sTvf1SFnD1hU65qhZ2I8H+FID45BnHW9uKfAqRL5OT0C4puGsZDiFM7MWAzhlCHmOzvVZSDQ1ByD7SwVk8wlXhnhtJEg7SydqhyLgemxB6yPvxci/yOvTrJ9IqE57wKKpOrqIqpYRWMEWKnFWUTINwUjDFDbH0OplBbI7OUrw2v6hvrSEiAxaLy8yKaKBwXCigG9dcKEOlo6jMN1xhO0UZUGe9YFw+SXQyJWCrWw1N044Rusn7FOBdKaTINIUYAYII9QIXg8Vb1RiMUdORxFvGVzyqtZzIXCOTb6UClyIVwW/UjOPQs/KqTeaLGdjYWmSex1tr5VBsLSUGrfHsLA+ItdzouOmZej6uAyuS/1SyKHatIpW4tWOGW0PF3gQJDf00mL9vAzj5V4G84KXGDHfapXzkQCV+TiJCpjhSDtxHPav5wKgKNhFpG+O54ryG9NllZmwHsn0XOUtrE9jM0hxxSQwF9KbT/3EW+ED/3rBfBYm53CdmEd3Aa0rxSBWxJLMNmIWBu2NB1lY+bQh0hEWPOtESUhgkubR+iYFiZPg/CqdRQ4xkP3rEQMwiu7tfXUc1ZD1WB1I4XAyDmfWWBGgMlZIkqhBQLcxAAa1ogLN1YpC96cRWiCdj8ZGt1lwu++sILMD7TR2L1YIJY4NkPWhBtnRmH6y4wmsjIjb8oCYlxJrIgA7yvs0Tuw4BCkjlfRZGW1awsqIZk9SrEpfKmKujHAmzB8+mmgGFHrWQ/apwPL0pyIMS4iKZE4FimPPBDps4Zar93sNWTc2/TmmqawUDbOHW4PNoS7j2sM8T2I0fvAwHsYUi3zrffQawYekEqcMz8gvEYr8ABbOlIOLfH2Gy4YpiMX2BIj3fgR4EIIX62HppeDHkA/3zGJ9LG4K2B9G6QiOeGNJGBt+ioCEWoREKWPfxfrUBFAUUnXNamExBnnXWSWsRMgKwMhvKDArCCEvdUiJjynQQsdl+JtKOKfH82qJh9FnYeGzjLSmqxMv+9bpGQ0Gn08nSf6ajRGwp30+4Us2CNTk1rkmtt41vY8oo0ZUZ1uoz8DjrxCh7SqR6tpEqrsSIaRneqfRkkPy/JdoGahXEkEol3ukEbRUrAQBCNgDwBEBMAYWPsEcc3CgBTg079JmMzjgQyG9cBbDHos3mgH6O9ov4aIEWELFp8IyvGpUQeThEHq0yvA9UvJEUHyQzMADYoygKw8XkvcRKubxRG9JO1AKTLxBNJkoVm2AHmEycYiMLofokYeuneArZ8xHOQnKA4KOI+xpEh+PhgghB0JYgzaC2AWwGNuPv+CehDm0jD5M55AT78rIsb8jEKR77HjpBBPCL7thEyQvnvYCuhtGxmswUCxXcUTDmGRPdciuACQG63trK+VvT1H5G4VkUh67ShheuZRwFOnHMFgpFBu/4M8i0lqNXUfNtfwYrg9GbfvMNET8lNErSujqOEmiDA9g7cAIOMJrIwh43MUDH70JIr3x5I5QYTn5I3wjCzDREaWEuDVED574O2oMxU/C321b9tsje0kERCJlGKM7Jhe/B2qXBhYVbBYPcCbGiTh0lAP27yfi0CnwRW1B7+/xmKHjHxL4QMAQOz0joygQQVwAy8LRiMdbOwMvSgZIuLXh9DJgao6EyAFFjGOcNOQDLPE4xplzglS+UmjTDsirHswEKB7cLg/FuNu16VU+u+VdFkGekpvhCvsY7/cJrmuGnl1VO/QkKan9w8tNCnyWvhQ/h7PWFQ7rkhvgKC6upEnJ85AJSI+l1mEqigMhJFATCC5Wrz4CedIH/tEYfSOgMNBUT5stB5J7EiLKQBdKOAAMusPuF+QLEFugbbIL3JJd4FoBsDlD0fgLbug+pNTppIDHMqg1ufHQlit4NiBUxAHZgNARyn8gDD/o04snLpcLSefjjtVmJYu8l2lb4AgVJ0CxZCyxiKZUK/gigsIvKqZul+aICUa9hI5D7Ch05CSRbVhJJiiPOLp4uFGLIwrzQ3HgPCAnQTkiOCRejHLR+Bt4E6BGoGX0QR8OyIQGgxEUPQr14MgMtcRfdJ+h8yzwpmESn0Q5a0QgVyAXuURCtuXSVshL9qjpwj61l0/DcwSdk4v1YpD/CTkBiu/c2mI9g30kiS8g4qoF6jFjMJUFM0W0OEV0CD86V7y0klwBH8UzXOPKhTDU2x7QJ/B496Czs5ekU3raDP6UHzkjLBkQgK5kzaWWGMsMBgwqgr/oBsQ6n6KXHIE3C/GUChHEEfBV3Tid0PIzPBSyzGORySQP3/FASIqPsAFIX/CzkaV2IA6EEHsHIcL3oWdZ0o/kln7Et+5pMiF1D+HweYJ8EXr0mhE7KR5QCPsPyI/hkzYZCPXwrSMafkAvuxCGV78MYxfAUqwM/qL7LEf3Wc5u2pQzZsEGXh4mQ3xcFogDNW/Qesh5LdBnKN6h0stB5Ih2AjQKp7yNKhfCJqRAqh0oF8DwtNrmQyv4iCQjpo8nSCRn/MGVzLmGMyB7aCNECLhpEwR4BmQemipE1zBlz07Kfl5s4GDkp1BRLliImAfgZZYCjOoMPdEsYBM1bbEY7slDHPCzI/CALqFHQ+0AXHQ/EHgKzReC4ukpTFtMkXuMIIgp4aG6zRDKgu9TPKjK/i1vuGRl8xnRO2MMSB/w4Q1VgL9AVPbTOZKk+GFSGoWweO3b/FvX4t+61WDwzWF50qIq3QAH6hP53+1AuZDSFh6v4j6261jB7ior2K2NSJR8Fsk+SL7DSDbC8iCHIeUZL8R3NMUce0U7AUqMZd7kTY6za3CcXTsozAdEiPIX/Ep5D+Mk7WWqVnt5JLWXET7S9bLwmMg/ZA+EfAQkhAMqjsCjp3T0XjnBdY7ePeXlUOwcYoC3qwxy12aQuysR0KvxEHo0D7pPC7xPq7sfEUFLH/DFeGzCX3BjjZZ4PJkMeOqhi/deOKmoCWYw5d2SKe9aAch5bxP/nd3InW8bPHtX8+xdE6yi0km/DHiBXg7NaI8oefyu5vG7Jpj4XW3mq4vP4te3a28D3BrOvlsfdTVLuQFoX3d14F5zdeBem5KC9ODaNwyudcPgVoPJp7lC7ZXbB7dy++CuRpFTGT9c5EUgoCMC8UJQsRBz2pG08Js3mGc5jQx9wQ/zcgCzElcDLgE8J/BxiXNQLjzUwOkX7wfpuKPcCJe1LA48oJycAH4lFY0khCqAjgDoSBQJrT8sJYlRNyKd3sWBkEVM1RUHHmf4CqbEgav3NO7KPY1bF204x4znmCl0whA6YYhlQ7HRcBTxAkQXL0Bo70KmrnbiCQnPTuaDvNXbIHflNsitixZxanSds1EV8IoLYayAJlNv3UtCRAXpZ/CHmjLBe6Q23SaxW7ijbfsqyjWvotxKIHp40Zf3U66+n3JNMC8kghCVxt8MqQp2HiJlwU7BMOwR/EJ3V2UVrYst17rYcqvB5BOkY16XucZ1mWsHEfuID8HaGZDwNN+Pta2bM9e4OXPtIHQzIVXeprn6usw1wSoqX6G1V27Z3Ootm7sah/LgS7a2fQHnmhdwbiWQky0nqppMXrnltZxrBaBzUSNErpJImFsJRM+Z7FPmHZ5r3OG5dhAd/OWIHtLxPEVmQYYyaiewME9gYZ7gaEBXjzbbwWgTvvfgew++eCvHJINxKeiWl4KuFUBO4w6vvP5rX3tz6F53c+hen7Zapro2bF9z2+hefdvoXpeOQuh8TS46YI/w7ANR9bUDytszqKtAZSxZlsorC1N49+1AMfE9an44XMD4GFefrnH16Voh3F3EvlNJNAfetW9E3Wq4cTmAPA/j5oD4GsbOWr1HdSv3qO5qlDi5h9yMe+hCB36ZN8Bf5npkzHrXzsA7hZl4CjPxFJKfQurT+/C9D99v4fstfOGD3IksiSYwrbP4HFkU6HtKPhWGHa4O7wzBPldn+FN+JsNBVF/kguDdpXBByElQFINJIgYfsZu5I2gHkdkj6Ao8Lk1hIPYp3MJ3yprdXblydu0rZ3clgrpvFkRcuY527etodyUCXe5R8iQiazkYg0FAOkTbCEIODa0e+gQiJU97p3G17ZZX264VwE6DTQO+kk2DPuJhGVfhbnkV7loB7JRzrHVB7poX5G4lkD2yztgjq4w9JXPpVB68BYZsP7uFrNOZoKg/QXRO+SmTb+XNPLqMBDpmea2GAeatG1NAfPhN5tN0UIQLnErgfs7uQMnzB+p2WO/e6h4W2UOkdIxYROQCGJ855bDJaA69MZE6BtpTQKG21GWAXJyWAvxabpRhOPvVnWm7RgjBXRFCcOuiKYi+Um3XySm4q3IKbm1EklWQpptCDK4hxODaQSzDsNkWYYZNisxiDa4BxCObQiLoVuhDeG72dBGgPWMEaGwSAjH2CIHY2aj0YguExCnaVXEL1xa3cFciKJQ2E3zG37A4V6Dt4nUJXZbQNyX0Ywl9i9AZDgHCyKEhilUkXnUpYIWqewgrjrqQmJGBVWI9niAeR9NCUbaIiE9CYPLS1bgRSnLDJDtgxCmFiTEm4bpFpDpY+VUXiwQ3sThFlhvalzGnE29CM3kiDBU7Jx7ma3IzP/MNumXbi+UacEXkxa2KvLg1kTJ6DkTWMUllLnjkSSt76FzFzh08XamTCp5TkhzNBpXM010NK+Od8HtRI5a8IKU4fMbBsFze94OLkbA4CEKXefxV/lwBiA1L6oED/oIfOwwGk7QAL5HJGhITEj/ISIXjMqE15UIYM1Y1U9WgQ6oyQm5FRshdjZJPmOc7YZ6v2oGVXAHyYAfzSZiVh2oFKU/VClKeHxVkV58jAUL1nnHFZ8gDVzcL7FMXctSXCr+T57kg+bwYDqNFLBgafDvKR5zc6ZhYudMx+xbsW6APraQU8YT4zOTpogdD0pkQDYbolFuKTrlWADr1TmMJVLmmQJVbCbTkocr94QqRK7de5Mq9MoEFNvaMq+Sz3Cvks9yrk+SFTLBCZg3JNLVFtkn5tQhXe1XMy62Kebk1kcpsyvGvyoG5K3Jgbl00hogYWLsqJubaYmLuSoQyOUqItVdkyNyKDJm7GoX9pfRYu0bGzF2RMXProjFEKDRLusw1pcvcSiB7jAlrSa65tuSauxIB1T+jmriKrMZZKGcDFd6xRTdehXJkUOFsJAam6krKxyrESJOdhINIoUH2HQk2JItKE3m1D6HkV6/46YIGGWSTOS5z8pBYRK6uac7VPc1rBVkqCGxSpFmN5PDaloSea0jouXYQukvJvPaK7J5bkd1zV6OgX1FQ6FYUFLoNxF4R+HNtgT93JUIBm30Be7tBVxUlQaWdiq5dERZ0q8KCbk0kVivKF1wpnPjnQC/OgSqcw9F0DkdTLRtYorwacUN3VdzQrY2oQQaKq5NJdGtkEt36qCJ32FYCiBqCgoptW4jRNYUY3UqgeEh+sV2RbnQt6Ua3GkxUF+7i07Yl9eiaUo+uHTZP+GKVuYimjy4Wyzs0S1DSNQUl3UqgWjcLWTIs18hije2K0KNrCT261WC8BKPRFgdBinC4WLYN4Ui3FI50TTi6NMPGkph0LYlJtxJaplu2bUlKK93SrYQuNJOpFBt1tdioa4IXFkfIFiZ1LWFStxqMGrTpLg4dD/E6Dh3qTIBudSBYxHncjyeEsUs3wO0jc0VS1bUlVd2VCIt0EPYBih+5b87lwhlGG2VJNe1niZm6ppipWwkUGVO5rjbFT11T/NStBJ4DojgHRHEOiOIcEAV0C3TIOVrITNDkyYSmEwA7DDkSCMRRHBQtr+qel/eQGkhyrXCYmhOtTb5t9mEC9LYl1K0Gc9JswHIUHMa+Min73Wow+ZgNSs7HJJEliRDuWgHkNIo5NMswCzgscwf65kygR2PkOkh0hLtWADlFHIHcXZZJkAQU4tpBnITYNwwm/o1KAB7XCjifTvCaq42yxHi5hVGnkzbCXAMIDhbJAAeLZFA0hLkGkAWSWS5ZouCkk6zo5a5E4vpY4syuIc7s2kHgpnzMbJYw/5Yw/5Yw/5Yw/2ClwQJbrsy/5cr8g7P+R/hN02mYDElSBd3byfAgTIJL7+HI/+TilcS66Cx12xseA/CSEm9MaXsrgaQW1wCIeGYJYYG/0i/2hksAsmCBGikG88LIiCTPSi9Op9oamFLQJVSET0sAnOygwVa9whyOQvOZUSQqUy+9sPBD04uyYHwlaoHKrasMMHhvJdCQ2DKASEWa1VJCViaEz/IlRAklGZA0M4aKtsBpeF6FxEkFkuCisyBIhhmdW6RT3AuUvz/PjYpN4kVkVhNpV2vGILdFdlgFg/2k3zdrTpYgIr4BH1rJ4fhKrBILQgJMFgQlrUwAC05X5y2U2TeqTjZgxKxuCUU+aJFW5uDETpmeJUbmSPAldIIrJ+pZpdYAqdRaRNnMAS34xlN3dAbLahJVFoFAr1wLqn/sQVTlC/TSe0nv9x8b+tUbGLG5/t9db/mLlSaT4oP/7s1+RToaHtGo/4IqHtKkddf7wK7j/2DdDz//z5sOb/5nTofXOPDHGB8jwmdzz3n3t/fHv2WkaP9voXYtamC5dg20K9OuWLtm2lVoV/turCyker/K95Z8ox5O0qKnbH0gzkrP2HIVu1tDsaW45vuLNB46GyshYrVrl4076XhegpmTpcRes8iWbIKuB+thSyzBDKMTPKrL9UAj6+F1UZ7jBud9whOOYQEOM9u4vGx6UviqSbmCRN4hk6ynY9WacTMjXg7Qui3lvklGPuMe90wo31S+OVScroMOxki9bnj9eb+PnOENjw3R0KF6w8P766MinM7aNeYLo5YOvrjYQWvIQAs0mpfqdc4B30hFQ8gozrvZPCf3pTfo+btJI4eGTXr+YQPtQPS8T3j+g5hMDkK0pjeneBOIN+x5Jz1v1vOmkmACCfhV3GtIw643WHuyo/RauxCGarFey5fiFNnkl2iJ6VB0lJ3hRBxo4oBdMGZwVItPYro+hkPU80R061OHoQM7DIgWtP7MR9f6frKi+GpKPYhaKGgjMw0NjLbybCBeCCxScbetiO1KfpcezoopNXu19EAHBjFUBbItYzcimN6z3u3bDfyJyJAzGrwkO+cYLXjQGPawWtzT67OecsJwaPibEv6m2YYASAO9DRFw4Jpl/d5cV7831fpB7B4ukTHNginMghG5aPynMP4oHck3pFGG86Xp9coIOEHskaEYizIGzjnLIgCMZURakYYorIETJo/mQz0IlH5pp0eZ234aZsMdfOJW0zorgmqhnUoWtwVEU7le3y6LXtFRJc57fr/nHcEa3s0H7QB+6D0BHez6IZzZnMAj7cnBNtCoZ6xd7MVMvC9mgceaitkvisZ2gCoVCDoBgM8udiJ+DPoKOaTPjwLvKT1F7JhPEbdns7wCOhLzpfx9kuKDhafpxwMUGkbUggsseJHE9OQQFtgQzo0daM/37QClMnM+ov7QDrrIqNmEI2pnEoVw9ty8D+1NSMBx8zvIn2W/N//B5UNh4IFMtvHicRPSH6D57cC7twERYGi5Jvf+UXba/XvUXffvY9xRhJ1z/1t2czfc/zuWOAQHlPc4RUm2+/+wevb+90bP3v/B7tZvN6xO/RZy2wdqHy9Kv/2u7N9NbOPeJjqgJnv30AHV2LuPDkiz9y06IMHe39EBFdj7Dh1Q9N4/0AHF7n2PXQXl7f2Ajk3McANdlDXmfQ/z3sTMv4XMn82n3B+bWCtzqO7dg+CngAhhWM5gWLblmTG9UpaObgeCR3FOFPSCihAnDD4L8CvkCnl07XWJ757NtUKG7QHIdl0L/6h3TP53Fxf0pV0XUJU9Y5rKNvpluR8JAkM5LTwUA/6K/A6W4SF88/4DmTxttrFFaBUfZXfSIRoBbratPPDNZoB1MGDzWfCgI/XDVFBHu1rtABpMDPUNkpYinv/NNx2+upe0tAfXbUMDqfMV2/JKN1Af4NYrtf5suquartuNmZ2N48H4y6rwxYUgvtu18b6Ir+wjXcHXgRvqqegGiXzk+IQXiBe8W6AnzQcGMJ4QeYBfJAaKM5Q33FAyNMjVI3IFUBU9fSKEu2NjYrYwVqhd57k9u4t0PhgTKcWc7a72I29tBLuLBtSMf+08qZkCWPCpXS0lmXLTvWy7sp1GkyKsJSE4RO1eEi84G0fRZMcIWo9aBgwnCEV9c2WWb6ws35hZvqnJ0opQE65LfEtkJDie8hyCtr63uyqJzrgjN7x0MlROkW6hBE97/vEPsN3AZgF7xDvvWc+/d+8H7wAOF0ArBUq7L7SK6HGsDm/k3h7T2FsUT50qiOcPcZQfaC6Ip88cZjQ2absvBXVRl6Vdwu3ba3s97wlHaKwd9C4u9sD1/Y/4u7n5k78HtNJhD00Nfuz5dZjuECI8pMPSS/p9DDieJUDWNuiFvvrSS31wu8qzTmjJRVg0RTodHFPYEMboSObTfkR54MEHL0nYQl/CRvty2MEHFLGIJvw5J4t9qpR5RuCzKDol830v5LTySr6P6AhGrQbnQdLg99FBE7uhti8vLn74sb6TuZd/0WdFOcTFtll5DW0/SrwPMiRXjyl2fm1x3s/ShDfyfS3ft9T/v/YMK1goTosHO60YMPBKN1IiTU/HjZXOwKtTaLWCZjqW2boyDUvLNg1VqNmci+galtsNz+E8saKX+V+RYLUEPndel6ZDMaxEqq+uSEG9dendwmO6Fy3wsE6zB5z1x/0GvnUKmi16k2F2u70CLy4aQyLcnF97LXPgSo9XE0GP1vXRqPNKb9NqUbUiZXqrVwwfz/Ri4ReZoVk1oomUVKCxMVmySlguQxYz3JobOLeqYBU/rQYM1Djm1RCu1GCh9D96k4WP73yzwgnn551JPDgVW+jddDSaoOF1zAo/qHNDfbssuuUMKAEaqYscQ3kKuGcQd144qH+DflCxKn/R1CK5zmMOfxKFi4hcaCKDHKxpFa8mnKGo++3Q1u5E01kBRKATJYNsOSvINcRfvCtwSlU+Er0EkDlzZ5QWB0yHdFg3jrLUyPddDpBFeIzAL5E06Hgxc/ARPv1EdHgUJ1LlQ+XlKkNPVAugsz5lSq6n6UJgz6FcdmCzyfUCLTrmMNtmeKpCu45L+kFbIjOVLQ2I+ChfcVPO4sa8lRNzFzfmn6Ujahk+b5ReIsuu+Iu6aXPYHKBD8YPFwiTD2xWHSTKHDY6jJcgp1JaM3BM5JtUiN441ObhPFqgYVRXFb/ohmGYXxaJ6n4V0c+8QsWFqPd2aLFqzeT5uiDoAwji04OYLH/ZQ+KHTC28yQJ7RQyuoDGwzbFwyuH17NRQ5aeZG1MQcTxa+EcWbLXyDoyiU98lCmHBbeIdL56npwkfm3FZt/KmKT+zC8UJth3AMgVVHs9LaEA149QhnMV1rmid8DkpLaMxqoBz9cOGvRGwEtH4C75NiU65ZfEqkQfgeri1lWd0b6SpELYkHwSLF+UCsLeugZltB4NBI7YwumziGa4pRHOczZLNy1YqmnEMvscMdY6yzFBV71Y0zh7RQLNLuAzOkEQA8RGHW3XN89cQvXptbUhqKIqeTqEVVhLpeeiPAld1xnCujpeMwB2QZJU5Kh5Wh0186h2iAGdAJGkx1JAvACiOY6k5IXMmcTbkDIHWmMP0dQiFIPVIakpzPWk43W2K6Ea1BtJRDyqQBTaCF11k0gLPKQCqStwKvh4thsfA3veXCv+f1F/597xy8GxveEVR7/bfz7Y3A64DzDjvPwPl//8//w56unpZSZWbp27CSGW32ad3islKbi24ahXhKNNN7u1ARIvZRgjt3/u//+/8F3ks/OBJz7hlDHvuBMoYeeDsLpOmeLxRNTY8JSHuGnNBimMFE/UEno3IYpPHbAYkkDk7buws4pkNipqHWN+ht8rpmjMM5bYHp8vbzxeWlt73wjwPGXkOHjIADBRS8896r2TBQlYc1PYjwntwZRtFssnSiD/NwgrNxlrecfcD2pCC8HyXRCaBSGnLcEaJpikOLo8/TB7sjxqbDPIqhTwDJw5QIvKc1VXm/gKMTjvsBjvsexHjn7eNkeII/hwvj/uQE9sGPcDZZMP78uGAK+aF8X0D8l5jTK7SmvkBr6uD7znu1wIPOowUdDbLlJ8ltxpcP5RMHOPqp+xGMvEEI7xcmNV5F4SmSGx+ofj9j1d5Isa/R85bgv6LzlsCjJVSlWPowbMmSQZl8H+Hwx0v8DQWUyjcn6GDpE3JrBFr213kawzJC21p6tbcdGr8YbSsD/QPDB6NFy91zQtjD8nE6nwwpcAL1d/B9Ew4YvSCMYERPnGU6/2tGeyYtacjOgxH7a+5M4tMIZkDo9OdoDZoHtgW012TpL6IG1rXpzQ33cIkk9Ik0YybfKTVnvFTLcxtJNeEPwgTBhfagAjNvwXAEIuzZwse6tfJ4lIQTOAphkggOj5te9WKsTF54SfNTxJtvAvvXFmVBSc19rmhJbj4eWVuw1nfDwbhRx7SCXRDy8UZL/2jamiP9CptLL5eV3gEkh0oEvJ4d/gyxx0QpX/MW0FG3bolU8MEUuaU5muriBQ+rAuUnxdcTASmS0K4B3RNYMUaJHnrm097QUVjSuZqXgnLaS28pQ9W3aw2bvne+9BXu5ENQN8xPH6yC2qtkA+d9hGugs4T1eLb0AUN16XeXfnek3Ofg22xteqcE3abfXxj0gT/vJeZTmkzPKMaBpNqTsP0logzxHMr3o0R6KP6X4n8s3xeU1SvxPZLvL5jVB0nys3zfyPe1RHor/l/Ff0u+UR+zLOg36UNGWZ8jxugJ+xwr7WNLcvodSIQJRpjjz1AgJ33/Y+toC/7K+Rp5BdFSDzv+0bjRFOlyp7CoCL13FS1AyolNQkDijZ9eLW/f3vjp0bL5CVrfXzYYoyZ+cQJ5Zn4En61Gsub7vy4vLjL4vl0iD0Va28RuSLAPsstXMdXpErJdLiEiYQNYRI3Ef3+2lQhkq9mJGwnMNThR+kkrgf0MKabEZ9Zu7qmIzU+YNsO0mZk2g8UMFct00nkfgjdgvvnLJQRwVKgi+gFjNLcwH7rhRgL7x6TF7we24jt3GK+EfnIcv9vKWiS39PykETYhl/XN27czxhkhrPXLk/6ayvqkzy2lrpr1S9Q37fsw7QdpNnyR5OFJ9CQ+iQbLgX7jkZvrA3DkBHI/YCrqRgk47yfRKBws5RJNItZk/PloQJ4OwmwoNagt8tIb9xHtjui3R78L+l3Sb59+z/vKIMvWtN+6tgcqE/i83wLis8GD37y4aOj5qomRV2SrfW4fAm7fXtuA8aiL1ur11HuZnQg+A/PFzO3b4z4PKtLsLZS2vv14YSyTF8+Otvd2e58rfVTmUl/jQ6agiLb5fMXN2J+pf+/L6391XRafawafjD/fAI73maovv7zqdeX3dTYoMNBv3WAZ+SukhJqvGz/ChGCMADgD3CvbfoG0AxAXjQ44Ly5KEh9oIJi+GFLw9EUJhD6hnPKEymWMjDJG/VrSopAyoivKiHQZo7KMxCijZ5TRqy8juXEZvbKMzChjYZSxqC8ju3EZi7KM2ChjaZSxrC8jvnEZy7KMUJeBG9+PfaOYfn0x4Y2LITTY9DZ+LFrIeuJJlvpjmDFb9vE7eJEjgX0lmkESG/kNA2SpDSNF0yNOnU6ZQ4gU/TRcQsxhPEC+FVDmOaYDGj5z8D65Bc2MHNRIm7fv3s2IYoez4F0U8b87pyWyroten6jVglZjM0eE7FvffPM3hzhamKNzFhdjB40DOixjnSMfQOexEw+p9nLciLAZMV6nItetiEw2QpHN8W0AZH8AZ5E8cubCfBujiWDUboj9o3PO285fUH9F83Ljx4w6F8YLezZrejfuWRMB/gt2MPNNUP0TNx1qBdGu62xBt5BBeXSjfhRGJ9T5DOi9iDim1Gq+UPagnSch9n/ZFofPgs4UTu/xRz5iFtFgnMQf5lBjYtVAJeGcDxEx73jgjKJiJ8qQQ0AXontZOuW9y3kShcgrROZOWLSv6qIhJ16nqn7pTMB1FppTIfyCqSCs3v9Ok+B3dF9kdl9Udh++OG4ENVhJcwgz0vw55IVe023YNphN/xYY6G/OIbXGqWkw5H01jsaFIHQOsUoceamNpSRpsm5MrZazLzwTZ/P71rnn4Gsbqopk71ANziBv5yzNTltON5VOdkKADYWOgq41egkqgHpsgQCALQ3j5h7OS7zVcrJ54vwWJLNzh7p9HTsPaiKZrkvnl5n9FuhZDaiC+MEs3YCzCBbq75pgiTnBkmsnmIWc/2vn2f90RFy/IKwBumJdVOP87/K4dnnE5vKIr10esmH9+y6MuimlL1yv26P/dxpdO42Y/XTU1xIQnRouTB0TqMKCUeyxRK4m/MhguGXlOb2R+Blz3pizu5UIr+1BhfjaPZ/Re1HsvxMgn5zQOaKhInv25SUT9EdoUWFFFsFI0lUGS0HE+vphgGIEdC9ZuYhwpNdQhTMsCUiSz6NW0GyvdSzWEjEEj/otQJi4HzG0JaIeKMqZr1FjlIxpiyz+dGrCC80H1JwLyLRjRLfYrFRw+YQIPMfvPKhIjhXxMkAHWQ074/pxa346uuJgjOLRfKxlpigzIqLjjXdeySuIvow50KmcdoUrgPv61m6j8IxqVWYCt0IJ1DjbB/slHgMcw7ME6TpjKqyXU+Gbb7qwCGB5UEpavP2IcAJd09AEAtjmdy1chTQPYIX254UTzmaTmLlPOWBDQhqFugabxqNM8AsuMuwV0bzxRYvwm2/MLRYtDNhYahxl0ZX77oR6Zl16JoB5gBdKPAHq2bLm6N+EJ1siBkYUZ328gOwShxqq0oMdf3Da65OR+R5Z12mbeAGvzHicR+Ot0dhf26ArU30BhhEuT9CY8GT5CcKzy8tLb7fvdxHz1OffQnsQjW6/6e3crBZq+tbWoMXqfBpWLQqsxfO+v/O5WuxALU5v2hfNT1iwwfFUh42GXBMjj3AfYkaCGvFyAC/c+/7p5ypyChV5f/NB8TIvrqsOb5kNDr+2Uk/7/vvPVeo9VOrZzXtHboxaFHErsirW4aq06Lm/90kHHWHctt5CgqCd0JXqQd9/9rnqPYPq7X3JRMb+SioM62RqjWDCnUXTGqqx3/f3PleNPajGky+byequdEvNYoDEcCLFa+0G7krDCJWKLXEie4d9/8nn6vAE6vDxi7viqlY/7PsfP1fiRyjx5Ze2uoeHcdXoAraS3ixcorAhDvnjvv/yc6W+hFJf9EUWwj0i2T1A0zeQgFhz9lGMAUkDVNsxVZoyhMh1YANHIzMBbgckWpjNZwXzCvia3GFE03LeAOk3neeFE8GOBee5jBT/neHOEk/JAlQBpIqnD2qYB2c9wG0KNggimJFiwBAYibs0CoHTR4GglsOCliQ8CCXghiJFMAjygM2JyKp5Eikiqx+Nw0WcZq3fkt8SoGrheDlEUgitOnIPwJ6I1nDUQdMkvxIhtPpo2iDMuPJUW6wiEKrTOI+g94KW1JRVUNLZAwX3KRor68RqUWtbbtN7pYYq+JKh+hOFVR79mXOHNc7SAfxPnEZWKf82Mwpnwy+ALlD8oH01pUjGXGAbl0McS1M6285EhHmAqsqNOuIYF4AqxnzKCB03SdOZi91A9jpaekhveFwANPRBhC1+lu8bEsp4Lb635PtVfLdQOuNnEe8694pzPzrH8OQcZZ8y+o3xd2vmVzFwKfeZmLIaCfxrAf4DahLfqCh3SxlzG2L4abT05RiyGgH20ntNK3+JsqaLafJUk7VZyujp8UPidS/NnkK/wBT5JVqq5ThG0fbQkTK/0iFtq6YRm3K8wIOIF/sZHEawwQHJ1Sbnx/E7OKrgB6W0UISkR0KFHm6lvWEE5T5Hv1z5BcGWKdNbhCPoc358BH3eiKkYPKNB1G++IXtpgtNwsSp0B2l/C4I78R2XsFt4cZGtJkGFtqTTSSWmNcqHjx+DO9md4KeWCHynWK9kTY6R+LQ+oZMhS3qqwbMq+wB7JGm2dSiyGUrZZE5OQDhQEmMpQEFNXDaIqPFCw6EjLUtrUn2gOk3v+hMcnhIlHZ3RcD1WpsSc+JOOC3PTJR5n6y/5X/Lr2E9yQiJVXMRvoiNUnLBlETyHBV6IV35IlPBAnvvTsLG20fRSdm02vfwc1uDg3N/0Juf+PW9+7t/3hrQKT+h3di6Sh+Qbn5diOiNyQ2Y9A7iQ6EvMsY85nqtoR1hSB+FnCO+e+996u+f+997Ouff8XB2rvdPSuV0635fOp5jPGy7mmRR3IN89quU+/T6h30OM/RF/Hkqcl+h5DFX4u/daJF0l5NW5v77pPaJ0v5wTcaaYEe1ejMb02rdC/CjRxPZD9koc9rFCSvHsT8kMQLyIHhP+F/CTEJB+YcekR+r44siEojCwOA+j4XwQZdp3Ii5+TMnuHVy5LN2oAGTacWjCysdNKgfYknbFrNIRIhJVpaE4Hqd5YT0lK+a5BKGBO7MGxv4qkOdoHBMmfDww2tTBXUd1H7oP0VBdPrb6kARRAQK7iozQz/J9I9/X8n0r31/le4u/Wx8qo1gjhdqLSZi/ZnDt45lEf+0HRpzAO4ADx2EIp0TvVcrybOaMqClPMlAsC0xfVkHG/pqSlbrTstx9o9yV6VbdNq28qrF1rknTe5yqE03d5LQrKLnZccwqHqSNb2HVe7qe1vy/prVmPDPDh0abaYnUVQgDjEQi6vOx9XgL/vy35yYj5BfJUHFBMEZyeWmuu2pXciESSuXInltfQqI71CwjU2WcXD1XyLARNuNZquYJry8zBUdlulbXpbiiLmPKyKxHwfUw8Iexm3HeZRgVcLmKXq4ZSCsit+ZnYwwNlLQq+8w5mC9OMXmcSx1Wsde1k34lOmeX2vN9eGU99oecYKDKLzHgNe3XkTjxxxB+dowOMNHmNdmYpxfKyMzDQLRXzqUyDqcf6SlVi+Pz3EbYUbqCsK/qJzMSlzVRPWZi9ytrakSSRUxVvcQ94E/G6XuN34vN934nNsd0XxOPY35fAYNjNl8Jd2NWX4C19xp/Nr7e+3Px9d6X4Ou9Pxtf7/1BfL33x/D13tfF13tfiq/3THz9e1DtXgXVfinO36vD+V+Kr/f+ifh674/h6z0DX7/5p+DrR38Wvl5F1Htp497Gt9/D4dX7qgj7xRcgbDu7Ory99/XwNmXVNbL6YuT9q4XOPvwJyNsuIbsx8r4Kd7+G1dpiGTKRCqtD5Ffg8ejqahWpXafon4/I3/wxRB5+XUSefykiv2Jk6lDyDRDyc41Q6/eFz+0KZfpadL4yHlWE3jMG489H6Vf03e9D8B8Fwb/+XwT/Px7B3/rTEbxdQvivguBXqvUvgOBf/zEEn/63QvDv/yCCf/8HEfzy3x/Bv/08gp9YeLYuxgBi3ApVjC/D/5j24HczZVTq38OYUWm/JnNG5fkVGDQqq6/EpFHZfQGjRpL8ycwas5Q/iWGj2n5jpo1Zpz+NcSOF/KEtQbXsDzBwVBZfkYmjsvwiRo5K9LuZ7yqDP8p7r8vnS/k5Ko+Sp1NuAlcg0Ogm7J9/PntetUSxfH79V9gwfv+hQaX+ooODSvRnHB5U3l/vAGHU9mttHL/nICHp/mRukVnKn8MxUu3/XYcKs3p/HudISvnDO8kf5CCpLMKvu5N88UHjMyP2ZYcNldkfYSat5vHl5w2NuCr023/JnvJVjyOqZepIcut/d5j/3WH+vXaY8F97hwn/pXaY1398h0n/O+4w77/CDvP+K+wwy//uOwyvlSN8glAcadnjpHRmpTMunWHpTEtnXjoHpXNSOufaWVHOGx3xqh1CTaLkwzyaRxBp9axKullRdp+ExNU7kFwQUjTnZwCLsJE1t+KWPBvzC0+LzzcWOYp9xq2BbHE++Ap/CdujF3sZuPWD7UYX9UcGrEFWKtNooq5sL5s3CkDNEL0figsGXip+GJE15T9aeRToH5x7X7MVmVGzm7QEFuZA1N1XFs5VzUikGRk2I2luZdSMyTlWqKx6gc/YddULXXXS1mlXPZGqn5RVsWue6JonTaSYTo5ElbB8p0fqcdlV77Zan3+3RQ9TIA4btwZ6whlrBcsnUYgGD+ipGT3pxndoeeUhmrw4u+FLF298hLL5I1qWPfpd0O+SfvsUek7uI/rt0O8Z/A4jrlk0FE3gsL4UvcYaGyLYDJ+ECdol0o2gHspFs2+Xst/l/tvaLZcsDvAOBT6Xzj2V7/aRv+G9P9LKJZ5SfZ4h9ODI3/T2jvx73j4lfUK/h/T7kX4fHik1z6gu+yiyNCI8EFgb0cdLKe6xfF/I9xXl84h+f6HfD/T7s4S/Id9r8b0l369H/vebP9zzbkFVUSMDYlyY72Sna/VRKhCwC1JCW7RQuwkphtA68/FpVqmyAZYAKtjleKi3gWaml1x6AyzjiHRR12B+LqI10BqtRW31JVrpoldKNYnGY0Dh5Ruuo+W0n05sBZgMwwUk2iw7fgnaijqNgGc1LISBocfBChiHeY8NffUGkzDPq+Fo9bsKQ/uxvXi4CoaDQZOUpBcdVD2QdMzhh9mzMvwAa+Osyjown+IOTKWw43/rpejNOzC9BgibdPz73hwDhh3/O++k4//de+tnHW/WkUcT8mYCUk0x6RiTjjBpD5MuMOkSU/Ux/XnH/4d31PG/9zod/wfvrONPO15Xstrt4BTaod/n9HuKOW53/LTjvUfnU/x5hj8H+LOHP/uS+ol8DynlRwx6iD8voRobG95jqNfdDe8FVAV8ryTyI/n+It8PmOJnbMIbbMJrbMJbhP2KsFsIi84AVpxBs5IzaFZ2ht13JoZ75ZsiMMefwRkqn54IfC7foXxP5DuT71S+4zP/Q8cbia8H5Wx4C8xuKaD+GSEr+j2i4A4Gn0lwlwJ26XdHYM/Jd3pWPpA6Q3TyXoKfyvcZRTug3z363affJ5j/ISbZahgrRmmuifyNrejHyUJpdo6UZufCnyyOo3e0yIv0SXqGVmdyWMxbhV8cb7wD4IvZTAHvFK18Eg+ixias7Qz3KZiud4BUBE+xQF/FthZGsuGmBS0IzexQZckKQoJhf0I2hwKMsZPO+5OIjBZJ8Ek6wJeDFLqHbhMOh0sKeDiZZwyPqaCqkS0ICCsBRhXSSpC2mQVheSWMrWM1AQvOigaEPEUbP2Jc9ZiNAHOl2LkA+DsrLplG+nxcsTikcxZrPxxfeepS6PyvS3FCKdjsBISyJjYx/SQd7qgOFnNKYnrSIXOTilhIE05qWvdRuR9RFMhdZyQ6XqZoTgpNQqHRIVWanT11yFAbWLpZgQ/JyNU+WbeD9g9Ka4NoIssrzWoC2QXVkIgBWWcyOsUwUkjJ7HzKbjFqPFN2pcyq11XRyJznn5U9GS/5agUwQWmXIMp8fl8RbGHkTBkXG4TJTOyH4bcQ+2HKuNfgJsa92OjWsLS/NTXtb3F/1NnNMg1eDbTBq2tNXZU2rqQT2IaVpBZbVWZ7vYcaSTcCNqBW2AbUyEaaMjNG9sTEFBZ/qDxKYWaLRNAgLBofz2DQXkJv8lGDbXVgFe48DYtxCxDOMJ3CubhIxbTS/e+agpXvNb3HtBu8oN9X9PuIfn+h3w/0+zP9vqH95fWZf/e37Lfkwd2R9xbd8w347+K3+d7e3g7AfoWK4Bvl9t27Z2dnrbP7rTQb3d384Ycf7p7jS+XAu1Ub4/XTJxjr+7ukFI4tUEddOnF3/eB9uAihL+JZ0ebn9tiffGL5Kz+5x4fOtjYDZSd22PornIUSyEWpvtN2X0QRVOBlEHo78GL43IVvCN9bgZeiF745eh8E3gC//xl4E/yuBd68iy2ZTgJvCK5+OlwG3gnCohDW+wxcexBrit/AG8MHh5bKG2Ft0Mph4PW6aJypi8aZumicqcv79rl8j7rY9x3oiWEcTtIRm+jsL+LojKx0nkm8bleIa2+3q0hFoKvR/iysT4taLMFtSbKjkwzQ0HddIjNAJXvexSfSpzrxASs3sdIJTCXZ7pY2zlAFZ6F38r2MX9+b1s5qYrR3u957nQkdwJ/GsEqKMD+1UttBbailOn482O3WsYFOu3D0z9OJer5O5j0gvCV6fU7gyP+0i+Tm1vuTFmCOIiWtdmyiMfJrmWaFbxgRUXoHPinU1i4u22QVF0/3LctIMNvk6akTgSfeQVqWKEw3qzJwCtL9Zek3Kwk7IydvpRg0GmLl0UB7y3g+xtmGLAs4jFxv9aPF6iu3Qs2iCFtsixlGIEKf3VDfL7RZEEzfVBbFs9W24a40L5C3B2unxqBeNUrDaqzVVOi5Z9YwVmwd+fWq29jeDJ/6UX1GQ7OblBqJNUQFcNQLE6VCgo+oFxfMWtDdkinjSM1m8xNXLjJrkJeGV2pDSy38dcFYu8OTRuhx9cn8ilKiT+p9cr/Yur7yaxtYgxZsM6g/xZhOcEhOYbGgLh2rz6SrTMM55YIsiJlFTfGyZrtosRIcNuSHyvqMrmnEfm0BrLkqlTZ52cqoNZimAFTufcJ686yNScPmFbllnk6DmiP9/RPkGoY8IT9hU9qRp5TmtAsvJQ1H+fPsBbKgyY5nO/GU7hxtKiv3EGUCodSOoQahmoonQK7itN+LARV4ByfQFOyOy9oRDi8rk7SmEVfM06umhNHHhQ/zI1N9iRxFmCGcHjrsuHi3lfhxq9owmXJxS5q3FWOPxa2abrmy2XvY7AT6G0YQCZoBKj+EI6KBMtAopt12y/Kjv8p9SmvLIuORhawkMRaJag/9eVSqAbiqsxJdnw2N7i4u1qKWWMLUnd1K0mGEXDEo6IcHyqxxhzQIA7UWNNsVi8dodPAZGgOHMCqpeWOTSitTPiQtojBjq0PlwcCEtQNDJqWKVjhDWpb0rKLxhwiWiW1fE4aQa1ZTK66QV7uyfledtDI7ybGs16UOqVavMkfoPGLNjaO6ScGaaD0gpT7iTBTahD+1WT6Bo13NlDt+t/WZ/B+ewOqy898qtQMX0p/rm1sbP6LCorWPMCzHyTs0NZqsrze3KpXpT+bZquGdq2Z+VK71COc7GgnyPwyRpgmJQS9bsFdGvGLBvoRualZ7Ju2TPVIyDFHTOai7C81CXpHlio5d0s3kf9csUC0pmXPVjGMAyMrdBFwK5MIa9FVFrZJZm0aTtDQN+MiWopalPSl8Hw/HsDGw7QPWaY2KdGnEsihpOc85oyx3hildg6B2a4cUx0M8XOg53j5wm1IVubpXlwFy9FtJwRqAr8SRj7HLKz0+Tz7T55UiCPeVupVZeTMSGy02XH5N8S+weHOqAgJIfnzWVRggUXgp8591YcYCYjqpdDFSdpAzEjqqRkgBPjDa0chIVyfGbrYhn+LOnXd+dqmL8Qs27FsZa9T3F2YRDTAezu1+wdHHwQ0TR5XrFOOwUNdafVJxKEGsLJnvpFQDHFWnlrMXZ3khivFIJZnOkeePVWwgCsSfdZFKPsCT29azKgU7iclO5KCosaAF+EQJYNSPyiMcFcCHXjXbwzSl/eQL9kV9QhF9sRipTbuimeEqjkUuEHT+jmxoB8IR+kM7soNFtXaed1483X3W7R08P9rv7j9/1tvZP+o8f/Zst9Pd3ZG9Gvrois4BXJsoqZv/n713W24cWxLF3vdXoHt3y2QXCAEgwZs2W1ZJLJW6dRuJVdW9NXUEkFwkUSIBFgDqUhIjztN5PCfm2GFHOBwx4RP2q8NPDkecefL+k/kBzyc4c62FOyCBoqp3z5zdF5EE1n1l5srMlRd2uuPB6kMSjd1Ne3ZEN3tg5Xujfc/SK2YRdT9GexDJ/Z62z+hWrXyPkfNo0gc6GdRRGiaceAfWyN7qOxh301hGalQx4CD7qoVf1UaZlt3C1ni2aRZGfhlebHsdq7zMHCRP/eXwZHIZ+xS5kaMC2bbZyVl8WPnezsHxedvZeLxEd+/y9a/0Ug8YOat8oeD1AIeq3NZPz7q73b2D4/02O5ys8iMjBg4eyYn88EDyxvLm5PDw5AO0t/1UgfZTIwIxwHzIG/fB0elhFx/t0J/np93dgzcHu0vKUVoX8kccLP1qBad7IKjlAB5wjDhxy+MHcttB0DVWRxGnY+Suolcuso2i8UgTZqEmeDzGxyAQhE/zsdeDjl2kp4cHt9CA+Aq6HQc4nI0N+0kY2tjIbTiAEtHD5igOPTxAqyb7NoBBbRcYVPubsPY3fvXt1YCubQMzVAAuHh5yi+W0/PDwM5BKMYvMWjTzQRS64Uza9tor4kv8UGGK7gPLs9+b5KaTYA79YKOdnKirSeYu0RwwBEObsMOfpzoQ4iVOmDwiCSCP0GPemJpjq2f37LnA9SGUKSDG0A846j1+EgWy5TcKnBeEnnmxo4idU4P8I9LpWNsO0NKHBwdW/OEh5zRts7dYMkjVy0kGbSXgq+8pmQVx6vOIWltwrFjSrtgbJ5BjYcwtuvROVLRVFDzl9InterppCc62I+F3ZjOTyl3CMu/4vBrwUPQKB6NL2/79RgZf7nNqlDWnAeVpWgoaldmg1kY0RLFPNfz6EtBHv1UaoZU4eCVAcL/aVhIggjNw6aRfLZcsTbK1HcpnbZlmcClZ2/Ddf1ze8rUl3oXzkVujwVJvl+gJYNKlNtGwpU1/prsSnVcd2qTCjQzfcHX+Ad4KHOKtwBneCnzpdari616nJr7vBfZDb3vB3f+7XuenmTTcwj+d+1E6zfu7noTZp73OYFEKzn+gPN5SdDIseVxquBMVHTijQr8yYNBxffVtBy3V2tC+Q1nFvVhr8HgPp9mfl/Sh5VbmDqEpj3TU/yCgLsXdhNEcVNml32glzCFkWxa9/2Xq7sOUtSDUOOTfOff3oUdBf2MDAxX7e6Tj9dOFQ6adb6FVvIr59uOF4Xa+1V91PZjDK/3bj/oWUmTdnBlj4geQpj/OnQGsM2zsq45+QZ+4zsAlHq8dK8VaCoMOs1fmF+LGggtHmqLv4i3hI9YQQA8tOoG144UIHyxXxW25IIyw7BQDwyX8ZqltdHbnuI2Mn2Rv6B0avtrDV0uqwX7fo4KhgbmiSeesdA+r09b5Guki9tt+fFmYZqNNRMNtA0RZZQBTatVlUBtE6fOCOHfnXPEOiPCNH3GbNsuGi2JivNzNHMZU9guxkadLndBS5bKv23a4ho2zUiW67UCzj1FvzH7goGI9l+wLMqbRr20J6A7akeIXKm1GpbShV8IQyuICP2FeeNEXU6LZNOfDLA3SM/qNHwkMPGEVSaBAjGQ+MiJgso0/2/7kxRgQz+zhYkoyQNmh0JEBL2IEVhwOK8ZiaNqo4ZgSgAv6aA5iixd/hFKuOSD4kDj+swmQ9WHsUfx9BqwFoEZVUj6oxWbCAY7QS7EoGFkpMPJPu/L9bz4pKsdlAqJ/roD4lgmI4jG9cggAcYEbBpNLwZJDYemXNCz98jgsTTEbF5zLJhyo/Sk5pyN2AXboNgAMONQw0yxvGYDwRidjHngRYvjUAAgdxew7a0BvnGFbQACFnWGtwFYezRnBNtJz5utFp2nQuRuRuWfM2sCuO+zaJYR7zhy0DXGAHEFbEamgzW1xHQokpmhQ2+bzrAPiPO+A8E+HKW5DZNWQMriiT0K9h4eOPiQjYzH1dC7fmHQBDMqrfWOzdtzOPb/jbx/0RA7RbJRYDKlTFo0ruxKv1jnsPbzuUfXnfYgglE65EwKgy7FD/BaNW/A8HZAhgaX5lhNeEML51hi4NZ/mjNfDwYFQlUsdYXsGdHsGke0ZSJdzymLwS/xSHBQHPq0k4iCglt4S66Wv5RhqR2hpMOUHmHNOJdpkXq0zrBX5/bon7syBxnt4nWYHIBRZugCM7AQYuUvR5ISGUfCjNNYd/TWxTmSTYYRS/93jIONlPwRmGv7l14/6Qt/G8sF1mLjPGd6fe506qYmfe52mLIs/UTsL8Vfkgn/hJf7MP/+u1/l1Jn7X69x/9x1rv306EwFEr0FEcJgssgsiCLTPf13yfDHM/+zvevEHKn0C8iT1IMWZAZEj3Y7+/eB79/sBMHLwHX0wxg4mYGkLfyR1/Hcr+gzExYlXGRrOVckZ942SLNJ/JaUsCvSBqmmi/78sqVoZs9hPMSPLH2X6j/8z0hJ/Iwp/HNF/gJWzHZhjxQGQX7htQZ3f6qLVxSx0DvwVYJe6nTcccqPXRqY1FI0uXsnYXbaKLv8c8M8p/1zwzyH/HPHPOf+c8c8J+9yC9iKo4ogIAfdABkrUXSZ2o2+BMBlzzoLCMhQXE487JjzpG9xhEX6R4D1NhtuhJjOJh6h120MDBBW+hSYWCwBJfAaCgxsbKeaJBFmWOR6I4UUvyH0GHO3xcTqijIgSH6UDT8JROgVH6QSjdKKjdPxRDhKjpOuZNU6z46TGiYVT4zRj43yp1Zx244YHsJpEmrP8iqxdeB5vFErJCBREMqbUHcpDs5LIr3j9+E/k2P0RedEReXRESwTchPdVvDkjazhfazDDbsosI9GgkzEc62sNZ9TNuJ3hNbYya8yzanxGnx2LVYSj0IpWtLh4PotXhKEukVZEn9nwjB4Q4y6KXJecolxT+nTHf/X55y3/PO+GSXnDrzddvGnrAe1LG3p79mIw4Ra29Dszo4UvzBzYWNwyO3Xfb0Dgtu28Dv9F2+TfoVXf3Bw/WTtD2AIhYdudssXOsY9mFvGBETnUm98JgwXaKgMPxO3ofaP6iNE7NAEMTdTGuNsNbNL6s5jFECZO6txlPMu7Pja5syJeAcbu6mI6113DQn0qt4E2LGFh+do6Byr6alKrYzhjetS7W75G5EL5GLctjd/upnS1qJB1UQ80FHx/SMFvlaadJrcEFg31g5H82YIx8mguOJwsoIooDMlgiqpIkydKDtOsoe0uu9ENPIFLZdQcErzIUT6WtzNuoMMkUP5Vn5//lg/WHyM6R9I14flVJUkqs6R1Q9v67zzBIiznGk3/B4MzxtAaTAXVoZgc25gib3Lnd8iy1TMmj2XWYuvdxpF+EzrZPTbk5AihweQIadZf6IsqYo0BZvZDrSwJlx4dWzpky7eB4kzV1i9zPM4WVKxFqkaVw0zZFwNNDjBx2PQfpjSYIRhFLgQu5I9xP76nQMn4rSFIJBlYFRjc+Haf0ZcMj4PkprFr5NKf4eDffTB2y6hDc3ZTE95hWnYGTyg8AMpaQBBhC/nKolevjVYtE/SnZcbzqDD3gSyYrcRfDhiij0zLdCd+KyxJJAM9AX9PMxIz0szUuERoazIUscvBRJgZd0GKRBiLMaCkbWiyLGVlEcCH+LAkqgx8SASKRFRhi97FT5OP7F48BVZMBLt08aIA5KXA3D95rRTQPQf2aot07mmKRzI8sbhbMLVaBjFs7pi2Y3p3IGNHTGLQIOamy+8CNjbwHAWs8+DZhfVR8utQS5ktKMcNHS1gglDs6tDSwxkLYVNKwfvuTOIptBHgEWB0pSVVJTlx93Vg0XtUz+wH28nruZiFkwjfUreQb2kiUPa9MrRn3wItGFyh8pllzqSZ53ALyS024RozEqTwFg7Y1Zcwtr32HwShItBm2gL9R39VIq/08DG2Dq/YYCMJvbMSd/O0de4m76oyM90ZTbdZZr5xHNETDq8g7hrzcMsTRsyxd35e9nh13xM47ka9sQEPcpuNvaPWr05eo493//CQQFq2a0OCPB2SWJwB3S5oCqiwOfUqQG2wOVeCd1eYsN3hN2V4PlCPIQOYlOndCBOQQmF7ivjXBzhB53opL20g2zC/InpE/jSTANOHeydHOeZE6ZAGnEXg5o0MOIP0kJzXiB73HHDf0bSiSAWwQ2pYR031opxEQF/xeCuRDo+HgVkO0YrxE7BlJV1E9oeTP/88Q3WG4bjYOjP5gvWhyxyk5pSEn6GVNoBvxPSUdG4x7gKh1ib0MpNqK0xuOxl/SkJrHzTJ+iaNw/f9BZq4U3d5ReQw3vbxWGRrQ5xThonH6N6iBziki5wI7nGbV+JgYKAvIr0SGwD1dt4nWlwG85DQQdOBo+ytbV8xyc/uihmP96gh4KnhTTpuZoEzgh5ZtMAgWoAJItPUo0iDi9TLSGNDfOmTaOZi2BlFn51hDIbOnD4iHt1gFqDK6cz4Qz/xsP98Eq9PI8N0rqPP8Hy9ZJX5e7/uncjs89ia07v1jjcTX1MLOCBFgN+XGxs3AKr2jeTZQI86/IdLpiMQ1irKnyzj2hwb6MCPMS12xghmUIbcnoyAYQbEmBEdGnq0WHc4hkLUXePh4ak235gOGdm3un/9tdf1BwUnmRFqgQb2dGvz35UoFdh+wEga5fZ3mzT6QGmvWw7ZCMwYWtK/H+yBsELJCh4JjD7tkeuebU9ZelEDUMpD5miI6VntOUU6dL5zTNRGtx8nOPDTw6bg6IARI3GAEbX1bf0PNJMzasACphh9NtGLE/g24W2vdypw+8sSt8dA5ppW39wsF+y2MjI+620dyIY+AvaqckOwx3YfiKZeXvoJ5SmsxFUKqOknCBDxI7hH+YSIGBDETwEyKhCmh0WB6BZP+8AuRHRQcWd2dvGe4cYV7U7PDUzzQls/iccqSdhV8KeC7y4bDhq7H+J12gAjnDCbFrqFMBpmfuo3iaVLwbBF4U8787mw+WM5YuvSjvjyBImV8bpS8rWvsH8ns8eljZ/Of/GXIRRdsHMmBQGI9uEsuBNmxOAlMM9vRCAJBiR0bw3kJwEsgGK2/wBsB5AbxoZ2Ig2XgIDu+hMrb0GxqHjjz3MLQIA6OXkRrtFzzIF3BESdWjRiglxAuCEM3RyZQKsB4czbiJRVQtEn+R7r2NY7a2DA1jDaFa1idlKvWY3d7PJGJ/GSlT6DgwBQAYedqmJ3skqUUVX0E14VKCLa5/tMNapD2RcT0wSL1zM47iiHHYh14oRaq6Pm5W5WQlUPiYJRVk7u9XFF9Dq58uwRsq1zpvYH+AD5ASiEb8YvGG6WjBsZcBKUou9i0BOihe5fH8LSmYi7BuKujbjrAu6KAya6+W4LAQpzP7psEHMoiFmPgpjZsTJAzHoMxIyOlQYxKx/E7I6VBDHrCRBzO1klsN7Ij1UXLQ6rE76IAaKMELO9zdwjAQIHFAZdCoWexPVenV/nPK20FQFKGhEMPQE7hN6j88hgsaBfNAW1UbJY0C8W6Su62egdzht2xKBpaWpYBKYo/orOaaiaHVLWMBcr+j5WcD4vkNd8Ieby8qy7s9u73Ou+752cHJ5f7h+evN45vHx7cvLz5eWf9EUoQzxeFMjYGO9IHZ8HP6L3gueUK4lKJM9upsSwlQlhS9isccculegh2Pnx3pPgpLcdz+1M2NtL4Ix/JH7ktNJm6cKofJErrY/l0sVO5c8fy5tjUf9OqXyn6uV41BjxOlH13/EaDxd/71YuP74q/f0N1uZUpfOjtW3FQ8y0E3FoyuIdNnmPx4LXuY6au0uDieHseCW5nBulBvaPdFD9Rco4LGAsYGlKQe/ffAMoSyTA31kJNTC6Tk2hODtGkG3zfLEEQzSwgqJH6JBQdUCHhRIaKVOTUKoedj+Y3qSkG45pVHTf4omGi+LfPdPD2FG+++ISAK5zfzubgoyfEUtBlWV5070e6+KNOfQmbbUmThiLA98wcsBr+7aty4IsqDX4TxdR+GvrFshFugjEyb4CZowD+C7eSvpPP7Dm+K9DoI4DYw4iC96B6pGnuAD+46XY7wxKC9wYB5ZWFvtIBYCHGQIDXi6V7tm9J+kkezS/kLbXgRFH+7YwrlUfjoGFB4AaPndEGnKLilCUNPsHQdsQTaAgKKS1bRE21l2KA9hJOpDYRXm5pNM1u0cDiwEWtQhfQM9fP89fHhIblbN9TF37gRL9oNY2+Q+v3LYiw4LDUJ8uBkDH0dMY20ez7288UnKBAb//lu7+xBwCnf+2rXvOAi/62YAv4MOWZsa8VLoAUPyYM35ET9rwjuMYd5Lp0s+SUd422hfGx4/w8rbjIzECopW5H8GILWzLWcJos/tzCFssM1xiL3PCle/uL0t3yAssQVoPnhH4ZZVZJ6EMblEnz6lxh4107ih5hTGgaK5Tt0XTu9PFiwsdhOIJbNewrR+pqqCok4oq1ZqGKqgCwrZcUaRWVVCkWn0Kb6qa0JSqdUNSNfiPllAqUF6QD1sS4oGkNKMvZfYyUnXHb1kRalKtBT2+VXXxityB/F1vfXFhv2CNRYONFAjoTYWGvkmMVVEF7Vqp8ZpuvdVCk46PYrTQTMHmKw2hUYF//U7M4edPvJPzsI/FPNHDTIO6WFOAf3ndiXEtA3AnusGxKK33Gi90K88+txzWgU1nAWIzxtNKLLYs1AUYX2Na0Sp+XWU8G6kDVtdldVGZmjH5+nV9CsvN681mV407PrCB6QwwJMr9AMiTAiUGd+zTgQ/Z72g2BthgHQ1YR/acAYRDzYTvGc7quMQcbel3aLOpi3f0rwM/sN07+sHabXy6I0ZqhWqCUh8AJCkAEGpFasEf9X1tgMCl4C8Bfk8UeUBLAHxILfjjt/nFvG0tRmysUzbW+SJjSVT5OhjGdKJcZW6UGpTxFq5cnaXLNGINOdagNcgsFJZRPAek8GQZikxBGa85alpZZRpBmYZNzPptRpmwiOEOJ0ROF5FjfX1uzj7dZBYKW1JG89HVNKtQpIzd9Jz0ZsYWqDa2PsmzrDLh+pi1u8mCFeHABYBTo1BU809XQP4IoNUD4GItXPfvho1kCwEc8haaYQMcOBUfglq35sJmELSgEATEcUBBaDVseQK9gvEOWvNGk/U3ZP1xTVAG2Cra+6qPxq2xcqukN0WBQte1gCYriDBvtejvinpd8YmhOWlY1UmKGDYERRY0/DcgN33HtRoyG+eIjpPckRShkuQ6wrJUhWMBRsKJN1D2eqsObUoNjf9lL4Bfbzbq7KtfVsguW/HL+utmDaYD+el1rgZw0fjiDNn453T8qMOqsIQAiYXWYMnqkWMNSYESeYAEZ6Ko0QdAoxp/DgjB59GXRpoQAA2O7Axrxd8Iz/rsTPvpOrLQetv0t0CZOVMnXQZWqxoU8mpEltXMQo2g0BdlMakabDFmwWL8rtYBRjZhI6M3KxlHoionOo5yInhIVBpSKwL4CgAWnCfAfNSFqtTaCSs3kG2pvq0lp1qNDzKY15VXrXNUGNMxjqd2nzyPRiSOHEOpSQD3+Ef2e5aF1MOKGrRVtZUv05wTxS/UMmvzRY2N+JKOGOSyYWXomNds2FMTJZH7WwUIEwz2VqUE6k5hY79T2Sfr8E5rmnaqQ02qAbmQFEXArq9TUFKPb9Z1BXjEKtSp1KVmdC+UugRYXnvbABYxxlk2gAGC5r/wYdi2V59xZIiMvs4GX5dkhY+/zsdf9/m/8UilBDdeETcHawLJya2qTGvGgHNCu7iKsIvEcdOEWmpWGXsbnUAdiNehCsAHgwupI50zlJ82Ja2JcKlEFopVoq9gsVrRShWs5C/Gl5vqJzsTBiJVoBFoHRqrZ3SjRbrZCetQNt+f/c1w8XmQyZe8QC8+33z1uX99W2drfE1BdWbcmjOQTStqBoGqToC7DZiZ1ujGSx1mcCRWKyFjrkxVw01R0RlsmCKErL/36VYzzNRkgddU3lYBeHmxG+/66vqajfaOjZa4qN2suJ8XhkOyxKZG4nAGBFDjkFJDVG9SIUqV4QX+3ZEagAP+KQkPFUlt1t9HTnbGGNejDwTVhxCl2Ww25mygNzjOuTEnQKrMlCwDJ0W90sQxCLhVMbyFkbbY3yktUWElakKNn/Ma7HGD/Z3CyyogLRTRFAMa5cc7VGxq7O+UlqjQEgFpNMlgwcbZpws6J1aF4Wli83HHJv6JpnxyLc3MYIckpVEDjGtGUQHBr1mnfxuHValZU5HsQMHILkgaIiVsRlVF6bOqqQY88gmwVFer8L86xTdVWiqyTlATZNlWI1h8o7lw+aRu6aQcdhVaGdwkp1VFpG2BtMe2sFWB78gEtUKuCSgkSs+N2iEMzV+A69ZEux5k8YPVa20SSo2fG54tZ7KNkW6x02S3Fey2QruFMfoIUF2Yo2k11V4TSgCeBL0Orus+k3tOF8AlhoNeqRdJVFWVCqxpjf7xa9c+NZxPWayews9XhZ6v/lLUyKdWgy/3Lu/NSrPTgGPVOuJRHUA4uretaqMiyWptWpc0YDsN2Mo6/u9DRr2q0T8AHS3YDC1SmdbDBqaMp4ieAQo9v9TYKaaMRrd31QySJTU1qiGpNSpwIrVqyAq3qi2/mjr4NOf82w2fId7RZgjlyANERB0mKTEpPEMmt8ZXN58+x6SnJ9pBQT+jIcDiz2br6eOZH7EBCa9/GVfVAqd6kx/N/p5bX26ady5bkR5fEQ+N5lKnM7B/DcRopQqkDYBMoH98LVNda1FCF30uwz5WUT8E55kmJOvA1ypUlKvVVDWs2KwqySqV/CqVR3qq5IwO66iV7CrYUyVncBU6uJ3kfOqofYOVBqKduQysp0Be18jg5nlSWJdt0xSdiNzKNeYvGxjTFJrCiRFIB4rrqMYok3FWrisBdjTcRsPMKtUMxGel6tQ+u1nKGqUedDdRFp+VeroQqgqDlmxlcf1ZySqEY/IXCriBejXdFFDSWtBdf/DJGLbSnDXgftDboN90B7OMMthZwOLcKAvPZKu8x1Z5bqAjbppVVQClGnikK7WIwA5bTBlPBcEAuHpNa8YYOQ0JEv6d0ncCLRcV+FkL00r0dZTDCRuoRPsIWqj4I2CvK4khsBYqvAX6spIaA2tjGn2bmANrIKDFrjp2nCw1F4irgUg7qtoZ0pYq1CaBUmV8Y998qmcgRY3hBJLSiAaofvX5k8KlihO6Wx5xZpgILksD1ApYnr5B7Ntm6uyAhW0AB0f/DUQ2a3znsR6uWA+OAdyHmoFsihLw09bAlu1ZlvweKWQvvGtlkQX+9WslqYdqxPVQ7/1GZuad5wwysKM+CSj8UL6ZyZ8yOI36+1qCCa7FeeBAu0gaLeUTx4sdug6LeY6mrXodyj238ifNTV8YNIQmquMrIPb6WtnPrYbTfDGdHIzyExulm1aAcPqicuYbkQKYpret6G+hFky91dCuyPQRQt2gMBnAeePOlTmdPgrGkCYf9cxB1HMGodzdmd7nLN0UMEogA/m1FKqTadSC0dTHTvNTFtYle6/ioRaIku6EjIcZc25lTdlajK44i3pMZ3xjjszMq4MJZUOY4E2uiNnKkImbICQZcCArPtMOZMTXxgytuQOCWQadBzqsgZQvo/qVU+JaqPG8VUg9jSRNVA0Bf6q2DNTYsmqNsFb/bjDiNyI9nNZtak6AQvBvgGhKf6qN0nSFlomoA4bN/lWdi76ndMG+GElhEi9zIudKRWogJa5Xpy2phXxtRKZSQGqq05tDINsqMiBqREMAwp4iTxoR8g5NCbSpCrQlJNqqQFsVbAzbqiTbwlUNiP7tZ3XI9Y1vCNpcoN1ALEEP/yp4vhNDPEqc7wQWCZkVGISUA+vgiO2eS3xr5si168MDkSz6mdEej00StOaHFCEs+oZw3WZvgrBcOg0+IxDivzh1bNTwOvzFnf/8PDCM4m+coIpv6stf3CafY9AA/u7cf7fj3xaz53bQGEZfimQJXWaHGPOj6vim7DQEkh/EP2WOdkYGxMR4otSA3c9DIbDG0OCDx6anxue4xm8ce4aW4aWyJPhZ96YmkMW7whnwwo3kS38ZrLDteHBis4lb/sSFxCbrfg5iVs7zy5WIdMnNrnIqlF/pku9kz2v32zy3IbeyDG3qY72K0EwHoNaKt2xxeNN1kQaX0rf1N4FZgt6O/Cjpr8grvYzTZx2bwfSsTmKC8cBkHkYZhuUqQzc0IXDbYi0YpI1VL3kSSZEmbkSTwmhOXKhdwuyJNB3E/XIZQbhlgJWRhBI6jDN8gdGx7rE1yzcBxgjJvDEMeUyBEIp0OFwFbnUUvkSz83T2Oj/DS88Yb2yQi/TTj4jX2L7nLGieOb7mzK1C93fM4ZH6RR39h7iJ5RBdVhFGKXxzfzo00YZhCd+7HIavMaIC8yjqo18XcQaEe3oxsiGwBDgC5moaox/dhDgAy2gRY7HYa/6KmSGB61xzYqP/6Ud9KxNbaayvGGEzSFBJkiSoh6vPgxlH0xJu63/SX1mv9B8BylhJviux2pGBGYF/x4BIOyGYx31D/HyEpXJY0w4zVXBzWGaY7nrG4Kri2fPKCHOc6JEqLl8FIDR0UwhNP6WXfXcc7hHDekMfCxBc7/YIi9phO0F5LEFXDk23TZcSFp7+phzE1g6oBFQJTDfDsQyYFXwE2OEHwE9pRNCRO04Qv/0enWuw79DEF0BpDoDi3PEogOhVylxeb9BvySHuYkpppb4ACjIyLTLUebhmNjQ0Zz8YUacn3z+At0HdbqnTGoVA9MREnyn0SURLsNCTSKS13Ym9gKeBxy1mHR2aoxGh7otsnKUcZwI4cAamMa3Mqe/9t2h0tbQSa4rrwbeGTcTfGljCb2FRvhUxnybah9nWyBwvqP0sTVYRLvc0gDOPRX6ktMuHtzm5IIDPJfqZXn44/HBdcOl8o2qHjKinJ4uuPwzOF7z3FvAl3acbmvZ1vJhCz2wdDvj29ElQdQRnF11ctOzv+pb9SAmoW+xogRH9oTQ9tyTMKsbdYOma4Ugolef5eBjGhBMfMntLP5oIC7eE0ZBHIbKFwV/GIs/RgRyUJ9IeYGEvbZoN1FmKJTvRle1HDtvO3SLoC7aIWHi+sa1RRApZLNxNub1STdxqqATn9aWLScQxrVVOA7yE+C1NBoYOHNBaHEgUMd76jWN6HHz4GDHnSe4AL4eYph3diZ/RMpv9U42fIz17Ruvm0033DPc5LRthyyyZ9sZGKZFcm8FmohjaLIoR0BzxoCy2OBUXDDRHGHGJW5sihR0FlJMSbpv+XZDSqMyyMNkdecv+08gPpG+/elWel0YX9sfyVmKE8ZGMypmx8BmL+Mm9bQtoWW8OQh8ITuSM6Y1x51IfSEBOahoq+FFZOcMJ7OrUHJje9C6IqR+06wq2E/7a674Po+S+NvoYXAM5aZp/LXQbYkOd46Ajh5cVHF4jdgbj+s1iXp1W2Te6zkjRRb2gsYVleQuW8U8zvojb+j0iv+DaM/IzuRMF/dWMW2G3BTi+4QEwrPTrEk75WOGlDuh5MXplIzGdxRt9ohmomiS6lGS6PtfPvVxwOQ2Bkn36HgktO9XcOTrdszTYQErb3J2JNdIBtgo9l/70vSvcQ5/06VLY/PEPjGzjegWsFve1Gpp4T4JJLWiD9BzE/IyM3WLd5fcCLXbu/XWJ96kDyI/EmTgq+8uFfiu4uSOeEyvmE4XBb0fAxb+CT9xU+szCLebP+Xe6m3BmhPlvJniEmEghrfLE32/0gblAf3/4U2bJQcyO5Z8GIxDGSqaYJfJu54i1+jvrykLj3DYpi3jejPCsKZUpWofojrHb7tERadsnzDQqD/sqBSS6owR+ck+wpKw6lzOo//DCpQ6Qiyka4QO/sz2LlqDUq4zNxB/FRpP1Jj64p0YfmfIsgm9Zc+IuEJFZjWme6kkHwzKMI2mzOXcreYGkbUwlzozo6DSSLjpnYiu6haRf+nGvdXTxSL9mXlWXM9QelNGNI6N5X+9AXTLS7we+RIsePdnvmfQr9rPGx0TUS+AAdOrskDFGX4uBlvj5ry8x3RiUMbPawKhROjUzT7+bGl+AvIrnGa8C03lq251+j34hl+FW6dSMO2MJmAMpxnF20NNXp1bYE+nycvfwAAO/Hxz3umfHO4fnl3snl8cnvct3593Lk7PLDztnx/j97Pyy97b76+XuzjF9e7p/trPXRfNofgyEsRMmhhsRatD+NebYgAaqPv3lWbWAOdhOP8pICc9Cck4693RWl1QAu+zbnmfPLqkMlpUhkmBSMnpmjQhabQKNmuHc89pg+eUmoo2RLCakMyQlE/gBaqZ3v9wikq8goz7q7HBN+FGKjp/9SyG1HweoWxlAhendLp3dkIqYlN1yX72iSSN8fpkKmBIdVA+DrByaM9PbynzaUeQtFr30cak0p7bNDnu3MyMBRQ44eFc0tum8gZFqT1DA5x5l3WyPsjeEvT4gnTGs2l6nC39POvqmMZ/j/3BwbbrOYHNnPpc891bfCgjXISndI/KjK5GFlgEzavHE/Yh0CxgUvMOyLR41geYGb1vLMnWFcWhwh0hFPpWSLO7xrSmj8fU1Ku0DFxd9NCW3IECSmVvBfSGOMDbmFVXSeJ7pCjpVCd/ds3DTMICpvq1PKg2dRdSeojcsfaLUgKOAD1lfRpyXLp7oHiQsAxN5CelxfALGwBzd8Z8rtOm7VwkVYOeIV1EE6shFhhU4pEAKnC6cymwo2HMDGMa7SkOG6Tnben9ccaBMXZYFnp+0Ml8AXMC04NXgzrAqWurdUl/62dGAbb9H4kwHcSKiuQXzo2orSgv4rOliZvEHrSVNTFEW4zNh3ltZq3NTaQoT+J8OFCk4HSoOB4O3VdyJMbRvKhfypXzZnN9esoCd1ZZYb+J/stQqf4Rp0Ip0IrVHa9ZFpamKqqLymrCh+U53cae3vE2KGbVreO2qtAZSk90cV6QG/VDwvqEi1SqSWpGaFfpEOUTzAGVaqQn1SrWiKJUq/KzUKmhvhhaytUFFqkpVNDBrVLBp6sciNVmb/v9fCu2Tqsb3SVGyNyp2+6Wx2y+N2SRL+DPYQdgtXCW6W7DmsAf0J92DKvwuNKjqMwblX0Oq0qPjMrDF6MgICqHTYfHB1Z4zuNbXXjKt2KhCh5YqM75q4Vh8r5iIU4saOLVkD7SeGKhWdKD1nIF+DGvL+bXlbLJSqLLSjFduZC9R9oGBfypQncZBA8GswlxvC5PoCLXHyK44LpTCB5ipvnKDFkwCDWzSn2KgO/p1Zlt2fg/u3LDiXVBip95Ow3Y93EtoOSSiNxMYQ5oQKmpAQ2NBjxshFaU1YycdnM+FtrxaEJ1zZlSFGUWWpsCBEJnNqidCWDXjSAhnXgzWq/W1Jv5bbmW/2HFRba2DvVW1EFNQkGPDc27mVWRKTFdDkovW/PZjiGQcvOzpMI6SLsZKRSN3vHCMw10m8NSzwK6ZBrvY0kOr//y//G/C8cH+297RzlkXCu+eHB3tHO8Ju10UzAptTK3gqdRfgKyDS8Iixfs/A9ZapGEL2vrP+JNYorCYCUPDFY53d4VdGtR2ao+FLwvhL//3aGQRK3o88LVt4trOb4EJnd/B7qgC8JJfTGtQacKaTTDwSNvnLluyvFn3H4ZLBIeewMKm8w9WvxHWZ08DDpVWpWWwKud9k/vrkpnp7zGXmCsYswjYOdd2KjxecBQprqvAVKnF1r+xDmLUqmsca1Ul+1grdiYmSJTGK4fKpavSPdPHE3Fm3LZR8pQ5lFjiwjK9ttPRv0e1KsaEMDv6H2V5NBoAK+Eu+rgxbYMJdHZHqcpcdHM7Jbui1MubQBE66g9HwCtLpwc/uOK0M6jQXzPTKrEvxm2JbNLA30r5h8EKMl5wZD8iZAlztGH8GsIbzWLR5sbvts9X2ct8WkVloWT5GH4FWvuKY2NIHkCg/MFHGVAbF/qOfmCaez9gyB+VgVqrNuOxQppczKG9sRyXhVCg9QxRIntcZmI87NeegZl+HOOuPYg8sUcjF6/qcgKcpKfib0xIBTDjCNatDIP2BDhVXAFvQmkTsKFtPULuSygTArWHQ8FcNptlfVlggVRZXodGtJTnHZ6BboCpBmShOG4wivyEMuIR5iWLoU1wNEI2KxPtLqLR5oZc2+R7pdORt4EmSZ79xrwlw5JSbsvF2KpbN3Je4DnOTgeABmE2TbATTpF9Teo6lOoK+6oqjbWYxAtFjvMyWUJFcPSF7ExsCSIztorMWFXWgGQ1eeasdNq15BwhztjYKLhgSmLBYsAwQ+0Ze0mG5mIWDUtUaGkaa0yu2XrqND4jpXt44tnOHRzIXBN1RgbXGMaH/TrHbMSWaLrHvmK0jeHv+MlrsvhBC5fQ2EHUDjU8U+kLFgq9XCr5MYcMzPzLI8VjjEDDT1aKL+2OQYOwsnuWkq4OdT+/VqSU6wc5HRJM4HYKODs9w2inDw8AS6yJ10iyAXLDfOt4udcZSPRMfHiogvS/gJ/saISKirxlsJedKfAOBn/TWcAPW3IHxpSU4FApww8a+5k2iUl+8MaQDmvYIfzq+EcFyMnFvUOX8gcJDh26jD9IAGD8KX+0/CiOOkNpBJzAkTFHa98LquOnQWuhBIaH6ASsiyJjsKQRDUb2gyIp2pYtseOG5ivr6IGoJoR/ZEnWysCVSwgc9BTsKDgj4uH5hsde6aIqVj+Wt/z4ZKSjbJE/dapb5NWrMg+kttis/UCguz4ZmxYG8C3hSqA1UM8uVTVMPcV6gJ/TSpP9ZmMrseWxOqX5DyWlQjZr5XJAauXyK/1Ih4bxcI3OQqkrosD+NGScRY1OArGpo4PIJSC+AVoOCD5GcNnBnL1QG7eNFoUWewhGllgFLvNVtbxMTPsjG9kMo7NVtVfkhxKMvaaVN4MVHwYZYIFhLIuTSGi5oIwsBkwmEedhIKtFRZEr3iZMelFR5fJSHHeCSx1oBcDab/1PShS8zY7NL69wpIazj+meMJMXSyoF0GZirjSqMqbB+mSMopV4pog6T0Ql8P/QYjZn/2awDSIOtywO/YjlpRILecdvR2YYZdHsTEreBflIcZJGsC8Hm+6IJruZ58sDFSoK5hGblIYX8PUj1hOBV/deOcCqU1D6YhJnd+HQMQDKiS6GaIR2lssINM0im+CPEnHQdkkwjxB4TP6LPnaNa8K+UEaArk7HCX6/ni6cTlOM45AXwxQ1sWSrLw9f4pdfHh+54KtD6JU+RzSjE18yl/YRPqFdxTDOSwGG4QxK2GFV5NANApVaDtZ2uTWm6l9gD51t/Y9kVIN/9DYV10Bgo08D5YVQb7L/ad4zKOUDplqTAxqFb7LbKotj6jINOK3/caS1iNzXOXCrNairaNC0otBGypEygHAXHN0+PsnY3rDLrUAkoyd3f8wYzs1aoAeoTMco5WVpFJqyvNmUn6fFTbDMfeLdEGIJ2UzZrA9jy2O5Lp6l/qquwpLnaNBWaeIGlnAC/8duFqPXiBq9EfBVO1TNJSS0Yx+LCJLVppbDTxfjiAM9UKDVi+p0zn4RSnuH5XaxkdTzRoKJ+zz4e9Sfu3oR3q7arD2Xz/9amwdbFdyGJXfqkqNkwR1rfcUd68GOvSu6Y0nxIL5j1mo71lxDyqk2q8VuwB/TUKMWVdJ8Paqv14zqUzMk2cS1kV6XXeEQCeTB5kmxNVxDG1ltqs+7ZAPorAmMpEcGn9AcGda14ep+BNP0WTDx7R0wjGWhqeaIooXqas/Xu1abylOS3hfgDZDxoNFjA6GNReKG9QNmuG8bDghb4gUel6kSoVkMlDBF44kStuimSqAASLM4AHuKOfRQSDsAOgRVbbn/5XK2mHrmfMDt9x4e9IlNbeAuBuJ0zcb8/HXixUIcpoeutFRJqTclEKhkud2sajJ2OxLnqaK8lZk4SbfCQp64xPTMMdYfi5epQiBwiBfX4l3mfKh3GBO/Hpsaej5fckNGJhz7fk7CT+cnx9LcgEGgJxX3U2Pv7ucDBty0kcrRyfF5r3tWOTvY18WIgWxb37VnM8OiIe6Ma8MznLb+L//4D/8AvJmNVzlHmJfQEd7C3ggfbOcKLVjRWlBENxxuxtLW8dDWRWbdeuSO2/qJRe+o//nf/xehRy1APccklbeLvmBcAb+lI0d7QQA4SWppvlEQKInokLztuBXf5FTrigfpNxf35hDXYUguKYiJACdW9toIJZxoOVgiXq7gGsHsznkcHHOONiUNCWRxSRFKhzvHbSEKdijaum39A1VruOgTfOrYwqawC5LG3ck5kFxrcQvNuHTI6NbAFret2xYLTDM3rfHlzG3LIhAy79IlSK0PaUC9wXxxSfOQazVJFR1jdol6O1Q/aA1JE8f+a2DRLeJdIlt/OYODDc1TJPYM2W/+DNpYiuESMnvQSyWyjPs7RwfH+5W97vnPvZPTylnvl+QC7iATUto3ZtTRwByXowv5H/9PfyHfWSAFT4WuNUbg0QSMMM3XMlw7LbV0bzHNTrhWSu5aVaNrtU9AzCYC6dN7SH9N1KZUiy1ZrRYuWFOF5YsvWbUm1RMrpmUumBpZsN7bg+OfT3f2YMneVz6cnP38+uTk5+SavXYWwPuXjuw+Zu+JLth//q/+glEwwUQ9zBUE8TK+WjWVrVYMroTSz8SxyFSoS0q1XGjltOjKvbcdQXUji9YCqImuWVWJglktBWVJEJOaSySUX4j4Ogt9qQJNUWSmQlNUX6eGNjnskRY8wvDx9FEtfKTwR/XwUT1dquar7SjE43h2xPc5dOYtEd+lX2GCoYsPRNzPefUzET/nNPgTEX/NoHfkRtiDbyWWRAFVkj1zRph7LxzjBAAIfe0ufiHin3M6/TsifpdLSYknel7GijM9a1s/fn9EBKBfu20AE5qjDUCp/fd/L5zfAcmb6eLIZaYAx7035yDT2J4xvRz32y2tCquJCXrxVw0j8oro1YS/tBpCR4BeVSRRxBgCKAAkNJFioTcXob9rmgRsc3w4KohgkeHs4XCAsmBwoZzRKC25ITWC4Sg1TQ5GU9PwlT+aRj0ci9psASkIx6JgkIfIYM7P94SqUOpGxtLFsdBTkqkpi42n2YKGgwEpstKIrk8dSobrg6/CIcmJ4dSE0pvIcN7gcF4bg6vFPH9xgJnUYJ7+YFRgieBnMJqGEo5F08KRyLFhILZ8Eq00KN3HzyL8hflK2/UaTAR/zTGRB6ytCp3i74HtELd9UWuKdVWsamKjKaqqqLVE4HlrsqipYr0hVqtirSU2NFFrijV4In+k5IfOCZqmP3BC7Wo9QZmCA5DR2OP3B3sHO8I+eWPDewFOLqEmt9Bid/+1Hjsox8HI6/Q7G3dVlXl71+EA1Fr4hI4CFrgePpoPvHZdK3jyiiPDci+d+YxBLZJpK4+tW8w9E18ptYmgqjNBabo6slmOJ5oZQsDpbmUHjhfMPExPZChpeKLtZZMR1xMHOa+mnrjwcriumTtGVsGlASLaqT5FHDGcOTM8tGptVW7j8c7gFFje2dzTfZuiPULm54RcAZN0ODVmRqUqNOTXnBAh90QLU4cdhH3f39GwBDLF+2Fj4YFoi7nChSt2+hk8bzc6CAk2Lp75xWAO/zTp3h946qodZ4A3zAN0cW7zE/S2Wb8EQBP+TCzAuk3hzEDne+HQuCKisPP+l4qmqAKhCS+H0h/2bQALgQdBEQZwFhNhZroucUXhmmBgBr9neh8l0qGhGCrw+dBYApYwAZmrAqj5eUGswZ3AVJKwTr7jtzdB/HSlP+zBnDFn3hfi2BWaY5yFYligw7tgYhYsdEOhfbosi/Huq1eqLBiePTMHArocOXfCCB1+XAmpxRWxXEStG+gU6LIqGp4H86AJmtsXHznDg9utxrb7tVA6tj3St23cuYCZie97VWvXZH/fcY3cYNtfwxAmIGZeCTuwXp4rbAjnEwPnvbeYIVkLdvwtwe12mKPq1MBUh0I/qD2ADYL9c+nSugMgb5Y7saG9wLOdZQ8zYNph1XDqMp+5Uo3P/J6ho+PdIuG4pPOa312SW8+BJZbm1ph7pKg1jdREtGjST4/3KdNlzjAPGfD2C2fK0vpg8AH61MXkYcAMuhMJQHRzDkO1K4qmyY2aptS1Sqs/kPuqpjbU+mgbQbuDlj2GtzEyvc7AsecbN52mLG987qCGmoUZAwJvoG22rNYrcquiYkhvWHod9o5NYrAYGpcMOS6HPAepNFjwCdSaaINCJ7D7Ljp+hY3/j4X78bhEeHc5hD28VGsTabgYXA37vKdmq+Yv1d673Z/3Xq/eG4a/o6fS0BNHXrZcPvfEmZfNjk08cezlMU2Xnnid+/LOE/s5dPLWE88zXqGLELzd9cSbjLdjx0QtTc/LuHkXu5lPL/Y88SSLIM8BRWvNFrDfTKq96xNnvrCuVLnRkMgtkxxRoqFCI54/WiAQgDCCbs24idgMMGoyb2Z+501sC+sLpdO7HhykQEze7e2UWXMgUGm0ORVkkrzm4Byt8ebsvgvMAW3t+H33eBeoqcKb4qJZGweY01BT8Wc3oNlXWUNVVegZfZc3A1IPbaYptXKnV1P96THIvATsv6KGTNBAjTEV7Wr+hLS6rPgNmC4wNcNwgRW+vsjy5FRv1PxpuPR8u5zZlgnHxOXQAMrM5NU2DB+bQbElZxZqM94KtVF1gE9weQtsPbOmgQhy5Yk72bjzKRvwjjzxOIMHnNs0wgDNOncNJ6GuSDKMAMkWzYaGJHBmWjTKes/uoZEeoPlcnWNQK6qfE6eT2Rue3w9Lw893Ps0EkhloWtpNualtDkFQlj65fJ124Hj3esi6NSmrFvkNtHwxNG36BLucGbfvjcXUQ2mZ7L8GXpwO8nQBfMAewMHe67f2wnGRw5tTh1iHDHeGcLLgYdeFQwRIpyeUFFnY73cxhMLUA4aFqT3KGMMg10iGdOBw8xeIPf6VFJX/lqJCqoEdDtSl9ipBawQvRtmNaLrzEcGQZ+htaW4OfBNtTGQ3IVaJZurDhSyVwyf31B08KLuxsY+xNILf5WVZoppI1v4S07WEXXA97SbT0z7Zy4ylzHRL7CsGVOHqFKZ9vYSzYGNjWMp4jGVdplG9RMZiY2NSij8pPz5UhjObgeb1ycEyHNrYcFgG6UeaRr2QW6BFWi744tsayRsbB7jk9OHjHcGueJs8JcATHcZTyLEQBGGHC++pOdGuGO+2Yj+XGU0/ArEMXWgICo/lX/X16F5H/+4+Lx02et8yFkvf1m9c+GjDR1tfbm5mVALCgxXo3cDDQ/I1imEbG99k1drOKtvWqYKffqVNLjdv3E1k0fUtmApg+QfSPwd+n3g05ahkW3zTqPlROL+owl9CMkfvAzwaKArHi5twyavq5XvcNdwEjPDBvplDmvyYUkhzWEarNcx9KbJHH8v8ixThcTF+WPJZBDK+Hgxwgkbj5EmccND82Py7jx6ADIlnOA3/ASMhbin+JFrCpwn+liGlyH9bpilq54vyvUVXt3RPFzDQc9CXEo0qGOoz2EP63Q82E3nUJlJQNFSRsAL49XJAw/jxFxG1CStCv1/e+GXoz1AF4knwVeLqnZguhL3hv0JlhyeN/QmMw7GMY2PxX0RUIaxIZCzBq4Q2hBUMfuOoYrqRyHt/bHFdiSfBb+THpOBZQnMSlgiehaoTT/K/4ij970u6r8CrXTGAxy8RKPcAMdlDZnJFOvdU2VLshKbMVgQwkOlKrX6Bha+hAg6NSTNWwGVbmp44jvqShgHCxLmo9aNPTHs78VuKKPfoI6rhe7JWVA+4tQPr1PkRaYqfYreitYCiAWV5TUkQJTfRV/crzwh402UQlJMSSxqMqUPJhlUKXlrRSIwYCsR7eEizWQyLYyaeMechycfsV+yhYwB9n5XKPzQrtbKItomtJmaSzqo6zqlar1ShqgZVWzSTdYj+NOcrjCfdGmsBjThKJNmeUqs0AH41HI9cRrtEeka8gb69sAUN1iqGSclmVBltLcsRrwi0V8xqSuFNBXuSNcNYQ1uPbr/JNttAseOAH1V8JeDMYtdT2wlCGxmXFxtynFqYCdpgLNv5Da2y/7WKSpe8pcVXLEpin2g6UjS1F2jIqSJ0yeVHZvfY5uTuc2pzEkuU1aikPbXlOOJYq5SkeuFmxhMRR6ypSUB5ciAScCRWPCA5KUSQK1pgj822OSBqyNDJ25G5WdHBtsNBRG42sI4SreMk6gRFl5jQmHk0rHwy5EIynhMxKKHnRN4UwlMjckBT9ErAA0O2xHZGzolaM3YAKJq29E3cd7xMLLYBb4ui5zijRHweId/khOxQpHSpLr/yfpCUBOKNs4pq2isLijZXRiL5OdTyaTxSV6acyyUX8JehgM9lcDSJx2zzGxtxid+DSvkCFFoQYZw97gkE8s03nzzfRSfql+B1wuciRqbO9NRx/CpOwk/GY9418Mk8a8rc2cF/bnT8N1tO3KvljwpRW9W+LjpRH5aIu4q8Rf5kbpFXnZpcdmKW7I5vf0/Q59fxfQqIaOCvwD8l3pSBTVVzmwJQiDRlsl9BU7AGV57v16HGnZuY+wc6PePCx2dJYrNDy5J491de6HpARNunnG7H3gw7BJr7gykOOjwDPbnwPpYfHmRx2jEqg03rh5KBnigAqFs2JX/BnFxxWm4Hc8Jfy+islls2dWiImPnFTfXr/fqwpossvzXOT7RL+h+r/aY6qqO1vjGLPDaamjZqwOOxX3pJtYtEtLhHzmmoUMRA7QxSCYadGy6AyPCjAxgfLyDTMM2yGDsc0Z4B8ygUbysg37mNHWQ1tuf5MUvp4YbyAyXyIOzsGoiSkmkNpguQREu/JN6UUeiYm8MgSnu8cJmp739Bhvkwq2tf/QGny5Ex98nyOAAVD4kDOj3B7HBclCx7/o2cJ7EvDw80RjIzudzWqXUfN11r64f2FYZkXCJETL1Yy9BoRAvw8AA0Jnhv0Z4nhltiof3pTHEgVjgQKzkQceaOD1AyMYdL1iPTDeCtXImwAJcu6g6Krvedl1jv7VuqyWG3ahgeNLhKYi8GqIncvtBPfwX4xIstvXcOf37CP7unp/TryTF8nOGT87fw5/VOT/8YdomXDF4ZmkOiOrQHLlDUC733Sw+Knu69gb9He/Bn72T3F/g4PNnPqPyNgigxhQNevPPEW4+eqGceVf9goGJyDQu+R0aonQbaMPNKGIxV/OIxqQd/YwuvWQ2k8NmVFNQuoTaHZsMYEUei6ho8TdJPA/nX9wmM7U26fJmzBDJF8a1RyCugF6P3MfYaj6j3keF69LKdN5TVX6zAqj299TqGe2cNBN7fN/H2EFSjv/nMqUdX7EAsOCKg+dfROLTb+nf3sQdLoYRPmJHuw8OniB5Cb2c9h/MXcf6N7cyAqzS2QryEGTmSMZ8DPpX8y3OkI+FDhmo6Og2GD+n9OsAjvfAQ3tG7VByUf7IsKfdqhg9+VLZ1YgF90JdoLBK2ZNkeNrRnOuSKBvPHkC/f3UcJTNRWGgMETpHEEH0psN4n9mAyJlNjSCzCuiWWBOxFaCD9ggpaXQ/ujRJaWRGA5MYwPYHrNL+7J8tQr+nn6rqfEW9iD9v66ck5oHjfHt61nSVXxNpXZS7fsJY8rvzcsiSulmW6dB9ag8f8HHQeGwHXrGJPTtAT4TUcv6cc5SrXitCkPfEY1mwPWCBpgc1SoK/aCEjLAM4pMe7A9ovvotgUaqd/k03aSiyQl1ygTVg0C6n6u7ODIP8OrkBk6/a6h91eFwDZ1yMtqN7Ko3Kqx5W6XszSI/PoY4cSrYlICgcAqrEB+S7Zw8wCQKc/8AX0+fFvDIyabAL/v7Ex9HKoD3lxmvJbbRl6PnvhaeJDTIKkDZ9D04AXd8O1S5G34F1ZNLKKMdoVvPJFlEdgrAAZMFPIafrISWJkgMIFvZyh3+jlTFCC3s949H4GOOWQToj5oP8iN280ti/qTkMtauDGDGTNXyoJ4M70Spt/777aDDDhtQ10xbDKfK99vQ1TWxo+CGxWpSYqKQOTse/ukehLln1TQjTlPCKJWIkV1KZkWQ4GIPDwoJ+qp9xUUDgH9Autx4Jp+fZeDrf3spKGbltR8m1+ZIfUI/Di38YlAWZC0IrNbd9/u8vGUMHcYN+2dYx5bDLE2qRGDEsGXPTuj+VUMkd3JbMcUq+l7VETowH7AHYIhX/gvXGNbBgw3dtuIMxvS+7AsafTA8uzMTVa6b5PJsa1iSTfndm2N9Gp0oHyVlENOqPzQ89XzvIHnCVnEKHDyQ0UYV4qb8NevcOYMYwVh/V/c3DYBT6kc8Fs4PSfTtnfLn7sHyCv/KH7Gpnu8/cxNtkLlHr0Dod1yKzFoF/4oOZiXmgnZlEzMWv73dkhj63Aoo3DbwB6aj+GDOzlo6W4J17U0KwYIKJ7078KXImQZaDrwYC3OdF9DJfOJwZI1EKUY3xjYsyUcgZaYQIGvoqxGiNWA7NXXCMbEhpcZiOgl8I/YO73vY6vW7YAiscGZjobTM059XFkQj6NCwKHxZjesCdQAx4yCyYV1Wziz1H25ju05tj6fTA5Vyb6t74wIaGmYmQZISdJwnHipbkZqMSYGREWiC7eUqxRxc5RJ6E4Ej97naOI9oi+hvVY4BgMjI/uR3CIKJZ+onWifuWqnBUgU9VohMzsgtEorCqUE4+xUd8DuqVh/IZEZAeMRYCBJavwwhhc0ahiPAI6i0/gTlnovIy67BU6VqeqFgs8ODOtyqTCrJMjztmKnIy7FgYdi0adx+iWoyksw21lYg5BmAJUY/O9gHWVG7Lxkc0BfjbloWJ8fCz2PIOrpJ+1Uke/ck14OpYFX5R+MAgWWqMlx5Ya9qAmx1YWnoRlgiUFWTG+qNOxAP0NrjDzzbwiC18qtfXDYtRyWzgkIks2YLJTJy+9ACIMnIERU7pCca2VguEPMzzf68JNZX4bj5PKdn82bBd2ZochVJ87BNbbdNzOSY4g+JHzcsKmvUQsCj8QeyzlAM04ST0ZK6ssxHoRRPyRhMEBefy8aFiF3ZOzrnDeO+vuHAk7u72D992CY6uvHyujHltx/Z///X8p2Hdjtb6DHk5PznptgRm+FeqouUZIRKheWytIvPLMUJkh0q0ccifVFpDYKgbuCFNxzIb+YZNAIkSrHLTzCa9PaKsx0ovhi2o8Bgj+rsYi8MTL00fRCmF6gdxZ3ZAE4mL+iQn+LZhb4tlomId1EY1IoQE8G9f8VCmxE0l/KDjvZ6LZhf7utHdw1G0LuvhJYs6AxSBeXQ/fiua0KAjlPneWHca7GQ1U8yQGxAIE5UKqmwupiXOqWPoRdS24ZUHGw7i28YiskTn8VAyKU/kTVtvcqrIWMVWrLxm0/xESGoSmjzJiU7wl8z0Jj9Cgt3K6KxzZIHoIN2QwAebZEkr0vlPY5BegNNQJ0PFNgUUSpUEoyrFI9QC3KguspIRhlRiopjmdcFPzExEkYsrH706CQFtIkhsBSWbPgvj17Gc1EYsrks6hpokYOA9ON1mqUqGJdsL8JnTOoC9Iohf6KOiE/srvQ2uJSlUW1Vo96ENPo3NW+KlqMji/H7L/kfNl/ATWhrl6iqXAUZ6Ltvzgd2dtk0fNCEYc3UeMGCOcd8/ed8+Etyi5JzbgX/7xf/yfBZZTTzg+2cNUDv/yj//T//H//T//STg8+XnnsOA0cqlPOJaisY4fjyLGgZIJwpEVV3NCiV10fU2XLpzuFouiBvNJHsLaSvSnJq+Y2SJfjvPpCPW8F3hIIGGXYXKY3WJD4PKgy+yrTPIb0w7fEYSPe/solqotwgAGaM0Omqdz4AQYHaTOiLKHNb+5QI6PjP/pLDm1FLkIsn0EBKMIAcnJUROnHfMXPfEbta9AOvTdtzvH+100Fyk2iPWk1hDZ1wwYSNOeKAXHXF+LN6lX10Bufj9nJo3c6MKYA4DFSGpIA1XHaH2UKBx+B9AFvLRR3cPpxAdkMKZE+HJjuoMJ7DInHKx9ARZXCGKsI0/yW9OJ1MwjkmI9RijqclxMLEAqajFSEW8ynngnyNlTjETk4/TemvJmq/oVsDi1yLFMTYc75+cHuwWHV1sLV5prHoQu8TyQQtzwHHxNrIX3BfYTjrzT3QqLboLmP12aFX46XcAJZAmGRTOVW09DdwHSnzoBMplG4alUDVVfof4UptC0RG5+kqdi2UzcaB6Ia4kFcnt4YJHcCiVOk18MNpPZrMLTMjrEWAr1TJOSQqNeD2RbzbVEz2pzjVwaqtx6frpHzAGC0BXcx7BNyIcbwzWHJKnnrtfYfY87cUzrKpV6J+e6xYne+TTlljz8mLxvqcrBLVBLHilhgeCyBcOaLwWQt6PXSyuoL2n4s8pdpf5kndUUon1fpZMKkR6egJEkNfFcNiH6a3EF+FtjMfdmxPrLPxVDxpS+S8uGDcvIWRZlRTXG/ZxfT3ux0L3LjBjGT1/L+Uo3pL+RGPc5TEVe2jsuZoSjSYgZeXKFVkyuKCZHaPlyRJxRTUoG6fNlU1stD3duGvDcNswke1ID5qRWDOKSGf5UpeDNy97O+dvXJztnewX7qeX0UyyVYC2pewi0fQlgeVoBcUNP4gn9m7zqY1uYyCteaHoJcaO2WqZENRmnvrEaC8UjCqCd1l8bb/2h/A1rn8DacSbWPkfBWK0rz0Tio3eHvQNUXL9997pgV+paeFyX8/B4laRyUcWhlpdWlYJHEihDY5FqFCb1dq5aPGWKw14BTKMuO64gj2iZUjqkGDRFe/vuvhvYrKHyMqG7ZVcFge9UsU2q5axysU3S5PWoERqn/h5IER3H3+jQE3Tobg3uodl4JuHZfbvTQ+H+7OTotHdesLPmWqQnlTPnBUlPdMOaSeVxZvKYU/W0YGJzeS1cTulBV8Rlajr7e0BmNpC/YfMT2Dx5PjbX5MazZYFe9+D12cmH86JZ4eW1cLkm/55w+TCwOS8yc2U9fG6tic88pDM69Pz1cToczN/w+gm8nq6B1+pz8RqO5z93z8+7BbtZD6fV3xNO762E09W1cLqmrInTfrSV3wFG+0P5Gz4/gc+7z0fn2nPR+e3Bee/k7KArlFjs83LB/tbD69qL4HWuil2tTYpNQ1sPSatrImnklvOvjqXBWP6NoemLY2lvjVO3rj0TTbsHmHnl8PDd8X73uGBf9bVQNFdfVAyxajmYUVD33VjHDK+qFry/Tt/7AUJFMCnXAsa/Wks7PahyhmtfYM2iynLSrU9LO589oiR86tBJXVeG1+4+ocy/snyS4jxtihAA7N8tgM7RNHFuMXBNGZQ1nu0GFVqYRQ+Fk+PDg+OCbGuuhqQY7jQKXtlmU6MkmY/tSMTWZGXDkAwHOH339J1waGDM8GIL03ruLmV5G0Rn8CmIfCrq3xez1q015fW2qfmvZpv2V9umZD7nl9ym8erbtNZhUEtmaf4db9PZzpHwmkzJuPBGNb7eRvkhz0Vd2H9ddKua621V/V/NVu1hdHVMmjIsuFUt5YW2yjdfj07j1MNs7683C/op1FrqWvuUukDQViOcazl5VVX5uR58HvBnnFvyksaZm3V5HUYpYbMZGgyThBFmpkdGIRCCNp/Jl0Zs5rMGW48PVph5qOmKjnlzUzhCH/A3p+c0Szb9cXryoXsmbG4WHPxam15rtdYxr6wqrUKefTPDtDItJAPjyLsK5lgS5iC2ubP2vFJHReDYMYZ4pV7x7Eqf5uirUCl5bmD8IgGfUgOBeMyHJ8yM8u0UhZlxW7mpNG6nwuyWjmcFyMUUbQL+QbtMF6Y2G7bDn6pwO438rD0RZyLdvC/+wNhwjR63Av3u/ngJf37y1lOM5cbySKJ4U2ZWmTP4s74qbkXFOpP1AllOo7JcnKIvi6FSSvm+ms9uwp7FF09zXXcpk3/U7Z0d7J4XHGAzZ4CFkFVT66upOZ4iy08q8HM9r/Wdoz3h7O4L9bDFgOXFrGW0pPZ+NeWJlgomkE2ursR7GuWyHRF+uLsDlctOdvZ0cWGZwE1+j1GuprbT/uyJ7qLv0XSV391/CvL0LP/f/2uXknb/IU2Gs/wgnAJUYES4YvMuNvCMWEJ4NL/g+fw0kXjqBEdNANAJ5RFVXlptodRh1fcPdncOBYyZUhBdkups9RlhUhIq7NPuWYVGbaFAUGwUjbWQtlZQN/nUgdQMPFsmFUUVAuO6GtDumIFtqGBLQoomx8JoxNPV8NhrTx1jZGp45jXJOcAIcG4x6JoE9r6+VxC6kPmkJuVa4WMpjAoDzC3bqEZffl9c78yV/P5aeEmt/HDh0FBq9DYS2v6xoQV6RnrykB81OWKWiKdPO6a5jyji2dEkupgIoH3PkiC0dTbiZSHYSvp5q41AG+w9XjFphupLGuViMN1aiw7X1jJ61NRaMZFvfSbq3xT7ZD5ixUxjOhQ1YtYa6m/LKB11QTD6FViFvb0zreAQq2tR3Ybye2GVuMaIZlujKiOhd9LbOdQLzkNbC1Eb8qoMUzRNEafGqH17d76z300xTWGqkBjv5GvIljjbTcF/RJcAnxWDgKb8NXmm8K7pxbzbMpVtRdmpFZip07e/nlNWCjam2FIm1Vqq9rLqUB9giqqutaSXtrqSokxL6gzVogqfmxQ7kg5DmGBKcpip4iyJH5JHo53F2BP6I86hBOwEza4U4hNf4sKcRdJ4MVjhYrW1tahvS16J5/29Idj5h51ToFunQPJoqOsiS1aXvxaO6Yoq1b4vOIi18Aqz3f+rwivTGppj+5mYxZe12Lqug011eS1sqsvrKU2arbWY9Xrrt2LW/w1qPE8fYdnnC2c+Lc6015X6b8u04934zu5u97B7ttM7OSs4yLWUJXVF+6uw7XwrEjrOs94vQk1uFd2etUTqulJblVMfJ1Sb+3mqzTBzX4xLH2dpOMcRDWdvv5jfVF2t/Z60m78Bg7APcmz9F+F9UQa8XtXWwt0QYyNEI2U9ch2xTNik4WODp6H0WYxBr1fra+FxtfZMpWc2I5EMH/AVWInoVaXDrir5WtNbYBvDkF+twcMHWzEfFGbi69VWzi4Uq9185iY8gkatxy72AZ1XwaLj94cHxz8LZ92dvV+LoVFtRb1VBEFGsEGXznwGSHB2eiS82Tk+L4gKtbU0UfWasta5kAr821rtWKn+TdX6DL7t+BG+LWISWwxqtd9Y23rc7X04OftZONg8KTjA9SBcU9ahMyvsykuzff5OJvi+w51jQZGF/X5ByV9b75oySVNzB+8PNxbb2ccQ/2WDaTezc1ikPOMPjveF6swtOM/WemCyliq7rj1XHZy4R1V5UHlk+bIjHBfR5+HNq4Y3r2r+vSsLmslcFdbwASiINoof9TbLDjLWorFeiM16UiNQXNOViuiYlVTl7Jdiw0jebayo66o318JadyY8rRu3iHfpkMH15aw/d4Hz0J/ph5ewsS0odCSv0FYLlFXPvSQsuL6NZ54KhfErDF3+2yJYaBmQ1+T5egjW+LoI1iuIYM31EKzxGyGYC1v010Gw5noI1lwPwRqNtc7TejFf4TM4LLinefsLEXnq0TMgau0kfePvzjFlZHJrTDeIkt0+Kra4rWee93MPT3cQRR+9/n0RQ7gVhN3X79686Z6dtwX5e+Hw5LyYBVy91VhLH5plAXd8sNtG/4ypR66Es95hU1E1QZW0/YIjWstDvd6qryXO1lrr+GdoqvJMP5qYNKw9S94NhGd3RlOLVRz7hgZ0ftQVvV+pIqday5WInxKZXsAze5HkF/Ewe1Z6lobcfImL4Um1oJgMZ0hMTM65YMVQDTv7XeFop3d28IuwIRwc7x28P9h71z087Arn53vCfvd89+0HfLz/c/egV9BXvJEMQJR3BM6fOMUfpTx6dzDxvhDTEw6JSzCO+/lg4hCz7xiYAWn0l38CuCJD4grXxOkjHFtEODQWoxviXAmlDzSnrStsCoemtbgtF5zZWiqDhrzWZUkjGT1LWS8hlZrORbaKDiInDH6QMyEV1tLPw5dInZAlol/o1FqMKkkxJdyKDm0N9dl2cDmzejJaZzOdy+qxiX04A3TCmb1ZdWZrRTluqGuFKGnI9WfqVdd0MyLeCsbacyp4ROWniNF4jo1486kI9b7dXDUva0My78LzzibXMxxvZRmucEePKVbDKCi5gmDuQC5fMiVRo5pk/1rF7juINCTX5oAU66SZ00kxTEjdFDZWcr583FU05XF5QaQZwDPSCryy1kUijVzvbl4sR2YjmUhMbaw2V20twTwn20+u5TCRVjWsbKRiv2urTbC2kgFYUXR7OfOw5E39k3m1n7qrTXmE+Gv+YzPpGRK8aaQ8RKKxmSIuIcH9b1C36NVv4xHPkCK1lWKA+mIWFMUlYYBqtFG4HPeZNTz+KAjcdbkYqcnocuQQEnSJP4p2qaxFMLTWWuioyc+0x6Q6kFz1R0MWci5Fot7uz7kbmWdngsphgVva6qEFWqkIdYkwbPmKnegRXvxyRKUHuJq6XSmEh6mrkuAA1ylLXxQKm+ucsf6x83ioDCI5xBhezvqr6FHzdsOynZkxjalUkbMvtGbJe4eauhLONNbD2NS1hVY4xllB0A8kqN8d7J8/Dvor6noazXzYp1JfQeBP6bnXBP7M6xsi3TiwcL8D8G8m4Le2mmaluR6H26ivdWDVHzEb9B7nPPOSIxVjeKrKOorhRtJCf7XAPZrSzAtAE0uJ8htFMkENdURhTU3r4zL9bBiqoKPiNjx/VB29atCTlfO/Z8xFTakwnlRBaREbmCxsfzw3UB1oXr0QrjblPB1UsdrVlbSYX8vWTZ+oBZUjfRrcMlOFzoI3RXMcoR6apUnfPXx33iuYraApr3drnGUKpmZmL+I5i/KSEeVlIkqlIYqnEPKd/dIt0MdBA/TXc9MYJXPQCzs/9w7eP5aJfmcf/j4rFX1TUdbR9DeLJrqYZ5/dCTN9L8dmS/8zzNkxpsQVemRKZsRzTFI5N2YzMu2TwRXQLlQX7UynRNij1yI3xEEtg2kJe4vB1d5rYUzcOTEHEwJ0EMt+gK0zXS+8NNkutl7qWva+TXmtC9KmrD5TL517LchOjRvHmK9yS5IZmnta+kYui6l8oHep8CXjVGrgcahgzlAMNeIBtZ9iinNTBOfOp/uEWnc11rhZVZ+bRM4eLlzhL/87rJRjFeyruhY8JkNW5R1SxROU5W969MYs2HffijJLgdDIvkN70a2/W89aslltPTcjiHoq7OLqFeqmtpaTaDM3QFVBKGmsw3435efaZSRYXQ4i3Jk0drQn+UMtnqpelYO4+zVNVLSmCOeeLClNDJafOOIj5/mjLWktUanKolqrBy3pUeh9tHI0Yr+C8f//GzI4yWPu1NvpIxxRFv8TsjzFsEjTfi/2KUKuqYJ/HBdXuUdXirGNldcYtrD7Wigd7SBvThl2ykWWU0kxGQd5fLLXFUpQ9fW7473usXB00AMUWyyhvH7e2zne2zk8Oe4KRyd7786FEuUvodmjk+OD3slZMaOSZl1e0+7VT0vEOX41g+MPSMTTWUgfTz+ay/dHGvB5/qB+nO1PW4iwR9Ea/smWKwzsvDs/P3kLm3R+fniw+5bLBefdg97Bflc4P+3Cw+7Zu+P95JDPe2fdnSOQDY55HRhUsjG2j7FWiu1kYx01UjPX02Q9u6lq1o1ydC0PZsI5cYDxqLymEkRfIM7Ino6BMA5NIpxzAWFhjQUEIjydKyhOmGgXYd9AESxGBYy+YV1NjKmHZY2F6w4msO5/+UdgjSaCS/twCfAfYym1Lc/sJBjpY73ByxFFW+iWztYzrKExtS0iMNbyq8x3iul0pWKQ01grgEBTW8s8tanVvrZh2Sr0+0ljrGy9QY6EFHP8OjnrtQXg+goKLM3mVzMja2SrWhopHV6uJZmf05neqe2+PYZz5+Ao0DoV2/jWelJ7s7EW+6xVv4o1GTcfW8/LjcYXrRaILtqUn+u4GVfyBHl0Yia6nBRVzj00ax2bxQLvNlutZ3ohPeaDAkzbwhrAMB4/Td5jGt22f6Jwupkk97zQGZnZ0B4rC7SZP6aJyBmFxbpFptyS5ReLoRII0nF2KaHySEfrzl6PoeEZm+w02qQphjeF0nnkcEqxnn/5X6EL2O8xPVQs4S2202btTO2BMQ2aoetULrg+6ylEWs1nHhG/M4zias/g8C64eC+MT4Hi5lFMorcLlwx0pCEMfNhPwgrChq/KBRpBjJnObyUuKaj41QrNUnkRFMpzwYmJY1HmDNXOam0inC6cMUlO8IPpDAVjRpFAgP10TZDcAT1gmhT6E7WLzXMtVGjJ/0ZQgS4pRobfKBxSs6W8MCKEPE7a5jWWw4vbvT4v8GZL/aqQrR+a16Ty1nCGN4ZDIlcxxdZ0vauTlvJvBByPifeF+ubsLZzBxDW8LwWXT/savE4aHPV//g//A4XApHs7QuY//4d/CN4F7p8FYbP+VWHzCAYilD6Q/rk9uCKegLAqvCFkWJBvUNfyt22pa8VMb7bW07DX6i+jYf9vy/Px6BHPx5UMQVvV+u/Q8fFCx0RVB2hA8O6NsNc98o0KAjXvtlDSxbR8XS542lSbv6X/YyU8bwRjOoX9DR0eLeGD7Vy5HjX1d0Xh0Jh7NtADeCvsGzNcpzNzXMxEr1VbyySiVV2PkDw7l8xznB9XcjPPSSao/4wXwoTqHomJe3G6KyxmwpC4cEIIR7hjaKFhWF8WsI/jooJubrL0YrXXUtm0qrWvorKppmzsutThj3R+vJ/CoWV1RiAVEMkcPjx8M9rYgG/uJcoSWw7xFo71JDWvZdyXJjxiivr/oVsL7z1xhaJmXKEkbjojic5jF654S2ptx25HqvHbEQS0p7OcK0HO9CCYTIarY6YLo758QZfF/FB2dRbK7q91k5qRNSjinvVkRE0iGdcGTPjhQf+Xf/zP/7UYxqZCNn1Ni0dltXUp6BIaqv6ohe6Foslxakek+eDSgiaLrUiCmFdDy2Eft5JWw48ao2PwuOTlZ4CaaHCgZuvU4xOPCccn572Cu5sQiasrXfq1ktm9q8pqjqRZ7ILPpPHnZGguZnGz/6HpzqfGHd2xwKn0ucFViOTY02Ib30xsvLbaYjXzFqvgWlfX8fltpdyaVrIyDI4WhrKYMyzTdncl7M0mAcXiID7Z+g1wSSmH1UhERmzYsMwZ0IXKfDF1C+o7kmlZQogHIgIs6eUMpOpZwYAIrdQVVmvdWEFEgjIoxhOr2Hy0taCqtZbrSivlJFdUxA0yAa1i4PqCqUuUtF4IBF95pQSLNK/lTjFKrcrJK5Cq8lL5gEhUVVkIcGE069AyqK6uxFT81ZOWZEQaD/hamhF5jVxBR4Y3kUCaLUX2QZHlckG3c1jMRs5eFKtdX4MAQHVlpWPl94J7mB/t+F3vzwWto1Q5mcnjJdHvGbcCMKDGWhioaP/qMTDAOoz0z+L+vwAORjdjJTRMXtOshoZKay00TKYiWY27SyJajCmLYt3c8/mzAPWelQUknVeg2/vzhy4LgN4uhpFq87m801MYyS9LyCOXJSQVxvSoIN6q62202niB0D0JDSAXj2NLcHDaptM053zeJ+fsge0WG2hVXYMzVEn1uS79j0bRyAwi+sSdRKaXzP28FCrSLCAxbdTvlUUPhmS4k75tOEMdMD+BaUzQp6Hib+NhkrMF4hBSi4UJiHvJoGLwu/uIZi7Q97pTFHtaSf1epidDzVfKPeLfFQKU+qgubrSWY44qa/LzgmvBGuxceea1YM6EvWB/qDlt8BN12YU12TAUZS08rhYUx7OhbwBw9t+jLjeqClkKOgVA5r61DBJzw09hZnpCujzVftIQbbGYGKt49sUPA/Y+pnrL99l6QZctVa7nSRTFNrO2DrGSq81803mkC4/KwFqe9fSy2KVIriFqwUuR6l/vljnTd9W/Ra7mquFzu9nNv/pdLXOfKjdqL+Ho/9JRbwNn/cOD993K++7Z/iF6eZxXWBjcglOrP9+9u/gN7z4BUvqXf4IOXI9Mp9QclF7w7k7h4ILdPLYxvq1pCf5dcMHRrxOGFqqv4zQJ1Z9r9R2IRKnQIPGKntGfkkyJi670lIy8VVRe3oQYwyiAJl47CUErz24jn3vMModKDSJBOeJXaDpCAubu3a3g+2Jg0CyYb+Gpvl8TawHQ56AdoQ3wWaz3lvwyvR+cQr+HaM77pWDHyst0THWPhlsQ54rmIn+qV9S6vCZTgsbhBXuuvkzP+6vNt/YyvR4TTzj7ZbNXkDC3tOd3y7DSwYQNMR8Mz/AWbsHu14kjBRjZfH7iQ6hdMOaI17eHd/HpA62FE7NyJ/Av2RqIwCbjcQoY53CbNFHNI5RtmNiJuyD8xrOSpK1xU68qcvUrKURWuR6HYdTyhrHy9XgzuB5/4j485TP8nNtwGLq2Rhw3qK4Wk+lyoCbuO/zYjffzb7sv9BIqcfDKW9SLmQTCvBK42VRWW5bG+suSFbOWK6cKLsaTF8psZSJ3uIWXJ0H4GisuT3Ot5fkKt3uK3HrJIVE9fTpy6TMuPRRFfsmBZSdmJmGW7uLjUl4IxBOYn6uJ3lxXD60oL0CskuxGEcfiZGC3qGSRSJjZzEuYWV8lYebJ8eHBcbfYAaDU1tAiKSnXrEZhNRDgXB5nX4x/aq0nFjfzQpgVY960NVRQIFSr60TybLQej+RJ1aFPhvFkpoFaGLwzMJqtrRT6Mmar+3xXChpz82V0amuF7vzu/iiIqI8o6WMd/q6lYqLUZSHfrfhxdS9V1RVD0uoaNuRQu/Eiij31ZRV7GDjs9Ozk6LQnbAhvDg67Qu9s5/j8DQvzU2xdasrLhW2MyZAEoEFYTDFYo2GNiXDq2LO5xxwx+qYrfFkIClBfP8oInOrCnmOMYSZ7jj0XvtyY7mCC8Ul8TwJXKjijdfIFQfV18gUBpNRfNi7jehmr4hct6Qb0nb6LG+UUuz5Xkskq1nRJ8e80M+KGMGP+eoEokCuvhxu1DL5+jtCs1Z7rwJjjFR8bEJfbsMLDwzWI0ezbJwml4MISddEIZys4WQrcMgfPIQs7S0pCWYMtLjGuFdIHqlfXC2DpEs8DgusmglhGbzafe60ZBD/IuNnkF65AHmFieLOBK9w1Lf8ChPpLzQ30oMo7F/vrXYMquRmci9VW1yKY2joB3YHeaqvcRNoWnjEnuDFnnsh+HRLjmrS/sJ/2vP3ai+6/Q6aGhw7EM9OqTCoXNZXiBXJ+8Eur01/BPc0d4wITHF3AFCbiVs69IMgkTz4kRLgmVQ7DSAaXmDHObu49yaEafRdWxyMAWADfFVn4UlHlkL6isASfQ5g3StwOch68y8AgBk1TiB9PLxhoLsP6lLkJyHK2ib8q5BqeuhXLtvJp+E4StBU00FfUGEMZmOT3YVCDYrcxSnM9Gp7HtmUyans7ve5B91h4ewCs2c7rw+4+/Cgd7fwiMR6IvS4XHPh6hP0xpu01fIFtIg4GeAPCg6yX4Noj2/HM/7+9b9ttJEnPvO+niO6xy9SASeWZpMbdBUpilTglUVqRqlp3o1FMkSEyW8lMOjMpVamrjbnw9RqzNjzA7AC9NtrYu929GhjYxl5svcm8gOcRNv7IA/NIRTLEqupDY6Yk8ZAZEfnHH//x+4gJR0EfnhOtRbyjJVTFQJXIx4yj5lPurVLlbvnFMfoKJInaOpLEVdPAVmkQS1y67TcVbtaGk6dcgUKhwJZskDFaywn2aqPOaCdEkVr5fuXOXnQBFoGSxQfBEC3viPHNOfZ8Y75gG01pypFcybnGtve4YnNfYBOLJcZHGgcwheGVMsr+bhQPoD5CQ/oLojHrWyJQ8NqLt390iTAwGmlyaVx+Dwoa2TZzuxT1EzfGZCpEOrMHW6HR9tSvxV+oB6WUzC5HKcRiCpO8wLRTVo5U0jfL1IqvrDri9IJV93nozxpE5RBVeu0sTOymTLqZHzZ8pyXlsPGEGClzmGJZYMG5B7Q+Ee1kUtbkv037Ftiiq8/o7BmPDllWeJoWZLms5nKv6jqP+exsWW5WW9ZVoCcQo2eR0LDdrcW3bDpHVFuWNJ6yAKldCkMKiplsrXsN33u7vOPC47TS95naeolMNivrsDVjzI9MCZyBoF0mQE9NIFaV2SvEKqDGZ2C0LFwc8Hl42MJjX4CrIwsbE4grgmPzCk9S0w8HzrQAqlq+AIbvG+MZ7CUPkCsSf4YIM5+JzBRZMu0fqUyht5bENAN6WViNNurYs7ffQeSSHpf5OdRHO3uMh6Ymb9iYkGPv9OYpDJECFNg0SkR64OyM4lMiaAsUO7+VwCNynVxrcUYyyXnvJXHlpvhxsfe+Ovtv4OxfutabN7gBOKEv6e9gg+wUuu8zQW6l4orjpes5rhA6o8VjXuPLlgukOZ+SsXrueC83wDpxq8irNCyWr9UMe9Ccy69gs45hRIg+ByGwR7yxYWFBElPtGvRX4qDN2Q4FXSuBbqhXDSQksfQcsldNn1irqfFGr0ppLyl8+f7mlEJfen1nCHtCSM7ShyrNKudbFuCkEgQGeQxSCRrI/TzXslgh4BJT/a467xJnyppmu0V2ZZtkZZv5BlqJcbF1NrFjJXu7n1MdN8gbbGNrcj3KcmCX+9OmKf7Y9oZtkawwKRGeTXJbBW5KpJFWa8eaZZCzcRnm2d8f+kj4w2XHeB6y8h5+cHJmeOYd3pVEWd0hfvETk5hANQmYap/tMx7mrSabLBvkzjMXXwXHQH3i3NpQH1Sg/9MINkV5g3UtfXDor1uFSSnRNdvezVZTx4qSLNrhMeuitbg2WbbSRFGqfV0ud4X89ZZbWb8w2zGhcVVHy9oa/MF7a4PaZdU5xXsTJLXLpDEVUeVK2TQ3bx4rTKvcV/Ji2oulT67kv16Em21UXxDTBc8ci6a+A/daGJJtZaFd1Hd88w7VnAWYK4ZVR3eN/Qb6q7PXQ8cdz9ATMhdhuLSJE4V6tkf06phiTf7Vzqh+Y1hLvOdBLulgBmUPe/jTz8ZgqvqGO8V+g35gp14IjbAu5d1KpFyIER5R68lFoahVI2Vilkni6vHS23OWPjwUmn0JX0pneJiUgyJJbOUOMCjDxaATXefW21PTT+DJ2++JozUzyazDeg9aNGKHVSN1dOAQNYYGrz2i+ZKrjhxYqSE4tuR7qHYL4OnSnlRUP4K81/Z45jq26UH0aafRaERPzEg/MWcLT4w8sK09K+KowbEmvGZ7aFnQidVDm/jsDnoRY/N9nmG0ZddC9m0KN5Ff2aIC8HsshHgF4HSD2qQatncQWSVs+uhuCbxRgDPL6PkrOUADpUJRwpVf++LLnZylEGU9E4YCvKRkOu4KI6+UGNfCzFFEJccqWunkVRRpQ6jylY9DI1hR6D7Iu8tqNuWemOPEL49z5P2LoJBFKIOVKyo+zuVh1vS3ymuE7zYbTYZYckZwmZ6RqrBVZRd4V/eDXLK6AoqqcoATEFEnehc3yMXJ4sPDs8mr9seffurv5HdAUY1NtCvmVsYaHr39HeMyauWV2GutREWVecqwFS5KV7LHxAcrylsTm3toMvq0VQZzG9XBBh369fnS8s0FcUzJrONj+XmqLCeI0rE9V51RBxUK5tBvjJcuGb//uDGGV2vsScbQRNsAFkO+L8l4T6lBVrWoRLWom6iWJuP5lUtZRXW9xtK7ffvdjJypqLYq+91hvDvf4aO3OEsgS9X6PcWQo1Mwfiami6/9XGVzWOJHEVbuTDxjFeOmxqUlslSbzOWRL/z6xPQAYWCy97HhN3zXnNd2Hj2KLaVPP/1UrDMUmpAdoeZ2RAFv4iq2l0Uliu/+5k3CUn286jbQk/sqMo4TRnYJMLnSrhNZIf8jJ0cEXBRjH6UJytV70JAKMcq1HBpSWpTCXITt+DBR5xZP1sAhHeCizc0mQ+1N+egHf9M/ODo/7fcGve55t894N4VLYlsST2Gpkg3dVItSKDnOq2oZ7Kzhn+kvonx2rA1G+jYbjOaTVYMR+f3eBiOVrcFoiy0wlTvlZ2vYXVbshiwirUrShhvo825/eE6psmm15/756YsB+eMROjjqDNHzzsXxkHEEMs+mUiVGY7Fqvw91LClyz+p0m2JiA9BC0sgagOafsMg0QPkxxzOfUgc77tQIAzP0U1G4/NJwG4wLw8O7JKvZ9mXOxh1lA4zprJ+faZRl+lJhL1bIqbogR9YdugQsFTZME1WWN3Xf1zeYj2S1RWzkk320S8xB9HSfcThcB4oqSxs6SrcQcUjZ7veA11ZCqY1VUCEKLfXK//JLxgXSOTo5VJkL5kotDSsybsDWxmkBpfh4o5GjLXXMltwgLKmmqJ0VLpnqMiFPnPh/6ThM+gIDfL9/h+KKDYD/gsCSs2BO+qkKI7LOvbmVSPNPKMXhEkLyibj763Tc/XILcXdLaKOFG/jiUlQR+94SJqrC1QehKvqDxXqKOiHU0iWlOeb84lVEwB34tRHUR6db7Ao6QP/i61dQDk0//DjvOYV2YBzhXhMXDI6eb7K2CtvTUlscoSOYLC1m89jnG37+waccGF1sk2btbi2d9NiZYPYp008/+IQhYcg2XV3knO7EGVd4wvTTDz7dQ+d6CTWerHPWubQQF6UeUWLaw5raVRqXih5N/khYma9xx2aSzDvFgafnOfAySGMhwzelJx89zoJfJCnv4u/GjeEhs90SZz5OX4o/Tv9SMu1UyRH/+dvf/halOMiJmgndAj8zvj9/+8//9h///g8oYBtPfY6890+/C6+DBr7jGlNGiWsyImgUpQXMyV4QMBGWC/AJR8UZgqNNMwRqi3FwlkGcJyjr8ufWE8fNjipx90x1cZQMyKBkrxO88sxCLiy6YfxTLIp/qtXjnyud9Q17H2+11hlN3DRwGbfenh4cHXcOGUOXmsjnabb5YhFNncuTUsqgkerHyZj943v9qqjPOmMxrghFs1ZibEgqYmneJG7sYI/XSeAak3+iIOjqgjqj3a1J8uZxrxRgyOgZ7YqO/Bpzjp6DEiB68ooyEDcYx6PwxOFKtHw0qFvsToKxBapa2KdkyZeQjfPGM8vEb7+lUTcveSJAYsrwjd3gxV2q23aT+r8x2iu6hW/YE8MibpFw4kyWXu4mFj1HoqvTU6bw4mzrxrWztNJ6tb2H7cSxpok/tZyZcuxX78UpLLTKw91t1oVT0Nyup9s2aFvrNlt1yGkgp5z7OCjyk2zV0RRxQ9KeH1urjqbwtKJqisZD06HJZSXc97fqKHKlVh0l36oTPTb2Pp02Wdb2pn06miptXEm2xpTl7tHRVC5eKE0VNyWGos5iWVtOpplqVd1aJZhc3AOc4aBOsRrzNu1o6qYEqsy8b+Kawpl3266jafJDFUe2crWRId6Jt7BMvzZCo50vxC+ZnoCmcMmzJm1OdCYVQs2X4M5U60Sr2PGUD8Kv74EqdojZ+55ofS2bHtRLUfFH6DCcFqv8tTjKYi/AdILFK6mB1YprYGNVki0YRHTBQnCSDrHVA9/FevtH2ixRdnhfcyxlU+Q5vHW+wztHk6VVOzea5fWH/nqroSx+wDZtWeJLpWpri48WrjPGnoe9D6IAaUsIxx9SAVJ3Tb62IseY1hY3jIQB+xcadgbP0Emn33lKi4/Ozk8PuoMBOjjtD89PjxlHIPHExrRWezsVSBEjmHDmOndEvC3Tg7Pb9CmHDy03ujXGM+AUgwKjGNbOReEXhCF256ZtYpeVaUhrK1zRiFZrw0RI7BqH/ijZN2SXqu+vYEBrtzeJ7xc3Y8LDCBr7znqHKGgJSVYN/Gecqhr4HP/YqwZ0kQuUWmtzlcJqufQIq7mZ0Pls7N5Z1f6B8+Olyrhi8Sqkus6z48WoQ2mevOSZ45bPyF1zxuWovlKxxxHZVGxSJ+kbUotl7nd++jk5ZPqdky7jfZsPcl9KV9cZDFHtL3cYb9x6kBtTxrrucffpRf9phZu3H+Tmg2FneDFgu6UsbnzLEuq4zrNh77TPeHeJxzjXcxBzVajjdEndMnVcz9+cO64KqGyOaifXQ5riZDMnbM9mU/qtqPA5BlcrIYdjDVbpcmvjkXCSDKWxbceL5WeymOQ1KSA1KcZnTefF6aWYWaJ0hcd/1uX25s+xlGCK8nBVmIH+Lp5gHnm0pKU70dtXpXDoltqBs1QJR2RZRrdltueyRO5KAt/So+ybjEvb4hEOpckpHOupvAojWs8gorUAqN64qfA/YQp8S168r4YuzSmUKnTJg07AqyGebwojIePnh12emaKaMuGZW1lL84uHipTpanszeNjV+j0e7WMISYOvtDd61jtm8+h1TeSBitVVHgI0XV1LgLZYj3Kkl6bnGPUjF1mQXlrFwWaDyCVuGdu3JZ4GRS1H3paOEZLffMd9/XOE8N1ECA/K4zMrqHwWqWhuGh48vDh4driPZFUYDC/6h90++rzbG553e0fdvjAk3sxJd3jeY/TgmlwhQl3fUohwgK/ffm9PoCoJoyPDndwaLhY6y6s7KEKyITQI8UKQ4rnhUwApl6zIDB0ux9eH+0LHJde6qRAg1JtcAUJdbz1opbRapYGjAodXyhCuZFPFWIQ5m6pSfKxVKvUjBGEAcMLZVrzZfnCGs1I+W57loddjXx+lfH0gWsG+Pi15O+tTTKvLs0LhFdnXSC9fo6eVZKjF1UepN7mitbrefBh4xfVn6NiwbwwvxI38yq+TA9Cf7UlYqc8weAV7FNWooHCuJaaL/BJljYUhYbaHl0vEsCrKuR/2a5bgz67FgGEvZRkJZK6D7jN6sjJNqSkyduoXJ/rC4/z49OnTHkQhJSG6Oxp2ng13GMcgbTiGX3eHnw8Z78HFH6e321y7pc1DI0w223orOuYUZDSj1QIzWt/cjF6/hZkN3cs4SbGZcTtcg79RCY6qKekbyuPgbwbD7olQh4z3k96xgB6h/sGB0O31yevHxxf9p6zbUuLqfWtKjL1vLKYt4F9LqUwL0ERSxFO0j+2lf4fdBeWVrFNQjhPomhLODhCt06+jJ4bnC/uO44fAqsKBAYYxZMdj43iAbc9xKQllg3GBuDZkM1fgz358afeTLiab7TQaa38ndG0PxNVWeoWv8AP5j02ZseN5prDz7SQynansZmZ8yXblbv9i+Hn3HPbp2YEQbFrU6Z91BgOgTnzy9g/nAXLOI3Kqnj/vnjMeaDIX431TLm0UxDlKIlYug3LKrMoljw5fl11TKUupgQm8atWBRU9BKX/MZhg3FZVv9Tfl1s4070jpbh35AXzjLQEbl18rakUtLAtdxwk4IvsJPo9qQeOWOxEiEvCI0pNxL5UzQJXkAYKan+jPZFbgde3rRqNxUw/oo/cSVNf5wtckc2OmYBiUvwtjzLQMpTLUy6vV6UYX4m7pvv1+fE1stTvGhuGmqvEAUzZVZXN0laAEKmLaThVCZVYxXRRFVjJVZ0VB7V+cnj+DgoHeaV/ojKqXTTWzIOdy5M9n4AzuLYeKTmS29deUByc3T8rIC0CRX3VPHlhki5KZg2EUbhFkWB46x+OZTd5/hm0aO5xSm4sNWqupc4H+NtVN4zBMmmpz7RLZnbB50S7qWKbhodppyKXAqFl0jX9/TEyPyPvr0k2SeJ9lp+y7S3JW06LEDtHaP6C9Uor18bB7he4KukMA39ZdORtv/xAB/SF4BnfYZESfaza5mvCbuvphbpFzB7ASd2P18fktHl8zrkiLf2O4jlW8I+ANlq1wjI0JeuG411CpQLZ1HT015mDUn5vTOjo27eUrdIhvtrJFHnJjNPl8AVZEk3ctXgNaPyKcYGsCh9Iu2jcdtgVhbS1YJ11B9cqJNy0UsfhdFjk7pbDa6E+/+Ve0H/BvXL393kUHF4cddCafffDyxdcn0Sztk2A0EMQNnaWEeAL1qswro3lw7yKp7dwYRCBQb+zYKASMZ1rllqg8aEJKXiE7pthg//ztf/0/o3qEjUR++9Pv/4X+/fvf0B//7V+Cl//87W//b/Djt/THf/lf9Mf/+O/BX/9z9GVxWWgFJ8mgS7VX5Bu9sijlYz6pksMMumkEl4HSocdJvJ9dOQ1JBd5VCGcgiSUAQkms8xhAKNiImpiLheWhJpqZGkn8TR2vf+h6if+1wyYzXCAiLVHecGstoK2mtLW2JfLWvfBHGKE5mL0RosRkjHtgikstR2AqCs8d1xvPjOUe2zaXtQ2RiEugtxhOisqUJiXLYU0TX4n2Hdukm9XYN5jxl1Pu0Zs3UTThzZtE5IVpgK1NB1geyik7Ir4Y1YiZUTDS+ogxMd/KRX8rDpeSkRKBkoLCVLEhl5NCFdQfBbY308Lmqr4rBZhaMhe+Y0tWK3KFlB9aX1O8pxAqsOFhv0c2VG1kO+Ll3culh92XQYaKSOevB6d9Yj+6xJUgmq12s7NT93HtY3GnTr42NOeYGGY1uCa8Ku3UZaJidupX2B/PaqNdY2Huxpf6eo79mTPZG52dDoajOvRrER907+tPDgKGe2FIBvzJ3shYLMhIqRez+5XngMkB/R57uaF8s9MgHyM3onP6hhwzaRWjFlH9VITQK8mepI5cueTIvR+ipwQ9sDRQ+qCZhZba3rAs8Yw+UhTlHmz0CBn2LeXgY7uzxhVnayl8poKscCVDc4js20iGBjilP6Js6NmabGg1vo+W1n7X6dDVABMW05POYCjsn54OUVjIcNA5OOqimj0ev/Ro7v7lGHL3DVBibEHWFl8AupWj12nzUbqXMC1GiVHo+chh3UVvxji4hWnU4oWETsXnqPbXSJp7rCvGpwuyYCQPlL5UHoBvJOmu5Xldi+vyeL0CMesVgEgLFK+V7XE0pQckJwm55GPIreTICncZ4xhlruB7XOlTsma9OToylgufmBdBCbvpMY6LK7Team5KOfkhCFqFDulWs/kwMpZUTIGkJUf0FFsGFGjViC3HrI2ara2KFsDcrhLlxAy7BMJz++0ffXPKOMA2n4zpP2AZ656Tk4ac1Oioc374onPO1jfTaikPI24xaFpe1g7OLupQ81+HovY6OjS9a6+O+r0DxhGq25Q6Gz9uTLFN9oqPJy8N/82bUWfVjIOwe0Uu5zOOlIsvs9XiKktu6Q9HJ5Y1qxf+OoTJRTUm02zhHTZXm/5iMXWJXgqxeGy8JDd/gj0feMSA1e3asG3PR5NlQPlGi0dnJvno3LCXmDiXxF8jX3IZK0dbbZEr7BA3FL+KIxCG99oeU5f9CY0k/Mp3X39tYR/hT41bw/Rr9F+UjCEEB30USth18ZWLvVk2pPDNzg61Amo7v3JxDe98Q6MDX3+TiVQ8CSIVRMPkIgYlQcn76IFjUon7kitsBAIhLGBxBLRUyF6VRgOA5uTxyLDNOYQ2vIVpZ72avdHoGyZxaIvNzWIGZADdQPDCRuhAMo1rf2lYtGCRMXbQFrnImlp86GCtFlchdUvTHzp2sAlP2gcZIJg+HB5fW2q+6whBYavc6OTieNiDept92qe7Pzg5PbwYxPXRwrPT/pPe04vzDjNAT1viEv82a7NGIU6ERQO/ayFjSxAiwuWBgEEzoUajl3M4EeEbcQwh/DsDFbEGkGcU0B7c4vHMwxYFqmNaXpnLwmhL2gcbTkgyMq5s7pBDKaZBStdUoCQtkkzxdMrIRVRx9E1ViO01XKRpvqMVnQXbU1QYPfw1dtn6pp7+EqjksUf0JVTTRTiW2G6ggIrkiYvNqXGJoQqvj/27W+xeM4qgwhUGaCubEqquFZCIZCsTnUYp1q1tSsiKuCslJTGDFjoiIwR3/Wh5ucO40M0tS8kgbs4woLpwiC08p6QvEwOGSuywAMOggT6HAkxEpnFJ+WowkSqPVVz4DoSNySvXisvYMsmZvxKYqDMeJYnTtikuMflaSlr+6XcIWg1CiYHlNpmTVm11y0rli9HAd7Ex99GxeYOFE5CUa9rkR125YNB7aFRfsj1ZlU+PqBLXSahwEQ+3H77j8J6+2wdvnWM2pEdSA3WOj592T7q9PrENV7guQq8/JIYieZMtVNXWxB92M9Z9xYvJVVtpU6Gz8iKX9tSDQBXjerGW4ZN7jaG6NqioPfEbC8ciV5r2wLEhL6YKa/s+LQo88euZT+ULbB+gWrZKrWyE31L6ABzaExJPdCQ2tJRVDdmYAb6mhxQ5as3pTDhz8ZgsvWOHFeeMh68us5X9ZEckNUQvvXnEaESr7jm0i7rzxZUDFaus41E2G4+cGY+8Gg9Zoa6N3SmxExcGeXPCOhSVp86orTW59L6mvc8S+lRTpHyGXuDLgTO+xn50aJ85rs+4jO1NKudt+uGodh52uryAe5bt8ODdPfKAPUz2eRb1/M2blqKJ72+nM61Uk6vqoK23uCyFLLV1tah8YWFucFxVLpQvqz4vAZqPS+oZ67UykkY8g/H1pQNta/AbnoC0AcqIRySoTN7i91dnSfjttIwlYi9UyHKiFcOD6TEuPlTWCYwi05I2rB07MX30gljdzq1HtHTQmBQgXUySGG/gNx/R5Zy6lBkC5sxqqbf4NGBLrMY8/GFJELBlzM07PHSGrvG6RIzSH3rPstTeVJb2MfQDh7SmgUMdgqbArFAwSfbMQptPbNpcfBDtJldmoZ0t5vzhOEyr0Dm7yyQ34iS+MOj2B6fnXXCdjnv7593ojZPTfm94es7y7MkWVDk7s5QHhnHMpGU2BU7N3Wmld+R1DYvH5qWLo6TziWObvuOi8+5gKDwxLOvSYGuOVcQsIG6ZWV08zlzYJNPnfExMax+dGKZ96QBoxvHb769g8WrnZyc7tPH54OxCOCOjNaaYmI635D0arA34jyF6S4w31BJbGuN0ZA7TnHx9o2bOQjVvzebRkyjR8YlPvFcFT6bNAzFD9mb7vXkkmXze8dEJ3QTo4vyYbeoyN6pI8KwvXKv8MZM3tx5aKOKSfTAXhKwTn4hwpe2IhPGge5KvKz/UszcuAWE/epUGGnZPzrrnneEFxQIb9A6OuudH3d5wIHSOO+dsjEKKqOg/nWAl4B0P8XwBRXRLV3hhuDZxcm4xpIVq/+9/H+ywLRlrCoKxGENhdTRcUDsj8Br2mmJ9brzaa2sr9TReLDsWdn2YYImSSn6kNFaSVlrUmZeQMYYBV1MmrCBYbC2a6FaQUnGE7JRH5AGO2DSFxmc/cKV0yNelDyW09/Rh9oPWfO/7QdeC/SCu9sP0/v0wfaf7QWtvez9MN9wPepNrP2gtrv2g6VxWw8ZoHpnA5A8jLjkxHfqISwOT0Qfes7PRVDeMJnWuweWmnNtRGKljGe4cXWITHbqO52ErAO8ZzrA7Nyzy03V8MH+nwNO6MDEjQIoitkQuwW1yUNyQb8tc1q6i/VCt3WTDD7O9qzYoqK3wvHNxDNC2IYj7sHcCoafzXneAoD+uv9/pP2N8+M2fjuF7YrwyyVYhT+DQ8LFJW/VCyCgAHLlYWI4x8djWra1smq0nJ/RzY2n5tOj86X5ZUDz9KcZz+UPM22uJJ6Chp/uM69veKAUOQa1VOl4kt0O1atl3RRLFjW6tJW+tBbeGogQUYluw3l3iskLafLGLtvyhWOVBNSKC7i7hbEkkHuoS/StsA9Iq41JuXFEDyT9602AURw4xXtYkQbMf/QHvVggqrzaQTIR3yVqVqEjSZnU0EG9bZVPU6J6rEhrGrSNtVjajtpInbKvilNXN9JSevGkTDYmCYLwhD7I02RM8eUXydY3LS8lmVyt5KWkWHmxPqhGLwsHv10ZdEzSIBdYzEbHbpQuSht0rx5q6UCGNpisc+49HO/fC+BTFole0wCcxH7AuZghJ4+bgoN9gL4mxl4H/SRUfj1KcJGhw1qUxzz6b+MgSh7UuySKXtd7Sebh0mjk6zDSXzphqZ8uZspLpaNxkOlqWTCcD0Eds4rgOKPCZae0IvH4vWJ/KnGbdFMmv0lQLsasKQVdioMiIAbuAwCN1u0Uh/Q+bPKv65iTv5NvVQAN5eZIidbEZS1I+SkBB0tDB6clJp3+IDrpQoY12d8FHJLrh+PQp2xrmELC0Si37RPmVYPPkIUOzyKG7qpgBJChE5blRGq2GzDgbqWQ2bCecyuh4sPIviUnEzOScnjuW5flvv7MnJjFunwMEumN7Aa2uievonFilhoeFvuNjj9YPPMEQoMZCAjCdeq9PTf9oeRkwVjUYF4nPilC5Yp2SqvIcQqryoJynCUDfKj2NhTbGc1z7uLPD0sgf7IYNGvIDdN4OtSsSnayxFk7QWubaVYvBecEWbWl1WW3WxYYSofNSGW7ncAZaolgcJI19uPLo2SkXRqAiNZXNoqlksZ7Rik2hY9NtQ2YY7plz4xbVGnNWD6PJ5V1LusbR8BzCUrzAb96MfoH+/O0//gGF+t+Zzw0oLwpkpka0wA7602/+ER1EBtFHH4XqBRFF2myIqCaLsi6IbUHWdj4SEi2tROsYYx8dGt6MVjFBGePcMO3G4jX53OFr25jTqPSqFl54HnSuEXuafAK6S6YuUD5hd3V/4bmJbwP6IDI4oqiC1Seft2/MiWkIc0tYvEZnrklUX9g5M/qVbdyYU4Now8bYMhd0OI1bl+yPIZG3Gt6p/20h+OffhuCfWKkEqbFO1NdLfPi1LFNH5W2d3DfP8GNGeM1cNJlNkrNxX1UMRTFtmo05t2z2Nm2FbcuS+Y+eOYuAO2wv/JXVJ2/xnU5NRuBCgwx4Buy2o92V61EP4j17o5eXlmFfj+outsBQI5/DrksTXywiGVvXWhYclshpPlBE32kG7xSYUxuIom/6Fhlhx/IQJvaJvbJUjoYnx8IAg5y//ePVlb2mHvSGU3ram4LC0jFGyp7lVrLIlQST2lw1X5LOgwJLLCJ5wyxYedfKg2LJkz1g+OYNZOtpxJPc6Jao19IrDIrhV4xLj8ySyJ2FrwAo33eI7O7KSKDCS4Mlr+kL6RpdtufPuOmLaiNTzCTxoYcmS3c885Y0h1u7ayCgU4tOzTrqP+8d9jr1gE8PIEHCmo2jNPfOBc7GkAsiyAtLaKOFGygT+b6AcitOZWcRNtaGtRLnW2LCK6C7gkh0RqmwPYjSAtujHINmoZ1EVmyUjtvFcuMC8XjA6cIkOsmTvSBHkeYw5lJ1sixxxDFkiSuqK4vNB/aoYNmuLOJqhNG15L6nL2TEKqytX1wKEnyI/ORAXFzl3TPhlzwK4xPT8mHTsj2iUj6nL8g5CajyUZwi/EUKfiEGd/CL3lCCX7ToFYn8ch/fS0a2aaiT3u7xaLSHs85mFvBImE9KKV5Wl3r06OMj4lccYSa2l7KATdpvzKqcdGQkazNXoXchj6LMMGAU+FKiWMb9Uoqc1nm8ScyYA0mJAQ3ycsUpc7n+qVTZc/eREMvFYErp684fDGdNkcsDd6M4Hko8fVQLXX9aA8JGDEIu3toqR+I5cKwfmi4eE3f3Ndt8NZlL56uM7HQLF2dyJz5kwcj/i8hyWqUWR9plLkYdpcISZGLIbYOQXPYosbAxgVIqsClf4QmCVM5M+ELXbmZfoiCTLwRmWby8m4VMQDGiW/AgwP9Bb/8euINp1rAeQZ0u7WtQp+RXCM8Ch+ncDD8TRGYnhod++cvye/7yl+gW0wwkkGIChldYm4QoebZDBkIbkCfO9XJOvgf+cOOjjw7JZZ847tzw0aVBCbaRsbxCzzBeIGM1BzoqelUPnbnOV/jaR7O331k+AscIsHwGmAzJN8dR+JksLLm8IAgfffSLX6AvguPsSySgOF6kwzuwlr//DerjJXqEjrB74xD7dOZcYvsjAXVfXVtLD6x9j6IkeMRVBL8xAqCCssUJDmuu6GQxkHaE9R4rUt19iqcCQaLOkhjA1+QrqziVEEDqzU0/7J5z0ZFh+UEQCiLr6Cp8OMRx/Z4+Q+TMAMuK2Hp3M8NiLSKRNR5Mf7LNyk6aPcaCGq2kdo4e2KHBgYJ/g/WG9vQomjchizq5RDdQSUZEisiLl3gKFEetQbaktZxgr3ZEHA3nGPoSD4jxVNvZ2bk3j5o5zcKtH7t78d6dmRMQ8pwFEqTHA5NBE3fbYp5yREuHrWUtClvLqlaXtFZdkupiQ47C1mHOXOS9WBW4r9i/AK9CDL0MMZjtFdmmaOVkQMAn5XMoxDZWZPAU5BV+HQxVWrljQZWQtXQFGfj7ggpqAd8QheBRR4tNkvX2hu2vfKRzMlggaqkFwo3iqlT2FMgiBtYLLfkuJ1WpkHWUc7mJJquBsDLaE9nT4JnniFCovZUUkyxPVHGGJyXd+s6XKMJfXiwtLwV12Xk2vOgeH3cH6Lx73O0MuoyzV0tmz6YkcyQYGqf/WZiNLZUT757gerVIUo7VoMkYtJT1Bjn7FmQ20BQOJy7bDXP1+xUXv8WTL5ebmzbVUztyVXefd334oQWSBibdOqwNqPPLqNysKFheKkiHfPFuOYcV02YUHWqOsRhej5I2VMcdg8F97S8ZbaFcYqWaLZQt/yrbGUur2BSSUVkkLltnbJaqiaD+qjJPZymnYww4m0XfT7tBwevJDE3AFbkSzTwRR4jLHcJ1sz2hbB5C2aigyfOJ8zEt2FA5aOTO0vNCzBsLfIq05IF1b88Cu5wxyJatX1dWXjzqZX0DVAOg3Z2wfBNTF2q9n1EbZRZi7ExwwUQTzzERTAcpyBzUycWYGL6xG6zALjW5dzebs9RS40nvIM+5JbOCmQUuEp2LfWnY1+HKbndSARFnMKtG4E9s+CQlKTErY43gNBiDMtkeHKVaBCQH9VQGrfXutEmU9s2EWO9J9jKokmGnf9g5Pu0z2nPt1rtWI2Uefo2Cru+waQ8lm8XNao/s1WPFkVQaEDWJ99gNgKkH2ywrsjTwwLz5Vg+zokKhcPhV9EluFaS2tlqGR2iLAw6UBR1xFV2RG7HcFle6glkdtPnUQfODUwcROnkaRjyjDujL1dTBwXGv2x8K/dPDLuPzUd+tPjigkO2oTyQT0Z3Kuv/18v1Pq2Z99+13Uz+Bfh8AcyVNhInpQqA0RDo/MaDfTAgBX2kIMYLrinQGRLmAQJpRTpVsD001OVWyAD8fgJwmOFjT5Wh5aY3eqSawZ93zQW8w7PY/Z5ODLLbZluX1k0NjSWTAuPIxeubYV+Z06VLOcHI6ADfomL4WsILu7H3CNgW5XJRXXA4golN8+/a7mQUsDqFd7M3p6RaG/yOj+eL8GE2igdJAOwUWYBXbLHpeVbFtc/mObb4gR47rT6tSXtHiAcFWZL0cBSKO4kNVbvBvInzv0mJcoOGAVBR5rgH6NMTt0XhVZ2SSP4NC2g80mh/HektD9PEn3lPcPS53ePCwO5Gen8PuZWH33MEflsswLWyOWGmrIfeS1sySiLtel1pyXSZKfCsBd0VReNShokg/noC7kiMdYg64axsF3BWlzbf4TZ6Au6KI2wq4f/HOI+5xSdn7CbgrKlfAvaD+gfG2XHF0Rf0RxtG3Ffnqdy/Ynon2jiPnLJ1SjF6vtiZmvr7LNHJ2AxxqqFaijR32HNtvv69T7+KIeLYQcaflqAHRM9nR6BnUpNKqI/hWdF1h35hMKc9gptoJm7aHZ5eGy+ptaFyxXUX7CcV2e/2nx13hSe+Y0XbQ3m1w95OkCAKtBkR6vaDRkIgV9W1MG43CNsMRo3+sl4Z6P4H2RYRfGdc+riNy2NgBkl54yydk3ETEJwjcJqK5r535wrRoEV3gMNMdEdTjobPX/oz4N0FNnhlv2QYaLeg7UXPkKCQF8ZHnXAGMO1SmwXO9IZMH7vPXkHo5vQQP6u13MBgaSiK3J2482ZkeGtmLOXKXNnH3yMKNGp8wCnqbb580fzL7pN8dfv6ie86Gi6fo7zjiWdhaC9lNoUu2i20zZ1AVXS/fGJ0VqQ09DMLG3Uj/mwEJOkW+hWhRbXRL2XEaENEHR79BSwZ36ujWod1NtJ134TqXFp5bjpfiM0C9M6FDJud5q/6nkdSWG5LearxqvNoDMqrRTnCkHBAP1plTBgQPTpUpdpdXgM8TVMdeG7bNuiN0vvCqrvxkdkTnrMcmUs13G04dEcMao33iLhA1LXTtyQJqeTGj/DfXBE63mPraNRZmog94o6G2m6uh1n49OO0Huf6APWSbY+cctyyKiYF3y/qFWTN5SpMv1KxzhZoVjSvUrKhapdjKNt3rJMbshh72GaeH3ZI29LD/9Pt/yXRUPEL72CWOhDmlfzPeX+aShdLaSkZXW0qFtN6xs51Dhkhs+T/94R8ZF1Bn0/3ZB1iq/FdannZAQ34Xu3YE+8Go5LOVkkpCc+5jYlbfLac+sUzM+dvvAsfWuboy70xq2jBq0oiYKlXgkMAr2WykktheDfXMgHzO3dIlgw5qn8Aau4EnRnwJaAbCCxcHthclJqCSz6pGc4tUTY3mcmbvzBJ6EMFti1sS3C9Gz5NeI3lKHAIFyTvGsp5svZq+qqcTTt2JDY3MbE82e6Xk7jk2Mdk5X2H/zo994TlxnReOB7xrr8FnrRMvl+wpsNSJD3DlBv7EU9MXntG8ZegDgz8xxZcGpOiIUyNc9NDMuGSX3zafGdBq/7DlV92W4qWzemmPx41Lw2dUuG2tXGQSlOdBI2KYz4YYSIJGFdMCPFq04KEI2vfSdW497FKnLyTAIwYYs4Tw+Xpthc844Op6UXKNItXyQKrCU5SgrCGDi4sS9IaCgn9p72DQRjiBWFj42KIGw4Xr3BFHH12bkDInlqWDfPK8sbeNggTaM18OnfUTy6pbU6asOmBPsGx0VWzxZNWzIKCl6fSSvvBivLUUiUPn16fn6OIMeC4YZ8SVrlXF5tZz5dpGuXK22UvqhtlxqbVRdlzNAZRXW+4ciLtW7WnpD5EdVwoekrLp9uYxIuIEeSEs7p9+869szySHLtTkC+CtCjPlM1o9S5zzM5eYxD4avLbH6Gh5ucc4smy0Tk6YomFnf3c88++IdyTQO4FVQfMxNNhMzgHqM90t54jYGDam6ZYhNuHHjWOjA2KL18PBBSWRIZ8SsUD8pZdIfR5hc24Tu5ecUNeMBkhu+BWFXRb5dcuHIF7alsTrMGlrPAokjdLisEqXXi5dg1BaXBQQ/wR9H86tTf8A0RmMXXLuezPH9+pEGKde+JEAi6NCN1kUky2KF/u7S3r7zSYkqa3KjRK5i1QVWvXHIbTtbenEwBgWTgzbmLKii6nZsq6UIjRvsDAE8hwLU/0HTOJ1dN45EfpL/47ovzoKoMyEAfHIr7AVSPM+Ed8JjSl5wukiLEjnFFkw8TebkaTK1WVVEflktfWjkFVF2ZaCDVB3Vv0wwlFYGsQqtmq52MrqjJI2udicYVsgGnQK9IRQ7MERgaUtZnSwY69Kk1luqJKYyAzCrqIF3sY1FLvbNG2loQPDvjE84alrLGbMgavcnSoKrSL/OIS2uSWhHUJoAXVtIk3MYtoqF9OLOTEcDcu/NFx0dxuSbh7AmphjdEDWoo760FowN1yoIZrUUc+eLMm4TMNCHeodBcrW9h0iKeaEWUxafGKic3lKUpsnfqSK2v3xI402tcC/1myOLGLJ4ZnhTm7JQs4dG8LJ6Mqwkbsgb779/gpcZI8YXI7rQZTJgEbS658jSB9IBElj7MtQ1faHHUE66pwfvuicd9Gg2x+cng/YZsVXFaCqrR90FEnTNowiifJmUSSNz0fRVC7dqDZ/VFGkFZQq55Guy1s60o/hbDgKz4aT8Gw47w6GQlAnTzPgjGd9toIvedY/Iar+kqg5Iewwv3KNqR/mncSWhozLALjzxDBtyjgiAIs8sQqBeIkYAsTxQmfk+8SxI9+6DY/+4+DwIlOZ3RnANItq52cnzD6OztXMperS+zUXH0669C1J1+D5U3RguuOlRUy8p8Zyij1WWWqWy9JzfE2kNARgxXXa40d/Rc+Ix+NNTIPI7XweeOzEg5iYNGokPHn7PaWfDCQtEnrh2IDO3ztg22AWnCaf4Gg/EsFpilvzNFxsTISBcYX914wikyteTIhM59KLYWYMK2Iit8mdl9dUw4Cs+NjyeDxknw4aoHyPif1c29ls2JKox+NmlcemxCePXAlxVRe5HBpVv9+hkahDA/+uuvHtm7mFpotl2IKPFt7SNy00X1q+OXaIy0g+gH/2Yj4QL0Zi9WJa8oftxZx3O8fCsHdC3Jgh+f2k13/KODE+a6Ml/aAdmdamzeKS1kCd5ZTshQpeTIuv9KDF1SmutsQflRezgmflsxba28pWSsIAXwfU9XEPF6uh2dbXBihDxvKgSm7pzYSBTw75uRn3blWFgEzldW69Xcu8wZuNVBITpYC0q/HWxERrzRwLiGvPHMsCW4TRhGjz+f3t95ybfDAZ3VZyMiy67z8/OWaTTE1ck5g8EDpnPbRv2mBuBv7Mc8hK7mMLT2la8unZhXAAVtABBHProdN86Bq3kAd6YfhB1y18bOVpMwpLbmhVhaX1oxAWTVS2JiwnGD1CJ2DK0qfIKjJrkoKH2DdMK6icR3BNYd+wrkMKld7uKTqktHmGfxc6wyAnJ/u7XiBe4DUFThOF8sPsssKVk9NEmesobnMV66rN9v2+iUh9E/jXtIlDYFiA3IUpDRpEFhYmWt6AQ2IjI8D9HoPH+Y4cE+QQa8L0X69jffzZRwl9FJHRR9Ek7X35KCqTj9Lr94a9znElaCtN4rIANEn9IfsnGmulZh7MqtVAv15aJrt3ovEVL2qlxYuMD0p5CO/kfuixDJ1ZupOr63r+DXaByJg8c4B1DmDj8wG4guOxnNeLcf0z9oeWOCYNy0MDYlRZWHhCvh4WrUZZ81SzDI0vPyE6nthidXQRKnk4Tl3sLRwbKCHm6KLHelLKTQ6sTE3WeU46TeJjtcvGACsSKWeR3aQqg5dyg6/STiQpWc0V7/yXfvFBnGQGvfFr9tKyUnSgVyYQ5AHyEsBi3hG9tQIFAOhN8nPiOguBYlzOi4gco2M1/BNY/8ZL13OIunecueAs/fv4WgpIoIGx71bQiL0Qcve1xZvZl+WHqTmHbee5472Xft2A2t/Pyc3JzM5cfGPi2xSlenBxCuUYXr1FmQGTZIWF51YE5AhYn87lV0AjOCaHoGGyNZprWfwwqUSdFfK6Fj29GN1UAHhTBQkBvqmCFim++AClFPgQJ4IendEBTXNMHA/vaaspWlNWEmM4uhgPrmwWUqqkNbI4RFI1rZGF+4qpJphuns32x32i43sN4HVbrKVttsXYtxS51Re/EC8lUcJfFsHBhJR3kajI4ZYLhDziDhf0FIapUohhKms7X8Znrh7DmRLX7MqY0J9UIZiAUwPE50HHuswXJswa9aUktmDnb9OcL/B7lJTfs8LoyTOgpoFjo9rKsoc8zdqPOtmCjPZcs4zSle3beiUS8JKlmikFNMGU3DVDxh1xzOccoMCqOrk4HvaEswMU0h8NTk4PLwboxdu/Pzru9tnWoyUyUtwWgRV7WVrm2O/JAym9MKHnnWymkGy10DC8DLDZY1Crx4yTUHj4R7Vs5KCaQaQ1tTKma4ZTzap9LKX5yRO85AFrcLyF47MqPo/v4Qt/+BMsy50VLxXbc2qVrBTjQqts5kMpT+y96iv5ZDyyUQMkt9TTUQuCOaG9F8KfZ8M6hZFQFf3F1w5wy9N7UFD4mCZtV83TsqY5WYtZK+EACuDjg8NVzRPMhyKUCUdUAZSn4kXB3gW5SFDbYhm9dVIb/Pnb3/6WSeL0bGvxPSo3fYKRvVTMDMxJGM99kMqb0cgHuOpzVJ6nypK/Bdws0GzK5nDrrCGHMhZ3iqiXhOnTCqgAExB8wStyCRugHnyyMPaf5dUbJOjRGOfKxVmhl/rh9dXOzlrHZbj/HmJJd3Sg8YZxbhldGzdBMs5N4rIL0pUaxBoIN6JHNGNS9Ee9OUsUKS3VbAuQixKuCAO3SoaYMYkCOLoHoEDMTajdLmZA5Kc+vHcKmxIe5h+KmJwEgySs40TccAjtVUixgTqQOyNXvKQ1CrTJCUpSwx546KQnr9ElRneQXzMsyoIFNq2NAIuWMYKoyyKPzapLXEE8LZs7l9ZmADJmEeWu27ZdFNyEGkax37gyaOL2u2KzKOuW/2Cson/+t//4939gk2NF+9kwKjaMivqyV7SWKEWaybbWqrRNoyiQ74RNRF+Qi+GLq1hEdIqMM5S5TCFVXGsKBZu5oi20vsW2gimUrVpWq6naXMLj/ZpCGUFmXIL2uzSGYnxlNluoMntrbjqSKD2sLcQ+gw3pXPNPhNcSsips9nY5lWzAVwL2DCBaAv6LC0W9Ifdw5FfSGkayINi1kyD5zO3/erbXs6L5k20Lr2b+6Nn0bSXzZ0wtwm3bP+FdHo8SHLcJ24W+VG4Aae26pIh1mai+H5gF9E+/Y5PhbEPgz+ZPZP5EHMhlZMG1czx3/OS2ZbSC9PY2raBAyBNWEH1BLuZyXmcFrZhfjXkYFGKbX5OrOUrXW2ttoHBDVzSC4n3OawRlg+eaWG1yzXdhBI1CmcR+5FKHRxCt38FkQHMUgc8ECaTg+UL/PP1WgAK1Yq4OGarBMf9V2pZJMdhHHCohmHMyqBCch+S+cA0UsNgB8jg56djWXS9buHVSUVTQpaAH0Bn39alEobaQlYatmFlvMfpHpr2Acpiv/deLcCyj+o1BRHxvWSenLGXY2MOffjap4QY5EqfYb9C3d+oLcnLhGRF/AAuLGHKkhiSKAUdOPZ3yD6pHS6pYIqWzojiV0hVyQWnIlTNeenvO0oepUjLb8KXsEbzammyLxedqtUSe6i9d17ksJ03jSuG1mxum8O49etGCmB/Ro/ZzBk7Gjl/H6VmyaQrKWkcvTBcqW1CGwDxBIT7FXnQcMSqMdrNiOjnYTNGfSWP1a+qWDHwHwpYND/s9soC1CB4MOhYW45dz6gE5O/UgFX2F/fGsFuDYhR/ZDT7yNdGpM2eyNzo7HQxH9RklPfT2vv7kgJLF+cKQDOQT4pgsFmQEtLpll9K5f1O/dCav94CspwGQUPaUPLfa13DVPaceaMAwmPxy6Vp7y292vtlp+DNs14guwHRJazurV74mcwnm9BLm/ujRrJZ+Bb5OBkDmQVeBXK6eruumm15OVIgFhmpchhJn2uMYRIbReGV6pbiN5aIApLrzZdb0TzsGKehmGpyiZ5yJXcro0rFv4XCzGcWHK8eu5zrXqhWZZVmPqhWZZXvjS2yMK8ehq5bcojOhBfpcRfcrilhH5Ir5qX6IONrDGlAt+jwUCIY+WFofJAnbgdI9/kbwWq4poJJb9QBtFRk3oejQD4txTk9OOv1DdNDtD7vnTOLWzAFYMjIwjN4wXl9iu35hcY1PnPWYtSvlr6cDjInCmXTgx8Nzk65cxpMHpeHCOEd13/QtcsGYnZaYnB6epVxB6FdpNWTGCctbXtB2tesntpg5ARsZ2orsYO6J4OXuLhrV7YbvXADbVtAcVR+hk9PDLltEqKmWSRLb17NQtW2ulpZKGyxcmPmkaGHOOyd7ZGm+arjG/OXSwxOyKrvxC77jGxZ55ek+6yqpG4oHa6dkM8vNVllAiteh//yki4anw84xLMeZD8IBHYvn6A35+0n89wvWhdC3vhDNDReCnB9Ul8CJkfYPmMBDyVbqn6Lj3klvOEC7u4yDbXHtnixRSrva3tOLuzKYejrkbNdpXBR/Y0DA+VOwRRfwfwv7u55LzFHgE/a9V6NfkQfRw42xi8lBe06sgp3ahHhogDzeIL5jF8IAtr//ujepjVzy9ogYkS7YUm4t9QgvGwOAyvWBZi0hKqnP3JF3ip/EPk7Op5WbTPCdHZYvZ5G04i/v/OojRP77611v7JoL/7OP4Hewqj/76K93Z/7c+uz/A5qqyLWQfAoA"""

try:
    EMBEDDED_HTML_DASHBOARD = gzip.decompress(base64.b64decode(REACT_APP_BUNDLE_B64)).decode("utf-8")
except Exception as _err:
    EMBEDDED_HTML_DASHBOARD = "<!DOCTYPE html><html><body><h1>no0bz Command Center</h1><p>Error loading React bundle</p></body></html>"

# Embedded or Prebuilt Frontend Route
@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(content=EMBEDDED_HTML_DASHBOARD)

@app.get("/index.html", response_class=HTMLResponse)
def index_html_page():
    return index_page()

if __name__ == "__main__":
    print("=" * 64)
    print(f"  👑 no0bz Command Center (NCC) - {VERSION}")
    print(f"  Web GUI & API: http://localhost:{PORT}")
    print(f"  WebSocket Feed: ws://localhost:{PORT}/ws/live")
    print("=" * 64)
    if not MULTIPART_AVAILABLE:
        print("  [Notice] File uploads disabled. To enable: pip install python-multipart")
    if not PYNVML_AVAILABLE:
        print("  [Notice] NVIDIA GPU sensors: install with 'pip install nvidia-ml-py'")
    if not DUCKDB_AVAILABLE:
        print("  [Notice] 24h DuckDB metrics logging: install with 'pip install duckdb'")
    print("=" * 64)
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False, workers=1)
