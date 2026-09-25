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

# ================= EMBEDDED STANDALONE HTML5 DASHBOARD =================
EMBEDDED_HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="de" data-theme="cachyos">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>no0bz Command Center (NCC) v3.7.0</title>
  <style>
    :root[data-theme="cachyos"] {
      --bg: #07090e; --panel: #0d131f; --panel-border: rgba(0, 255, 200, 0.18);
      --accent: #00ffc8; --accent-glow: rgba(0, 255, 200, 0.35); --text: #f1f5f9;
      --muted: #94a3b8; --danger: #ef4444; --card-bg: rgba(13, 19, 31, 0.85);
    }
    :root[data-theme="cyber"] {
      --bg: #0b0314; --panel: #160a29; --panel-border: rgba(255, 0, 127, 0.25);
      --accent: #ff007f; --accent-glow: rgba(255, 0, 127, 0.4); --text: #ffffff;
      --muted: #a78bfa; --danger: #ff3366; --card-bg: rgba(22, 10, 41, 0.85);
    }
    :root[data-theme="oled"] {
      --bg: #000000; --panel: #0a0a0c; --panel-border: rgba(59, 130, 246, 0.2);
      --accent: #3b82f6; --accent-glow: rgba(59, 130, 246, 0.35); --text: #f8fafc;
      --muted: #64748b; --danger: #f43f5e; --card-bg: rgba(10, 10, 12, 0.9);
    }
    :root[data-theme="matrix"] {
      --bg: #020904; --panel: #051408; --panel-border: rgba(0, 255, 65, 0.25);
      --accent: #00ff41; --accent-glow: rgba(0, 255, 65, 0.4); --text: #dcfce7;
      --muted: #86efac; --danger: #ef4444; --card-bg: rgba(5, 20, 8, 0.88);
    }
    :root[data-theme="dracula"] {
      --bg: #1e1f29; --panel: #282a36; --panel-border: rgba(189, 147, 249, 0.25);
      --accent: #bd93f9; --accent-glow: rgba(189, 147, 249, 0.4); --text: #f8f8f2;
      --muted: #6272a4; --danger: #ff5555; --card-bg: rgba(40, 42, 54, 0.88);
    }
    :root[data-theme="nordic"] {
      --bg: #0f172a; --panel: #1e293b; --panel-border: rgba(56, 189, 248, 0.22);
      --accent: #38bdf8; --accent-glow: rgba(56, 189, 248, 0.35); --text: #f1f5f9;
      --muted: #94a3b8; --danger: #f87171; --card-bg: rgba(30, 41, 59, 0.85);
    }
    :root[data-theme="amber"] {
      --bg: #120b02; --panel: #211606; --panel-border: rgba(255, 176, 0, 0.25);
      --accent: #ffb000; --accent-glow: rgba(255, 176, 0, 0.4); --text: #fef3c7;
      --muted: #d97706; --danger: #ef4444; --card-bg: rgba(33, 22, 6, 0.88);
    }
    :root[data-theme="light"] {
      --bg: #f8fafc; --panel: #ffffff; --panel-border: rgba(2, 132, 199, 0.2);
      --accent: #0284c7; --accent-glow: rgba(2, 132, 199, 0.2); --text: #0f172a;
      --muted: #64748b; --danger: #dc2626; --card-bg: rgba(255, 255, 255, 0.95);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      min-height: 100vh;
      overflow-x: hidden;
      transition: background 0.2s, color 0.2s;
    }

    /* Header & Navigation */
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--panel-border);
      padding: 0.75rem 1.5rem;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      position: sticky;
      top: 0;
      z-index: 50;
      backdrop-filter: blur(12px);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      text-decoration: none;
      color: inherit;
    }
    .crown-icon {
      width: 32px;
      height: 32px;
      fill: var(--accent);
      filter: drop-shadow(0 0 8px var(--accent-glow));
    }
    .brand-title {
      font-size: 1.25rem;
      font-weight: 900;
      letter-spacing: -0.5px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .brand-title span { color: var(--accent); }
    .badge {
      font-size: 0.65rem;
      font-weight: 700;
      padding: 0.15rem 0.5rem;
      border-radius: 9999px;
      background: rgba(255,255,255,0.08);
      border: 1px solid var(--panel-border);
      color: var(--accent);
      font-family: monospace;
      letter-spacing: 0.5px;
    }

    .top-meta {
      display: flex;
      align-items: center;
      gap: 1rem;
      font-size: 0.8rem;
      color: var(--muted);
      flex-wrap: wrap;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      display: inline-block;
      margin-right: 4px;
    }
    .status-dot.offline {
      background: var(--danger);
      box-shadow: 0 0 8px var(--danger);
    }

    .controls {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    select, button, input {
      background: var(--panel);
      border: 1px solid var(--panel-border);
      color: var(--text);
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      font-size: 0.8rem;
      outline: none;
      transition: all 0.2s;
    }
    select:focus, input:focus, button:hover {
      border-color: var(--accent);
      box-shadow: 0 0 10px var(--accent-glow);
    }
    button.btn-accent {
      background: var(--accent);
      color: #000;
      font-weight: 700;
      cursor: pointer;
    }

    /* Main Container */
    main {
      max-width: 1440px;
      margin: 1.5rem auto;
      padding: 0 1.5rem 3rem;
    }

    /* Bento Grid */
    .bento-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    .bento-card {
      background: var(--card-bg);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      padding: 1.25rem;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
      position: relative;
      overflow: hidden;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      padding-bottom: 0.5rem;
    }
    .card-title {
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--muted);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .card-val {
      font-size: 1.5rem;
      font-weight: 900;
      color: var(--accent);
      font-family: monospace;
    }

    /* Gauges */
    .gauge-container {
      display: flex;
      align-items: center;
      justify-content: space-around;
      gap: 1rem;
      margin: 0.5rem 0;
    }
    .gauge-svg {
      width: 110px;
      height: 110px;
      transform: rotate(-90deg);
    }
    .gauge-bg {
      fill: none;
      stroke: rgba(255,255,255,0.08);
      stroke-width: 8;
    }
    .gauge-progress {
      fill: none;
      stroke: var(--accent);
      stroke-width: 8;
      stroke-linecap: round;
      transition: stroke-dashoffset 0.6s ease;
      filter: drop-shadow(0 0 6px var(--accent-glow));
    }
    .gauge-text {
      position: absolute;
      text-align: center;
      font-family: monospace;
    }
    .gauge-text .pct {
      font-size: 1.35rem;
      font-weight: 800;
      color: var(--text);
    }
    .gauge-text .lbl {
      font-size: 0.65rem;
      color: var(--muted);
      text-transform: uppercase;
    }

    .meta-list {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      font-size: 0.78rem;
      color: var(--muted);
      font-family: monospace;
      margin-top: 0.5rem;
    }
    .meta-row {
      display: flex;
      justify-content: space-between;
      border-bottom: 1px dashed rgba(255,255,255,0.04);
      padding-bottom: 0.2rem;
    }
    .meta-row span:last-child {
      color: var(--text);
      font-weight: 600;
    }

    /* Core load bars */
    .cores-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 4px;
      margin-top: 0.75rem;
    }
    .core-bar-wrapper {
      background: rgba(255,255,255,0.05);
      height: 24px;
      border-radius: 4px;
      position: relative;
      overflow: hidden;
    }
    .core-bar-fill {
      background: var(--accent);
      height: 100%;
      width: 0%;
      transition: width 0.4s ease;
      opacity: 0.8;
    }
    .core-bar-label {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 0.62rem;
      font-family: monospace;
      font-weight: 700;
      color: #fff;
      text-shadow: 0 0 3px #000;
    }

    /* Canvas Chart */
    .chart-card {
      background: var(--card-bg);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
    }
    canvas#telemetryChart {
      width: 100%;
      height: 220px;
      display: block;
      margin-top: 0.75rem;
    }

    /* Process Manager & Chat tabs */
    .tabs-section {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
    }
    @media (max-width: 1024px) {
      .tabs-section { grid-template-columns: 1fr; }
    }
    .section-card {
      background: var(--card-bg);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      padding: 1.25rem;
    }
    .search-box {
      width: 100%;
      margin-bottom: 0.75rem;
    }
    .proc-table-wrapper {
      max-height: 380px;
      overflow-y: auto;
      border: 1px solid rgba(255,255,255,0.05);
      border-radius: 6px;
    }
    table.proc-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.78rem;
      font-family: monospace;
    }
    table.proc-table th {
      background: var(--panel);
      padding: 0.5rem;
      text-align: left;
      position: sticky;
      top: 0;
      border-bottom: 1px solid var(--panel-border);
      color: var(--muted);
    }
    table.proc-table td {
      padding: 0.4rem 0.5rem;
      border-bottom: 1px solid rgba(255,255,255,0.03);
    }
    table.proc-table tr:hover {
      background: rgba(255,255,255,0.03);
    }
    .btn-kill {
      background: transparent;
      border: 1px solid var(--danger);
      color: var(--danger);
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      font-size: 0.7rem;
      cursor: pointer;
    }
    .btn-kill:hover {
      background: var(--danger);
      color: #fff;
    }

    /* Chat & File Vault */
    .chat-messages {
      max-height: 280px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
      margin-bottom: 0.75rem;
      padding-right: 0.25rem;
    }
    .chat-bubble {
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 8px;
      padding: 0.6rem 0.75rem;
      font-size: 0.8rem;
    }
    .chat-bubble-header {
      display: flex;
      justify-content: space-between;
      color: var(--muted);
      font-size: 0.7rem;
      margin-bottom: 0.3rem;
      font-family: monospace;
    }
    .chat-bubble-title {
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 0.25rem;
    }
    .chat-bubble-content {
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.4;
    }
    .chat-actions {
      display: flex;
      gap: 0.5rem;
      margin-top: 0.4rem;
    }
    .prompt-form {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    textarea {
      background: var(--panel);
      border: 1px solid var(--panel-border);
      color: var(--text);
      padding: 0.5rem;
      border-radius: 6px;
      font-size: 0.8rem;
      resize: vertical;
      min-height: 70px;
      font-family: inherit;
    }

    /* Upload Dropzone */
    .dropzone {
      border: 2px dashed var(--panel-border);
      border-radius: 8px;
      padding: 1rem;
      text-align: center;
      color: var(--muted);
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.2s;
      margin-top: 0.5rem;
    }
    .dropzone:hover {
      border-color: var(--accent);
      color: var(--text);
    }

    /* Debug Console */
    .debug-console {
      background: #000;
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 8px;
      padding: 0.75rem;
      font-family: monospace;
      font-size: 0.7rem;
      color: #10b981;
      height: 140px;
      overflow-y: auto;
      margin-top: 1.5rem;
    }
    .debug-line { margin-bottom: 2px; }
    .debug-time { color: #6b7280; margin-right: 6px; }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <a href="/" class="brand">
      <svg class="crown-icon" viewBox="0 0 24 24">
        <path d="M2.5 19h19c.8 0 1.5-.7 1.5-1.5 0-.4-.2-.8-.5-1.1L19 11l-4 6-3-11-3 11-4-6-3.5 5.4c-.3.3-.5.7-.5 1.1 0 .8.7 1.5 1.5 1.5z" />
        <circle cx="5" cy="5" r="1.5" />
        <circle cx="12" cy="2.5" r="1.5" />
        <circle cx="19" cy="5" r="1.5" />
        <rect x="3" y="19.5" width="18" height="2" rx="1" />
      </svg>
      <div class="brand-title">no<span>0</span>bz COMMAND CENTER</div>
      <span class="badge">v3.7.0</span>
    </a>

    <div class="top-meta">
      <div><span id="wsStatusDot" class="status-dot"></span> <span id="wsStatusText">WS: Connecting...</span></div>
      <div>Host: <strong id="hostNameBadge" style="color:var(--text);">--</strong></div>
      <div>Uptime: <span id="uptimeBadge">--:--:--</span></div>
    </div>

    <div class="controls">
      <select id="themeSelect">
        <option value="cachyos">CachyOS Cyan</option>
        <option value="cyber">Cyber Neon</option>
        <option value="oled">Dark Matter OLED</option>
        <option value="matrix">Matrix Hacker</option>
        <option value="dracula">Dracula</option>
        <option value="nordic">Nordic Frost</option>
        <option value="amber">Retro Amber</option>
        <option value="light">Clean Light</option>
      </select>
      <button id="btnRefreshProcs" title="Refresh Process List">⟳ Procs</button>
    </div>
  </header>

  <!-- Main Dashboard -->
  <main>
    <!-- Bento Grid Cards -->
    <div class="bento-grid">
      
      <!-- CPU Card -->
      <div class="bento-card">
        <div class="card-header">
          <div class="card-title">⚡ CPU Package</div>
          <div class="card-val" id="cpuLoadText">0%</div>
        </div>
        <div class="gauge-container">
          <div style="position:relative; display:flex; align-items:center; justify-content:center;">
            <svg class="gauge-svg" viewBox="0 0 100 100">
              <circle class="gauge-bg" cx="50" cy="50" r="40" />
              <circle id="cpuGaugeCircle" class="gauge-progress" cx="50" cy="50" r="40" stroke-dasharray="251.2" stroke-dashoffset="251.2" />
            </svg>
            <div class="gauge-text">
              <div class="pct" id="cpuGaugePct">0%</div>
              <div class="lbl">Load</div>
            </div>
          </div>
          <div class="meta-list" style="flex:1;">
            <div class="meta-row"><span>Freq:</span> <span id="cpuFreqVal">-- GHz</span></div>
            <div class="meta-row"><span>Cores:</span> <span id="cpuCoresVal">-- Cores</span></div>
            <div class="meta-row"><span>Power:</span> <span id="cpuPowerVal">-- W</span></div>
            <div class="meta-row"><span>Temp:</span> <span id="cpuTempVal">-- °C</span></div>
          </div>
        </div>
        <div class="cores-grid" id="cpuCoresGrid"></div>
      </div>

      <!-- RAM Card -->
      <div class="bento-card">
        <div class="card-header">
          <div class="card-title">🧠 Memory (RAM)</div>
          <div class="card-val" id="ramLoadText">0%</div>
        </div>
        <div class="gauge-container">
          <div style="position:relative; display:flex; align-items:center; justify-content:center;">
            <svg class="gauge-svg" viewBox="0 0 100 100">
              <circle class="gauge-bg" cx="50" cy="50" r="40" />
              <circle id="ramGaugeCircle" class="gauge-progress" cx="50" cy="50" r="40" stroke-dasharray="251.2" stroke-dashoffset="251.2" />
            </svg>
            <div class="gauge-text">
              <div class="pct" id="ramGaugePct">0%</div>
              <div class="lbl">RAM</div>
            </div>
          </div>
          <div class="meta-list" style="flex:1;">
            <div class="meta-row"><span>Used:</span> <span id="ramUsedVal">-- GB</span></div>
            <div class="meta-row"><span>Total:</span> <span id="ramTotalVal">-- GB</span></div>
            <div class="meta-row"><span>Swap Used:</span> <span id="swapUsedVal">-- GB</span></div>
            <div class="meta-row"><span>Swap %:</span> <span id="swapPctVal">-- %</span></div>
          </div>
        </div>
      </div>

      <!-- GPU Card -->
      <div class="bento-card">
        <div class="card-header">
          <div class="card-title">🎮 GPU (NVIDIA / Core)</div>
          <div class="card-val" id="gpuLoadText">0%</div>
        </div>
        <div class="gauge-container">
          <div style="position:relative; display:flex; align-items:center; justify-content:center;">
            <svg class="gauge-svg" viewBox="0 0 100 100">
              <circle class="gauge-bg" cx="50" cy="50" r="40" />
              <circle id="gpuGaugeCircle" class="gauge-progress" cx="50" cy="50" r="40" stroke-dasharray="251.2" stroke-dashoffset="251.2" />
            </svg>
            <div class="gauge-text">
              <div class="pct" id="gpuGaugePct">0%</div>
              <div class="lbl">GPU</div>
            </div>
          </div>
          <div class="meta-list" style="flex:1;">
            <div class="meta-row"><span>VRAM:</span> <span id="gpuVramVal">-- GB</span></div>
            <div class="meta-row"><span>Temp:</span> <span id="gpuTempVal">-- °C</span></div>
            <div class="meta-row"><span>Power:</span> <span id="gpuPowerVal">-- W</span></div>
            <div class="meta-row" style="text-overflow:ellipsis; overflow:hidden;"><span>Model:</span> <span id="gpuNameVal" style="font-size:0.65rem;">--</span></div>
          </div>
        </div>
      </div>

      <!-- Network Card -->
      <div class="bento-card">
        <div class="card-header">
          <div class="card-title">🌐 Network I/O</div>
          <div class="card-val" id="netSpeedText">0 Mbps</div>
        </div>
        <div class="gauge-container">
          <div style="position:relative; display:flex; align-items:center; justify-content:center;">
            <svg class="gauge-svg" viewBox="0 0 100 100">
              <circle class="gauge-bg" cx="50" cy="50" r="40" />
              <circle id="netGaugeCircle" class="gauge-progress" cx="50" cy="50" r="40" stroke-dasharray="251.2" stroke-dashoffset="251.2" />
            </svg>
            <div class="gauge-text">
              <div class="pct" id="netGaugePct">0</div>
              <div class="lbl">Mbps</div>
            </div>
          </div>
          <div class="meta-list" style="flex:1;">
            <div class="meta-row"><span>Down:</span> <span id="netRecvVal">0.0 Mbps</span></div>
            <div class="meta-row"><span>Up:</span> <span id="netSentVal">0.0 Mbps</span></div>
            <div class="meta-row"><span>Total In:</span> <span id="netTotalInVal">-- GB</span></div>
            <div class="meta-row"><span>Total Out:</span> <span id="netTotalOutVal">-- GB</span></div>
          </div>
        </div>
      </div>

    </div>

    <!-- Live Telemetry History Chart -->
    <div class="chart-card">
      <div class="card-header" style="margin-bottom:0;">
        <div class="card-title">📈 Real-Time Telemetry History (60 Seconds)</div>
        <div style="display:flex; gap:1rem; font-size:0.75rem; font-family:monospace;">
          <span style="color:var(--accent);">■ CPU %</span>
          <span style="color:#a855f7;">■ RAM %</span>
          <span style="color:#ef4444;">■ GPU %</span>
          <span style="color:#38bdf8;">■ Net Mbps</span>
        </div>
      </div>
      <canvas id="telemetryChart"></canvas>
    </div>

    <!-- Process Manager & P2P Chat/Vault Section -->
    <div class="tabs-section">
      
      <!-- Process Manager -->
      <div class="section-card">
        <div class="card-header">
          <div class="card-title">⚙ Process Manager</div>
          <span class="badge" id="procCountBadge">0 Running</span>
        </div>
        <input type="text" id="procSearchInput" class="search-box" placeholder="Search processes by name or PID..." />
        <div class="proc-table-wrapper">
          <table class="proc-table">
            <thead>
              <tr>
                <th>PID</th>
                <th>Name</th>
                <th>CPU %</th>
                <th>RAM %</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="procTableBody">
              <tr><td colspan="5" style="text-align:center; color:var(--muted); padding:1rem;">Loading process list...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- P2P Prompt & Vault Hub -->
      <div class="section-card">
        <div class="card-header">
          <div class="card-title">💬 P2P Prompt &amp; File Vault</div>
          <span class="badge">WebSocket Sync</span>
        </div>
        <div class="chat-messages" id="chatMessagesList">
          <div style="color:var(--muted); text-align:center; padding:1rem;">No prompts or files shared yet.</div>
        </div>
        <div class="prompt-form">
          <div style="display:flex; gap:0.5rem;">
            <input type="text" id="promptTitleInput" placeholder="Prompt Title (e.g., PyTorch Optimizer)" style="flex:1;" />
            <input type="text" id="promptSenderInput" value="PC-User" style="width:110px;" />
          </div>
          <textarea id="promptContentInput" placeholder="Type prompt, script, or notes to broadcast..."></textarea>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:0.7rem; color:var(--muted); font-family:monospace;" id="tokenCounter">0 words • ~0 tokens</span>
            <button class="btn-accent" id="btnSendPrompt">🚀 Broadcast Prompt</button>
          </div>
          <div class="dropzone" id="fileDropzone">
            📂 Drag &amp; drop files here to upload to shared vault
            <input type="file" id="fileInputElem" multiple style="display:none;" />
          </div>
        </div>
      </div>

    </div>

    <!-- Debug Console -->
    <div class="debug-console" id="debugConsole">
      <div class="debug-line"><span class="debug-time">[INIT]</span> no0bz Command Center v3.7.0 standalone dashboard initialized.</div>
    </div>
  </main>

  <script>
    // Theme Management
    const themeSelect = document.getElementById('themeSelect');
    const savedTheme = localStorage.getItem('no0bz_theme') || 'cachyos';
    document.documentElement.setAttribute('data-theme', savedTheme);
    themeSelect.value = savedTheme;
    themeSelect.addEventListener('change', (e) => {
      document.documentElement.setAttribute('data-theme', e.target.value);
      localStorage.setItem('no0bz_theme', e.target.value);
    });

    // Logging helper
    const debugConsole = document.getElementById('debugConsole');
    function logMsg(tag, msg) {
      const line = document.createElement('div');
      line.className = 'debug-line';
      const timeStr = new Date().toLocaleTimeString();
      line.innerHTML = `<span class="debug-time">[${timeStr}] [${tag}]</span> ${msg}`;
      debugConsole.appendChild(line);
      debugConsole.scrollTop = debugConsole.scrollHeight;
    }

    // SVG Gauge Helper
    function setGauge(circleId, pct) {
      const circle = document.getElementById(circleId);
      if (!circle) return;
      const circumference = 251.2;
      const offset = circumference - (Math.min(Math.max(pct, 0), 100) / 100) * circumference;
      circle.style.strokeDashoffset = offset;
    }

    // Telemetry History Buffer
    const maxHistory = 60;
    const historyData = {
      cpu: new Array(maxHistory).fill(0),
      ram: new Array(maxHistory).fill(0),
      gpu: new Array(maxHistory).fill(0),
      net: new Array(maxHistory).fill(0)
    };

    // Canvas Chart Setup
    const canvas = document.getElementById('telemetryChart');
    const ctx = canvas.getContext('2d');
    function resizeCanvas() {
      canvas.width = canvas.parentElement.clientWidth - 40;
      canvas.height = 220;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function drawChart() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;
      const pad = 25;

      // Draw Grid Lines
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 1;
      for (let y = 0; y <= 4; y++) {
        const yPos = pad + (h - pad * 2) * (y / 4);
        ctx.beginPath();
        ctx.moveTo(pad, yPos);
        ctx.lineTo(w - pad, yPos);
        ctx.stroke();
        ctx.fillStyle = '#64748b';
        ctx.font = '10px monospace';
        ctx.fillText(`${100 - y * 25}%`, 4, yPos + 3);
      }

      function drawLine(arr, color) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.shadowColor = color;
        ctx.shadowBlur = 6;
        ctx.beginPath();
        for (let i = 0; i < arr.length; i++) {
          const x = pad + (i / (maxHistory - 1)) * (w - pad * 2);
          const val = Math.min(Math.max(arr[i], 0), 100);
          const y = (h - pad) - (val / 100) * (h - pad * 2);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#00ffc8';
      drawLine(historyData.cpu, accentColor);
      drawLine(historyData.ram, '#a855f7');
      drawLine(historyData.gpu, '#ef4444');
      drawLine(historyData.net, '#38bdf8');
    }

    // WebSocket Connection
    let ws = null;
    function connectWS() {
      const isHttps = location.protocol === 'https:';
      const wsProtocol = isHttps ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${location.host}/ws/live`;
      logMsg('WS', `Connecting to ${wsUrl}...`);

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        document.getElementById('wsStatusDot').classList.remove('offline');
        document.getElementById('wsStatusText').textContent = 'WS: Connected';
        logMsg('WS', 'Connected to real-time telemetry feed.');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'chat_message') {
            appendChatMessage(data.data);
            return;
          }

          // Update System Header
          if (data.hostname) document.getElementById('hostNameBadge').textContent = data.hostname;
          if (data.uptime_seconds !== undefined) {
            const h = Math.floor(data.uptime_seconds / 3600);
            const m = Math.floor((data.uptime_seconds % 3600) / 60);
            const s = data.uptime_seconds % 60;
            document.getElementById('uptimeBadge').textContent = 
              `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
          }

          // CPU Metrics
          if (data.cpu) {
            const cpuLoad = Math.round(data.cpu.load);
            document.getElementById('cpuLoadText').textContent = `${cpuLoad}%`;
            document.getElementById('cpuGaugePct').textContent = `${cpuLoad}%`;
            setGauge('cpuGaugeCircle', cpuLoad);
            document.getElementById('cpuFreqVal').textContent = `${(data.cpu.freq_current / 1000).toFixed(2)} GHz`;
            document.getElementById('cpuCoresVal').textContent = `${data.cpu.count} Cores`;
            document.getElementById('cpuPowerVal').textContent = data.cpu.power_w ? `${data.cpu.power_w.toFixed(1)} W` : '-- W';
            document.getElementById('cpuTempVal').textContent = data.cpu.temp_c ? `${data.cpu.temp_c.toFixed(1)} °C` : '-- °C';

            // Cores Grid
            if (data.cpu.cores && data.cpu.cores.length > 0) {
              const grid = document.getElementById('cpuCoresGrid');
              if (grid.children.length !== data.cpu.cores.length) {
                grid.innerHTML = '';
                data.cpu.cores.forEach((_, idx) => {
                  const el = document.createElement('div');
                  el.className = 'core-bar-wrapper';
                  el.innerHTML = `<div class="core-bar-fill" id="coreFill_${idx}"></div><div class="core-bar-label">C${idx}</div>`;
                  grid.appendChild(el);
                });
              }
              data.cpu.cores.forEach((cLoad, idx) => {
                const fill = document.getElementById(`coreFill_${idx}`);
                if (fill) fill.style.width = `${Math.min(cLoad, 100)}%`;
              });
            }

            // Push to history
            historyData.cpu.shift();
            historyData.cpu.push(cpuLoad);
          }

          // RAM Metrics
          if (data.ram) {
            const ramPct = Math.round(data.ram.percent);
            document.getElementById('ramLoadText').textContent = `${ramPct}%`;
            document.getElementById('ramGaugePct').textContent = `${ramPct}%`;
            setGauge('ramGaugeCircle', ramPct);
            document.getElementById('ramUsedVal').textContent = `${data.ram.used_gb.toFixed(1)} GB`;
            document.getElementById('ramTotalVal').textContent = `${data.ram.total_gb.toFixed(1)} GB`;
            document.getElementById('swapUsedVal').textContent = `${data.ram.swap_used_gb.toFixed(1)} GB`;
            document.getElementById('swapPctVal').textContent = `${Math.round(data.ram.swap_percent)} %`;

            historyData.ram.shift();
            historyData.ram.push(ramPct);
          }

          // GPU Metrics
          if (data.gpu) {
            const gpuLoad = Math.round(data.gpu.load);
            document.getElementById('gpuLoadText').textContent = `${gpuLoad}%`;
            document.getElementById('gpuGaugePct').textContent = `${gpuLoad}%`;
            setGauge('gpuGaugeCircle', gpuLoad);
            document.getElementById('gpuVramVal').textContent = `${data.gpu.vram_used_gb.toFixed(1)} / ${data.gpu.vram_total_gb.toFixed(1)} GB`;
            document.getElementById('gpuTempVal').textContent = data.gpu.temp_c ? `${data.gpu.temp_c.toFixed(1)} °C` : '-- °C';
            document.getElementById('gpuPowerVal').textContent = data.gpu.power_w ? `${data.gpu.power_w.toFixed(1)} W` : '-- W';
            document.getElementById('gpuNameVal').textContent = data.gpu.name || 'NVIDIA Core';

            historyData.gpu.shift();
            historyData.gpu.push(gpuLoad);
          }

          // Network Metrics
          if (data.network) {
            const totalMbps = (data.network.recv_mbps + data.network.sent_mbps);
            document.getElementById('netSpeedText').textContent = `${totalMbps.toFixed(1)} Mbps`;
            document.getElementById('netGaugePct').textContent = totalMbps.toFixed(0);
            setGauge('netGaugeCircle', Math.min(totalMbps, 100));
            document.getElementById('netRecvVal').textContent = `${data.network.recv_mbps.toFixed(2)} Mbps`;
            document.getElementById('netSentVal').textContent = `${data.network.sent_mbps.toFixed(2)} Mbps`;
            document.getElementById('netTotalInVal').textContent = `${data.network.total_recv_gb.toFixed(2)} GB`;
            document.getElementById('netTotalOutVal').textContent = `${data.network.total_sent_gb.toFixed(2)} GB`;

            historyData.net.shift();
            historyData.net.push(Math.min(totalMbps, 100));
          }

          drawChart();

        } catch (err) {
          console.error(err);
        }
      };

      ws.onclose = () => {
        document.getElementById('wsStatusDot').classList.add('offline');
        document.getElementById('wsStatusText').textContent = 'WS: Disconnected';
        logMsg('WS', 'Connection lost. Reconnecting in 2s...');
        setTimeout(connectWS, 2000);
      };

      ws.onerror = (e) => {
        logMsg('WS-ERR', 'WebSocket communication issue.');
      };
    }
    connectWS();

    // Process Manager Logic
    let allProcesses = [];
    async function loadProcesses() {
      try {
        const res = await fetch('/api/processes');
        if (res.ok) {
          allProcesses = await res.json();
          renderProcesses();
        }
      } catch (err) {
        logMsg('PROC-ERR', `Failed to load processes: ${err}`);
      }
    }

    function renderProcesses() {
      const q = document.getElementById('procSearchInput').value.toLowerCase();
      const tbody = document.getElementById('procTableBody');
      const filtered = allProcesses.filter(p => 
        p.name.toLowerCase().includes(q) || String(p.pid).includes(q)
      );
      document.getElementById('procCountBadge').textContent = `${filtered.length} Procs`;
      
      if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:1rem; color:var(--muted);">No matching processes found.</td></tr>';
        return;
      }

      tbody.innerHTML = filtered.slice(0, 30).map(p => `
        <tr>
          <td><strong style="color:var(--text);">${p.pid}</strong></td>
          <td style="color:var(--accent); font-weight:600;">${p.name}</td>
          <td>${p.cpu}%</td>
          <td>${p.ram}%</td>
          <td><button class="btn-kill" onclick="killProcess(${p.pid}, '${p.name}')">Kill</button></td>
        </tr>
      `).join('');
    }

    document.getElementById('procSearchInput').addEventListener('input', renderProcesses);
    document.getElementById('btnRefreshProcs').addEventListener('click', loadProcesses);
    loadProcesses();
    setInterval(loadProcesses, 4000);

    window.killProcess = async function(pid, name) {
      if (!confirm(`Are you sure you want to terminate PID ${pid} (${name})?`)) return;
      try {
        const res = await fetch('/api/kill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pid })
        });
        const out = await res.json();
        if (res.ok) {
          logMsg('PROC', `Killed PID ${pid} (${name}) successfully.`);
          loadProcesses();
        } else {
          alert(`Error: ${out.detail || 'Could not terminate'}`);
        }
      } catch (e) {
        alert(`Error terminating process: ${e}`);
      }
    };

    // Chat & Prompt Vault Logic
    const chatList = document.getElementById('chatMessagesList');
    function appendChatMessage(msg) {
      if (!msg) return;
      if (chatList.children.length === 1 && chatList.children[0].textContent.includes('No prompts')) {
        chatList.innerHTML = '';
      }
      const el = document.createElement('div');
      el.className = 'chat-bubble';
      
      let attachHtml = '';
      if (msg.attachments && msg.attachments.length > 0) {
        attachHtml = `<div style="margin-top:0.4rem; display:flex; flex-direction:column; gap:4px;">` +
          msg.attachments.map(a => `
            <div style="font-size:0.75rem; background:rgba(255,255,255,0.04); padding:4px 8px; border-radius:4px; display:flex; justify-content:space-between; align-items:center;">
              <span>📁 ${a.name} (${(a.size/1024).toFixed(1)} KB)</span>
              <a href="${a.url}" download="${a.name}" style="color:var(--accent); text-decoration:none; font-weight:bold;">Download</a>
            </div>
          `).join('') + `</div>`;
      }

      el.innerHTML = `
        <div class="chat-bubble-header">
          <span>${msg.sender || 'User'}</span>
          <span>${msg.timestamp}</span>
        </div>
        ${msg.title ? `<div class="chat-bubble-title">${msg.title}</div>` : ''}
        <div class="chat-bubble-content">${escapeHtml(msg.content)}</div>
        ${attachHtml}
        <div class="chat-actions">
          <button style="padding:2px 8px; font-size:0.68rem;" onclick="copyText('${escapeQuotes(msg.content)}')">📋 Copy Content</button>
        </div>
      `;
      chatList.appendChild(el);
      chatList.scrollTop = chatList.scrollHeight;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    function escapeQuotes(str) {
      if (!str) return '';
      return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    }
    window.copyText = function(text) {
      navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
      });
    };

    // Load initial messages
    async function loadChatMessages() {
      try {
        const res = await fetch('/api/chat/messages');
        if (res.ok) {
          const msgs = await res.json();
          chatList.innerHTML = '';
          msgs.forEach(appendChatMessage);
        }
      } catch (e) {
        console.error(e);
      }
    }
    loadChatMessages();

    // Token & Word counter
    const promptInput = document.getElementById('promptContentInput');
    promptInput.addEventListener('input', () => {
      const text = promptInput.value.trim();
      const words = text ? text.split(/\\s+/).length : 0;
      const tokens = Math.round(text.length / 3.8);
      document.getElementById('tokenCounter').textContent = `${words} words • ~${tokens} tokens`;
    });

    // Send Prompt
    document.getElementById('btnSendPrompt').addEventListener('click', async () => {
      const content = promptInput.value.trim();
      const title = document.getElementById('promptTitleInput').value.trim() || 'Prompt Transfer';
      const sender = document.getElementById('promptSenderInput').value.trim() || 'PC-User';
      if (!content) return;

      try {
        const res = await fetch('/api/chat/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, title, sender, type: 'prompt' })
        });
        if (res.ok) {
          promptInput.value = '';
          document.getElementById('promptTitleInput').value = '';
          document.getElementById('tokenCounter').textContent = '0 words • ~0 tokens';
          logMsg('CHAT', 'Broadcast prompt successfully.');
        }
      } catch (err) {
        alert(`Error sending prompt: ${err}`);
      }
    });

    // File Upload Drag & Drop
    const dropzone = document.getElementById('fileDropzone');
    const fileElem = document.getElementById('fileInputElem');
    dropzone.addEventListener('click', () => fileElem.click());
    fileElem.addEventListener('change', () => handleUpload(fileElem.files));

    dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.style.borderColor = 'var(--accent)'; });
    dropzone.addEventListener('dragleave', () => { dropzone.style.borderColor = 'var(--panel-border)'; });
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.style.borderColor = 'var(--panel-border)';
      if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files);
    });

    async function handleUpload(files) {
      if (!files || !files.length) return;
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
      formData.append('sender', document.getElementById('promptSenderInput').value.trim() || 'PC-User');
      formData.append('note', `Uploaded ${files.length} file(s) via Web UI`);

      dropzone.textContent = `⏳ Uploading ${files.length} file(s)...`;
      try {
        const res = await fetch('/api/chat/upload', {
          method: 'POST',
          body: formData
        });
        if (res.ok) {
          logMsg('VAULT', `Uploaded ${files.length} files successfully.`);
          dropzone.textContent = '✅ Files uploaded! Drag & drop more files here';
        } else {
          const err = await res.json();
          alert(`Upload failed: ${err.detail || 'Server error'}`);
          dropzone.textContent = '📂 Drag & drop files here to upload to shared vault';
        }
      } catch (e) {
        alert(`Upload error: ${e}`);
        dropzone.textContent = '📂 Drag & drop files here to upload to shared vault';
      }
    }
  </script>
</body>
</html>
"""

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

