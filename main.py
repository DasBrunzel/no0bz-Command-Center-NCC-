#!/usr/bin/env python3
"""
no0bz Command Center (NCC) - Version v3.6.3
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
import uvicorn

# Optional: pynvml or nvidia-ml-py for NVIDIA GPU
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")
warnings.filterwarnings("ignore", message=".*pynvml package is deprecated.*")

try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    try:
        import nvidia_ml_py as pynvml
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

VERSION = "v3.6.3"
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

# Embedded Frontend
@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <title>no0bz Command Center (NCC) v3.6.3</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    body { background: #07090e; color: #fff; font-family: system-ui, sans-serif; margin: 0; padding: 2rem; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 80vh; }
    .card { background: rgba(15,23,42,0.8); border: 1px solid rgba(0,255,200,0.2); border-radius: 1rem; padding: 2rem; max-width: 600px; text-align: center; box-shadow: 0 0 30px rgba(0,255,200,0.1); }
    h1 { color: #00ffc8; margin-bottom: 0.5rem; text-shadow: 0 0 10px rgba(0,255,200,0.4); }
    p { color: #94a3b8; line-height: 1.6; }
    .badge { display: inline-block; background: #00ffc8; color: #000; font-weight: bold; padding: 0.2rem 0.6rem; border-radius: 9999px; margin-bottom: 1rem; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">NCC v3.6.3 ONLINE</div>
    <h1>no0bz Command Center</h1>
    <p>High-Performance System Monitor &amp; P2P Chat/Prompt Sync Hub.</p>
    <p>WebSockets are active at <code>ws://localhost:8350/ws/live</code>.<br/>API endpoints are ready for React Client &amp; Terminal Services.</p>
  </div>
</body>
</html>
""")

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
