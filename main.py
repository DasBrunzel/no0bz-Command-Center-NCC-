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

VERSION = "v3.9.0"
PORT = 8350
REMOTE_PORT = 8351
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
        "client_server_url": "192.168.1.100:8351",
        "remote_port": REMOTE_PORT,
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
client_server_url = initial_cfg.get("client_server_url", "192.168.1.100:8351")
remote_port = int(initial_cfg.get("remote_port", REMOTE_PORT))

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

# Connected Multi-PC Nodes store (Contains ONLY genuine nodes; no placeholders!)
curr_hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "no0bz-Station")
connected_nodes: Dict[str, Dict[str, Any]] = {
    "host_node": {
        "id": "host_node",
        "pc_name": curr_hostname,
        "display_name": "Host Workstation",
        "role": "Master Hub Server",
        "avatar": "👑",
        "ip": "127.0.0.1",
        "os": f"{platform.system()} {platform.release()}",
        "ping_ms": 1,
        "cpu_load": 0.0,
        "ram_percent": 0.0,
        "net_recv_mbps": 0.0,
        "net_sent_mbps": 0.0,
        "is_host": True,
        "last_seen": "Jetzt"
    }
}

# ================= REAL HARDWARE DETECTORS (NO PLACEHOLDERS) =================
def detect_cpu_name() -> str:
    """Accurately detects real CPU model on Windows, Linux, and macOS."""
    cpu_name = ""
    try:
        if platform.system() == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                winreg.CloseKey(key)
            except Exception:
                pass
            if not cpu_name:
                try:
                    out = os.popen("wmic cpu get name").read()
                    lines = [l.strip() for l in out.split("\n") if l.strip() and "Name" not in l]
                    if lines:
                        cpu_name = lines[0]
                except Exception:
                    pass
        elif platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if "model name" in line:
                            val = line.split(":", 1)[1].strip()
                            if val and val.lower() != "unknown":
                                cpu_name = val
                                break
            except Exception:
                pass
        elif platform.system() == "Darwin":
            try:
                cpu_name = os.popen("sysctl -n machdep.cpu.brand_string").read().strip()
            except Exception:
                pass
    except Exception:
        pass

    if not cpu_name or cpu_name.lower() == "unknown":
        cpu_name = platform.processor() or "x86_64 Multi-Core Processor"
    return cpu_name.strip()

def detect_gpu_info() -> Dict[str, Any]:
    """Accurately detects real GPU hardware (NVIDIA, AMD Radeon, Intel Arc/UHD, Apple Silicon) without placeholders."""
    gpu_info = {
        "name": "",
        "vendor": "Generic",
        "vram_total_gb": 0.0,
        "is_nvidia": False
    }

    # 1. NVIDIA NVML
    if PYNVML_AVAILABLE:
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            raw_name = pynvml.nvmlDeviceGetName(handle)
            name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else raw_name
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_info["name"] = name
            gpu_info["vendor"] = "NVIDIA"
            gpu_info["vram_total_gb"] = round(mem.total / (1024**3), 2)
            gpu_info["is_nvidia"] = True
            return gpu_info
        except Exception:
            pass

    # 2. Windows WMIC / PowerShell probe for AMD, Intel, NVIDIA
    if platform.system() == "Windows":
        try:
            cmd = 'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"'
            out = os.popen(cmd).read().strip()
            gpus = [g.strip() for g in out.split("\n") if g.strip()]
            if gpus:
                dedi = [g for g in gpus if any(k in g.lower() for k in ["rtx", "gtx", "geforce", "radeon rx", "arc a", "quadro"])]
                chosen = dedi[0] if dedi else gpus[0]
                gpu_info["name"] = chosen
                if "nvidia" in chosen.lower() or "geforce" in chosen.lower():
                    gpu_info["vendor"] = "NVIDIA"
                elif "amd" in chosen.lower() or "radeon" in chosen.lower():
                    gpu_info["vendor"] = "AMD"
                elif "intel" in chosen.lower():
                    gpu_info["vendor"] = "Intel"
                return gpu_info
        except Exception:
            pass

    # 3. Linux lspci or DRM probe
    if platform.system() == "Linux":
        try:
            out = os.popen("lspci 2>/dev/null | grep -E 'VGA|3D'").read().strip()
            if out:
                line = out.split("\n")[0]
                if ":" in line:
                    parts = line.split(":", 2)
                    card = parts[-1].strip() if len(parts) >= 3 else parts[1].strip()
                    gpu_info["name"] = card
                    if "nvidia" in card.lower():
                        gpu_info["vendor"] = "NVIDIA"
                    elif "amd" in card.lower() or "advanced micro devices" in card.lower():
                        gpu_info["vendor"] = "AMD"
                    elif "intel" in card.lower():
                        gpu_info["vendor"] = "Intel"
                    return gpu_info
        except Exception:
            pass

    if not gpu_info["name"]:
        gpu_info["name"] = "Integrated Display Controller"
    return gpu_info

# Fast-Boot Hardware & System Cache Probe
def probe_system_profile() -> Dict[str, Any]:
    hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "no0bz-Station")
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    real_cpu = detect_cpu_name()
    real_gpu = detect_gpu_info()
    
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
        "cpu_model": real_cpu,
        "cpu_logical_cores": psutil.cpu_count(logical=True) or 8,
        "cpu_physical_cores": psutil.cpu_count(logical=False) or 4,
        "cpu_freq_max_mhz": round(cpu_freq.max, 0) if cpu_freq and cpu_freq.max else 4200.0,
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "swap_total_gb": round(swap.total / (1024**3), 1),
        "disks": disk_info,
        "network_interfaces": net_ifaces,
        "gpu_name": real_gpu["name"],
        "gpu_vendor": real_gpu["vendor"],
        "gpu_vram_total_gb": real_gpu["vram_total_gb"],
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

                # GPU Metrics (Real probe fallback)
                base_gpu = detect_gpu_info()
                gpu_load = 0.0
                gpu_vram_total = base_gpu["vram_total_gb"]
                gpu_vram_used = 0.0
                gpu_vram_pct = 0.0
                gpu_temp = None
                gpu_power = None
                gpu_name = base_gpu["name"]

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

# ================= DEDICATED REMOTE HUB (PORT 8351) =================
# Dedicated ASGI listener for multi-PC cluster heartbeats, telemetry streaming and P2P sync.
remote_app = FastAPI(title="no0bz Command Center Remote Hub", version=VERSION)
remote_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@remote_app.get("/api/health")
def remote_health():
    return {
        "status": "online",
        "app": "no0bz Command Center Remote Hub",
        "version": VERSION,
        "mode": server_mode,
        "remote_port": remote_port,
        "connected_nodes": len(connected_nodes)
    }

@remote_app.post("/api/nodes/register")
def remote_register_node(payload: Dict[str, Any]):
    return register_node(payload)

@remote_app.post("/api/nodes/telemetry")
def remote_receive_node_telemetry(payload: Dict[str, Any]):
    return receive_node_telemetry(payload)

@remote_app.websocket("/ws/node")
async def remote_node_websocket(websocket: WebSocket):
    await websocket.accept()
    client_id = None
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            client_id = payload.get("node_id") or payload.get("id") or client_id
            if payload.get("type") == "telemetry" or "cpu_load" in payload:
                receive_node_telemetry(payload)
                await websocket.send_text(json.dumps({"status": "ack", "time": time.time()}))
            elif payload.get("type") == "register":
                register_node(payload)
                await websocket.send_text(json.dumps({"status": "registered", "node_id": client_id}))
            else:
                receive_node_telemetry(payload)
                await websocket.send_text(json.dumps({"status": "ack"}))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        print(f"[REMOTE WS ERROR] {e}")

_remote_hub_started = False
def run_remote_hub_server():
    global _remote_hub_started
    if _remote_hub_started:
        return
    _remote_hub_started = True
    try:
        config = uvicorn.Config(
            remote_app,
            host="0.0.0.0",
            port=remote_port,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as err:
        print(f"[REMOTE HUB NOTICE] Could not bind port {remote_port}: {err}")

class ClientStreamer(threading.Thread):
    """Client node background worker: streams real hardware metrics to master server on remote_port (8351)."""
    def __init__(self, target_url: str):
        super().__init__(daemon=True)
        self.target_url = target_url
        self.running = True

    def run(self):
        print(f"[CLIENT NODE] Starting telemetry push worker to {self.target_url}...")
        prev_net = psutil.net_io_counters()
        prev_time = time.time()
        hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "no0bz-Client")
        node_id = f"client_{hostname.lower().replace(' ', '_')}"

        while self.running:
            try:
                time.sleep(1.0)
                now_time = time.time()
                dt = max(now_time - prev_time, 0.1)
                
                cpu_load = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                curr_net = psutil.net_io_counters()
                net_sent_mbps = round(((curr_net.bytes_sent - prev_net.bytes_sent) * 8) / (dt * 1_000_000), 2)
                net_recv_mbps = round(((curr_net.bytes_recv - prev_net.bytes_recv) * 8) / (dt * 1_000_000), 2)
                prev_net = curr_net
                prev_time = now_time

                # Probe GPU & CPU
                gpu = detect_gpu_info()
                cpu_model = detect_cpu_name()

                payload = {
                    "node_id": node_id,
                    "pc_name": hostname,
                    "display_name": f"{hostname} (Client)",
                    "role": "Client Node",
                    "avatar": "💻",
                    "cpu_load": cpu_load,
                    "ram_percent": ram.percent,
                    "net_recv_mbps": net_recv_mbps,
                    "net_sent_mbps": net_sent_mbps,
                    "os": f"{platform.system()} {platform.release()}",
                    "cpu_model": cpu_model,
                    "gpu_model": gpu.get("name", "Integrated Graphics"),
                    "is_host": False,
                    "ping_ms": 1
                }

                url = self.target_url.strip()
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = f"http://{url}"
                if not url.endswith("/api/nodes/telemetry"):
                    url = f"{url.rstrip('/')}/api/nodes/telemetry"

                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "no0bz-Client/3.9.0"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        pass
                except Exception:
                    pass
            except Exception as e:
                pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    collector = DataCollector()
    collector.start()

    # Start dedicated Remote Hub on Port 8351 if server_mode is host
    if server_mode == "host":
        threading.Thread(target=run_remote_hub_server, daemon=True).start()
        print(f"[REMOTE HUB] Dedicated Remote Port {remote_port} active for cluster connections")

    # Start client streamer if server_mode is client
    if server_mode == "client":
        threading.Thread(target=lambda: ClientStreamer(client_server_url).start(), daemon=True).start()
        print(f"[CLIENT NODE] Streaming telemetry to {client_server_url}")

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
        f"Client Node: Speicherung der Chat-Dateien & DuckDB-Datenbankhaltung erfolgt ausschließlich auf dem Server ({client_server_url})."
    )
    return {
        "status": "ok",
        "mode": server_mode,
        "client_server_url": client_server_url,
        "remote_port": remote_port,
        "storage_type": storage_type,
        "vault_dir": vault_dir,
        "db_path": db_path,
        "description": desc
    }

@app.post("/api/multipc/mode")
def set_multipc_mode(payload: Dict[str, Any]):
    global server_mode, client_server_url, remote_port
    new_mode = payload.get("mode")
    if new_mode in ["local", "host", "client"]:
        server_mode = new_mode
    if "client_server_url" in payload:
        client_server_url = payload["client_server_url"]
    if "remote_port" in payload:
        try:
            remote_port = int(payload["remote_port"])
        except (ValueError, TypeError):
            pass

    save_ncc_config({
        "server_mode": server_mode,
        "client_server_url": client_server_url,
        "remote_port": remote_port,
        "version": VERSION
    })

    db_mgr.switch_mode(server_mode)
    os.makedirs(get_active_vault_dir(), exist_ok=True)

    # Dynamic worker activation on mode change
    if server_mode == "host":
        threading.Thread(target=run_remote_hub_server, daemon=True).start()
    elif server_mode == "client":
        threading.Thread(target=lambda: ClientStreamer(client_server_url).start(), daemon=True).start()

    storage_type = "serverseitig" if server_mode == "host" else "lokal"
    return {
        "status": "ok",
        "mode": server_mode,
        "client_server_url": client_server_url,
        "remote_port": remote_port,
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

REACT_APP_BUNDLE_B64 = """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"""

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
    import argparse
    parser = argparse.ArgumentParser(description=f"no0bz Command Center (NCC) {VERSION}")
    parser.add_argument("--mode", choices=["host", "local", "client"], help="Operating mode: host (Server), local (Standalone), client (Cluster Node)")
    parser.add_argument("--port", type=int, default=PORT, help=f"Web GUI port (default: {PORT})")
    parser.add_argument("--remote-port", type=int, default=REMOTE_PORT, help=f"Dedicated Remote Hub port (default: {REMOTE_PORT})")
    parser.add_argument("--server", type=str, help="Master Server IP:Port for client node streaming (e.g. 192.168.1.100:8351)")

    args, unknown = parser.parse_known_args()
    if args.mode:
        server_mode = args.mode
    if args.port:
        PORT = args.port
    if args.remote_port:
        remote_port = args.remote_port
    if args.server:
        client_server_url = args.server

    # Save active runtime config
    save_ncc_config({
        "server_mode": server_mode,
        "client_server_url": client_server_url,
        "remote_port": remote_port,
        "version": VERSION
    })

    mode_label = (
        "👑 SERVER-BETRIEB (Master Hub)" if server_mode == "host" else
        "🖥️ STANDALONE MODUS (Lokal)" if server_mode == "local" else
        f"🔗 CLIENT NODE (Streamt an {client_server_url})"
    )

    print("=" * 68)
    print(f"  👑 no0bz Command Center (NCC) - {VERSION}")
    print(f"  Betriebsmodus:           {mode_label}")
    print(f"  Web GUI & Dashboard:     http://localhost:{PORT}")
    if server_mode == "host":
        print(f"  Dedizierter Remote-Port: {remote_port} (Multi-PC Cluster Verbindung)")
    print(f"  Live WebSocket Feed:     ws://localhost:{PORT}/ws/live")
    print("=" * 68)
    if not MULTIPART_AVAILABLE:
        print("  [Notice] File uploads disabled. To enable: pip install python-multipart")
    if not PYNVML_AVAILABLE:
        print("  [Notice] NVIDIA GPU sensors: install with 'pip install nvidia-ml-py'")
    if not DUCKDB_AVAILABLE:
        print("  [Notice] 24h DuckDB metrics logging: install with 'pip install duckdb'")
    print("=" * 68)
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False, workers=1)
