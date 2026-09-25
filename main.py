#!/usr/bin/env python3
"""
no0bz Command Center (NCC) - Version v3.7.0
High-Performance Single-File System Monitor & Local P2P Sync Hub
FastAPI, WebSockets, NVML, DuckDB, File Transfer & HTML/JS Frontend
"""

import os
import sys
import time
import json
import shutil
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

VERSION = "v3.7.0"
PORT = 8350
LHM_URL = "http://127.0.0.1:8085/data.json"
DB_FILE = "no0bz_metrics.duckdb"
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ncc_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Thread-safe telemetry store
data_lock = threading.Lock()
chat_lock = threading.Lock()

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
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self.conn = None
        if DUCKDB_AVAILABLE:
            try:
                self.conn = duckdb.connect(self.db_path, read_only=False)
                self.init_db()
            except Exception as e:
                print(f"[DB] Init warning: {e}")
                self.conn = None

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
        except Exception as e:
            print(f"[DB] Table creation error: {e}")

    def insert_metric(self, snapshot: Dict[str, Any]):
        if not self.conn:
            return
        try:
            now = datetime.now()
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
            # Purge data older than 24h
            cutoff = now - timedelta(hours=24)
            self.conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        except Exception as e:
            print(f"[DB] Insert error: {e}")

    def query_history(self, limit: int = 120) -> List[Dict[str, Any]]:
        if not self.conn:
            return []
        try:
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
                snapshot = json.dumps(live_data)
            await websocket.send_text(snapshot)
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, asyncio.CancelledError):
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

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
        return chat_messages

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

    with chat_lock:
        chat_messages.append(new_msg)
        if len(chat_messages) > 300:
            chat_messages.pop(0)

    await broadcast_chat_event("chat_message", new_msg)
    return {"status": "ok", "message": new_msg}

# ================= FILE BROWSER & UPLOAD ENDPOINTS =================
if MULTIPART_AVAILABLE:
    @app.post("/api/chat/upload")
    async def upload_files(
        files: List[UploadFile] = File(...),
        sender: str = Form("PC-User"),
        note: Optional[str] = Form(None)
    ):
        if len(files) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 files allowed per upload batch")

        saved_attachments = []
        for f in files:
            safe_filename = os.path.basename(f.filename or f"file_{int(time.time())}")
            file_path = os.path.join(UPLOAD_DIR, safe_filename)

            # Write file to disk
            size_bytes = 0
            with open(file_path, "wb") as buffer:
                while chunk := await f.read(1024 * 1024):
                    buffer.write(chunk)
                    size_bytes += len(chunk)

            ext = os.path.splitext(safe_filename)[1].lower()
            is_image = ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]

            saved_attachments.append({
                "name": safe_filename,
                "size": size_bytes,
                "ext": ext.replace(".", "").upper() or "FILE",
                "is_image": is_image,
                "url": f"/api/chat/download/{safe_filename}",
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        # Create associated chat message
        new_msg = {
            "id": f"msg_{int(time.time()*1000)}",
            "sender": sender,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": "files",
            "title": f"Sent {len(saved_attachments)} file(s)",
            "content": note or f"Uploaded {len(saved_attachments)} file(s) to shared vault.",
            "tokens": 0,
            "attachments": saved_attachments
        }

        with chat_lock:
            chat_messages.append(new_msg)

        await broadcast_chat_event("chat_message", new_msg)
        return {"status": "ok", "uploaded_count": len(saved_attachments), "attachments": saved_attachments}
else:
    @app.post("/api/chat/upload")
    async def upload_files_fallback():
        raise HTTPException(
            status_code=501,
            detail="File upload requires 'python-multipart'. Please run: pip install python-multipart"
        )

@app.get("/api/chat/files")
def list_uploaded_files():
    file_list = []
    if os.path.exists(UPLOAD_DIR):
        for fname in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                ext = os.path.splitext(fname)[1].lower()
                is_img = ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]
                file_list.append({
                    "name": fname,
                    "size": stat.st_size,
                    "ext": ext.replace(".", "").upper() or "FILE",
                    "is_image": is_img,
                    "url": f"/api/chat/download/{fname}",
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
    file_list.sort(key=lambda x: x["uploaded_at"], reverse=True)
    return file_list

@app.get("/api/chat/download/{filename}")
def download_file(filename: str):
    safe_name = os.path.basename(filename)
    fpath = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(fpath, filename=safe_name)

@app.delete("/api/chat/files/{filename}")
def delete_file(filename: str):
    safe_name = os.path.basename(filename)
    fpath = os.path.join(UPLOAD_DIR, safe_name)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            return {"status": "ok", "message": f"Deleted {safe_name}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="File not found")


# ================= CHANGELOG ROUTES =================
DEFAULT_CHANGELOG_MD = """# 📜 no0bz Command Center (NCC) – Changelog

Alle wichtigen Änderungen, neuen Funktionen und Optimierungen für das **no0bz Command Center (NCC)** werden in dieser Datei chronologisch dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

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
