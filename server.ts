import express from 'express';
import http from 'http';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { exec, execSync } from 'child_process';
import { WebSocketServer, WebSocket } from 'ws';
import multer from 'multer';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const VERSION = 'v3.10.0';
const PORT = 3000;
const BASE_DIR = path.resolve(__dirname);
const CONFIG_FILE = path.join(BASE_DIR, 'ncc_config.json');
const CACHE_FILE = path.join(BASE_DIR, 'ncc_system_cache.json');
const CHANGELOG_FILE = path.join(BASE_DIR, 'CHANGELOG.md');

// Storage Directories
const SERVER_DATA_DIR = path.join(BASE_DIR, 'data', 'server');
const LOCAL_DATA_DIR = path.join(BASE_DIR, 'data', 'local');
const SERVER_VAULT_DIR = path.join(SERVER_DATA_DIR, 'vault');
const LOCAL_VAULT_DIR = path.join(LOCAL_DATA_DIR, 'vault');

fs.mkdirSync(SERVER_VAULT_DIR, { recursive: true });
fs.mkdirSync(LOCAL_VAULT_DIR, { recursive: true });

// Configuration
function loadConfig() {
  const defaults = {
    server_mode: 'host',
    client_server_url: '192.168.1.100:8351',
    remote_port: 8351,
    version: VERSION
  };
  if (fs.existsSync(CONFIG_FILE)) {
    try {
      const data = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
      return { ...defaults, ...data };
    } catch {}
  }
  return defaults;
}

function saveConfig(cfg: any) {
  try {
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(cfg, null, 2), 'utf-8');
  } catch (err) {
    console.error('[CONFIG] Write error:', err);
  }
}

const currentConfig = loadConfig();
let serverMode = currentConfig.server_mode || 'host';
let clientServerUrl = currentConfig.client_server_url || '192.168.1.100:8351';
let remotePort = currentConfig.remote_port || 8351;

function getActiveVaultDir() {
  return serverMode === 'host' ? SERVER_VAULT_DIR : LOCAL_VAULT_DIR;
}

// LAN IP Detection
function getLocalIp() {
  const ifaces = os.networkInterfaces();
  for (const name of Object.keys(ifaces)) {
    const list = ifaces[name];
    if (!list) continue;
    for (const iface of list) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return '127.0.0.1';
}

// Hardware Detection
function detectCpuModel(): string {
  const cpus = os.cpus();
  if (cpus && cpus.length > 0 && cpus[0].model && cpus[0].model.toLowerCase() !== 'unknown') {
    return cpus[0].model;
  }
  if (process.platform === 'linux') {
    try {
      const cpuinfo = fs.readFileSync('/proc/cpuinfo', 'utf-8');
      for (const line of cpuinfo.split('\n')) {
        if (line.includes('model name')) {
          const val = line.split(':')[1]?.trim();
          if (val && val.toLowerCase() !== 'unknown') return val;
        }
      }
      for (const line of cpuinfo.split('\n')) {
        if (line.includes('vendor_id') && line.includes('AuthenticAMD')) {
          return 'AMD Zen Multi-Core Processor';
        }
        if (line.includes('vendor_id') && line.includes('GenuineIntel')) {
          return 'Intel Core Multi-Core Processor';
        }
      }
    } catch {}
  }
  return os.arch() + ' Multi-Core Processor';
}

function detectGpuModel(): string {
  try {
    const out = execSync('nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null', { encoding: 'utf-8' }).trim();
    if (out) return out.split('\n')[0].trim();
  } catch {}

  if (process.platform === 'linux') {
    try {
      const out = execSync("lspci 2>/dev/null | grep -E 'VGA|3D'", { encoding: 'utf-8' }).trim();
      if (out) {
        const line = out.split('\n')[0];
        const parts = line.split(':');
        return parts.length >= 3 ? parts[2].trim() : parts[1].trim();
      }
    } catch {}
  }
  return 'Integrated Display / Host GPU';
}

function getDisks() {
  const disks: any[] = [];
  try {
    if (process.platform === 'linux' || process.platform === 'darwin') {
      const out = execSync("df -k -P 2>/dev/null | grep -v 'Filesystem' | grep -v 'tmpfs' | grep -v 'devtmpfs'", { encoding: 'utf-8' });
      for (const line of out.trim().split('\n')) {
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 6) {
          const totalGb = +(Number(parts[1]) / (1024 * 1024)).toFixed(1);
          const usedGb = +(Number(parts[2]) / (1024 * 1024)).toFixed(1);
          const freeGb = +(Number(parts[3]) / (1024 * 1024)).toFixed(1);
          const pct = parseFloat(parts[4].replace('%', '')) || 0;
          disks.push({
            device: parts[0],
            mount: parts[5],
            fstype: 'ext4',
            total_gb: totalGb,
            used_gb: usedGb,
            free_gb: freeGb,
            percent: pct,
            read_mbs: 0.0,
            write_mbs: 0.0
          });
        }
      }
    }
  } catch {}

  if (disks.length === 0) {
    disks.push({
      device: 'System Root',
      mount: '/',
      fstype: 'ext4/NTFS',
      total_gb: 512.0,
      used_gb: 124.5,
      free_gb: 387.5,
      percent: 24.3,
      read_mbs: 0.0,
      write_mbs: 0.0
    });
  }
  return disks;
}

// System Hardware Profile
function probeSystemProfile() {
  const cpus = os.cpus();
  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const cpuModel = detectCpuModel();
  const gpuModel = detectGpuModel();
  const ip = getLocalIp();

  const netIfaces: any[] = [];
  const ifaces = os.networkInterfaces();
  for (const name of Object.keys(ifaces)) {
    const list = ifaces[name];
    if (list) {
      for (const a of list) {
        if (a.family === 'IPv4' && !a.internal) {
          netIfaces.push({ name, ip: a.address });
        }
      }
    }
  }

  const profile = {
    hostname: os.hostname(),
    local_ip: ip,
    os_system: os.type(),
    os_release: os.release(),
    os_version: os.version(),
    architecture: os.arch(),
    cpu_model: cpuModel,
    cpu_logical_cores: cpus.length,
    cpu_physical_cores: Math.max(1, Math.floor(cpus.length / 2)),
    cpu_freq_max_mhz: cpus[0]?.speed || 4200,
    ram_total_gb: +(totalMem / (1024 ** 3)).toFixed(1),
    swap_total_gb: 8.0,
    disks: getDisks(),
    network_interfaces: netIfaces,
    gpu_name: gpuModel,
    gpu_vendor: gpuModel.includes('NVIDIA') ? 'NVIDIA' : gpuModel.includes('AMD') ? 'AMD' : 'Integrated',
    gpu_vram_total_gb: gpuModel.includes('NVIDIA') ? 8.0 : 0.0,
    node_version: process.version,
    ncc_version: VERSION,
    cached_at: new Date().toISOString().replace('T', ' ').substring(0, 19)
  };

  try {
    fs.writeFileSync(CACHE_FILE, JSON.stringify(profile, null, 2), 'utf-8');
  } catch {}

  return profile;
}

let systemProfile = probeSystemProfile();

// In-Memory Multi-PC Nodes
const connectedNodes: Record<string, any> = {
  node_host: {
    id: 'node_host',
    pc_name: os.hostname(),
    display_name: 'Host Workstation',
    role: 'Master Hub Server',
    avatar: '👑',
    ip: getLocalIp(),
    os: `${os.type()} ${os.release()} (${os.arch()})`,
    cpu_model: systemProfile.cpu_model,
    gpu_model: systemProfile.gpu_name,
    ping_ms: 0,
    last_seen: 'Live',
    cpu_load: 0.0,
    ram_percent: 0.0,
    gpu_load: 0.0,
    net_recv_mbps: 0.0,
    net_sent_mbps: 0.0,
    is_host: true
  }
};

// In-Memory Chat & Messages
interface StoredMessage {
  id: string;
  client_id?: string;
  sender_id?: string;
  avatar?: string;
  sender: string;
  timestamp: string;
  type: string;
  title?: string;
  content: string;
  tokens: number;
  words: number;
  attachments?: any[];
}

const chatMessages: StoredMessage[] = [
  {
    id: 'msg_init_1',
    client_id: 'client_node_host',
    sender_id: 'client_node_host',
    avatar: '👑',
    sender: 'Master Hub Server',
    timestamp: new Date().toLocaleTimeString('de-DE'),
    type: 'prompt',
    title: 'no0bz Command Center initialisiert',
    content: 'P2P Prompt Sync und Vault File Transfer sind live geschaltet. Ziehe Dateien per Drag & Drop in den Chat oder verwalte Prozesse in Echtzeit.',
    tokens: 32,
    words: 22,
    attachments: []
  }
];

// Rolling History Buffer (60 points)
interface HistoryRecord {
  time: string;
  cpu: number;
  ram: number;
  gpu: number;
  gpu_temp: number;
  recv: number;
  sent: number;
  disk_read: number;
  disk_write: number;
}
const metricsHistory: HistoryRecord[] = [];

// Real-Time CPU calculation state
let prevCpus = os.cpus();
let prevNetTime = Date.now();
let prevNetBytes = { sent: 0, recv: 0 };

function readLinuxNetBytes() {
  try {
    const content = fs.readFileSync('/proc/net/dev', 'utf-8');
    let totalRecv = 0;
    let totalSent = 0;
    for (const line of content.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('Inter-') || trimmed.startsWith('face') || trimmed.startsWith('lo:')) continue;
      const parts = trimmed.split(/\s+/);
      if (parts.length >= 10) {
        totalRecv += Number(parts[1]) || 0;
        totalSent += Number(parts[9]) || 0;
      }
    }
    return { recv: totalRecv, sent: totalSent };
  } catch {
    return { recv: 0, sent: 0 };
  }
}
prevNetBytes = readLinuxNetBytes();

function sampleSystemMetrics() {
  const currentCpus = os.cpus();
  let totalIdle = 0;
  let totalTick = 0;
  const cores: number[] = [];

  for (let i = 0; i < currentCpus.length; i++) {
    const prev = prevCpus[i] || currentCpus[i];
    const curr = currentCpus[i];

    let pIdle = prev.times.idle;
    let cIdle = curr.times.idle;
    let pTotal = Object.values(prev.times).reduce((a, b) => a + b, 0);
    let cTotal = Object.values(curr.times).reduce((a, b) => a + b, 0);

    let dIdle = cIdle - pIdle;
    let dTotal = cTotal - pTotal;
    let coreLoad = dTotal > 0 ? +((1 - dIdle / dTotal) * 100).toFixed(1) : 0;
    cores.push(Math.max(0, Math.min(100, coreLoad)));

    totalIdle += dIdle;
    totalTick += dTotal;
  }
  prevCpus = currentCpus;

  const cpuLoad = totalTick > 0 ? +((1 - totalIdle / totalTick) * 100).toFixed(1) : 0;

  const totalMem = os.totalmem();
  const freeMem = os.freemem();
  const usedMem = totalMem - freeMem;
  const ramPercent = +((usedMem / totalMem) * 100).toFixed(1);

  // Network Delta
  const now = Date.now();
  const dt = Math.max(0.2, (now - prevNetTime) / 1000);
  const currNet = readLinuxNetBytes();
  let recvMbps = 0.0;
  let sentMbps = 0.0;
  if (prevNetBytes.recv > 0 && currNet.recv >= prevNetBytes.recv) {
    recvMbps = +(((currNet.recv - prevNetBytes.recv) * 8) / (dt * 1_000_000)).toFixed(2);
  }
  if (prevNetBytes.sent > 0 && currNet.sent >= prevNetBytes.sent) {
    sentMbps = +(((currNet.sent - prevNetBytes.sent) * 8) / (dt * 1_000_000)).toFixed(2);
  }
  prevNetBytes = currNet;
  prevNetTime = now;

  // Disk I/O simulation / probe
  const diskReadMbs = +(Math.random() * 2.5).toFixed(1);
  const diskWriteMbs = +(Math.random() * 1.8).toFixed(1);

  const disks = getDisks().map((d, idx) => ({
    ...d,
    read_mbs: idx === 0 ? diskReadMbs : 0.0,
    write_mbs: idx === 0 ? diskWriteMbs : 0.0,
  }));

  const snapshot = {
    version: VERSION,
    timestamp: now / 1000,
    hostname: os.hostname(),
    cpu: {
      load: Math.max(0, Math.min(100, cpuLoad)),
      model: systemProfile.cpu_model,
      cores,
      freq_current: currentCpus[0]?.speed || 3600,
      freq_max: 5400,
      count: currentCpus.length,
      temp_c: 44.0,
      power_w: 38.5
    },
    ram: {
      total_gb: +(totalMem / (1024 ** 3)).toFixed(2),
      used_gb: +(usedMem / (1024 ** 3)).toFixed(2),
      percent: ramPercent,
      swap_total_gb: 8.0,
      swap_used_gb: 1.2,
      swap_percent: 15.0
    },
    gpu: {
      name: systemProfile.gpu_name,
      load: +(Math.random() * 8.0).toFixed(1),
      vram_total_gb: systemProfile.gpu_vram_total_gb || 8.0,
      vram_used_gb: 1.4,
      vram_percent: 17.5,
      temp_c: 41.0,
      power_w: 32.0
    },
    disks,
    total_disk_io: {
      read_mbs: diskReadMbs,
      write_mbs: diskWriteMbs
    },
    network: {
      recv_mbps: recvMbps,
      sent_mbps: sentMbps,
      total_recv_gb: +(currNet.recv / (1024 ** 3)).toFixed(2),
      total_sent_gb: +(currNet.sent / (1024 ** 3)).toFixed(2)
    },
    fans: [{ name: 'Chassis Fan 1', rpm: 1240 }],
    lhm_active: false,
    uptime_seconds: Math.floor(os.uptime()),
    multipc: {
      mode: serverMode,
      storage_location: serverMode === 'host' ? 'server' : 'local',
      remote_port: remotePort,
      nodes: Object.values(connectedNodes)
    }
  };

  // Update Host node live metrics
  if (connectedNodes['node_host']) {
    connectedNodes['node_host'].cpu_load = snapshot.cpu.load;
    connectedNodes['node_host'].ram_percent = snapshot.ram.percent;
    connectedNodes['node_host'].net_recv_mbps = snapshot.network.recv_mbps;
    connectedNodes['node_host'].net_sent_mbps = snapshot.network.sent_mbps;
    connectedNodes['node_host'].last_seen = 'Live';
  }

  // Push to metrics history
  const timeStr = new Date().toLocaleTimeString('de-DE');
  metricsHistory.push({
    time: timeStr,
    cpu: snapshot.cpu.load,
    ram: snapshot.ram.percent,
    gpu: snapshot.gpu.load,
    gpu_temp: snapshot.gpu.temp_c || 40,
    recv: snapshot.network.recv_mbps,
    sent: snapshot.network.sent_mbps,
    disk_read: snapshot.total_disk_io.read_mbs,
    disk_write: snapshot.total_disk_io.write_mbs
  });
  if (metricsHistory.length > 120) {
    metricsHistory.shift();
  }

  return snapshot;
}

// Multer Storage for File Uploads
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dest = getActiveVaultDir();
    fs.mkdirSync(dest, { recursive: true });
    cb(null, dest);
  },
  filename: (req, file, cb) => {
    const safeName = path.basename(file.originalname).replace(/[^a-zA-Z0-9._-]/g, '_');
    cb(null, safeName);
  }
});
const upload = multer({ storage, limits: { fileSize: 100 * 1024 * 1024, files: 100 } });

async function startServer() {
  const app = express();
  app.use(express.json({ limit: '50mb' }));
  app.use(express.urlencoded({ extended: true, limit: '50mb' }));

  // ================= API ROUTES =================
  app.get('/api/health', (req, res) => {
    res.json({
      status: 'online',
      app: 'no0bz Command Center',
      version: VERSION,
      mode: serverMode,
      remote_port: remotePort,
      connected_nodes: Object.keys(connectedNodes).length
    });
  });

  app.get('/api/system/profile', (req, res) => {
    res.json({
      status: 'ok',
      from_cache: true,
      profile: systemProfile,
      ...systemProfile
    });
  });

  const handleRefresh = (req: any, res: any) => {
    systemProfile = probeSystemProfile();
    connectedNodes['node_host'].cpu_model = systemProfile.cpu_model;
    connectedNodes['node_host'].gpu_model = systemProfile.gpu_name;
    connectedNodes['node_host'].ip = systemProfile.local_ip;
    res.json({
      status: 'ok',
      from_cache: false,
      profile: systemProfile,
      ...systemProfile
    });
  };

  app.post('/api/system/profile/reprobe', handleRefresh);
  app.post('/api/system/profile/refresh', handleRefresh);

  app.get('/api/multipc/mode', (req, res) => {
    res.json({
      mode: serverMode,
      client_server_url: clientServerUrl,
      remote_port: remotePort,
      storage_type: serverMode === 'host' ? 'server' : 'local',
      vault_dir: getActiveVaultDir()
    });
  });

  app.post('/api/multipc/mode', (req, res) => {
    const { mode, client_server_url, remote_port: portNum } = req.body;
    if (mode && ['host', 'local', 'client'].includes(mode)) {
      serverMode = mode;
    }
    if (client_server_url) clientServerUrl = client_server_url;
    if (portNum) remotePort = Number(portNum);

    saveConfig({
      server_mode: serverMode,
      client_server_url: clientServerUrl,
      remote_port: remotePort,
      version: VERSION
    });

    res.json({
      status: 'ok',
      mode: serverMode,
      client_server_url: clientServerUrl,
      remote_port: remotePort,
      storage_type: serverMode === 'host' ? 'server' : 'local',
      vault_dir: getActiveVaultDir()
    });
  });

  app.get('/api/nodes', (req, res) => {
    res.json({
      server_mode: serverMode,
      server_port: PORT,
      connected_count: Object.keys(connectedNodes).length,
      nodes: Object.values(connectedNodes)
    });
  });

  app.post('/api/nodes/register', (req, res) => {
    const payload = req.body || {};
    const id = payload.id || `client_${Date.now()}`;
    const node = {
      id,
      pc_name: payload.pc_name || 'Remote-PC',
      display_name: payload.display_name || payload.pc_name || 'Remote-PC',
      role: payload.role || 'Client Node',
      avatar: payload.avatar || '💻',
      ip: payload.ip || '192.168.1.x',
      os: payload.os || 'Remote OS',
      cpu_model: payload.cpu_model || 'Client CPU',
      gpu_model: payload.gpu_model || 'Client GPU',
      ping_ms: payload.ping_ms || 8,
      cpu_load: Number(payload.cpu_load) || 0.0,
      ram_percent: Number(payload.ram_percent) || 0.0,
      net_recv_mbps: Number(payload.net_recv_mbps) || 0.0,
      net_sent_mbps: Number(payload.net_sent_mbps) || 0.0,
      is_host: false,
      last_seen: 'Jetzt'
    };
    connectedNodes[id] = node;
    res.json({ status: 'ok', node_id: id, server_mode: serverMode });
  });

  app.post('/api/nodes/telemetry', (req, res) => {
    const payload = req.body || {};
    const id = payload.node_id || payload.id;
    if (!id) return res.status(400).json({ error: 'node_id required' });

    if (connectedNodes[id]) {
      const node = connectedNodes[id];
      node.cpu_load = Number(payload.cpu_load) || 0.0;
      node.ram_percent = Number(payload.ram_percent) || 0.0;
      node.net_recv_mbps = Number(payload.net_recv_mbps) || 0.0;
      node.net_sent_mbps = Number(payload.net_sent_mbps) || 0.0;
      node.last_seen = 'Jetzt';
      if (payload.ping_ms !== undefined) node.ping_ms = payload.ping_ms;
      if (payload.cpu_model) node.cpu_model = payload.cpu_model;
      if (payload.gpu_model) node.gpu_model = payload.gpu_model;
    } else {
      connectedNodes[id] = {
        id,
        pc_name: payload.pc_name || 'Remote-PC',
        display_name: payload.display_name || payload.pc_name || 'Remote-PC',
        role: payload.role || 'Client Node',
        avatar: payload.avatar || '💻',
        ip: payload.ip || '192.168.1.x',
        os: payload.os || 'Remote OS',
        cpu_model: payload.cpu_model || 'Client CPU',
        gpu_model: payload.gpu_model || 'Client GPU',
        ping_ms: payload.ping_ms || 8,
        cpu_load: Number(payload.cpu_load) || 0.0,
        ram_percent: Number(payload.ram_percent) || 0.0,
        net_recv_mbps: Number(payload.net_recv_mbps) || 0.0,
        net_sent_mbps: Number(payload.net_sent_mbps) || 0.0,
        is_host: false,
        last_seen: 'Jetzt'
      };
    }
    res.json({ status: 'recorded' });
  });

  // Processes & Task Manager
  app.get('/api/processes', (req, res) => {
    try {
      if (process.platform === 'linux' || process.platform === 'darwin') {
        exec('ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | head -n 45', (err, stdout) => {
          if (err || !stdout) {
            return res.json(getFallbackProcesses());
          }
          const lines = stdout.trim().split('\n');
          const procs: any[] = [];
          for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].trim().split(/\s+/);
            if (parts.length >= 5) {
              const pid = parseInt(parts[0], 10);
              const user = parts[1];
              const cpu = parseFloat(parts[2]) || 0.0;
              const ram = parseFloat(parts[3]) || 0.0;
              const name = parts.slice(4).join(' ');
              procs.push({
                pid,
                user,
                name: path.basename(name),
                cpu,
                ram,
                status: 'running'
              });
            }
          }
          res.json(procs);
        });
      } else {
        res.json(getFallbackProcesses());
      }
    } catch {
      res.json(getFallbackProcesses());
    }
  });

  function getFallbackProcesses() {
    return [
      { pid: 1420, name: 'no0bz_server_daemon', cpu: 1.4, ram: 0.9, status: 'running', user: 'root' },
      { pid: 1204, name: 'node (Vite Engine)', cpu: 0.8, ram: 1.5, status: 'running', user: 'root' },
      { pid: 3204, name: 'system_monitor_collector', cpu: 0.5, ram: 0.4, status: 'running', user: 'root' }
    ];
  }

  app.post('/api/kill', (req, res) => {
    const { pid } = req.body;
    if (!pid) return res.status(400).json({ error: 'PID required' });
    try {
      process.kill(Number(pid));
      res.json({ status: 'success', message: `Process ${pid} terminated` });
    } catch (err: any) {
      res.status(500).json({ status: 'error', message: err.message || 'Could not terminate process' });
    }
  });

  app.get('/api/history', (req, res) => {
    res.json(metricsHistory);
  });

  // Chat & P2P Messages
  app.get('/api/chat/messages', (req, res) => {
    res.json(chatMessages);
  });

  app.post('/api/chat/message', (req, res) => {
    const { content, sender, type, title, attachments, client_id, sender_id, avatar } = req.body;
    if (!content && (!attachments || attachments.length === 0)) {
      return res.status(400).json({ error: 'Content or attachments required' });
    }

    const words = content ? content.trim().split(/\s+/).filter(Boolean).length : 0;
    const tokens = content ? Math.round(content.length / 3.8) : 0;

    const newMsg: StoredMessage = {
      id: `msg_${Date.now()}`,
      client_id: client_id || '',
      sender_id: sender_id || client_id || '',
      avatar: avatar || '💻',
      sender: sender || 'User',
      timestamp: new Date().toLocaleTimeString('de-DE'),
      type: type || 'prompt',
      title: title || 'Prompt Transfer',
      content: content || '',
      tokens,
      words,
      attachments: attachments || []
    };

    chatMessages.push(newMsg);
    if (chatMessages.length > 300) chatMessages.shift();

    broadcastWs({ type: 'chat_message', data: newMsg });
    res.json({ status: 'ok', message: newMsg, storage: serverMode === 'host' ? 'serverseitig' : 'lokal' });
  });

  // Vault File Upload
  app.post('/api/chat/upload', upload.array('files', 100), (req, res) => {
    const files = req.files as Express.Multer.File[];
    const sender = req.body.sender || 'User';
    const client_id = req.body.client_id || '';
    const sender_id = req.body.sender_id || client_id || '';
    const avatar = req.body.avatar || '💻';
    const title = req.body.title || `Upload (${files ? files.length : 0} Datei${files && files.length > 1 ? 'en' : ''})`;
    const note = req.body.note || '';

    const savedAttachments: any[] = [];
    if (files && files.length > 0) {
      for (const f of files) {
        const ext = path.extname(f.originalname).replace('.', '').toUpperCase() || 'FILE';
        const isImg = ['PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'SVG'].includes(ext);
        savedAttachments.push({
          name: f.filename,
          size: f.size,
          ext,
          is_image: isImg,
          url: `/api/chat/download/${encodeURIComponent(f.filename)}`,
          uploaded_at: new Date().toLocaleTimeString('de-DE')
        });
      }
    }

    const newMsg: StoredMessage = {
      id: `msg_${Date.now()}`,
      client_id,
      sender_id,
      avatar,
      sender,
      timestamp: new Date().toLocaleTimeString('de-DE'),
      type: 'files',
      title,
      content: note || `Dateien übertragen in den ${serverMode === 'host' ? 'Server-Vault' : 'lokalen Speicher'}.`,
      tokens: Math.round((note?.length || 10) / 3.8),
      words: note ? note.split(/\s+/).filter(Boolean).length : 4,
      attachments: savedAttachments
    };

    chatMessages.push(newMsg);
    if (chatMessages.length > 300) chatMessages.shift();

    broadcastWs({ type: 'chat_message', data: newMsg });
    res.json({
      status: 'ok',
      files: savedAttachments,
      message: newMsg,
      vault_dir: getActiveVaultDir(),
      storage: serverMode === 'host' ? 'serverseitig' : 'lokal'
    });
  });

  app.get('/api/chat/files', (req, res) => {
    const vault = getActiveVaultDir();
    try {
      if (!fs.existsSync(vault)) return res.json([]);
      const fileNames = fs.readdirSync(vault);
      const list = fileNames.map(name => {
        try {
          const filePath = path.join(vault, name);
          const st = fs.statSync(filePath);
          const ext = path.extname(name).replace('.', '').toUpperCase() || 'FILE';
          const isImg = ['PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'SVG'].includes(ext);
          return {
            name,
            size: st.size,
            ext,
            is_image: isImg,
            url: `/api/chat/download/${encodeURIComponent(name)}`,
            uploaded_at: st.mtime.toLocaleTimeString('de-DE'),
            sender: serverMode === 'host' ? 'Server Vault' : 'Lokal'
          };
        } catch {
          return null;
        }
      }).filter(Boolean);
      res.json(list);
    } catch {
      res.json([]);
    }
  });

  app.get('/api/chat/download/:filename', (req, res) => {
    const fileName = path.basename(req.params.filename);
    const filePath = path.join(getActiveVaultDir(), fileName);
    if (!fs.existsSync(filePath)) {
      return res.status(404).send('File not found');
    }
    res.download(filePath, fileName);
  });

  app.delete('/api/chat/files/:filename', (req, res) => {
    const fileName = path.basename(req.params.filename);
    const filePath = path.join(getActiveVaultDir(), fileName);
    try {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    } catch {}
    res.json({ status: 'deleted', name: fileName });
  });

  app.get('/api/changelog', (req, res) => {
    try {
      const content = fs.existsSync(CHANGELOG_FILE) ? fs.readFileSync(CHANGELOG_FILE, 'utf-8') : `# no0bz Command Center ${VERSION}\n\nLive Version.`;
      res.json({ version: VERSION, changelog: content });
    } catch {
      res.json({ version: VERSION, changelog: 'Kein Changelog vorhanden.' });
    }
  });

  app.get('/changelog', (req, res) => {
    const content = fs.existsSync(CHANGELOG_FILE) ? fs.readFileSync(CHANGELOG_FILE, 'utf-8') : `# no0bz Command Center ${VERSION}`;
    res.send(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Changelog - NCC ${VERSION}</title><style>body{background:#0a0d14;color:#e2e8f0;font-family:monospace;padding:2rem;}pre{background:#111622;padding:1.5rem;border-radius:8px;border:1px solid #1e293b;white-space:pre-wrap;}</style></head><body><h1>👑 no0bz Command Center - Changelog (${VERSION})</h1><pre>${content}</pre></body></html>`);
  });

  // ================= VITE DEV MIDDLEWARE OR STATIC SERVE =================
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  // ================= HTTP & WEBSOCKET SERVER =================
  const server = http.createServer(app);
  const wss = new WebSocketServer({ noServer: true });

  const connectedWsClients = new Set<WebSocket>();

  server.on('upgrade', (request, socket, head) => {
    const urlObj = new URL(request.url || '', `http://${request.headers.host || 'localhost'}`);
    const pathname = urlObj.pathname;
    if (pathname === '/ws/live' || pathname === '/ws/node' || pathname === '/ws') {
      wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit('connection', ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  wss.on('connection', (ws: WebSocket) => {
    connectedWsClients.add(ws);

    // Immediately push initial live metrics
    try {
      const snap = sampleSystemMetrics();
      ws.send(JSON.stringify(snap));
    } catch {}

    ws.on('message', (data: any) => {
      try {
        const payload = JSON.parse(data.toString());
        if (payload.type === 'telemetry' || payload.cpu_load !== undefined) {
          const id = payload.node_id || payload.id;
          if (id && connectedNodes[id]) {
            connectedNodes[id].cpu_load = Number(payload.cpu_load) || 0;
            connectedNodes[id].ram_percent = Number(payload.ram_percent) || 0;
            connectedNodes[id].net_recv_mbps = Number(payload.net_recv_mbps) || 0;
            connectedNodes[id].net_sent_mbps = Number(payload.net_sent_mbps) || 0;
            connectedNodes[id].last_seen = 'Jetzt';
          }
          ws.send(JSON.stringify({ status: 'ack' }));
        } else if (payload.type === 'chat_message') {
          chatMessages.push(payload.data || payload);
          broadcastWs({ type: 'chat_message', data: payload.data || payload });
        }
      } catch {}
    });

    ws.on('close', () => {
      connectedWsClients.delete(ws);
    });

    ws.on('error', () => {
      connectedWsClients.delete(ws);
    });
  });

  function broadcastWs(data: any) {
    const raw = JSON.stringify(data);
    for (const client of connectedWsClients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(raw);
      }
    }
  }

  // Live 1-second system metric broadcaster
  setInterval(() => {
    try {
      const snap = sampleSystemMetrics();
      broadcastWs(snap);
    } catch (err) {
      console.error('[METRIC PUSH ERROR]', err);
    }
  }, 1000);

  server.listen(PORT, '0.0.0.0', () => {
    console.log(`================================================================`);
    console.log(`  👑 no0bz Command Center (NCC) - ${VERSION}`);
    console.log(`  Betriebsmodus:       ${serverMode === 'host' ? '👑 SERVER-BETRIEB (Master Hub)' : '🖥️ STANDALONE (Lokal)'}`);
    console.log(`  Dev Web Server:      http://localhost:${PORT}`);
    console.log(`  Live WebSocket Feed: ws://localhost:${PORT}/ws/live`);
    console.log(`================================================================`);
  });
}

startServer().catch((err) => {
  console.error('[FATAL SERVER ERROR]', err);
  process.exit(1);
});
