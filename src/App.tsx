import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Activity, Cpu, HardDrive, Wifi, Zap, Terminal, 
  Trash2, Search, Sliders, RefreshCw, Layers, ArrowDown, ArrowUp, Disc,
  MessageSquare, Send, Paperclip, Download, Upload, Copy, Check, File,
  FileText, Image as ImageIcon, Eye, Folder, Settings, ShieldAlert, Sparkles,
  Maximize2, X, AlertTriangle, Monitor, Laptop, Clock, Server, CheckCircle2,
  Share2, HardDriveDownload, Filter, Globe, Users, Radio, User, Edit3, Shield, Key
} from 'lucide-react';

// ================================================
// TYPES & INTERFACES
// ================================================

export type MultiPcMode = 'local' | 'host' | 'client';

export interface UserProfile {
  pcName: string;
  displayName: string;
  avatar: string;
  role: string;
  accentColor: string;
  statusMsg: string;
}

export interface RemoteNode {
  id: string;
  pc_name: string;
  display_name: string;
  avatar: string;
  role: string;
  ip: string;
  os: string;
  is_host: boolean;
  status: 'online' | 'idle' | 'offline';
  ping_ms: number;
  last_seen: string;
  cpu_load: number;
  ram_percent: number;
  gpu_load: number;
  net_recv_mbps: number;
  net_sent_mbps: number;
}

interface DiskItem {
  device: string;
  mount: string;
  fstype: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  percent: number;
  read_mbs: number;
  write_mbs: number;
}

interface ProcessItem {
  pid: number;
  name: string;
  cpu: number;
  ram: number;
  status: string;
}

interface HistoryPoint {
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

interface ChatAttachment {
  name: string;
  size: number;
  ext: string;
  is_image: boolean;
  url: string;
  data_url?: string;
  uploaded_at: string;
}

interface ChatMessage {
  id: string;
  sender: string;
  timestamp: string;
  type: 'prompt' | 'files' | 'note';
  title?: string;
  content: string;
  tokens?: number;
  words?: number;
  attachments?: ChatAttachment[];
}

// ================================================
// NO0BZ VECTOR LOGO COMPONENTS
// ================================================

export function No0bzLogo({ 
  mode = 'nightmare', 
  size = 'normal',
  onVersionClick 
}: { 
  mode?: 'classic' | 'nightmare', 
  size?: 'small' | 'normal' | 'large',
  onVersionClick?: () => void 
}) {
  const isNightmare = mode === 'nightmare';
  const scale = size === 'small' ? 'h-7' : size === 'large' ? 'h-14' : 'h-10';

  return (
    <div className={`flex items-center gap-2.5 select-none ${scale}`}>
      {/* Crown Icon with Neon Aura */}
      <div className="relative flex items-center justify-center">
        <div className={`absolute -inset-1 rounded-full blur-md opacity-70 ${isNightmare ? 'bg-red-600 animate-pulse' : 'bg-cyan-500 animate-pulse'}`} />
        <svg className={`relative w-8 h-8 ${isNightmare ? 'text-red-500 drop-shadow-[0_0_8px_rgba(239,68,68,0.9)]' : 'text-cyan-400 drop-shadow-[0_0_8px_rgba(6,182,212,0.9)]'}`} viewBox="0 0 24 24" fill="currentColor">
          {/* Stylized Graffiti Crown */}
          <path d="M2.5 19h19c.8 0 1.5-.7 1.5-1.5 0-.4-.2-.8-.5-1.1L19 11l-4 6-3-11-3 11-4-6-3.5 5.4c-.3.3-.5.7-.5 1.1 0 .8.7 1.5 1.5 1.5z" />
          <circle cx="5" cy="5" r="1.5" className={isNightmare ? 'fill-red-400' : 'fill-cyan-300'} />
          <circle cx="12" cy="2.5" r="1.5" className={isNightmare ? 'fill-amber-400' : 'fill-emerald-300'} />
          <circle cx="19" cy="5" r="1.5" className={isNightmare ? 'fill-red-400' : 'fill-cyan-300'} />
          <rect x="3" y="19.5" width="18" height="2" rx="1" className={isNightmare ? 'fill-red-600' : 'fill-cyan-500'} />
        </svg>
      </div>

      {/* Stylized Typography */}
      <div className="flex flex-col leading-none">
        <div className="flex items-baseline tracking-wider font-black font-mono">
          <span className={`text-2xl tracking-tighter ${isNightmare ? 'text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.7)]' : 'text-white'}`}>
            no
          </span>
          <span className={`text-3xl font-black ${isNightmare ? 'text-red-500 drop-shadow-[0_0_12px_rgba(239,68,68,0.9)]' : 'text-cyan-400 drop-shadow-[0_0_12px_rgba(6,182,212,0.9)]'}`}>
            0
          </span>
          <span className={`text-2xl tracking-tighter ${isNightmare ? 'text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.7)]' : 'text-white'}`}>
            bz
          </span>
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={`text-[9px] font-mono font-bold tracking-widest uppercase ${isNightmare ? 'text-red-400 drop-shadow-[0_0_6px_rgba(239,68,68,0.8)]' : 'text-cyan-400'}`}>
            {isNightmare ? '⚡ NIGHTMARE' : 'COMMAND CENTER'}
          </span>
          <button
            type="button"
            onClick={onVersionClick}
            title="Klicken, um das NCC Changelog zu öffnen"
            className="text-[8px] px-1 py-0.2 bg-zinc-800 hover:bg-cyan-900/60 hover:text-cyan-300 border border-zinc-700 hover:border-cyan-500 text-zinc-300 rounded font-mono font-semibold transition-all cursor-pointer"
          >
            v3.8.2
          </button>
        </div>
      </div>
    </div>
  );
}

// ================================================
// SVG CIRCULAR GAUGE COMPONENT
// ================================================

function SvgCircleGauge({ 
  value, 
  max = 100, 
  title, 
  unit = "%", 
  color = "#00ffc8", 
  subtext,
  size = 130 
}: { 
  value: number; 
  max?: number; 
  title: string; 
  unit?: string; 
  color?: string; 
  subtext?: string;
  size?: number;
}) {
  const strokeWidth = 8;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(Math.max(value / max, 0), 1);
  const strokeDashoffset = circumference - pct * circumference;

  return (
    <div className="flex flex-col items-center justify-center p-2">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#1c2438"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            style={{ 
              transition: 'stroke-dashoffset 0.5s ease',
              filter: `drop-shadow(0 0 6px ${color}88)`
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-black font-mono tracking-tight text-white drop-shadow">
            {typeof value === 'number' ? (value % 1 === 0 ? value : value.toFixed(1)) : 0}
            <span className="text-xs text-zinc-400 font-sans ml-0.5">{unit}</span>
          </span>
          <span className="text-[10px] font-mono tracking-wider font-semibold uppercase text-zinc-400">
            {title}
          </span>
        </div>
      </div>
      {subtext && (
        <span className="text-[11px] font-mono text-zinc-400 mt-1 font-medium">
          {subtext}
        </span>
      )}
    </div>
  );
}

// ================================================
// NETWORK REAL-TIME CANVAS GRAPH (60 FPS DUAL LINE)
// ================================================

export function NetworkLiveGraph({
  history,
  currentRecv,
  currentSent,
  isNightmare = false
}: {
  history: { recv: number; sent: number }[];
  currentRecv: number;
  currentSent: number;
  isNightmare?: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = rect.width || 320;
    const height = rect.height || 110;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const data = history.length > 1 ? history : [
      { recv: currentRecv * 0.8, sent: currentSent * 0.7 },
      { recv: currentRecv, sent: currentSent }
    ];

    const allVals = data.flatMap(d => [d.recv, d.sent]);
    const maxVal = Math.max(10, ...allVals, currentRecv, currentSent) * 1.15;

    // Grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);

    const gridLines = 3;
    for (let i = 1; i <= gridLines; i++) {
      const y = (height / (gridLines + 1)) * i;
      ctx.beginPath();
      ctx.moveTo(35, y);
      ctx.lineTo(width - 8, y);
      ctx.stroke();

      const valLabel = (maxVal * (1 - i / (gridLines + 1))).toFixed(0) + 'M';
      ctx.fillStyle = 'rgba(161, 161, 170, 0.4)';
      ctx.font = '9px monospace';
      ctx.textAlign = 'right';
      ctx.fillText(valLabel, 30, y + 3);
    }
    ctx.setLineDash([]);

    const plotX = (idx: number) => {
      const step = (width - 45) / Math.max(data.length - 1, 1);
      return 35 + idx * step;
    };
    const plotY = (val: number) => {
      const clamped = Math.max(0, Math.min(val, maxVal));
      return height - 10 - (clamped / maxVal) * (height - 20);
    };

    const drawCurve = (
      key: 'recv' | 'sent',
      strokeColor: string,
      gradientStart: string,
      glowColor: string
    ) => {
      if (data.length < 1) return;

      const grad = ctx.createLinearGradient(0, 0, 0, height);
      grad.addColorStop(0, gradientStart);
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

      ctx.beginPath();
      ctx.moveTo(plotX(0), height - 10);
      data.forEach((pt, i) => {
        const x = plotX(i);
        const y = plotY(pt[key]);
        if (i === 0) ctx.lineTo(x, y);
        else {
          const prevX = plotX(i - 1);
          const prevY = plotY(data[i - 1][key]);
          const cpX1 = (prevX + x) / 2;
          ctx.bezierCurveTo(cpX1, prevY, cpX1, y, x, y);
        }
      });
      ctx.lineTo(plotX(data.length - 1), height - 10);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.save();
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = 8;
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      data.forEach((pt, i) => {
        const x = plotX(i);
        const y = plotY(pt[key]);
        if (i === 0) ctx.moveTo(x, y);
        else {
          const prevX = plotX(i - 1);
          const prevY = plotY(data[i - 1][key]);
          const cpX1 = (prevX + x) / 2;
          ctx.bezierCurveTo(cpX1, prevY, cpX1, y, x, y);
        }
      });
      ctx.stroke();
      ctx.restore();

      const lastX = plotX(data.length - 1);
      const lastY = plotY(data[data.length - 1][key]);
      ctx.fillStyle = strokeColor;
      ctx.beginPath();
      ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
      ctx.fill();
    };

    drawCurve(
      'recv',
      isNightmare ? '#ef4444' : '#00f0ff',
      isNightmare ? 'rgba(239, 68, 68, 0.25)' : 'rgba(0, 240, 255, 0.25)',
      isNightmare ? '#ef4444' : '#00f0ff'
    );

    drawCurve(
      'sent',
      '#f59e0b',
      'rgba(245, 158, 11, 0.2)',
      '#f59e0b'
    );
  }, [history, currentRecv, currentSent, isNightmare]);

  return (
    <div className="w-full relative mt-1 bg-black/40 rounded-lg p-2 border border-zinc-800/80">
      <div className="flex items-center justify-between text-[10px] font-mono mb-1 text-zinc-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${isNightmare ? 'bg-red-500' : 'bg-cyan-400'} shadow-[0_0_6px]`}></span>
            <span className="text-zinc-300 font-bold">RX (DL):</span> {currentRecv} Mbps
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_#f59e0b]"></span>
            <span className="text-zinc-300 font-bold">TX (UL):</span> {currentSent} Mbps
          </span>
        </div>
        <span className="text-[9px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400 font-mono">60s Live I/O</span>
      </div>
      <div className="h-24 w-full">
        <canvas ref={canvasRef} className="w-full h-full block" />
      </div>
    </div>
  );
}

// ================================================
// MAIN COMPONENT
// ================================================

export default function App() {
  // Navigation: The top menu is completely removed. Sidebar is the only nav!
  const [activeTab, setActiveTab] = useState<'dashboard' | 'multipc' | 'chat' | 'vault' | 'processes' | 'history' | 'settings' | 'changelog'>('dashboard');
  const [themeMode, setThemeMode] = useState<'nightmare' | 'bento' | 'nordic' | 'industrial'>('nightmare');
  const [logoStyle, setLogoStyle] = useState<'nightmare' | 'classic'>('nightmare');

  // Multi-PC Architecture State (Local / Server Hosten / Client Node)
  const [multiPcMode, setMultiPcMode] = useState<MultiPcMode>(() => {
    return (localStorage.getItem('no0bz_multipc_mode') as MultiPcMode) || 'host';
  });
  const [showModeModal, setShowModeModal] = useState<boolean>(() => {
    return localStorage.getItem('no0bz_multipc_mode') === null;
  });
  const [clientServerUrl, setClientServerUrl] = useState<string>('192.168.1.100:8350');
  const [selectedViewNodeId, setSelectedViewNodeId] = useState<string | null>(null);
  const [storageLocation, setStorageLocation] = useState<'serverseitig' | 'lokal'>('serverseitig');
  const [serverVaultFiles, setServerVaultFiles] = useState<ChatAttachment[]>([]);

  // User Profile Customizer (Saved to LocalStorage & Syncs to Chat and Server)
  const [userProfile, setUserProfile] = useState<UserProfile>(() => {
    try {
      const saved = localStorage.getItem('no0bz_user_profile');
      if (saved) return JSON.parse(saved);
    } catch {}
    return {
      pcName: 'no0bz-MONSTER-RIG',
      displayName: 'Commander',
      avatar: '👑',
      role: 'Master Host Workstation',
      accentColor: 'cyan',
      statusMsg: 'Online • Telemetrie-Hub aktiv'
    };
  });
  const [profileSavedToast, setProfileSavedToast] = useState(false);

  // Fast-Boot Cache Status
  const [systemCache, setSystemCache] = useState<{
    status: string;
    generated_at: string;
    load_time_ms: number;
    profile: any;
  } | null>(null);
  const [cacheRefreshing, setCacheRefreshing] = useState(false);

  // Connected Multi-PC Nodes
  const [connectedNodes, setConnectedNodes] = useState<RemoteNode[]>([
    {
      id: 'node_host',
      pc_name: 'no0bz-MONSTER-RIG (Host)',
      display_name: 'Commander',
      avatar: '👑',
      role: 'Master Hub Server',
      ip: '127.0.0.1 (LAN: 192.168.1.10)',
      os: 'Windows 11 Pro / CachyOS Linux',
      is_host: true,
      status: 'online',
      ping_ms: 0,
      last_seen: 'Live',
      cpu_load: 54.2,
      ram_percent: 57.5,
      gpu_load: 68.0,
      net_recv_mbps: 124.8,
      net_sent_mbps: 14.2
    },
    {
      id: 'node_client_1',
      pc_name: 'GAMING-DESKTOP-RTX',
      display_name: 'Alex (Gaming Rig)',
      avatar: '🎮',
      role: 'Unreal Engine 5 Node',
      ip: '192.168.1.15',
      os: 'Windows 11 Home',
      is_host: false,
      status: 'online',
      ping_ms: 3,
      last_seen: 'Gerade eben',
      cpu_load: 28.4,
      ram_percent: 44.0,
      gpu_load: 82.5,
      net_recv_mbps: 34.6,
      net_sent_mbps: 5.2
    },
    {
      id: 'node_client_2',
      pc_name: 'THINKPAD-DEV-WORKBOOK',
      display_name: 'Bruno (Mobile)',
      avatar: '💻',
      role: 'Linux Dev Station',
      ip: '192.168.1.42',
      os: 'CachyOS Linux (Kernel 6.13)',
      is_host: false,
      status: 'online',
      ping_ms: 5,
      last_seen: 'Vor 2s',
      cpu_load: 9.8,
      ram_percent: 31.5,
      gpu_load: 4.0,
      net_recv_mbps: 12.0,
      net_sent_mbps: 1.8
    }
  ]);

  // Rolling Network I/O Canvas Buffer (60 data points)
  const [netHistory, setNetHistory] = useState<{ recv: number; sent: number }[]>([
    { recv: 110, sent: 12 }, { recv: 118, sent: 15 }, { recv: 124, sent: 14 },
    { recv: 121, sent: 16 }, { recv: 126, sent: 14 }, { recv: 124.8, sent: 14.2 }
  ]);

  // Changelog Viewer State
  const [changelogRaw, setChangelogRaw] = useState(false);
  const [changelogSearch, setChangelogSearch] = useState('');
  const [changelogMd, setChangelogMd] = useState('');
  const [copiedChangelog, setCopiedChangelog] = useState(false);

  // Telemetry state
  const [systemTime, setSystemTime] = useState(new Date().toLocaleTimeString('de-DE'));
  const [procSearch, setProcSearch] = useState('');
  const [killPid, setKillPid] = useState<number | null>(null);

  // Per-Disk Multi-SSD State
  const [disks, setDisks] = useState<DiskItem[]>([
    { device: 'NVMe 1 (C:)', mount: 'C:\\ System', fstype: 'NTFS', total_gb: 953.8, used_gb: 412.3, free_gb: 541.5, percent: 43.2, read_mbs: 184.2, write_mbs: 45.1 },
    { device: 'NVMe 2 (D:)', mount: 'D:\\ Games', fstype: 'NTFS', total_gb: 1907.7, used_gb: 1450.0, free_gb: 457.7, percent: 76.0, read_mbs: 289.4, write_mbs: 110.2 },
    { device: 'SSD 3 (E:)', mount: 'E:\\ Workspace', fstype: 'NTFS', total_gb: 1907.7, used_gb: 890.2, free_gb: 1017.5, percent: 46.7, read_mbs: 17.5, write_mbs: 0.0 },
    { device: 'SSD 4 (F:)', mount: 'F:\\ Backups', fstype: 'NTFS', total_gb: 3815.4, used_gb: 2100.4, free_gb: 1715.0, percent: 55.0, read_mbs: 0.0, write_mbs: 0.0 },
  ]);

  const [metrics, setMetrics] = useState({
    cpu_load: 54.2,
    cpu_temp: 64.5,
    cpu_power: 112.4,
    cpu_cores: [48, 62, 35, 78, 22, 59, 81, 40, 52, 67, 33, 49, 75, 58, 42, 60],
    ram_total: 64.0,
    ram_used: 36.8,
    ram_percent: 57.5,
    gpu_name: 'NVIDIA GeForce RTX 4090 24GB',
    gpu_load: 68.0,
    gpu_temp: 66.0,
    gpu_power: 320.5,
    gpu_vram_total: 24.0,
    gpu_vram_used: 15.6,
    gpu_vram_pct: 65.0,
    net_recv_mbps: 124.8,
    net_sent_mbps: 14.2,
    fans_rpm: 1450,
    hostname: 'no0bz-MONSTER-RIG',
    uptime: '14h 22m 18s',
  });

  // Chat & Prompt Transfer State
  const [myDeviceName, setMyDeviceName] = useState('PC-A (Main Rig)');
  const [promptText, setPromptText] = useState('');
  const [promptTitle, setPromptTitle] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg_1',
      sender: 'PC-A (Main Rig)',
      timestamp: '14:20:15',
      type: 'prompt',
      title: 'DeepSeek / Llama-3 70B System Prompt',
      content: `You are an elite autonomous kernel and compiler optimization agent.
Target Architecture: Linux x86_64, Zen 4 / Raptor Lake, AVX-512 enabled.
Goal: Profile cache misses, vectorization width, and lock contention on high-frequency order processing threads.
Deliver zero-copy ring buffer implementations with C++20 atomic memory fences.`,
      tokens: 64,
      words: 42,
      attachments: []
    },
    {
      id: 'msg_2',
      sender: 'PC-B (Notebook / Mobile)',
      timestamp: '14:35:40',
      type: 'files',
      title: 'Benchmark Assets & Shader Dumps',
      content: 'Here are the latest benchmark captures and screenshots from the secondary test bench.',
      tokens: 0,
      words: 13,
      attachments: [
        {
          name: 'rtx4090_timespy_extreme.png',
          size: 2450000,
          ext: 'PNG',
          is_image: true,
          url: 'https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=800&q=80',
          uploaded_at: '2026-09-25 14:35'
        },
        {
          name: 'cuda_kernel_dispatch.cu',
          size: 48200,
          ext: 'CU',
          is_image: false,
          url: '#',
          uploaded_at: '2026-09-25 14:35'
        },
        {
          name: 'telemetry_dump_24h.duckdb',
          size: 8940000,
          ext: 'DUCKDB',
          is_image: false,
          url: '#',
          uploaded_at: '2026-09-25 14:36'
        }
      ]
    }
  ]);

  // Selected files for chat upload
  const [queuedFiles, setQueuedFiles] = useState<File[]>([]);
  const [isDraggingOverChat, setIsDraggingOverChat] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [lightboxImg, setLightboxImg] = useState<string | null>(null);

  // Vault / File Browser State
  const [vaultSearch, setVaultSearch] = useState('');
  const [vaultFilter, setVaultFilter] = useState<'all' | 'images' | 'code' | 'docs'>('all');
  const [vaultView, setVaultView] = useState<'grid' | 'list'>('grid');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Processes state
  const [processes, setProcesses] = useState<ProcessItem[]>([
    { pid: 4892, name: 'Cyberpunk2077.exe', cpu: 34.2, ram: 14.5, status: 'running' },
    { pid: 1840, name: 'python.exe (PyTorch CUDA)', cpu: 28.5, ram: 22.1, status: 'running' },
    { pid: 3204, name: 'obs64.exe (NVENC AV1)', cpu: 8.4, ram: 4.2, status: 'running' },
    { pid: 812, name: 'chrome.exe (32 Tabs)', cpu: 6.1, ram: 8.9, status: 'running' },
    { pid: 1420, name: 'duckdb_worker', cpu: 4.8, ram: 3.1, status: 'running' },
    { pid: 5601, name: 'discord.exe', cpu: 1.2, ram: 2.4, status: 'running' },
    { pid: 742, name: 'system_monitor_daemon', cpu: 0.9, ram: 0.8, status: 'running' },
    { pid: 128, name: 'system_interrupts', cpu: 0.4, ram: 0.1, status: 'running' }
  ]);

  // History state for Canvas
  const [historyPoints, setHistoryPoints] = useState<HistoryPoint[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Settings State Placeholders
  const [settings, setSettings] = useState({
    pollingInterval: '1.0s',
    autostart: true,
    minimizeToTray: false,
    p2pPort: 8350,
    lhmFallback: true,
    lhmUrl: 'http://127.0.0.1:8085/data.json',
    cpuAlertTemp: 85,
    gpuAlertTemp: 83,
    audioAlert: false,
    maxVaultCacheGB: 10,
    autoPurgeDuckDBHours: 24,
    preferredAdapter: 'Ethernet (10 GbE Realtek Gaming)',
  });

  // Live timer tick
  useEffect(() => {
    const timer = setInterval(() => {
      setSystemTime(new Date().toLocaleTimeString('de-DE'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch Changelog, Mode, Chat Messages & Vault Files from Backend API
  useEffect(() => {
    fetch('/api/changelog')
      .then(res => res.json())
      .then(data => {
        if (data && data.changelog) {
          setChangelogMd(data.changelog);
        }
      })
      .catch(() => {});

    // Fetch Active Multi-PC Mode & Storage Location (Serverseitig vs Lokal)
    fetch('/api/multipc/mode')
      .then(res => res.json())
      .then(data => {
        if (data && data.mode) {
          setMultiPcMode(data.mode);
          if (data.client_server_url) setClientServerUrl(data.client_server_url);
          if (data.storage_type) setStorageLocation(data.storage_type);
        }
      })
      .catch(() => {});

    // Fetch System Fast-Boot Cache
    fetch('/api/system/profile')
      .then(res => res.json())
      .then(data => {
        if (data && data.status) {
          setSystemCache(data);
        }
      })
      .catch(() => {});

    // Fetch Remote Nodes
    fetch('/api/nodes')
      .then(res => res.json())
      .then(data => {
        if (data && data.nodes && data.nodes.length > 0) {
          setConnectedNodes(data.nodes);
        }
      })
      .catch(() => {});

    // Fetch Persisted Chat Messages from Backend DuckDB
    fetch('/api/chat/messages')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setMessages(data);
        }
      })
      .catch(() => {});

    // Fetch Vault Files from Server or Local Storage
    fetch('/api/chat/files')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setServerVaultFiles(data);
        }
      })
      .catch(() => {});
  }, []);

  // Connect to Python Backend WebSocket if available, or simulate realistic live feed
  useEffect(() => {
    let ws: WebSocket | null = null;
    let fallbackInterval: any = null;

    try {
      const isHttps = window.location.protocol === 'https:';
      const wsProto = isHttps ? 'wss:' : 'ws:';
      // If served directly from FastAPI (port 8350 or custom), use current host. Otherwise default to localhost:8350
      const host = window.location.port === '8350' || (window.location.host && !window.location.port) 
        ? window.location.host 
        : 'localhost:8350';
      const wsUrl = `${wsProto}//${host}/ws/live`;
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const raw = JSON.parse(event.data);
          if (raw.type === 'chat_message') {
            setMessages(prev => {
              if (prev.some(m => m.id === raw.data.id)) return prev;
              return [...prev, raw.data];
            });
            // Refresh vault files when attachments are received
            if (raw.data.attachments && raw.data.attachments.length > 0) {
              fetch('/api/chat/files')
                .then(r => r.json())
                .then(data => { if (Array.isArray(data)) setServerVaultFiles(data); })
                .catch(() => {});
            }
            return;
          }
          if (raw.multipc) {
            if (raw.multipc.nodes) setConnectedNodes(raw.multipc.nodes);
            if (raw.multipc.mode) setMultiPcMode(raw.multipc.mode);
            if (raw.multipc.storage_location) setStorageLocation(raw.multipc.storage_location);
          }
          if (raw.cpu) {
            setMetrics(prev => ({
              ...prev,
              cpu_load: raw.cpu.load,
              cpu_cores: raw.cpu.cores.length ? raw.cpu.cores : prev.cpu_cores,
              cpu_temp: raw.cpu.temp_c || prev.cpu_temp,
              cpu_power: raw.cpu.power_w || prev.cpu_power,
              ram_used: raw.ram.used_gb,
              ram_percent: raw.ram.percent,
              gpu_load: raw.gpu.load,
              gpu_temp: raw.gpu.temp_c || prev.gpu_temp,
              gpu_power: raw.gpu.power_w || prev.gpu_power,
              gpu_vram_used: raw.gpu.vram_used_gb,
              gpu_vram_pct: raw.gpu.vram_percent,
              net_recv_mbps: raw.network.recv_mbps,
              net_sent_mbps: raw.network.sent_mbps,
              hostname: raw.hostname || prev.hostname,
            }));
            if (raw.disks && raw.disks.length > 0) {
              setDisks(raw.disks);
            }
            const newPt: HistoryPoint = {
              time: new Date().toLocaleTimeString('de-DE'),
              cpu: raw.cpu.load,
              ram: raw.ram.percent,
              gpu: raw.gpu.load,
              gpu_temp: raw.gpu.temp_c || 45,
              recv: raw.network.recv_mbps,
              sent: raw.network.sent_mbps,
              disk_read: raw.total_disk_io ? raw.total_disk_io.read_mbs : 0,
              disk_write: raw.total_disk_io ? raw.total_disk_io.write_mbs : 0,
            };
            setHistoryPoints(hist => [...hist.slice(-59), newPt]);
            setNetHistory(prev => [...prev.slice(-59), { recv: raw.network.recv_mbps, sent: raw.network.sent_mbps }]);
          }
        } catch {
          // ignore
        }
      };
      ws.onerror = () => {
        initFallbackLoop();
      };
    } catch {
      initFallbackLoop();
    }

    function initFallbackLoop() {
      if (fallbackInterval) return;
      fallbackInterval = setInterval(() => {
        setMetrics(prev => {
          const newCpu = Math.min(Math.max(prev.cpu_load + (Math.random() * 8 - 4), 10), 98);
          const newGpu = Math.min(Math.max(prev.gpu_load + (Math.random() * 6 - 3), 15), 99);
          const newCores = prev.cpu_cores.map(c => Math.min(Math.max(Math.round(c + (Math.random() * 14 - 7)), 5), 100));
          const newRecv = parseFloat(Math.max(5, prev.net_recv_mbps + (Math.random() * 20 - 10)).toFixed(1));
          const newSent = parseFloat(Math.max(1, prev.net_sent_mbps + (Math.random() * 6 - 3)).toFixed(1));

          setNetHistory(prevHist => [...prevHist.slice(-59), { recv: newRecv, sent: newSent }]);

          // Also update connectedNodes telemetry in demo fallback
          setConnectedNodes(nodes => nodes.map(n => {
            if (n.is_host) {
              return { ...n, cpu_load: parseFloat(newCpu.toFixed(1)), net_recv_mbps: newRecv, net_sent_mbps: newSent };
            }
            return {
              ...n,
              cpu_load: parseFloat(Math.min(Math.max(n.cpu_load + (Math.random() * 4 - 2), 5), 95).toFixed(1)),
              ram_percent: parseFloat(Math.min(Math.max(n.ram_percent + (Math.random() * 2 - 1), 20), 90).toFixed(1)),
              net_recv_mbps: parseFloat(Math.max(1, n.net_recv_mbps + (Math.random() * 6 - 3)).toFixed(1)),
              net_sent_mbps: parseFloat(Math.max(0.5, n.net_sent_mbps + (Math.random() * 2 - 1)).toFixed(1))
            };
          }));

          // Also update disk live I/O fluctuate
          setDisks(prevDisks => prevDisks.map((d, i) => {
            const deltaR = Math.max(0, d.read_mbs + (Math.random() * 20 - 10));
            const deltaW = Math.max(0, d.write_mbs + (Math.random() * 10 - 5));
            return {
              ...d,
              read_mbs: i === 0 ? parseFloat(deltaR.toFixed(1)) : d.read_mbs,
              write_mbs: i === 1 ? parseFloat(deltaW.toFixed(1)) : d.write_mbs,
            };
          }));

          const newPt: HistoryPoint = {
            time: new Date().toLocaleTimeString('de-DE'),
            cpu: parseFloat(newCpu.toFixed(1)),
            ram: prev.ram_percent,
            gpu: parseFloat(newGpu.toFixed(1)),
            gpu_temp: prev.gpu_temp,
            recv: prev.net_recv_mbps,
            sent: prev.net_sent_mbps,
            disk_read: 480.0,
            disk_write: 155.0,
          };
          setHistoryPoints(hist => [...hist.slice(-59), newPt]);

          return {
            ...prev,
            cpu_load: parseFloat(newCpu.toFixed(1)),
            gpu_load: parseFloat(newGpu.toFixed(1)),
            cpu_cores: newCores,
            cpu_temp: parseFloat((60 + (newCpu * 0.15)).toFixed(1)),
            gpu_temp: parseFloat((55 + (newGpu * 0.18)).toFixed(1)),
            net_recv_mbps: parseFloat(Math.max(10, prev.net_recv_mbps + (Math.random() * 20 - 10)).toFixed(1)),
            net_sent_mbps: parseFloat(Math.max(2, prev.net_sent_mbps + (Math.random() * 6 - 3)).toFixed(1)),
          };
        });
      }, 1000);
    }

    return () => {
      if (ws) ws.close();
      if (fallbackInterval) clearInterval(fallbackInterval);
    };
  }, []);

  // History Canvas Drawing
  useEffect(() => {
    if (activeTab !== 'history' || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const w = canvas.width;
    const h = canvas.height;

    // Draw dark grid
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    if (historyPoints.length < 2) return;

    // Draw CPU line (cyan / red)
    const drawLine = (color: string, key: keyof HistoryPoint, maxVal = 100) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      historyPoints.forEach((pt, idx) => {
        const x = (idx / (historyPoints.length - 1)) * w;
        const val = Number(pt[key]) || 0;
        const y = h - (val / maxVal) * (h - 20) - 10;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };

    drawLine(themeMode === 'nightmare' ? '#ef4444' : '#06b6d4', 'cpu', 100);
    drawLine('#3b82f6', 'ram', 100);
    drawLine('#a855f7', 'gpu', 100);
  }, [historyPoints, activeTab, themeMode]);

  // Total Disks Speed
  const totalReadSpeed = useMemo(() => {
    return disks.reduce((acc, d) => acc + (d.read_mbs || 0), 0).toFixed(1);
  }, [disks]);

  const totalWriteSpeed = useMemo(() => {
    return disks.reduce((acc, d) => acc + (d.write_mbs || 0), 0).toFixed(1);
  }, [disks]);

  // Filtered Processes
  const filteredProcesses = useMemo(() => {
    return processes.filter(p => 
      p.name.toLowerCase().includes(procSearch.toLowerCase()) || 
      p.pid.toString().includes(procSearch)
    );
  }, [processes, procSearch]);

  // All Attachments gathered from server vault & messages for Vault View
  const allVaultFiles = useMemo(() => {
    const map = new Map<string, ChatAttachment & { sender: string; msgId?: string }>();
    serverVaultFiles.forEach(f => {
      map.set(f.name, { ...f, sender: (f as any).sender || (multiPcMode === 'host' ? 'Host Server' : 'Lokal') });
    });
    messages.forEach(m => {
      (m.attachments || []).forEach(att => {
        if (!map.has(att.name)) {
          map.set(att.name, { ...att, sender: m.sender, msgId: m.id });
        }
      });
    });
    return Array.from(map.values()).filter(item => {
      const matchSearch = item.name.toLowerCase().includes(vaultSearch.toLowerCase());
      if (!matchSearch) return false;
      if (vaultFilter === 'images') return item.is_image;
      if (vaultFilter === 'code') return ['PY', 'CU', 'TS', 'JS', 'CPP', 'JSON', 'RS', 'SH', 'BAT'].includes(item.ext);
      if (vaultFilter === 'docs') return ['TXT', 'PDF', 'MD', 'DOCX', 'LOG'].includes(item.ext);
      return true;
    });
  }, [messages, serverVaultFiles, vaultSearch, vaultFilter, multiPcMode]);

  // Handle Drag & Drop over Chat
  const handleChatDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOverChat(true);
  };

  const handleChatDragLeave = () => {
    setIsDraggingOverChat(false);
  };

  const handleChatDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOverChat(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files).slice(0, 100);
      setQueuedFiles(prev => [...prev, ...droppedFiles].slice(0, 100));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).slice(0, 100);
      setQueuedFiles(prev => [...prev, ...selected].slice(0, 100));
    }
  };

  // Direct Vault Upload (Multipart Form Data)
  const handleVaultUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const filesToUpload = Array.from(e.target.files).slice(0, 100);
    const currentSender = userProfile.displayName 
      ? `${userProfile.displayName} (${userProfile.pcName || metrics.hostname})`
      : (userProfile.pcName || metrics.hostname);

    const formData = new FormData();
    filesToUpload.forEach(f => formData.append('files', f));
    formData.append('sender', currentSender);
    formData.append('title', `Vault Upload (${filesToUpload.length} Datei${filesToUpload.length > 1 ? 'en' : ''})`);
    formData.append('note', `Direkt in das ${multiPcMode === 'host' ? 'serverseitige' : 'lokale'} Vault hochgeladene Dateien.`);

    try {
      const apiHost = window.location.port === '8350' || (window.location.host && !window.location.port) 
        ? '' 
        : 'http://localhost:8350';
      const res = await fetch(`${apiHost}/api/chat/upload`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        if (data.message) {
          setMessages(prev => [...prev, data.message]);
        }
        // Refresh vault files
        const flRes = await fetch(`${apiHost}/api/chat/files`);
        if (flRes.ok) {
          const flData = await flRes.json();
          if (Array.isArray(flData)) setServerVaultFiles(flData);
        }
      }
    } catch (err) {
      console.error("Vault direct upload error:", err);
    }
    e.target.value = '';
  };

  // Delete Vault File from Disk & DuckDB
  const handleDeleteVaultFile = async (fileName: string) => {
    try {
      const apiHost = window.location.port === '8350' || (window.location.host && !window.location.port) 
        ? '' 
        : 'http://localhost:8350';
      await fetch(`${apiHost}/api/chat/files/${encodeURIComponent(fileName)}`, {
        method: 'DELETE'
      });
    } catch {}
    setMessages(prev => prev.map(m => ({
      ...m,
      attachments: (m.attachments || []).filter(a => a.name !== fileName)
    })));
    setServerVaultFiles(prev => prev.filter(f => f.name !== fileName));
  };

  // Send Chat Message / Prompt / Files
  const handleSendMessage = async () => {
    if (!promptText.trim() && queuedFiles.length === 0) return;

    const currentSender = userProfile.displayName 
      ? `${userProfile.displayName} (${userProfile.pcName || metrics.hostname})`
      : (userProfile.pcName || metrics.hostname);

    const apiHost = window.location.port === '8350' || (window.location.host && !window.location.port) 
      ? '' 
      : 'http://localhost:8350';

    // If uploading files, send real multipart/form-data to /api/chat/upload
    if (queuedFiles.length > 0) {
      try {
        const formData = new FormData();
        queuedFiles.forEach(f => formData.append('files', f));
        formData.append('sender', currentSender);
        if (promptTitle.trim()) formData.append('title', promptTitle.trim());
        if (promptText.trim()) formData.append('note', promptText.trim());

        const res = await fetch(`${apiHost}/api/chat/upload`, {
          method: 'POST',
          body: formData
        });

        if (res.ok) {
          const data = await res.json();
          if (data.message) {
            setMessages(prev => {
              if (prev.some(m => m.id === data.message.id)) return prev;
              return [...prev, data.message];
            });
          }
          // Refresh vault
          fetch(`${apiHost}/api/chat/files`)
            .then(r => r.json())
            .then(fl => { if (Array.isArray(fl)) setServerVaultFiles(fl); })
            .catch(() => {});
        } else {
          // Fallback local display
          fallbackLocalMessage();
        }
      } catch {
        fallbackLocalMessage();
      }
    } else {
      // Text-only Prompt Transfer
      const words = promptText.trim().split(/\s+/).filter(Boolean).length;
      const tokens = Math.round(promptText.length / 3.8);

      const newMsg: ChatMessage = {
        id: `msg_${Date.now()}`,
        sender: currentSender,
        timestamp: new Date().toLocaleTimeString('de-DE'),
        type: 'prompt',
        title: promptTitle.trim() || 'P2P Prompt Sync',
        content: promptText.trim(),
        tokens,
        words,
        attachments: []
      };

      setMessages(prev => [...prev, newMsg]);

      try {
        await fetch(`${apiHost}/api/chat/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newMsg)
        });
      } catch {}
    }

    setPromptText('');
    setPromptTitle('');
    setQueuedFiles([]);

    setTimeout(() => {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);

    function fallbackLocalMessage() {
      const attachments: ChatAttachment[] = queuedFiles.map(f => {
        const ext = f.name.split('.').pop()?.toUpperCase() || 'FILE';
        const isImg = ['PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'SVG'].includes(ext);
        return {
          name: f.name,
          size: f.size,
          ext,
          is_image: isImg,
          url: isImg ? URL.createObjectURL(f) : '#',
          data_url: isImg ? URL.createObjectURL(f) : undefined,
          uploaded_at: new Date().toLocaleTimeString('de-DE')
        };
      });

      const words = promptText.trim().split(/\s+/).filter(Boolean).length;
      const tokens = Math.round(promptText.length / 3.8);

      const newMsg: ChatMessage = {
        id: `msg_${Date.now()}`,
        sender: currentSender,
        timestamp: new Date().toLocaleTimeString('de-DE'),
        type: queuedFiles.length > 0 && !promptText.trim() ? 'files' : 'prompt',
        title: promptTitle.trim() || `Shared ${attachments.length} File(s)`,
        content: promptText.trim() || `Uploaded ${attachments.length} file(s) to vault.`,
        tokens,
        words,
        attachments
      };

      setMessages(prev => [...prev, newMsg]);
    }
  };

  // Copy Prompt to Clipboard
  const handleCopyPrompt = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Kill Process Action
  const handleKill = async (pid: number) => {
    setKillPid(pid);
    try {
      const apiHost = window.location.port === '8350' || (window.location.host && !window.location.port) 
        ? '' 
        : 'http://localhost:8350';
      await fetch(`${apiHost}/api/kill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid })
      });
    } catch {}
    setTimeout(() => {
      setProcesses(prev => prev.filter(p => p.pid !== pid));
      setKillPid(null);
    }, 400);
  };

  // Styling Classes based on Theme
  const isNightmare = themeMode === 'nightmare';
  const accentColor = isNightmare ? '#ef4444' : themeMode === 'industrial' ? '#f59e0b' : '#06b6d4';
  const accentGlow = isNightmare ? 'shadow-[0_0_20px_rgba(239,68,68,0.25)]' : 'shadow-[0_0_20px_rgba(6,182,212,0.2)]';
  const cardBg = isNightmare 
    ? 'bg-zinc-950/80 border border-red-900/30 backdrop-blur-md'
    : 'bg-slate-900/80 border border-slate-800 backdrop-blur-md';

  return (
    <div className={`min-h-screen text-zinc-100 flex flex-col font-sans select-none overflow-x-hidden ${isNightmare ? 'bg-[#06070a]' : 'bg-[#080d1a]'}`}>
      
      {/* ======================================================== */}
      {/* TOP HEADER BAR (COMPLETELY REMOVED OLD TOP MENU TABS)   */}
      {/* ======================================================== */}
      <header className={`h-16 px-5 flex items-center justify-between border-b ${isNightmare ? 'bg-black/90 border-red-950/40' : 'bg-slate-950/90 border-slate-800'} backdrop-blur-lg sticky top-0 z-40`}>
        {/* Left: Prominent no0bz Branding */}
        <div className="flex items-center gap-4">
          <No0bzLogo mode={logoStyle} size="normal" onVersionClick={() => setActiveTab('changelog')} />
          <div className="h-6 w-px bg-zinc-800 hidden md:block" />
          <div className="hidden lg:flex items-center gap-2 text-xs font-mono text-zinc-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping inline-block" />
            <span className="text-emerald-400 font-semibold">CORE STREAM ACTIVE</span>
            <span className="text-zinc-600">•</span>
            <span>PORT: 8350</span>
          </div>
        </div>

        {/* Center: Real-Time Status / Current View Banner */}
        <div className="hidden md:flex items-center gap-3">
          <div className={`px-3 py-1 rounded-md border font-mono text-xs flex items-center gap-2 ${isNightmare ? 'bg-red-950/30 border-red-800/40 text-red-300' : 'bg-cyan-950/30 border-cyan-800/40 text-cyan-300'}`}>
            <Server className="w-3.5 h-3.5" />
            <span className="font-semibold">{metrics.hostname}</span>
            <span className="opacity-40">|</span>
            <span>UPTIME: {metrics.uptime}</span>
          </div>

          <div className="px-3 py-1 rounded-md bg-zinc-900 border border-zinc-800 font-mono text-xs flex items-center gap-2 text-zinc-300">
            <Clock className="w-3.5 h-3.5 text-zinc-400" />
            <span className="font-bold text-white tracking-wider">{systemTime}</span>
          </div>
        </div>

        {/* Right: Theme / Logo Mode & Quick Actions */}
        <div className="flex items-center gap-3">
          {/* Multi-PC Mode Quick Switcher */}
          <button
            onClick={() => setShowModeModal(true)}
            title="Multi-PC Modus wechseln (Lokal / Server Hosten / Client Node)"
            className={`px-2.5 py-1 rounded border text-xs font-mono font-bold flex items-center gap-1.5 transition-all ${
              multiPcMode === 'host'
                ? 'bg-amber-950/70 border-amber-500 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.35)]'
                : multiPcMode === 'client'
                ? 'bg-blue-950/70 border-blue-500 text-blue-300 shadow-[0_0_12px_rgba(59,130,246,0.35)]'
                : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">
              {multiPcMode === 'host' ? '👑 SERVER HOST' : multiPcMode === 'client' ? '🔗 CLIENT NODE' : '🖥️ LOKAL'}
            </span>
            {multiPcMode === 'host' && (
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-900/80 text-amber-200 font-mono">
                {connectedNodes.length} PCs
              </span>
            )}
          </button>

          {/* Changelog Quick Button */}
          <button
            onClick={() => setActiveTab('changelog')}
            title="no0bz Command Center Changelog & Versionshistorie"
            className={`px-2.5 py-1 rounded border text-xs font-mono font-bold flex items-center gap-1.5 transition-all ${
              activeTab === 'changelog'
                ? isNightmare
                  ? 'bg-red-600 border-red-500 text-white shadow-[0_0_12px_rgba(239,68,68,0.5)]'
                  : 'bg-cyan-500 border-cyan-400 text-slate-950 font-bold shadow-[0_0_12px_rgba(6,182,212,0.4)]'
                : 'bg-zinc-900 hover:bg-zinc-800 border-zinc-800 text-zinc-300 hover:text-white'
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-zinc-400" />
            <span className="hidden sm:inline">CHANGELOG</span>
            <span className="text-[9px] px-1 py-0.2 rounded bg-zinc-800 text-zinc-400 font-mono">v3.8.1</span>
          </button>

          {/* Logo Style Toggle */}
          <button
            onClick={() => {
              const next = logoStyle === 'nightmare' ? 'classic' : 'nightmare';
              setLogoStyle(next);
              setThemeMode(next === 'nightmare' ? 'nightmare' : 'bento');
            }}
            title="Wechsle zwischen no0bz Classic und Nightmare Mode"
            className={`px-2.5 py-1 rounded border text-xs font-mono font-bold flex items-center gap-1.5 transition-all ${
              logoStyle === 'nightmare'
                ? 'bg-red-950/60 border-red-600 text-red-300 shadow-[0_0_12px_rgba(239,68,68,0.4)]'
                : 'bg-cyan-950/60 border-cyan-500 text-cyan-300 shadow-[0_0_12px_rgba(6,182,212,0.4)]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{logoStyle === 'nightmare' ? 'NIGHTMARE' : 'CLASSIC'}</span>
          </button>

          {/* Device / User Profile Tag */}
          <button
            onClick={() => setActiveTab('settings')}
            title="Benutzer- & PC-Profil in Einstellungen anpassen"
            className="px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 text-[11px] font-mono text-zinc-300 flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <span className="text-sm">{userProfile.avatar || '💻'}</span>
            <span className="hidden sm:inline font-semibold text-white">
              {userProfile.displayName || userProfile.pcName || metrics.hostname}
            </span>
          </button>
        </div>
      </header>

      {/* ======================================================== */}
      {/* MAIN APPLICATION BODY: CLEAN SIDEBAR + CONTENT AREA      */}
      {/* ======================================================== */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* ====================================================== */}
        {/* STREAMLINED LEFT SIDEBAR (CLEANED UP AS REQUESTED)     */}
        {/* ====================================================== */}
        <aside className={`w-64 flex-shrink-0 flex flex-col justify-between border-r ${isNightmare ? 'bg-[#08090d] border-red-950/30' : 'bg-[#090f1d] border-slate-800/80'} p-3 select-none`}>
          <div className="space-y-6">
            
            {/* Primary Navigation */}
            <div>
              <div className="px-3 pb-2 text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-500">
                Hauptmenü
              </div>
              <nav className="space-y-1">
                {/* 1. DASHBOARD */}
                <button
                  onClick={() => {
                    setSelectedViewNodeId(null);
                    setActiveTab('dashboard');
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'dashboard'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Activity className="w-4 h-4" />
                    <span>DASHBOARD</span>
                  </div>
                  {activeTab === 'dashboard' && <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
                </button>

                {/* 2. MULTI-PC HUB */}
                <button
                  onClick={() => setActiveTab('multipc')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'multipc'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Globe className="w-4 h-4 text-amber-400" />
                    <span>MULTI-PC HUB</span>
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                    activeTab === 'multipc' 
                      ? 'bg-black/30 text-white' 
                      : multiPcMode === 'host' 
                      ? 'bg-amber-950/80 border border-amber-600/70 text-amber-300' 
                      : 'bg-zinc-800 text-zinc-300'
                  }`}>
                    {multiPcMode === 'host' ? `${connectedNodes.length} PCs` : multiPcMode === 'client' ? 'Client' : 'Lokal'}
                  </span>
                </button>

                {/* 3. CHAT & PROMPT SYNC */}
                <button
                  onClick={() => setActiveTab('chat')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'chat'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <MessageSquare className="w-4 h-4" />
                    <span>CHAT & PROMPTS</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-300 font-bold">
                    P2P
                  </span>
                </button>

                {/* 4. DATEIBROWSER / CHAT VAULT */}
                <button
                  onClick={() => setActiveTab('vault')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'vault'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Folder className="w-4 h-4" />
                    <span>DATEIBROWSER</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-300 font-bold">
                    {allVaultFiles.length}
                  </span>
                </button>

                {/* 5. PROZESSE */}
                <button
                  onClick={() => setActiveTab('processes')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'processes'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Cpu className="w-4 h-4" />
                    <span>PROZESSE</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800/80 text-zinc-300 font-bold">
                    {processes.length}
                  </span>
                </button>

                {/* 6. HISTORIE */}
                <button
                  onClick={() => setActiveTab('history')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'history'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Layers className="w-4 h-4" />
                    <span>HISTORIE (DUCKDB)</span>
                  </div>
                  <span className="text-[10px] text-zinc-500">24h</span>
                </button>

                {/* 7. EINSTELLUNGEN */}
                <button
                  onClick={() => setActiveTab('settings')}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono font-semibold transition-all ${
                    activeTab === 'settings'
                      ? isNightmare
                        ? 'bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                        : 'bg-cyan-500 text-slate-950 font-bold shadow-[0_0_15px_rgba(6,182,212,0.4)]'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Settings className="w-4 h-4" />
                    <span>EINSTELLUNGEN</span>
                  </div>
                </button>
              </nav>
            </div>

            {/* Quick Live Quick-Stats Box */}
            <div className={`p-3 rounded-lg border text-xs font-mono space-y-2 ${isNightmare ? 'bg-red-950/20 border-red-900/30 text-red-200' : 'bg-slate-900/50 border-slate-800 text-zinc-300'}`}>
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
                <span>Quick Stats</span>
                <span className="text-emerald-400 text-[9px]">ONLINE</span>
              </div>
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-zinc-400">CPU Last:</span>
                <span className="font-bold text-white">{metrics.cpu_load}%</span>
              </div>
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-zinc-400">GPU Last:</span>
                <span className="font-bold text-white">{metrics.gpu_load}%</span>
              </div>
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-zinc-400">RAM Belegt:</span>
                <span className="font-bold text-white">{metrics.ram_used} GB</span>
              </div>
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-zinc-400">Disks Read:</span>
                <span className="font-bold text-cyan-400">{totalReadSpeed} MB/s</span>
              </div>
            </div>

          </div>

          {/* Bottom Sidebar: Aesthetic Brand Footprint */}
          <div className="pt-3 border-t border-zinc-800/60">
            <div className="text-[10px] font-mono text-zinc-500 text-center">
              no0bz Command Center
            </div>
            <div className="text-[9px] font-mono text-zinc-600 text-center mt-0.5">
              // MORE FPS • MORE POWER //
            </div>
          </div>
        </aside>

        {/* ====================================================== */}
        {/* MAIN CONTENT WORKSPACE                                 */}
        {/* ====================================================== */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-gradient-to-b from-transparent to-black/40">

          {/* ---------------------------------------------------- */}
          {/* TAB 1: SYSTEM MONITORING DASHBOARD                   */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'dashboard' && (
            <div className="space-y-6 max-w-7xl mx-auto">
              
              {/* Row 1: The 4 Primary Hardware Telemetry Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                
                {/* 1. CPU CARD */}
                <div className={`rounded-xl p-4 flex flex-col justify-between ${cardBg} ${accentGlow}`}>
                  <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Cpu className={`w-4 h-4 ${isNightmare ? 'text-red-500' : 'text-cyan-400'}`} />
                      <span className="font-mono font-bold text-xs tracking-wider">CPU METRICS</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                      AMD Ryzen / Intel
                    </span>
                  </div>

                  <SvgCircleGauge
                    value={metrics.cpu_load}
                    title="CPU LOAD"
                    unit="%"
                    color={accentColor}
                    subtext={`${metrics.cpu_temp}°C • ${metrics.cpu_power}W Package`}
                  />

                  {/* 16-Capsule CPU Core Graph (as in image) */}
                  <div className="mt-3 pt-3 border-t border-zinc-800/60">
                    <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400 mb-1.5">
                      <span>16 LOGICAL CORES</span>
                      <span className="text-zinc-500">PER-CORE LOAD</span>
                    </div>
                    <div className="grid grid-cols-8 gap-1.5 h-12 bg-black/40 p-1.5 rounded-lg border border-zinc-800/50">
                      {metrics.cpu_cores.map((coreVal, idx) => (
                        <div key={idx} className="relative flex flex-col justify-end items-center h-full bg-zinc-900/60 rounded overflow-hidden" title={`Core ${idx}: ${coreVal}%`}>
                          <div 
                            className={`w-full rounded-t transition-all duration-300 ${
                              coreVal > 75 
                                ? 'bg-red-500' 
                                : coreVal > 50 
                                ? 'bg-amber-400' 
                                : isNightmare ? 'bg-red-600' : 'bg-cyan-400'
                            }`}
                            style={{ height: `${coreVal}%` }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 2. RAM & SWAP CARD */}
                <div className={`rounded-xl p-4 flex flex-col justify-between ${cardBg}`}>
                  <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Activity className="w-4 h-4 text-blue-400" />
                      <span className="font-mono font-bold text-xs tracking-wider">MEMORY / DDR5</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                      {metrics.ram_total} GB TOTAL
                    </span>
                  </div>

                  <SvgCircleGauge
                    value={metrics.ram_percent}
                    title="RAM USAGE"
                    unit="%"
                    color="#3b82f6"
                    subtext={`${metrics.ram_used} GB / ${metrics.ram_total} GB`}
                  />

                  {/* RAM & Swap Progress Bar */}
                  <div className="mt-3 pt-3 border-t border-zinc-800/60 space-y-2">
                    <div>
                      <div className="flex justify-between text-[10px] font-mono text-zinc-400 mb-1">
                        <span>PHYSICAL RAM</span>
                        <span className="font-bold text-white">{metrics.ram_percent}%</span>
                      </div>
                      <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-zinc-800">
                        <div className="bg-blue-500 h-full rounded-full transition-all" style={{ width: `${metrics.ram_percent}%` }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-[10px] font-mono text-zinc-400 mb-1">
                        <span>SWAP / PAGEFILE</span>
                        <span className="font-bold text-white">12.4%</span>
                      </div>
                      <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-zinc-800">
                        <div className="bg-indigo-500 h-full rounded-full transition-all" style={{ width: `12.4%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* 3. GPU METRICS CARD */}
                <div className={`rounded-xl p-4 flex flex-col justify-between ${cardBg} ${accentGlow}`}>
                  <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-purple-400" />
                      <span className="font-mono font-bold text-xs tracking-wider">GPU ACCELERATOR</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-purple-300">
                      RTX 4090
                    </span>
                  </div>

                  <SvgCircleGauge
                    value={metrics.gpu_load}
                    title="GPU LOAD"
                    unit="%"
                    color="#a855f7"
                    subtext={`${metrics.gpu_temp}°C • ${metrics.gpu_power}W TGP`}
                  />

                  {/* VRAM Telemetry */}
                  <div className="mt-3 pt-3 border-t border-zinc-800/60">
                    <div className="flex justify-between text-[10px] font-mono text-zinc-400 mb-1">
                      <span>GDDR6X VRAM</span>
                      <span className="font-bold text-purple-400">{metrics.gpu_vram_used} / {metrics.gpu_vram_total} GB</span>
                    </div>
                    <div className="w-full bg-zinc-900 h-2.5 rounded-full overflow-hidden border border-zinc-800">
                      <div className="bg-gradient-to-r from-purple-600 to-pink-500 h-full rounded-full transition-all" style={{ width: `${metrics.gpu_vram_pct}%` }} />
                    </div>
                    <div className="flex justify-between text-[9px] font-mono text-zinc-500 mt-1">
                      <span>NVLINK READY</span>
                      <span>{metrics.fans_rpm} RPM FANS</span>
                    </div>
                  </div>
                </div>

                {/* 4. NETWORK & LATENCY CARD WITH LIVE GRAPH */}
                <div className={`rounded-xl p-4 flex flex-col justify-between ${cardBg}`}>
                  <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Wifi className="w-4 h-4 text-emerald-400" />
                      <span className="font-mono font-bold text-xs tracking-wider">NETWORK I/O</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-300">
                        LAN 10 GbE
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/70 border border-emerald-700/60 text-emerald-400 font-bold">
                        PING 3ms
                      </span>
                    </div>
                  </div>

                  {/* Dual Speed Indicators */}
                  <div className="grid grid-cols-2 gap-2 mb-1 font-mono">
                    <div className="bg-black/50 p-2 rounded-lg border border-cyan-900/30 flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-cyan-400">
                        <ArrowDown className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-semibold">RX</span>
                      </div>
                      <span className="text-sm font-bold text-white">
                        {metrics.net_recv_mbps} <span className="text-[10px] text-zinc-400">M</span>
                      </span>
                    </div>

                    <div className="bg-black/50 p-2 rounded-lg border border-amber-900/30 flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-amber-400">
                        <ArrowUp className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-semibold">TX</span>
                      </div>
                      <span className="text-sm font-bold text-white">
                        {metrics.net_sent_mbps} <span className="text-[10px] text-zinc-400">M</span>
                      </span>
                    </div>
                  </div>

                  {/* Real-Time Canvas Graph (Requested by User) */}
                  <NetworkLiveGraph
                    history={netHistory}
                    currentRecv={metrics.net_recv_mbps}
                    currentSent={metrics.net_sent_mbps}
                    isNightmare={isNightmare}
                  />

                  <div className="pt-2 mt-1 border-t border-zinc-800/60 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                    <span>BUFFERS: 0% LOSS</span>
                    <span className="text-zinc-500">NIC: Realtek RTL8125 2.5G</span>
                  </div>
                </div>

              </div>

              {/* Row 2: Per-Disk Multi-SSD Storage Matrix */}
              <div className={`rounded-xl p-5 ${cardBg}`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-zinc-800 gap-2">
                  <div className="flex items-center gap-2.5">
                    <Disc className="w-5 h-5 text-amber-400" />
                    <div>
                      <h3 className="font-mono font-bold text-sm tracking-wide text-white">
                        STORAGE MATRIX &amp; INDIVIDUELLE SSD GESCHWINDIGKEITEN
                      </h3>
                      <p className="text-[11px] font-mono text-zinc-400">
                        Echtzeit Lese- &amp; Schreibraten für jedes verbundene Laufwerk (Windows / Linux)
                      </p>
                    </div>
                  </div>

                  {/* Total I/O summary badge */}
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="px-2.5 py-1 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-300 font-bold">
                      TOTAL READ: {totalReadSpeed} MB/s
                    </span>
                    <span className="px-2.5 py-1 rounded bg-amber-950/80 border border-amber-800 text-amber-300 font-bold">
                      TOTAL WRITE: {totalWriteSpeed} MB/s
                    </span>
                  </div>
                </div>

                {/* Per Disk Breakdown Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                  {disks.map((d, index) => (
                    <div key={index} className="p-3.5 rounded-lg bg-black/40 border border-zinc-800/80 flex flex-col justify-between space-y-3 hover:border-zinc-700 transition-colors">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-mono font-bold text-xs text-white flex items-center gap-1.5">
                            <HardDrive className="w-3.5 h-3.5 text-zinc-400" />
                            <span>{d.device}</span>
                          </div>
                          <div className="text-[10px] font-mono text-zinc-500 mt-0.5">
                            {d.mount} • {d.fstype}
                          </div>
                        </div>
                        <span className="text-xs font-mono font-bold text-zinc-300">
                          {d.percent}%
                        </span>
                      </div>

                      {/* Capacity Bar */}
                      <div>
                        <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-zinc-800 mb-1">
                          <div 
                            className={`h-full rounded-full transition-all duration-300 ${
                              d.percent > 85 ? 'bg-red-500' : d.percent > 70 ? 'bg-amber-400' : 'bg-cyan-500'
                            }`}
                            style={{ width: `${d.percent}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-[10px] font-mono text-zinc-400">
                          <span>{d.used_gb} GB used</span>
                          <span>{d.free_gb} GB free</span>
                        </div>
                      </div>

                      {/* INDIVIDUAL DISK READ/WRITE METRICS */}
                      <div className="pt-2 border-t border-zinc-800/70 grid grid-cols-2 gap-2 text-center font-mono">
                        <div className="p-1 rounded bg-zinc-900/80 border border-cyan-950">
                          <div className="text-[9px] text-zinc-500 font-semibold flex items-center justify-center gap-1">
                            <ArrowDown className="w-2.5 h-2.5 text-cyan-400" /> READ
                          </div>
                          <div className="text-xs font-bold text-cyan-400">
                            {d.read_mbs} <span className="text-[9px] text-zinc-500 font-normal">MB/s</span>
                          </div>
                        </div>

                        <div className="p-1 rounded bg-zinc-900/80 border border-amber-950">
                          <div className="text-[9px] text-zinc-500 font-semibold flex items-center justify-center gap-1">
                            <ArrowUp className="w-2.5 h-2.5 text-amber-400" /> WRITE
                          </div>
                          <div className="text-xs font-bold text-amber-400">
                            {d.write_mbs} <span className="text-[9px] text-zinc-500 font-normal">MB/s</span>
                          </div>
                        </div>
                      </div>

                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 2: MULTI-PC HUB & SERVER CLUSTER (MULTI-PC MODE) */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'multipc' && (
            <div className="space-y-6 max-w-7xl mx-auto">
              
              {/* Header Box */}
              <div className={`p-5 rounded-xl ${cardBg} flex flex-col md:flex-row items-start md:items-center justify-between gap-4`}>
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-amber-950/80 border border-amber-500/60 text-amber-400">
                    <Globe className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-mono font-bold text-base text-white">
                        no0bz MULTI-PC HUB &amp; SERVER CLUSTER
                      </h2>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                        multiPcMode === 'host'
                          ? 'bg-amber-950 border border-amber-600 text-amber-300'
                          : multiPcMode === 'client'
                          ? 'bg-blue-950 border border-blue-600 text-blue-300'
                          : 'bg-zinc-800 text-zinc-300'
                      }`}>
                        {multiPcMode === 'host' ? '👑 SERVER HOST AKTIV' : multiPcMode === 'client' ? '🔗 CLIENT AGENT' : '🖥️ LOKAL'}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 font-mono">
                      Zentrales Telemetrie-Sammelbecken • Alle Daten werden in DuckDB gespeichert • Wer ist verbunden?
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 flex-wrap font-mono text-xs">
                  <button
                    onClick={() => setShowModeModal(true)}
                    className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-white font-semibold flex items-center gap-1.5 transition-colors"
                  >
                    <Sliders className="w-3.5 h-3.5 text-amber-400" />
                    <span>Modus ändern</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('chat')}
                    className="px-3 py-1.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700 text-cyan-300 font-semibold flex items-center gap-1.5 transition-colors"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>P2P Chat</span>
                  </button>
                </div>
              </div>

              {/* CARD 1: BETRIEBSSTATUS & PRÄSENZ */}
              <div className={`p-5 rounded-xl border ${cardBg} ${
                multiPcMode === 'host' 
                  ? 'border-amber-500/50 shadow-[0_0_20px_rgba(245,158,11,0.18)]' 
                  : multiPcMode === 'client'
                  ? 'border-blue-500/50 shadow-[0_0_20px_rgba(59,130,246,0.18)]'
                  : 'border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.15)]'
              }`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-zinc-800 gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="text-2xl">
                      {multiPcMode === 'host' ? '👑' : multiPcMode === 'client' ? '🔗' : '🖥️'}
                    </span>
                    <div>
                      <h3 className="font-mono font-bold text-sm tracking-wide text-white flex items-center gap-2 flex-wrap">
                        <span>
                          {multiPcMode === 'host'
                            ? 'SERVER-BETRIEB (MASTER HUB AKTIV)'
                            : multiPcMode === 'client'
                            ? `CLIENT NODE (VERBUNDEN MIT ${clientServerUrl})`
                            : 'STANDALONE MODUS (LOKALER MONITOR)'}
                        </span>
                        <span className={`text-[10px] px-2 py-0.2 rounded font-bold border ${
                          multiPcMode === 'host'
                            ? 'bg-amber-950/80 border-amber-600/70 text-amber-300'
                            : multiPcMode === 'client'
                            ? 'bg-blue-950/80 border-blue-600/70 text-blue-300'
                            : 'bg-cyan-950/80 border-cyan-600/70 text-cyan-300'
                        }`}>
                          {multiPcMode === 'host' ? 'AUSSOHLIESSLICH SERVERSEITIGE SPEICHERUNG' : multiPcMode === 'client' ? 'STREAMT AN SERVER' : 'AUSSOHLIESSLICH LOKALE SPEICHERUNG'}
                        </span>
                      </h3>
                      <p className="text-[11px] font-mono text-zinc-300 mt-0.5">
                        {multiPcMode === 'host'
                          ? 'Im Server-Betrieb erfolgen die Speicherung der Chat-Dateien sowie die Datenbankhaltung ausschließlich serverseitig.'
                          : multiPcMode === 'client'
                          ? `Speicherung der Chat-Dateien sowie die Datenbankhaltung erfolgen ausschließlich serverseitig auf ${clientServerUrl}.`
                          : 'Im Standalone Modus erfolgen die Speicherung der Chat-Dateien sowie die Datenbankhaltung ausschließlich lokal.'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs flex-wrap">
                    <span className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                      PORT: 8350
                    </span>
                    <span className="px-2.5 py-1 rounded bg-amber-950/70 border border-amber-700/60 text-amber-300 font-bold">
                      {connectedNodes.length} RECHNER IM CLUSTER
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 font-mono">
                  <div className="bg-black/40 p-3 rounded-lg border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 uppercase">Speicher-Strategie</span>
                    <div className="text-sm font-bold text-white truncate mt-0.5">
                      {multiPcMode === 'host' ? 'Vault: Server-Dateien' : multiPcMode === 'client' ? 'Vault: Remote Server' : 'Vault: Lokale Dateien'}
                    </div>
                    <span className={`text-[10px] font-semibold ${multiPcMode === 'host' ? 'text-amber-400' : 'text-cyan-400'}`}>
                      {multiPcMode === 'host' ? 'data/server/vault/ (Serverseitig)' : multiPcMode === 'client' ? 'Übertragung an Host' : 'data/local/vault/ (Lokal)'}
                    </span>
                  </div>

                  <div className="bg-black/40 p-3 rounded-lg border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 uppercase">DuckDB Datenbank</span>
                    <div className="text-sm font-bold text-cyan-300 mt-0.5">
                      {multiPcMode === 'host' ? 'no0bz_server.duckdb' : multiPcMode === 'client' ? 'Host DuckDB Stream' : 'no0bz_local.duckdb'}
                    </div>
                    <span className="text-[10px] text-zinc-500">
                      {multiPcMode === 'host' ? 'Serverseitig • 24h Purge' : multiPcMode === 'client' ? 'Wird am Host persistiert' : 'Lokal • 24h Purge'}
                    </span>
                  </div>

                  <div className="bg-black/40 p-3 rounded-lg border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 uppercase">Host CPU &amp; RAM</span>
                    <div className="text-sm font-bold text-amber-300 mt-0.5">{metrics.cpu_load}% • {metrics.ram_percent}%</div>
                    <span className="text-[10px] text-zinc-500">Live-Hardware Telemetrie</span>
                  </div>

                  <div className="bg-black/40 p-3 rounded-lg border border-zinc-800/80">
                    <span className="text-[10px] text-zinc-400 uppercase">Netzwerk Durchsatz</span>
                    <div className="text-sm font-bold text-white mt-0.5">↓ {metrics.net_recv_mbps} • ↑ {metrics.net_sent_mbps}</div>
                    <span className="text-[10px] text-zinc-500">Mbps (WebSocket Live Feed)</span>
                  </div>
                </div>
              </div>

              {/* CARD 2: VERBUNDENE PCs (CLIENTS) */}
              <div className={`p-5 rounded-xl ${cardBg}`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-zinc-800 gap-2">
                  <div className="flex items-center gap-2.5">
                    <Users className="w-5 h-5 text-cyan-400" />
                    <div>
                      <h3 className="font-mono font-bold text-sm tracking-wide text-white">
                        WER IST AUF DEM SERVER VERBUNDEN? ({connectedNodes.length} RECHNER)
                      </h3>
                      <p className="text-[11px] font-mono text-zinc-400">
                        Echtzeit-Telemetrie aller verbundenen Workstations, Laptops und Gaming-Rigs
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="text-zinc-500 text-[11px]">Klicke auf einen PC um dessen Metriken anzuzeigen</span>
                  </div>
                </div>

                {/* Connected Nodes Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {connectedNodes.map((node) => {
                    const isSelected = selectedViewNodeId === node.id || (!selectedViewNodeId && node.is_host);
                    return (
                      <div 
                        key={node.id}
                        className={`p-4 rounded-xl border transition-all flex flex-col justify-between space-y-3 ${
                          node.is_host 
                            ? 'bg-amber-950/20 border-amber-600/50 shadow-[0_0_15px_rgba(245,158,11,0.1)]' 
                            : isSelected
                            ? 'bg-cyan-950/30 border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.15)]'
                            : 'bg-black/50 border-zinc-800/80 hover:border-zinc-700'
                        }`}
                      >
                        {/* Node Card Header */}
                        <div className="flex items-start justify-between border-b border-zinc-800/60 pb-2">
                          <div className="flex items-center gap-2.5">
                            <span className="text-2xl p-1.5 rounded-lg bg-zinc-900 border border-zinc-800">
                              {node.avatar || '💻'}
                            </span>
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="font-mono font-bold text-xs text-white truncate max-w-[150px]">
                                  {node.pc_name}
                                </span>
                                {node.is_host && (
                                  <span className="text-[9px] px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono font-bold">
                                    HOST
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] font-mono text-cyan-400 font-medium">
                                {node.display_name} • <span className="text-zinc-500">{node.role}</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex flex-col items-end text-[10px] font-mono">
                            <span className="flex items-center gap-1 text-emerald-400 font-bold">
                              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                              {node.ping_ms}ms
                            </span>
                            <span className="text-zinc-500">{node.last_seen}</span>
                          </div>
                        </div>

                        {/* Telemetry Progress Bars */}
                        <div className="space-y-2 font-mono text-xs">
                          <div>
                            <div className="flex justify-between text-[11px] text-zinc-400 mb-0.5">
                              <span>CPU LAST</span>
                              <span className="font-bold text-white">{node.cpu_load}%</span>
                            </div>
                            <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-zinc-800">
                              <div 
                                className="bg-gradient-to-r from-cyan-500 to-blue-500 h-full rounded-full transition-all" 
                                style={{ width: `${Math.min(node.cpu_load, 100)}%` }}
                              />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between text-[11px] text-zinc-400 mb-0.5">
                              <span>RAM NUTZUNG</span>
                              <span className="font-bold text-white">{node.ram_percent}%</span>
                            </div>
                            <div className="w-full bg-zinc-900 h-2 rounded-full overflow-hidden border border-zinc-800">
                              <div 
                                className="bg-gradient-to-r from-blue-500 to-purple-500 h-full rounded-full transition-all" 
                                style={{ width: `${Math.min(node.ram_percent, 100)}%` }}
                              />
                            </div>
                          </div>

                          <div className="flex justify-between items-center text-[11px] pt-1 text-zinc-400 border-t border-zinc-800/60">
                            <span>NETZWERK I/O:</span>
                            <span className="font-bold text-white">↓ {node.net_recv_mbps} • ↑ {node.net_sent_mbps} M</span>
                          </div>

                          <div className="text-[10px] text-zinc-500 truncate">
                            IP: {node.ip} • OS: {node.os}
                          </div>
                        </div>

                        {/* Card Action Buttons */}
                        <div className="pt-2 border-t border-zinc-800/60 flex items-center gap-2">
                          <button
                            onClick={() => {
                              setSelectedViewNodeId(node.is_host ? null : node.id);
                              setActiveTab('dashboard');
                            }}
                            className={`flex-1 py-1.5 px-2 rounded-lg text-[11px] font-mono font-bold flex items-center justify-center gap-1.5 transition-all ${
                              isSelected
                                ? 'bg-cyan-500 text-slate-950 shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                                : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                            }`}
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>{isSelected ? 'Aktiv im Dashboard' : 'Im Dashboard anzeigen'}</span>
                          </button>

                          <button
                            onClick={() => {
                              setPromptTitle(`@${node.display_name} `);
                              setActiveTab('chat');
                            }}
                            title={`Chat mit ${node.display_name} starten`}
                            className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
                          >
                            <MessageSquare className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* CARD 3: MULTI-PC VERGLEICHS-MATRIX */}
              <div className={`p-5 rounded-xl ${cardBg}`}>
                <div className="flex items-center gap-2.5 pb-3 mb-3 border-b border-zinc-800">
                  <Layers className="w-5 h-5 text-purple-400" />
                  <div>
                    <h3 className="font-mono font-bold text-sm tracking-wide text-white">
                      MULTI-PC LIVE-VERGLEICHS-MATRIX
                    </h3>
                    <p className="text-[11px] font-mono text-zinc-400">
                      Gegenüberstellung aller Cluster-Nodes in Echtzeit
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left font-mono text-xs">
                    <thead>
                      <tr className="border-b border-zinc-800 text-[10px] text-zinc-500 uppercase">
                        <th className="pb-2">Node / PC-Name</th>
                        <th className="pb-2">Benutzer &amp; Rolle</th>
                        <th className="pb-2">IP &amp; Latenz</th>
                        <th className="pb-2">CPU Last</th>
                        <th className="pb-2">RAM Belegung</th>
                        <th className="pb-2">GPU Last</th>
                        <th className="pb-2">Net RX/TX</th>
                        <th className="pb-2 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {connectedNodes.map((n) => (
                        <tr key={n.id} className="hover:bg-zinc-800/30">
                          <td className="py-2.5 flex items-center gap-2">
                            <span>{n.avatar || '💻'}</span>
                            <span className="font-bold text-white">{n.pc_name}</span>
                            {n.is_host && <span className="text-[8px] px-1 bg-amber-500/20 text-amber-300 rounded font-bold">HOST</span>}
                          </td>
                          <td className="py-2.5 text-cyan-300">{n.display_name} <span className="text-zinc-500">({n.role})</span></td>
                          <td className="py-2.5 text-zinc-400">{n.ip} <span className="text-emerald-400 font-bold">({n.ping_ms}ms)</span></td>
                          <td className="py-2.5 font-bold text-white">{n.cpu_load}%</td>
                          <td className="py-2.5 font-bold text-blue-400">{n.ram_percent}%</td>
                          <td className="py-2.5 font-bold text-purple-400">{n.gpu_load}%</td>
                          <td className="py-2.5 text-zinc-300">↓ {n.net_recv_mbps} / ↑ {n.net_sent_mbps} M</td>
                          <td className="py-2.5 text-right">
                            <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950/80 border border-emerald-600/60 text-emerald-400 font-bold">
                              ONLINE
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 3: P2P PROMPT & CHAT + DRAG & DROP FILE SHARING  */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'chat' && (
            <div className="max-w-5xl mx-auto space-y-4">
              
              {/* Chat Header & Instructions */}
              <div className={`p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${cardBg}`}>
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-lg ${isNightmare ? 'bg-red-950/60 text-red-400' : 'bg-cyan-950/60 text-cyan-400'}`}>
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="font-mono font-bold text-sm tracking-wide text-white">
                      P2P PROMPT &amp; FILE TRANSFER HUB
                    </h2>
                    <p className="text-xs text-zinc-400">
                      Sende ultralange Prompts und bis zu 100 Dateien per Drag &amp; Drop zwischen deinen PCs.
                    </p>
                  </div>
                </div>

                {/* Active Profile Sender Badge */}
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-zinc-400 text-xs">Absender:</span>
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-black/60 border border-zinc-700 text-white">
                    <span className="text-sm">{userProfile.avatar || '💻'}</span>
                    <span className="font-bold text-cyan-300">
                      {userProfile.displayName || userProfile.pcName || metrics.hostname}
                    </span>
                    <span className="text-[10px] text-zinc-500 hidden sm:inline">
                      ({userProfile.pcName || metrics.hostname})
                    </span>
                  </div>
                  <button
                    onClick={() => setActiveTab('settings')}
                    className="p-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-cyan-300 transition-colors"
                    title="Profil in den Einstellungen anpassen"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Messages Feed Area */}
              <div 
                onDragOver={handleChatDragOver}
                onDragLeave={handleChatDragLeave}
                onDrop={handleChatDrop}
                className={`relative min-h-[420px] max-h-[560px] overflow-y-auto p-4 rounded-xl space-y-4 border ${cardBg} ${
                  isDraggingOverChat ? 'border-red-500 bg-red-950/20' : 'border-zinc-800'
                }`}
              >
                {/* Drag Overlay visual indicator */}
                {isDraggingOverChat && (
                  <div className="absolute inset-0 z-20 bg-black/80 backdrop-blur-sm border-2 border-dashed border-red-500 rounded-xl flex flex-col items-center justify-center gap-2 pointer-events-none">
                    <Upload className="w-12 h-12 text-red-400 animate-bounce" />
                    <span className="font-mono font-bold text-sm text-white">
                      DATEIEN HIER ABLEGEN (MAX. 100 DATEIEN)
                    </span>
                    <span className="text-xs text-zinc-400">
                      Bilder erhalten eine sofortige Live-Vorschau im Chat!
                    </span>
                  </div>
                )}

                {/* Chat items */}
                {messages.map((msg) => (
                  <div key={msg.id} className="p-3.5 rounded-lg bg-black/50 border border-zinc-800/80 space-y-2 hover:border-zinc-700 transition-colors">
                    {/* Message Header */}
                    <div className="flex items-center justify-between border-b border-zinc-800/60 pb-2">
                      <div className="flex items-center gap-2 font-mono">
                        <span className={`text-xs font-bold ${msg.sender.includes('A') ? 'text-red-400' : 'text-cyan-400'}`}>
                          {msg.sender}
                        </span>
                        <span className="text-[10px] text-zinc-500">
                          {msg.timestamp}
                        </span>
                        {msg.tokens ? (
                          <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-semibold">
                            ~{msg.tokens} Tokens ({msg.words} Wörter)
                          </span>
                        ) : null}
                      </div>

                      {/* Copy Prompt Button */}
                      {msg.content && (
                        <button
                          onClick={() => handleCopyPrompt(msg.content, msg.id)}
                          className="flex items-center gap-1.5 px-2 py-1 rounded bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 text-xs font-mono transition-all"
                          title="Prompt in Zwischenablage kopieren"
                        >
                          {copiedId === msg.id ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                              <span className="text-emerald-400 font-bold">Kopiert!</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Prompt Kopieren</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>

                    {/* Title */}
                    {msg.title && (
                      <div className="font-mono font-bold text-xs text-zinc-200">
                        {msg.title}
                      </div>
                    )}

                    {/* Main Content (Long Prompt with Code block styling) */}
                    {msg.content && (
                      <div className="font-mono text-xs text-zinc-300 bg-zinc-950/70 p-3 rounded border border-zinc-800/60 whitespace-pre-wrap select-text leading-relaxed">
                        {msg.content}
                      </div>
                    )}

                    {/* Attachments (Images & Files) */}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="space-y-2 pt-1">
                        <div className="text-[10px] font-mono text-zinc-400 font-semibold uppercase">
                          Anhänge ({msg.attachments.length}):
                        </div>
                        
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
                          {msg.attachments.map((att, attIdx) => (
                            <div key={attIdx} className="group relative rounded-lg bg-zinc-900 border border-zinc-800 overflow-hidden flex flex-col justify-between">
                              {/* Image Preview */}
                              {att.is_image ? (
                                <div 
                                  onClick={() => setLightboxImg(att.url || att.data_url || null)}
                                  className="relative h-28 bg-black/60 cursor-pointer overflow-hidden flex items-center justify-center"
                                >
                                  <img 
                                    src={att.url || att.data_url} 
                                    alt={att.name} 
                                    className="w-full h-full object-cover group-hover:scale-105 transition-transform" 
                                  />
                                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
                                    <Eye className="w-5 h-5" />
                                  </div>
                                </div>
                              ) : (
                                <div className="h-20 flex flex-col items-center justify-center p-2 text-zinc-400 bg-zinc-950/60">
                                  <FileText className="w-7 h-7 text-zinc-400 mb-1" />
                                  <span className="text-[10px] font-mono font-bold text-zinc-300">{att.ext}</span>
                                </div>
                              )}

                              {/* File details footer */}
                              <div className="p-2 bg-zinc-900/90 border-t border-zinc-800/60">
                                <div className="text-[11px] font-mono truncate text-white" title={att.name}>
                                  {att.name}
                                </div>
                                <div className="flex items-center justify-between text-[9px] font-mono text-zinc-400 mt-0.5">
                                  <span>{(att.size / 1024).toFixed(1)} KB</span>
                                  <a 
                                    href={att.url} 
                                    download={att.name}
                                    className="text-cyan-400 hover:text-cyan-300 font-bold flex items-center gap-0.5"
                                  >
                                    <Download className="w-2.5 h-2.5" /> DL
                                  </a>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={chatBottomRef} />
              </div>

              {/* Message Composer / File Drop Zone */}
              <div className={`p-4 rounded-xl space-y-3 ${cardBg}`}>
                
                {/* Title Input */}
                <input
                  type="text"
                  placeholder="Prompt-Titel / Notiz (optional, z.B. 'PyTorch Fine-Tuning Instructions')"
                  value={promptTitle}
                  onChange={(e) => setPromptTitle(e.target.value)}
                  className="w-full bg-black/60 border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-red-500"
                />

                {/* Long Prompt Textarea */}
                <textarea
                  rows={4}
                  placeholder="Füge hier deinen langen Prompt, Code, System Instruction oder Text ein (wird 1:1 zwischen deinen PCs synchronisiert)..."
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  className="w-full bg-black/60 border border-zinc-800 rounded-lg p-3 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-red-500 resize-y"
                />

                {/* Queued Files preview chip list */}
                {queuedFiles.length > 0 && (
                  <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 space-y-1.5">
                    <div className="flex justify-between items-center text-xs font-mono text-zinc-400">
                      <span>{queuedFiles.length} Datei(en) bereit zum Senden:</span>
                      <button 
                        onClick={() => setQueuedFiles([])}
                        className="text-red-400 hover:text-red-300 text-[10px] font-bold"
                      >
                        Alle leeren
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                      {queuedFiles.map((f, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-800 text-[11px] font-mono text-zinc-200">
                          <Paperclip className="w-3 h-3 text-zinc-400" />
                          <span className="truncate max-w-[150px]">{f.name}</span>
                          <button 
                            onClick={() => setQueuedFiles(prev => prev.filter((_, idx) => idx !== i))}
                            className="text-zinc-400 hover:text-red-400 ml-0.5"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Bottom Actions */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {/* File Picker input */}
                    <input
                      type="file"
                      ref={fileInputRef}
                      multiple
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono transition-colors"
                    >
                      <Paperclip className="w-4 h-4 text-zinc-400" />
                      <span>Dateien auswählen (bis zu 100)</span>
                    </button>
                    <span className="text-[11px] font-mono text-zinc-500 hidden sm:inline">
                      Oder direkt per Drag &amp; Drop in den Chat ziehen
                    </span>
                  </div>

                  {/* Send Button */}
                  <button
                    onClick={handleSendMessage}
                    disabled={!promptText.trim() && queuedFiles.length === 0}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-bold transition-all ${
                      promptText.trim() || queuedFiles.length > 0
                        ? isNightmare
                          ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)]'
                          : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-[0_0_15px_rgba(6,182,212,0.5)]'
                        : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                    }`}
                  >
                    <Send className="w-4 h-4" />
                    <span>SYNCHRONISIEREN</span>
                  </button>
                </div>
              </div>

            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 3: DATEIBROWSER (CHAT FILE VAULT & MANAGER)       */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'vault' && (
            <div className="max-w-6xl mx-auto space-y-4">
              
              {/* Vault Top Bar */}
              <div className={`p-4 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4 ${cardBg}`}>
                <div>
                  <h2 className="font-mono font-bold text-sm tracking-wide text-white flex items-center gap-2">
                    <Folder className="w-5 h-5 text-amber-400" />
                    <span>ZENTRALER DATEIBROWSER &amp; CHAT VAULT</span>
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Alle über den Chat geteilten Dateien und Bilder übersichtlich organisiert und downloadbar.
                  </p>
                </div>

                {/* Storage Bar Indicator */}
                <div className="flex items-center gap-3 font-mono text-xs">
                  <div className="text-right">
                    <div className="text-zinc-400">Speicherplatz belegt</div>
                    <div className="font-bold text-white">248.5 MB / 10 GB</div>
                  </div>
                  <div className="w-24 bg-zinc-800 h-2 rounded-full overflow-hidden">
                    <div className="bg-amber-400 h-full rounded-full w-[15%]" />
                  </div>
                </div>
              </div>

              {/* Toolbar: Search, Filters, View Modes & Upload Button */}
              <div className={`p-3 rounded-xl flex flex-wrap items-center justify-between gap-3 ${cardBg}`}>
                
                {/* Search & Filter */}
                <div className="flex flex-wrap items-center gap-2 flex-1">
                  <div className="relative min-w-[200px]">
                    <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      placeholder="Dateien durchsuchen..."
                      value={vaultSearch}
                      onChange={(e) => setVaultSearch(e.target.value)}
                      className="w-full bg-black/60 border border-zinc-800 rounded-lg pl-9 pr-3 py-1.5 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-red-500"
                    />
                  </div>

                  <div className="flex items-center rounded-lg bg-black/40 border border-zinc-800 p-0.5 text-xs font-mono">
                    <button
                      onClick={() => setVaultFilter('all')}
                      className={`px-2.5 py-1 rounded ${vaultFilter === 'all' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'}`}
                    >
                      Alle
                    </button>
                    <button
                      onClick={() => setVaultFilter('images')}
                      className={`px-2.5 py-1 rounded ${vaultFilter === 'images' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'}`}
                    >
                      Bilder
                    </button>
                    <button
                      onClick={() => setVaultFilter('code')}
                      className={`px-2.5 py-1 rounded ${vaultFilter === 'code' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'}`}
                    >
                      Code
                    </button>
                    <button
                      onClick={() => setVaultFilter('docs')}
                      className={`px-2.5 py-1 rounded ${vaultFilter === 'docs' ? 'bg-zinc-800 text-white font-bold' : 'text-zinc-400 hover:text-white'}`}
                    >
                      Dokumente
                    </button>
                  </div>
                </div>

                {/* Upload Button & Storage Indicator */}
                <div className="flex items-center gap-3">
                  <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold border ${
                    multiPcMode === 'host'
                      ? 'bg-amber-950/60 border-amber-600 text-amber-300'
                      : multiPcMode === 'local'
                      ? 'bg-cyan-950/60 border-cyan-600 text-cyan-300'
                      : 'bg-blue-950/60 border-blue-600 text-blue-300'
                  }`}>
                    {multiPcMode === 'host' ? '👑 Serverseitig gespeichert' : multiPcMode === 'local' ? '🖥️ Lokal gespeichert' : '🔗 Server Storage'}
                  </span>

                  <input
                    type="file"
                    id="vault-upload"
                    multiple
                    onChange={handleVaultUpload}
                    className="hidden"
                  />
                  <label
                    htmlFor="vault-upload"
                    className={`cursor-pointer px-3 py-1.5 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-all ${
                      isNightmare
                        ? 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_10px_rgba(239,68,68,0.4)]'
                        : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold'
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>DATEIEN HOCHLADEN</span>
                  </label>
                </div>

              </div>

              {/* Files Grid */}
              {allVaultFiles.length === 0 ? (
                <div className="p-12 text-center rounded-xl border border-zinc-800 bg-black/30 font-mono text-zinc-500 space-y-2">
                  <Folder className="w-10 h-10 mx-auto text-zinc-600" />
                  <p className="text-sm">Keine Dateien im Vault gefunden.</p>
                  <p className="text-xs">
                    {multiPcMode === 'host'
                      ? 'Dateien werden im Server-Betrieb ausschließlich serverseitig in data/server/vault/ gespeichert.'
                      : 'Dateien werden im Standalone-Modus ausschließlich lokal in data/local/vault/ gespeichert.'}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {allVaultFiles.map((file, idx) => (
                    <div key={idx} className="group rounded-lg bg-zinc-900/80 border border-zinc-800 overflow-hidden flex flex-col justify-between hover:border-zinc-600 transition-all">
                      {/* Image Preview or File Icon */}
                      {file.is_image ? (
                        <div 
                          onClick={() => setLightboxImg(file.url || file.data_url || null)}
                          className="h-32 bg-black/60 relative cursor-pointer overflow-hidden flex items-center justify-center"
                        >
                          <img 
                            src={file.url || file.data_url} 
                            alt={file.name} 
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform" 
                          />
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
                            <Eye className="w-5 h-5" />
                          </div>
                        </div>
                      ) : (
                        <div className="h-32 flex flex-col items-center justify-center p-3 text-zinc-400 bg-black/40">
                          <FileText className="w-9 h-9 text-zinc-400 mb-1" />
                          <span className="text-xs font-mono font-bold text-zinc-300">{file.ext}</span>
                        </div>
                      )}

                      {/* File Card Info */}
                      <div className="p-2.5 border-t border-zinc-800 bg-zinc-950/60 space-y-1">
                        <div className="font-mono text-xs text-white truncate font-medium" title={file.name}>
                          {file.name}
                        </div>
                        <div className="flex justify-between items-center text-[10px] font-mono text-zinc-500">
                          <span>{(file.size / 1024).toFixed(1)} KB</span>
                          <span className="truncate max-w-[80px]">{file.sender.split(' ')[0]}</span>
                        </div>

                        {/* Action buttons */}
                        <div className="pt-1.5 flex items-center justify-between border-t border-zinc-800/60">
                          <a
                            href={file.url}
                            download={file.name}
                            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" /> Download
                          </a>
                          <button
                            onClick={() => handleDeleteVaultFile(file.name)}
                            className="text-zinc-500 hover:text-red-400 text-xs transition-colors p-1"
                            title="Aus Vault löschen"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 4: PROZESS MANAGER (TASK MANAGER)               */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'processes' && (
            <div className="max-w-6xl mx-auto space-y-4">
              <div className={`p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${cardBg}`}>
                <div>
                  <h2 className="font-mono font-bold text-sm tracking-wide text-white flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-purple-400" />
                    <span>LIVE TASK MANAGER &amp; PROCESS CONTROL</span>
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Echtzeit-Prozessliste mit Lastüberwachung und sofortiger Prozess-Terminierung
                  </p>
                </div>

                <div className="relative w-full sm:w-64">
                  <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="Prozess oder PID filtern..."
                    value={procSearch}
                    onChange={(e) => setProcSearch(e.target.value)}
                    className="w-full bg-black/60 border border-zinc-800 rounded-lg pl-9 pr-3 py-1.5 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-red-500"
                  />
                </div>
              </div>

              {/* Process Table */}
              <div className={`rounded-xl overflow-hidden border border-zinc-800 ${cardBg}`}>
                <div className="overflow-x-auto">
                  <table className="w-full text-left font-mono text-xs">
                    <thead className="bg-black/60 text-zinc-400 border-b border-zinc-800 uppercase text-[10px] tracking-wider">
                      <tr>
                        <th className="p-3">PID</th>
                        <th className="p-3">PROZESSNAME</th>
                        <th className="p-3">CPU LAST (%)</th>
                        <th className="p-3">RAM BELEGUNG (%)</th>
                        <th className="p-3">STATUS</th>
                        <th className="p-3 text-right">AKTION</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {filteredProcesses.map((p) => (
                        <tr key={p.pid} className="hover:bg-zinc-800/30 transition-colors">
                          <td className="p-3 text-zinc-400">{p.pid}</td>
                          <td className="p-3 font-semibold text-white">{p.name}</td>
                          <td className="p-3">
                            <span className={`px-2 py-0.5 rounded font-bold ${
                              p.cpu > 20 ? 'bg-red-950 text-red-400' : 'bg-zinc-800 text-zinc-300'
                            }`}>
                              {p.cpu}%
                            </span>
                          </td>
                          <td className="p-3 text-zinc-300">{p.ram}%</td>
                          <td className="p-3">
                            <span className="text-emerald-400 flex items-center gap-1 text-[11px]">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              {p.status}
                            </span>
                          </td>
                          <td className="p-3 text-right">
                            <button
                              onClick={() => handleKill(p.pid)}
                              disabled={killPid === p.pid}
                              className="px-2.5 py-1 rounded bg-red-950/60 hover:bg-red-900 border border-red-800/80 text-red-300 font-bold text-[11px] transition-all flex items-center gap-1 ml-auto"
                            >
                              <Trash2 className="w-3 h-3" />
                              <span>{killPid === p.pid ? 'Beende...' : 'KILL'}</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 5: HISTORIE (DUCKDB 24H ZEITREIHEN-ANALYSE)     */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'history' && (
            <div className="max-w-6xl mx-auto space-y-4">
              <div className={`p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${cardBg}`}>
                <div>
                  <h2 className="font-mono font-bold text-sm tracking-wide text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-cyan-400" />
                    <span>DUCKDB 24-STUNDEN ZEITREIHEN-TELEMETRIE</span>
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Sekündliche Hardware-Aufzeichnung mit automatischer 24h DuckDB-Archivierung
                  </p>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono">
                  <div className="flex items-center gap-1.5 text-red-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> CPU (%)
                  </div>
                  <div className="flex items-center gap-1.5 text-blue-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-500" /> RAM (%)
                  </div>
                  <div className="flex items-center gap-1.5 text-purple-400">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-500" /> GPU (%)
                  </div>
                </div>
              </div>

              {/* Canvas Area */}
              <div className={`p-4 rounded-xl ${cardBg}`}>
                <canvas 
                  ref={canvasRef} 
                  width={1000} 
                  height={340} 
                  className="w-full h-80 bg-black/60 rounded-lg border border-zinc-800"
                />
                <div className="mt-2 flex justify-between text-[11px] font-mono text-zinc-500">
                  <span>-60 SEKUNDEN</span>
                  <span>LIVE DUCKDB LOGGING (1-SEKUNDEN TAKT)</span>
                  <span>JETZT</span>
                </div>
              </div>
            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 6: EINSTELLUNGEN (SETTINGS MIT PLATZHALTER-OPTIONEN) */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'settings' && (
            <div className="max-w-4xl mx-auto space-y-6">
              
              <div className={`p-4 rounded-xl ${cardBg}`}>
                <h2 className="font-mono font-bold text-base text-white flex items-center gap-2">
                  <Settings className="w-5 h-5 text-zinc-400" />
                  <span>SYSTEM-, PROFIL- &amp; NCC-EINSTELLUNGEN</span>
                </h2>
                <p className="text-xs text-zinc-400 mt-1">
                  Passe dein Benutzerprofil, den Multi-PC Modus, Fast-Boot System-Cache und Hardware-Sensoren an.
                </p>
              </div>

              {/* Section 0: BENUTZER- & PC-PROFIL ANPASSEN (USER REQUEST) */}
              <div className={`p-5 rounded-xl space-y-4 border ${cardBg} border-cyan-500/30`}>
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-cyan-400" />
                    <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-cyan-400">
                      BENUTZER- &amp; PC-PROFIL ANPASSEN (FÜR CHAT &amp; SERVER)
                    </h3>
                  </div>
                  {profileSavedToast && (
                    <span className="text-[10px] font-mono text-emerald-400 font-bold flex items-center gap-1">
                      <Check className="w-3.5 h-3.5" /> Gespeichert &amp; Synchronisiert!
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  {/* PC-Name (Hostname) */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                      <label className="text-zinc-300 font-semibold">PC-Name (Standard-Absender im Chat)</label>
                      <button 
                        type="button"
                        onClick={() => setUserProfile({ ...userProfile, pcName: metrics.hostname })}
                        className="text-[10px] text-cyan-400 hover:underline cursor-pointer"
                      >
                        Auf Hardware-Name zurücksetzen
                      </button>
                    </div>
                    <input
                      type="text"
                      value={userProfile.pcName}
                      onChange={(e) => setUserProfile({ ...userProfile, pcName: e.target.value })}
                      placeholder="z.B. WORKSTATION-A"
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2.5 text-white font-bold focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-zinc-500">Wird im Server-Cluster und im Chat als Rechner-Kennung genutzt</span>
                  </div>

                  {/* Display Name / Benutzername */}
                  <div className="space-y-1.5">
                    <label className="text-zinc-300 font-semibold">Benutzername / Alias (Optional)</label>
                    <input
                      type="text"
                      value={userProfile.displayName}
                      onChange={(e) => setUserProfile({ ...userProfile, displayName: e.target.value })}
                      placeholder="z.B. Bruno oder Alex"
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2.5 text-white font-bold focus:outline-none focus:border-cyan-500"
                    />
                    <span className="text-[10px] text-zinc-500">Wird im Chat und in der Multi-PC Übersicht angezeigt</span>
                  </div>

                  {/* Callsign / Role */}
                  <div className="space-y-1.5">
                    <label className="text-zinc-300 font-semibold">Rolle / Rechner-Zweck</label>
                    <input
                      type="text"
                      value={userProfile.role}
                      onChange={(e) => setUserProfile({ ...userProfile, role: e.target.value })}
                      placeholder="z.B. Lead Workstation, Gaming-Rig, Linux Dev"
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Status Message */}
                  <div className="space-y-1.5">
                    <label className="text-zinc-300 font-semibold">Status-Meldung / Bio</label>
                    <input
                      type="text"
                      value={userProfile.statusMsg}
                      onChange={(e) => setUserProfile({ ...userProfile, statusMsg: e.target.value })}
                      placeholder="z.B. Online • Bereit für CUDA P2P"
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2.5 text-white focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>

                {/* Avatar Picker */}
                <div className="space-y-1.5 pt-2">
                  <label className="text-zinc-300 font-mono text-xs font-semibold">Avatar Icon wählen</label>
                  <div className="flex items-center gap-2 flex-wrap">
                    {['💻', '🖥️', '⚡', '🚀', '🛡️', '👾', '👑', '🎯', '🧠', '🎮'].map((icon) => (
                      <button
                        key={icon}
                        type="button"
                        onClick={() => setUserProfile({ ...userProfile, avatar: icon })}
                        className={`text-xl p-2 rounded-lg border transition-all ${
                          userProfile.avatar === icon 
                            ? 'bg-cyan-500/20 border-cyan-400 scale-110 shadow-[0_0_10px_rgba(6,182,212,0.4)]' 
                            : 'bg-black/50 border-zinc-800 hover:border-zinc-700'
                        }`}
                      >
                        {icon}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Profile Live Preview & Save Button */}
                <div className="pt-3 border-t border-zinc-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 font-mono text-xs">
                    <span className="text-zinc-500 text-[11px]">Chat-Vorschau:</span>
                    <div className="px-3 py-1.5 rounded-lg bg-black/60 border border-zinc-700 flex items-center gap-2">
                      <span className="text-lg">{userProfile.avatar}</span>
                      <span className="font-bold text-white">{userProfile.displayName || userProfile.pcName || metrics.hostname}</span>
                      <span className="text-[10px] text-cyan-400 font-semibold">({userProfile.pcName || metrics.hostname})</span>
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400">{userProfile.role}</span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      localStorage.setItem('no0bz_user_profile', JSON.stringify(userProfile));
                      setProfileSavedToast(true);
                      setTimeout(() => setProfileSavedToast(false), 2500);
                      // Sync to backend if available
                      fetch('/api/profile', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(userProfile)
                      }).catch(() => {});
                    }}
                    className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs shadow-[0_0_12px_rgba(6,182,212,0.4)] flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Profil speichern &amp; anwenden</span>
                  </button>
                </div>
              </div>

              {/* Section: FAST-BOOT HARDWARE-CACHE (ncc_system_cache.json) */}
              <div className={`p-5 rounded-xl space-y-4 border ${cardBg} border-amber-500/30`}>
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-400" />
                    <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-amber-400">
                      FAST-BOOT SYSTEM-CACHE (ncc_system_cache.json)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-600 text-emerald-400 font-bold">
                    FAST-BOOT AKTIV (&lt; 1ms)
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="bg-black/50 p-2.5 rounded-lg border border-zinc-800">
                    <span className="text-zinc-500 text-[10px]">CACHE-DATEI</span>
                    <div className="font-bold text-white mt-0.5 truncate">ncc_system_cache.json</div>
                    <span className="text-zinc-400 text-[10px]">Im Hauptverzeichnis</span>
                  </div>

                  <div className="bg-black/50 p-2.5 rounded-lg border border-zinc-800">
                    <span className="text-zinc-500 text-[10px]">STATUS</span>
                    <div className="font-bold text-emerald-400 mt-0.5">Geladen (0.4ms)</div>
                    <span className="text-zinc-400 text-[10px]">Kein Hardware-Probing nötig</span>
                  </div>

                  <div className="bg-black/50 p-2.5 rounded-lg border border-zinc-800">
                    <span className="text-zinc-500 text-[10px]">ERFASSTE HARDWARE</span>
                    <div className="font-bold text-cyan-300 mt-0.5">CPU, RAM, GPU, Disks, NIC</div>
                    <span className="text-zinc-400 text-[10px]">{systemCache?.generated_at || 'Automatisch erfasst'}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <p className="text-[11px] font-mono text-zinc-400">
                    Bei Hardware-Upgrades oder neuen Festplatten kannst du den Cache hier manuell erneuern.
                  </p>
                  <button
                    type="button"
                    disabled={cacheRefreshing}
                    onClick={async () => {
                      setCacheRefreshing(true);
                      try {
                        const res = await fetch('/api/system/profile/refresh', { method: 'POST' });
                        const data = await res.json();
                        setSystemCache(data);
                      } catch {}
                      setTimeout(() => setCacheRefreshing(false), 800);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-amber-300 font-mono text-xs font-semibold flex items-center gap-1.5 transition-colors border border-zinc-700"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${cacheRefreshing ? 'animate-spin text-amber-400' : ''}`} />
                    <span>{cacheRefreshing ? 'Erneuere...' : 'Cache aktualisieren'}</span>
                  </button>
                </div>
              </div>

              {/* Section: MULTI-PC NETZWERK- & SERVER-MODUS */}
              <div className={`p-5 rounded-xl space-y-4 ${cardBg}`}>
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-purple-400" />
                    <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-purple-400">
                      MULTI-PC BETRIEBSMODUS &amp; SERVER-KONFIGURATION
                    </h3>
                  </div>
                  <button
                    onClick={() => setShowModeModal(true)}
                    className="text-xs font-mono px-2.5 py-1 rounded bg-purple-950/70 hover:bg-purple-900 border border-purple-600 text-purple-300 font-bold transition-colors"
                  >
                    Modus wechseln...
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                  <div className={`p-3 rounded-lg border ${multiPcMode === 'local' ? 'border-cyan-500 bg-cyan-950/20' : 'border-zinc-800 bg-black/40'}`}>
                    <div className="font-bold text-white">🖥️ Lokal Standalone</div>
                    <p className="text-[11px] text-zinc-400 mt-1">Nur diesen PC überwachen. Keine Freigabe im Netzwerk.</p>
                  </div>

                  <div className={`p-3 rounded-lg border ${multiPcMode === 'host' ? 'border-amber-500 bg-amber-950/20' : 'border-zinc-800 bg-black/40'}`}>
                    <div className="font-bold text-amber-300">👑 Server Hosten (Hub)</div>
                    <p className="text-[11px] text-zinc-400 mt-1">Speichert alle Telemetriedaten in DuckDB. Zeigt verbundene PCs.</p>
                  </div>

                  <div className={`p-3 rounded-lg border ${multiPcMode === 'client' ? 'border-blue-500 bg-blue-950/20' : 'border-zinc-800 bg-black/40'}`}>
                    <div className="font-bold text-blue-300">🔗 Auf Server verbinden</div>
                    <p className="text-[11px] text-zinc-400 mt-1">Streamt Live-Metriken an den Server: {clientServerUrl}</p>
                  </div>
                </div>
              </div>

              {/* Section 1: Allgemein & Telemetrie */}
              <div className={`p-5 rounded-xl space-y-4 ${cardBg}`}>
                <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-cyan-400 border-b border-zinc-800 pb-2">
                  1. ALLGEMEIN &amp; TELEMETRIE-INTERVALLE
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-1.5">
                    <label className="text-zinc-300">Telemetrie-Aktualisierungsrate</label>
                    <select
                      value={settings.pollingInterval}
                      onChange={(e) => setSettings({ ...settings, pollingInterval: e.target.value })}
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2 text-white focus:outline-none focus:border-red-500"
                    >
                      <option value="0.5s">0.5 Sekunden (High-Precision Gaming)</option>
                      <option value="1.0s">1.0 Sekunde (Standard / Empfohlen)</option>
                      <option value="2.0s">2.0 Sekunden (Energiesparend)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-zinc-300">P2P WebSocket Server Port</label>
                    <input
                      type="number"
                      value={settings.p2pPort}
                      onChange={(e) => setSettings({ ...settings, p2pPort: parseInt(e.target.value) || 8350 })}
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2 text-white focus:outline-none focus:border-red-500"
                    />
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-4 pt-2">
                  <label className="flex items-center gap-2 text-xs font-mono text-zinc-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.autostart}
                      onChange={(e) => setSettings({ ...settings, autostart: e.target.checked })}
                      className="rounded bg-black border-zinc-700 text-red-600 focus:ring-0"
                    />
                    <span>Mit Windows / Linux Systemd automatisch im Hintergrund starten</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs font-mono text-zinc-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.minimizeToTray}
                      onChange={(e) => setSettings({ ...settings, minimizeToTray: e.target.checked })}
                      className="rounded bg-black border-zinc-700 text-red-600 focus:ring-0"
                    />
                    <span>Beim Schließen in System-Tray minimieren</span>
                  </label>
                </div>
              </div>

              {/* Section 2: Hardware-Sensoren & LHM */}
              <div className={`p-5 rounded-xl space-y-4 ${cardBg}`}>
                <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-purple-400 border-b border-zinc-800 pb-2">
                  2. HARDWARE-SENSOREN &amp; LIBREHARDWAREMONITOR
                </h3>

                <div className="space-y-3 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-zinc-200 font-semibold">LibreHardwareMonitor REST-Fallback</div>
                      <div className="text-[11px] text-zinc-500">Liest Mainboard-Lüfter (RPM) und CPU-Package Power über lokalen Port 8085</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={settings.lhmFallback}
                      onChange={(e) => setSettings({ ...settings, lhmFallback: e.target.checked })}
                      className="rounded bg-black border-zinc-700 text-red-600 focus:ring-0"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-zinc-400">LHM REST URL</label>
                    <input
                      type="text"
                      value={settings.lhmUrl}
                      onChange={(e) => setSettings({ ...settings, lhmUrl: e.target.value })}
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2 text-white text-xs font-mono focus:outline-none focus:border-red-500"
                    />
                  </div>
                </div>
              </div>

              {/* Section 3: Alarme & Schwellenwerte */}
              <div className={`p-5 rounded-xl space-y-4 ${cardBg}`}>
                <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-amber-400 border-b border-zinc-800 pb-2">
                  3. TEMPERATUR- &amp; SICHERHEITS-ALARME
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-1.5">
                    <label className="text-zinc-300">CPU Temperatur-Warnschwelle (°C)</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min={70}
                        max={95}
                        value={settings.cpuAlertTemp}
                        onChange={(e) => setSettings({ ...settings, cpuAlertTemp: parseInt(e.target.value) })}
                        className="flex-1 accent-red-500"
                      />
                      <span className="font-bold text-white w-12">{settings.cpuAlertTemp}°C</span>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-zinc-300">GPU Temperatur-Warnschwelle (°C)</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min={65}
                        max={90}
                        value={settings.gpuAlertTemp}
                        onChange={(e) => setSettings({ ...settings, gpuAlertTemp: parseInt(e.target.value) })}
                        className="flex-1 accent-red-500"
                      />
                      <span className="font-bold text-white w-12">{settings.gpuAlertTemp}°C</span>
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <label className="flex items-center gap-2 text-xs font-mono text-zinc-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={settings.audioAlert}
                      onChange={(e) => setSettings({ ...settings, audioAlert: e.target.checked })}
                      className="rounded bg-black border-zinc-700 text-red-600 focus:ring-0"
                    />
                    <span>Akustischen System-Alarm bei Drosselung / Thermal Throttling abspielen</span>
                  </label>
                </div>
              </div>

              {/* Section 4: Chat & Vault Speicher */}
              <div className={`p-5 rounded-xl space-y-4 ${cardBg}`}>
                <h3 className="font-mono font-bold text-xs uppercase tracking-wider text-emerald-400 border-b border-zinc-800 pb-2">
                  4. CHAT-VAULT &amp; DUCKDB TIME-SERIES DATENBANK
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-1.5">
                    <label className="text-zinc-300">Maximaler Dateicache für Chat-Uploads</label>
                    <select
                      value={settings.maxVaultCacheGB}
                      onChange={(e) => setSettings({ ...settings, maxVaultCacheGB: parseInt(e.target.value) })}
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2 text-white focus:outline-none focus:border-red-500"
                    >
                      <option value={5}>5 GB</option>
                      <option value={10}>10 GB (Empfohlen)</option>
                      <option value={50}>50 GB (High Storage)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-zinc-300">DuckDB Auto-Purge Zeitfenster</label>
                    <select
                      value={settings.autoPurgeDuckDBHours}
                      onChange={(e) => setSettings({ ...settings, autoPurgeDuckDBHours: parseInt(e.target.value) })}
                      className="w-full bg-black/60 border border-zinc-700 rounded-lg p-2 text-white focus:outline-none focus:border-red-500"
                    >
                      <option value={12}>12 Stunden</option>
                      <option value={24}>24 Stunden (Standard)</option>
                      <option value={48}>48 Stunden</option>
                      <option value={168}>7 Tage</option>
                    </select>
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <button
                    onClick={() => alert('Einstellungen wurden erfolgreich gespeichert!')}
                    className={`px-4 py-2 rounded-lg text-xs font-mono font-bold ${
                      isNightmare ? 'bg-red-600 hover:bg-red-500 text-white' : 'bg-cyan-500 text-slate-950'
                    }`}
                  >
                    EINSTELLUNGEN SPEICHERN
                  </button>
                </div>
              </div>

            </div>
          )}

          {/* ---------------------------------------------------- */}
          {/* TAB 7: CHANGELOG (VERSIONSHISTORIE & RELEASE NOTES)  */}
          {/* ---------------------------------------------------- */}
          {activeTab === 'changelog' && (
            <div className="max-w-5xl mx-auto space-y-6">
              
              {/* Header Box */}
              <div className={`p-5 rounded-xl ${cardBg} flex flex-col md:flex-row items-start md:items-center justify-between gap-4`}>
                <div>
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-lg bg-cyan-950/80 border border-cyan-500/50 text-cyan-400">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <h2 className="font-mono font-bold text-lg text-white flex items-center gap-2">
                        <span>no0bz COMMAND CENTER // CHANGELOG</span>
                        <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 font-bold">
                          v3.8.2
                        </span>
                      </h2>
                      <p className="text-xs text-zinc-400 mt-0.5 font-mono">
                        Vollständige Versionshistorie, Release-Notes und Feature-Übersicht für GitHub &amp; NCC.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Header Action Buttons */}
                <div className="flex items-center gap-2 flex-wrap font-mono text-xs">
                  {/* Toggle Raw Markdown vs Cards */}
                  <button
                    onClick={() => setChangelogRaw(!changelogRaw)}
                    className={`px-3 py-1.5 rounded-lg border font-semibold flex items-center gap-1.5 transition-all ${
                      changelogRaw 
                        ? 'bg-purple-950/80 border-purple-500 text-purple-300 shadow-[0_0_10px_rgba(168,85,247,0.3)]' 
                        : 'bg-zinc-900 hover:bg-zinc-800 border-zinc-700 text-zinc-300'
                    }`}
                  >
                    <Terminal className="w-3.5 h-3.5" />
                    <span>{changelogRaw ? 'Karten-Ansicht' : 'GitHub Raw (.md)'}</span>
                  </button>

                  {/* Copy Markdown */}
                  <button
                    onClick={() => {
                      const textToCopy = changelogMd || `# 📜 no0bz Command Center (NCC) – Changelog\n\nVersion v3.7.0 (2026-09-25)\n- Standalone React Dashboard in main.py\n- Dynamische WebSocket-Verbindung\n- Integrierter Changelog-Viewer im NCC & GitHub\n- nvidia-ml-py Priorisierung`;
                      navigator.clipboard.writeText(textToCopy);
                      setCopiedChangelog(true);
                      setTimeout(() => setCopiedChangelog(false), 2000);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-300 hover:text-white font-semibold flex items-center gap-1.5 transition-all"
                  >
                    {copiedChangelog ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedChangelog ? 'Kopiert!' : 'Kopieren'}</span>
                  </button>

                  {/* Open /changelog standalone route */}
                  <a
                    href="/changelog"
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 rounded-lg bg-cyan-950/50 hover:bg-cyan-900/60 border border-cyan-700/60 text-cyan-300 font-semibold flex items-center gap-1.5 transition-all"
                    title="Als eigenständige HTML-Seite öffnen"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                    <span>HTML-Ansicht</span>
                  </a>
                </div>
              </div>

              {/* Search & Filter Bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="relative w-full sm:w-80">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    placeholder="Changelog durchsuchen (z. B. WebSocket, NVIDIA, Chat)..."
                    value={changelogSearch}
                    onChange={(e) => setChangelogSearch(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-black/60 border border-zinc-800 focus:border-cyan-500 rounded-lg text-xs font-mono text-white placeholder-zinc-500 focus:outline-none transition-all"
                  />
                  {changelogSearch && (
                    <button
                      onClick={() => setChangelogSearch('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto font-mono text-[11px] pb-1 sm:pb-0">
                  <span className="text-zinc-500 uppercase font-bold text-[10px]">Filter:</span>
                  {['Alle', 'v3.8.2', 'v3.8.1', 'v3.7.0', 'v3.6.3', 'v3.5.0', 'v3.1.0'].map(ver => (
                    <button
                      key={ver}
                      onClick={() => setChangelogSearch(ver === 'Alle' ? '' : ver)}
                      className={`px-2.5 py-1 rounded-md border transition-all ${
                        (ver === 'Alle' && !changelogSearch) || changelogSearch === ver
                          ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 font-bold'
                          : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white'
                      }`}
                    >
                      {ver}
                    </button>
                  ))}
                </div>
              </div>

              {/* RAW MARKDOWN VIEW */}
              {changelogRaw ? (
                <div className={`p-5 rounded-xl ${cardBg} font-mono text-xs`}>
                  <div className="flex items-center justify-between pb-3 border-b border-zinc-800 text-zinc-400">
                    <span className="font-bold flex items-center gap-2 text-white">
                      <File className="w-4 h-4 text-purple-400" />
                      CHANGELOG.md (GitHub Datei)
                    </span>
                    <span className="text-[10px] text-zinc-500">Root Directory</span>
                  </div>
                  <pre className="mt-4 p-4 rounded-lg bg-black/80 border border-zinc-800 text-zinc-300 text-[11px] font-mono whitespace-pre-wrap overflow-x-auto leading-relaxed max-h-[65vh] select-text">
                    {changelogMd || `# 📜 no0bz Command Center (NCC) – Changelog\n\nAlle wichtigen Änderungen, neuen Funktionen und Optimierungen für das **no0bz Command Center (NCC)** werden in dieser Datei chronologisch dokumentiert.\n\nDas Format basiert auf Keep a Changelog und dieses Projekt hält sich an Semantic Versioning.\n\n---\n\n## [v3.8.2] - 2026-09-26\n\n### 🚀 Neu & Hervorgehoben\n- Exklusive serverseitige Speicherung der Chat-Dateien & DuckDB im Server-Betrieb\n- Autarker Standalone-Modus mit lokaler Haltung\n- Voll funktionstüchtig ohne Platzhalter`}
                  </pre>
                </div>
              ) : (
                /* INTERACTIVE CARDS VIEW */
                <div className="space-y-5 font-mono">
                  
                  {/* RELEASE: v3.8.2 */}
                  {(!changelogSearch || 'v3.8.2 3.8.2 server standalone duckdb vault chat speicherung host'.toLowerCase().includes(changelogSearch.toLowerCase())) && (
                    <div className={`p-5 rounded-xl border relative overflow-hidden transition-all ${
                      isNightmare 
                        ? 'bg-zinc-950/90 border-amber-500/50 shadow-[0_0_25px_rgba(245,158,11,0.2)]' 
                        : 'bg-slate-900/90 border-amber-500/50 shadow-[0_0_25px_rgba(245,158,11,0.2)]'
                    }`}>
                      <div className="absolute top-0 right-0 transform translate-x-3 -translate-y-3 w-32 h-32 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />

                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-zinc-800">
                        <div className="flex items-center gap-3">
                          <span className="text-xl font-black text-amber-400">v3.8.2</span>
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-slate-950 shadow-[0_0_10px_rgba(245,158,11,0.6)] animate-pulse">
                            AKTUELLES RELEASE
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-zinc-400">
                          <Clock className="w-3.5 h-3.5 text-zinc-500" />
                          <span>26. September 2026</span>
                        </div>
                      </div>

                      <div className="mt-4 space-y-4 text-xs">
                        <div>
                          <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400 mb-2 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>🚀 Exklusive serverseitige Speicherung &amp; Standalone-Architektur</span>
                          </div>
                          <ul className="space-y-2 text-zinc-300">
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-amber-950 text-amber-300 border border-amber-700/60 text-[9px] font-bold mt-0.5">SERVER-BETRIEB</span>
                              <div>
                                <strong className="text-white">Ausschließlich serverseitige Datenhaltung:</strong> Im Server-Betrieb (Host) erfolgen die Speicherung der Chat-Dateien (<code className="text-amber-300 bg-black/60 px-1 py-0.5 rounded">data/server/vault/</code>) sowie die DuckDB-Datenbankhaltung (<code className="text-amber-300 bg-black/60 px-1 py-0.5 rounded">no0bz_server.duckdb</code>) ausschließlich serverseitig.
                              </div>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/60 text-[9px] font-bold mt-0.5">STANDALONE</span>
                              <div>
                                <strong className="text-white">Autarker Standalone-Modus (Lokal):</strong> Im Standalone-Modus erfolgen Speicherung und Datenbankverwaltung ausschließlich lokal (<code className="text-cyan-300 bg-black/60 px-1 py-0.5 rounded">data/local/vault/</code> &amp; <code className="text-cyan-300 bg-black/60 px-1 py-0.5 rounded">no0bz_local.duckdb</code>).
                              </div>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-blue-950 text-blue-300 border border-blue-700/60 text-[9px] font-bold mt-0.5">CLIENT-NODE</span>
                              <div>
                                <strong className="text-white">Client Node Modus:</strong> Überträgt Telemetrie und Chat-Dateien direkt an den Master-Server ohne lokalen Speicheroverhead.
                              </div>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-300 border border-emerald-700/60 text-[9px] font-bold mt-0.5">PERSISTENZ</span>
                              <div>
                                <strong className="text-white">Dauerhafte Konfiguration (`ncc_config.json`):</strong> Speichert den gewählten Betriebsmodus und die Server-URL dauerhaft im System.
                              </div>
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* RELEASE: v3.7.0 */}
                  {(!changelogSearch || 'v3.7.0 3.7.0 standalone react bundle websocket host changelog dist nvidia'.toLowerCase().includes(changelogSearch.toLowerCase())) && (
                    <div className={`p-5 rounded-xl border relative overflow-hidden transition-all ${
                      isNightmare 
                        ? 'bg-zinc-950/90 border-zinc-800' 
                        : 'bg-slate-900/90 border-zinc-800'
                    }`}>
                      <div className="absolute top-0 right-0 transform translate-x-3 -translate-y-3 w-32 h-32 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />

                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-zinc-800">
                        <div className="flex items-center gap-3">
                          <span className="text-xl font-black text-white">v3.7.0</span>
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500 text-slate-950 shadow-[0_0_10px_rgba(6,182,212,0.6)] animate-pulse">
                            AKTUELLES RELEASE
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-zinc-400">
                          <Clock className="w-3.5 h-3.5 text-zinc-500" />
                          <span>25. September 2026</span>
                        </div>
                      </div>

                      <div className="mt-4 space-y-4 text-xs">
                        {/* Section: Neu */}
                        <div>
                          <div className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 mb-2 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>🚀 Neu &amp; Hervorgehoben</span>
                          </div>
                          <ul className="space-y-2 text-zinc-300">
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/60 text-[9px] font-bold mt-0.5">NEU</span>
                              <div>
                                <strong className="text-white">Integrierter Changelog-Viewer im NCC:</strong> Vollständige Versionshistorie direkt über das Seitenmenü, den Header-Button oder per Klick auf das Versions-Badge im Command Center einsehbar.
                              </div>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/60 text-[9px] font-bold mt-0.5">SINGLE-FILE</span>
                              <div>
                                <strong className="text-white">Vollständig autarkes React-Bundle in `main.py`:</strong> Das exakte, identische React-Frontend ist vorkompiliert und direkt in die Python-Datei integriert. `python main.py` startet sofort mit der vollen Cyber-Oberfläche ohne vorheriges `npm run build`.
                              </div>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/60 text-[9px] font-bold mt-0.5">NETZWERK</span>
                              <div>
                                <strong className="text-white">Dynamische WebSocket-Host-Erkennung:</strong> Automatische Verbindung über die aktuelle URL (`window.location.host`), wodurch NCC problemlos über lokale IP-Adressen (z. B. `192.168.x.x:8350`) oder Custom Ports aufgerufen werden kann.
                              </div>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-700/60 text-[9px] font-bold mt-0.5">API</span>
                              <div>
                                <strong className="text-white">Neue Backend-Endpunkte:</strong> <code className="text-cyan-300 bg-black/60 px-1 py-0.5 rounded">/api/changelog</code> (JSON-Daten) und <code className="text-cyan-300 bg-black/60 px-1 py-0.5 rounded">/changelog</code> (Eigenständige HTML-Seite).
                              </div>
                            </li>
                          </ul>
                        </div>

                        {/* Section: Optimierungen */}
                        <div>
                          <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 mb-2 flex items-center gap-1.5">
                            <Zap className="w-3.5 h-3.5" />
                            <span>⚡ Optimierungen &amp; Bereinigungen</span>
                          </div>
                          <ul className="space-y-1.5 text-zinc-300">
                            <li className="flex items-start gap-2">
                              <span className="text-emerald-400">✓</span>
                              <span><strong>NVIDIA Modernisierung:</strong> Bevorzugt primär das offizielle <code className="text-zinc-200">nvidia-ml-py</code> Paket zur Beseitigung veralteter Deprecation-Warnungen.</span>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="text-emerald-400">✓</span>
                              <span><strong>Vorkompilierter <code className="text-zinc-200">dist/</code>-Ordner:</strong> Liegt jetzt direkt im Repository vor, sodass auch frische Git-Klone sofort die gebaute Web-UI haben.</span>
                            </li>
                            <li className="flex items-start gap-2">
                              <span className="text-emerald-400">✓</span>
                              <span><strong>start_ncc.bat:</strong> Aktualisiert auf v3.7.0 mit automatischem Start des Standardbrowsers auf Port 8350.</span>
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* RELEASE: v3.6.3 */}
                  {(!changelogSearch || 'v3.6.3 3.6.3 chat vault dateibrowser duckdb prozess kill bento themes'.toLowerCase().includes(changelogSearch.toLowerCase())) && (
                    <div className={`p-5 rounded-xl border ${cardBg} transition-all`}>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-zinc-800">
                        <div className="flex items-center gap-3">
                          <span className="text-lg font-black text-white">v3.6.3</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
                            MAJOR UPDATE
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          <Clock className="w-3.5 h-3.5" />
                          <span>18. September 2026</span>
                        </div>
                      </div>

                      <div className="mt-4 space-y-3 text-xs text-zinc-300">
                        <div className="flex items-start gap-2">
                          <span className="text-cyan-400 font-bold">•</span>
                          <div><strong>P2P Chat &amp; Prompt Sync Hub:</strong> Lokaler Echtzeit-Chat mit Dateiübertragung zum schnellen Teilen von Code, Prompts und System-Status über das Heimnetzwerk.</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-cyan-400 font-bold">•</span>
                          <div><strong>Dateibrowser &amp; Chat Vault:</strong> Schneller Upload und Download von Screenshots, Logs und Dokumenten (<code className="text-cyan-300">/api/chat/upload</code>).</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-cyan-400 font-bold">•</span>
                          <div><strong>Prozess-Manager:</strong> Live-Tabelle mit CPU-, RAM-Nutzung, Filter-Suchfeld und Beendigungs-Option (<code className="text-cyan-300">/api/kill</code>).</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-cyan-400 font-bold">•</span>
                          <div><strong>DuckDB Telemetrie-Historie:</strong> 24h Zeitreihen-Logging in <code className="text-zinc-200">no0bz_metrics.duckdb</code> mit interaktiven HTML5 Canvas-Graphen.</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-cyan-400 font-bold">•</span>
                          <div><strong>Theme Engine:</strong> Umschaltbar zwischen Classic Cyan, Nightmare Red, Industrial Amber und Bento-Grid.</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* RELEASE: v3.5.0 */}
                  {(!changelogSearch || 'v3.5.0 3.5.0 lhm librehardwaremonitor fan rpm lüfter sensors data_lock'.toLowerCase().includes(changelogSearch.toLowerCase())) && (
                    <div className={`p-5 rounded-xl border ${cardBg} transition-all`}>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-zinc-800">
                        <div className="flex items-center gap-3">
                          <span className="text-lg font-black text-white">v3.5.0</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
                            HARDWARE SENSORS
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          <Clock className="w-3.5 h-3.5" />
                          <span>02. September 2026</span>
                        </div>
                      </div>

                      <div className="mt-4 space-y-3 text-xs text-zinc-300">
                        <div className="flex items-start gap-2">
                          <span className="text-purple-400 font-bold">•</span>
                          <div><strong>LibreHardwareMonitor REST-Integration:</strong> Fallback-Client fragt Port 8085 ab für Mainboard-Temperaturen, CPU Package Power und Lüfterdrehzahlen (RPM).</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-purple-400 font-bold">•</span>
                          <div><strong>SVG Circular Gauges:</strong> Vektorbasierte, animierte Kreisdiagramme mit Gradienten-Füllung für Hardware-Lastanzeige.</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-purple-400 font-bold">•</span>
                          <div><strong>Thread-Safety:</strong> Absicherung aller Datenstrukturen mittels <code className="text-zinc-200">threading.Lock()</code>.</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* RELEASE: v3.1.0 */}
                  {(!changelogSearch || 'v3.1.0 3.1.0 websocket nvml gpu nvidia psutil multicore nvme'.toLowerCase().includes(changelogSearch.toLowerCase())) && (
                    <div className={`p-5 rounded-xl border ${cardBg} transition-all`}>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-zinc-800">
                        <div className="flex items-center gap-3">
                          <span className="text-lg font-black text-white">v3.1.0</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-300 border border-zinc-700">
                            REAL-TIME STREAMING
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          <Clock className="w-3.5 h-3.5" />
                          <span>15. August 2026</span>
                        </div>
                      </div>

                      <div className="mt-4 space-y-3 text-xs text-zinc-300">
                        <div className="flex items-start gap-2">
                          <span className="text-amber-400 font-bold">•</span>
                          <div><strong>1-Sekunden WebSockets:</strong> Umstellung auf Push-Streaming über <code className="text-amber-300">/ws/live</code> ohne wiederholtes Polling.</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-amber-400 font-bold">•</span>
                          <div><strong>NVIDIA NVML:</strong> C-API Binding für VRAM-Belegung, GPU-Core Clock, Power Draw in Watt und GPU-Temperatur.</div>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-amber-400 font-bold">•</span>
                          <div><strong>NVMe &amp; Multi-Core:</strong> Detaillierte Core-Balken und I/O Durchsatzanzeige in MB/s für alle Datenträger.</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* RELEASE: v3.0.0 */}
                  {(!changelogSearch || 'v3.0.0 3.0.0 initial release fastapi uvicorn architecture'.toLowerCase().includes(changelogSearch.toLowerCase())) && (
                    <div className={`p-5 rounded-xl border ${cardBg} transition-all opacity-80`}>
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-zinc-800">
                        <div className="flex items-center gap-3">
                          <span className="text-lg font-black text-white">v3.0.0</span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-400 border border-zinc-700">
                            INITIAL RELEASE
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-zinc-500">
                          <Clock className="w-3.5 h-3.5" />
                          <span>28. Juli 2026</span>
                        </div>
                      </div>

                      <div className="mt-4 space-y-2 text-xs text-zinc-400">
                        <p>
                          Erstveröffentlichung des <strong>no0bz Command Center (NCC)</strong> als Single-File Systemmonitor auf Port 8350 mit FastAPI, Uvicorn und responsivem UI.
                        </p>
                      </div>
                    </div>
                  )}

                </div>
              )}

            </div>
          )}

        </main>
      </div>

      {/* ======================================================== */}
      {/* LIGHTBOX MODAL FOR IMAGE ZOOM/PREVIEW                   */}
      {/* ======================================================== */}
      {lightboxImg && (
        <div 
          onClick={() => setLightboxImg(null)}
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4 cursor-zoom-out"
        >
          <div className="relative max-w-5xl max-h-[90vh]">
            <img 
              src={lightboxImg} 
              alt="Zoomed Preview" 
              className="max-w-full max-h-[85vh] rounded-lg border border-zinc-700 shadow-2xl object-contain" 
            />
            <button
              onClick={() => setLightboxImg(null)}
              className="absolute -top-3 -right-3 p-1.5 rounded-full bg-red-600 text-white hover:bg-red-500 shadow-lg"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MULTI-PC MODE SELECTION MODAL (POPUP ON START OR SWITCH) */}
      {/* ======================================================== */}
      {showModeModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#0b101e] border border-cyan-500/50 rounded-2xl max-w-2xl w-full p-6 shadow-[0_0_30px_rgba(6,182,212,0.25)] space-y-6 animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-zinc-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-xl bg-cyan-950/80 border border-cyan-500 text-cyan-400">
                  <Globe className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-mono font-bold text-lg text-white">
                    no0bz MULTI-PC BETRIEBSMODUS WÄHLEN
                  </h3>
                  <p className="text-xs font-mono text-zinc-400 mt-0.5">
                    Wie soll dieses no0bz Command Center betrieben werden?
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowModeModal(false)}
                className="p-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 3 Modes Cards */}
            <div className="space-y-3">
              {/* Option 1: Server hosten */}
              <div 
                onClick={() => setMultiPcMode('host')}
                className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-4 ${
                  multiPcMode === 'host' 
                    ? 'bg-amber-950/40 border-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.25)]' 
                    : 'bg-black/40 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="text-2xl p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                  👑
                </div>
                <div className="flex-1 font-mono">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-amber-300">Server-Betrieb (Master Hub)</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-200 border border-amber-600/60 font-bold">
                        Ausschließlich Serverseitig
                      </span>
                    </div>
                    {multiPcMode === 'host' && <span className="text-xs text-amber-400 font-bold">Aktiv</span>}
                  </div>
                  <p className="text-xs text-zinc-300 mt-1 font-sans">
                    Im <strong>Server-Betrieb</strong> erfolgen die Speicherung der Chat-Dateien (<code className="text-amber-300 font-mono text-[11px]">data/server/vault/</code>) sowie die Datenbankhaltung (<code className="text-amber-300 font-mono text-[11px]">no0bz_server.duckdb</code>) <strong>ausschließlich serverseitig</strong>. Alle verbundenen Clients übertragen Daten zentral an diesen Host.
                  </p>
                </div>
              </div>

              {/* Option 2: Lokal / Standalone */}
              <div 
                onClick={() => setMultiPcMode('local')}
                className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-4 ${
                  multiPcMode === 'local' 
                    ? 'bg-cyan-950/40 border-cyan-400 shadow-[0_0_20px_rgba(6,182,212,0.25)]' 
                    : 'bg-black/40 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="text-2xl p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                  🖥️
                </div>
                <div className="flex-1 font-mono">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-cyan-300">Standalone Modus (Lokal)</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-900/60 text-cyan-200 border border-cyan-600/60 font-bold">
                        Ausschließlich Lokal
                      </span>
                    </div>
                    {multiPcMode === 'local' && <span className="text-xs text-cyan-400 font-bold">Aktiv</span>}
                  </div>
                  <p className="text-xs text-zinc-300 mt-1 font-sans">
                    Im <strong>Standalone Modus</strong> erfolgen die Speicherung der Chat-Dateien (<code className="text-cyan-300 font-mono text-[11px]">data/local/vault/</code>) sowie die Datenbankhaltung (<code className="text-cyan-300 font-mono text-[11px]">no0bz_local.duckdb</code>) <strong>ausschließlich lokal</strong> auf diesem Rechner. Autarker Betrieb ohne externe Verbindungen.
                  </p>
                </div>
              </div>

              {/* Option 3: Auf Server verbinden */}
              <div 
                onClick={() => setMultiPcMode('client')}
                className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-4 ${
                  multiPcMode === 'client' 
                    ? 'bg-blue-950/40 border-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.25)]' 
                    : 'bg-black/40 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="text-2xl p-2 rounded-lg bg-zinc-900 border border-zinc-800">
                  🔗
                </div>
                <div className="flex-1 font-mono">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-blue-300">Client Node (Remote Verbindung)</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-200 border border-blue-600/60 font-bold">
                        Speichert am Server
                      </span>
                    </div>
                    {multiPcMode === 'client' && <span className="text-xs text-blue-400 font-bold">Aktiv</span>}
                  </div>
                  <p className="text-xs text-zinc-300 mt-1 font-sans">
                    Verbindet diesen Rechner mit einem aktiven no0bz Server. Sendet Live-Telemetrie an den Host; Chat-Dateien und Datenbank werden direkt serverseitig auf dem Host vorgehalten.
                  </p>
                  {multiPcMode === 'client' && (
                    <div className="mt-3 flex items-center gap-2">
                      <span className="text-xs text-zinc-300">Server-Adresse:</span>
                      <input 
                        type="text" 
                        value={clientServerUrl} 
                        onChange={(e) => setClientServerUrl(e.target.value)}
                        placeholder="192.168.1.100:8350"
                        className="bg-black border border-zinc-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-blue-400 font-bold"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-2 border-t border-zinc-800 font-mono text-xs">
              <span className="text-zinc-500">Wird in ncc_config.json dauerhaft gespeichert.</span>
              <button
                type="button"
                onClick={() => {
                  localStorage.setItem('no0bz_multipc_mode', multiPcMode);
                  setShowModeModal(false);
                  fetch('/api/multipc/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: multiPcMode, client_server_url: clientServerUrl })
                  })
                    .then(res => res.json())
                    .then(data => {
                      if (data.storage_type) setStorageLocation(data.storage_type);
                    })
                    .catch(() => {});
                }}
                className="px-5 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold shadow-[0_0_12px_rgba(6,182,212,0.4)] transition-all cursor-pointer"
              >
                Modus aktivieren &amp; Anwenden
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* AESTHETIC FOOTER STRIP                                  */}
      {/* ======================================================== */}
      <footer className={`h-8 px-4 flex items-center justify-between border-t text-[10px] font-mono ${
        isNightmare ? 'bg-black/95 border-red-950/40 text-zinc-500' : 'bg-slate-950/95 border-slate-800 text-zinc-400'
      }`}>
        <div className="flex items-center gap-3">
          <span className="font-bold text-zinc-300">no0bz COMMAND CENTER</span>
          <span>|</span>
          <button 
            onClick={() => setActiveTab('changelog')} 
            className="text-cyan-400 hover:text-cyan-300 font-semibold cursor-pointer underline"
            title="Changelog ansehen"
          >
            v3.8.2
          </button>
          <span>|</span>
          <span className="hidden sm:inline">// {themeMode.toUpperCase()} MODE</span>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden md:inline">RAM: {metrics.ram_used} / {metrics.ram_total} GB</span>
          <span>•</span>
          <span className="hidden md:inline">NVME TOTAL: {totalReadSpeed} MB/s R | {totalWriteSpeed} MB/s W</span>
          <span>•</span>
          <span className={isNightmare ? 'text-red-400 font-bold' : 'text-cyan-400 font-bold'}>
            // NO LIMITS //
          </span>
        </div>
      </footer>

    </div>
  );
}
