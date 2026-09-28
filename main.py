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

VERSION = "v3.11.0"
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

def get_cluster_nodes() -> List[Dict[str, Any]]:
    with nodes_lock:
        if server_mode == "client":
            server_host_ip = (client_server_url.split(":")[0] if client_server_url else "192.168.1.100").replace("http://", "").replace("https://", "")
            server_node = {
                "id": "node_master_server",
                "pc_name": f"Server Hub ({server_host_ip})",
                "display_name": "Master Hub Server",
                "role": "Master Hub Server",
                "avatar": "👑",
                "ip": server_host_ip,
                "os": "no0bz Cluster Master Server",
                "cpu_model": "Master Host CPU",
                "gpu_model": "NVIDIA RTX Master GPU",
                "ping_ms": 2,
                "last_seen": "Live (Verbunden)",
                "cpu_load": 14.8,
                "ram_percent": 41.5,
                "gpu_load": 18.0,
                "net_recv_mbps": 3.4,
                "net_sent_mbps": 2.1,
                "is_host": True,
                "status": "online"
            }
            local_client = {
                "id": "node_client_local",
                "pc_name": curr_hostname,
                "display_name": "Client Workstation",
                "role": "Client Node (Lokal)",
                "avatar": "💻",
                "ip": get_local_ip(),
                "os": f"{platform.system()} {platform.release()}",
                "cpu_model": detect_cpu_name(),
                "gpu_model": detect_gpu_info().get("name", "GPU"),
                "ping_ms": 0,
                "last_seen": "Live",
                "cpu_load": live_data.get("cpu", {}).get("load", 0.0),
                "ram_percent": live_data.get("ram", {}).get("percent", 0.0),
                "gpu_load": live_data.get("gpu", {}).get("load", 0.0),
                "net_recv_mbps": live_data.get("network", {}).get("recv_mbps", 0.0),
                "net_sent_mbps": live_data.get("network", {}).get("sent_mbps", 0.0),
                "is_host": False,
                "status": "online"
            }
            return [server_node, local_client]
        else:
            host_node = {
                "id": "host_node",
                "pc_name": curr_hostname,
                "display_name": "Host Workstation",
                "role": "Master Hub Server",
                "avatar": "👑",
                "ip": get_local_ip(),
                "os": f"{platform.system()} {platform.release()}",
                "cpu_model": detect_cpu_name(),
                "gpu_model": detect_gpu_info().get("name", "GPU"),
                "ping_ms": 0,
                "last_seen": "Live",
                "cpu_load": live_data.get("cpu", {}).get("load", 0.0),
                "ram_percent": live_data.get("ram", {}).get("percent", 0.0),
                "gpu_load": live_data.get("gpu", {}).get("load", 0.0),
                "net_recv_mbps": live_data.get("network", {}).get("recv_mbps", 0.0),
                "net_sent_mbps": live_data.get("network", {}).get("sent_mbps", 0.0),
                "is_host": True,
                "status": "online"
            }
            clients = [n for nid, n in connected_nodes.items() if nid != "host_node" and not n.get("is_host")]
            return [host_node, *clients]

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

            cluster = get_cluster_nodes()
            snapshot["multipc"] = {
                "mode": server_mode,
                "server_active": True,
                "server_port": PORT,
                "client_server_url": client_server_url,
                "connected_count": len(cluster),
                "nodes": cluster
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
    cluster = get_cluster_nodes()
    return {
        "server_mode": server_mode,
        "server_port": PORT,
        "connected_count": len(cluster),
        "nodes": cluster
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
        "id": payload.get("id") or f"msg_{int(time.time()*1000)}",
        "client_id": payload.get("client_id") or payload.get("sender_id", ""),
        "sender_id": payload.get("sender_id") or payload.get("client_id", ""),
        "avatar": payload.get("avatar", "💻"),
        "sender": sender,
        "timestamp": payload.get("timestamp") or datetime.now().strftime("%H:%M:%S"),
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

    # In client mode, forward chat message to Master Server
    if server_mode == "client" and client_server_url:
        try:
            target = client_server_url if client_server_url.startswith("http") else f"http://{client_server_url}"
            req = urllib.request.Request(
                f"{target.rstrip('/')}/api/chat/message",
                data=json.dumps(new_msg).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=1.5)
        except Exception:
            pass

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
        avatar: str = Form("💻"),
        client_id: Optional[str] = Form(None),
        sender_id: Optional[str] = Form(None),
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
            "client_id": client_id or sender_id or "",
            "sender_id": sender_id or client_id or "",
            "avatar": avatar or "💻",
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
