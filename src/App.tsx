import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Activity, Cpu, HardDrive, Wifi, Zap, Terminal, 
  Trash2, Search, Sliders, RefreshCw, Layers, ArrowDown, ArrowUp, Disc,
  MessageSquare, Send, Paperclip, Download, Upload, Copy, Check, File,
  FileText, Image as ImageIcon, Eye, Folder, Settings, ShieldAlert, Sparkles,
  Maximize2, X, AlertTriangle, Monitor, Laptop, Clock, Server, CheckCircle2,
  Share2, HardDriveDownload, Filter
} from 'lucide-react';

// ================================================
// TYPES & INTERFACES
// ================================================

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

export function No0bzLogo({ mode = 'nightmare', size = 'normal' }: { mode?: 'classic' | 'nightmare', size?: 'small' | 'normal' | 'large' }) {
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
          <span className="text-[8px] px-1 py-0.2 bg-zinc-800 border border-zinc-700 text-zinc-300 rounded font-mono font-semibold">
            v3.7.0
          </span>
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
// MAIN COMPONENT
// ================================================

export default function App() {
  // Navigation: The top menu is completely removed. Sidebar is the only nav!
  const [activeTab, setActiveTab] = useState<'dashboard' | 'chat' | 'vault' | 'processes' | 'history' | 'settings'>('dashboard');
  const [themeMode, setThemeMode] = useState<'nightmare' | 'bento' | 'nordic' | 'industrial'>('nightmare');
  const [logoStyle, setLogoStyle] = useState<'nightmare' | 'classic'>('nightmare');

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
            setMessages(prev => [...prev, raw.data]);
            return;
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
          }
        } catch {
          // ignore
        }
      };
      ws.onerror = () => {
        // Fallback simulation
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

  // All Attachments gathered from messages for Vault View
  const allVaultFiles = useMemo(() => {
    const list: (ChatAttachment & { sender: string; msgId: string })[] = [];
    messages.forEach(m => {
      (m.attachments || []).forEach(att => {
        list.push({ ...att, sender: m.sender, msgId: m.id });
      });
    });
    return list.filter(item => {
      const matchSearch = item.name.toLowerCase().includes(vaultSearch.toLowerCase());
      if (!matchSearch) return false;
      if (vaultFilter === 'images') return item.is_image;
      if (vaultFilter === 'code') return ['PY', 'CU', 'TS', 'JS', 'CPP', 'JSON', 'RS'].includes(item.ext);
      if (vaultFilter === 'docs') return ['TXT', 'PDF', 'MD', 'DOCX'].includes(item.ext);
      return true;
    });
  }, [messages, vaultSearch, vaultFilter]);

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
      const droppedFiles = Array.from(e.dataTransfer.files).slice(0, 100); // max 100
      setQueuedFiles(prev => [...prev, ...droppedFiles].slice(0, 100));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).slice(0, 100);
      setQueuedFiles(prev => [...prev, ...selected].slice(0, 100));
    }
  };

  // Send Chat Message / Prompt / Files
  const handleSendMessage = async () => {
    if (!promptText.trim() && queuedFiles.length === 0) return;

    const attachments: ChatAttachment[] = [];

    // Convert local files to attachments with preview URLs
    for (const f of queuedFiles) {
      const ext = f.name.split('.').pop()?.toUpperCase() || 'FILE';
      const isImg = ['PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'SVG'].includes(ext);
      let previewUrl = '';
      if (isImg) {
        previewUrl = URL.createObjectURL(f);
      }
      attachments.push({
        name: f.name,
        size: f.size,
        ext,
        is_image: isImg,
        url: previewUrl || '#',
        data_url: previewUrl,
        uploaded_at: new Date().toLocaleTimeString('de-DE')
      });
    }

    const words = promptText.trim().split(/\s+/).filter(Boolean).length;
    const tokens = Math.round(promptText.length / 3.8);

    const newMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: myDeviceName,
      timestamp: new Date().toLocaleTimeString('de-DE'),
      type: queuedFiles.length > 0 && !promptText.trim() ? 'files' : 'prompt',
      title: promptTitle.trim() || (attachments.length > 0 ? `Shared ${attachments.length} File(s)` : 'P2P Prompt Sync'),
      content: promptText.trim(),
      tokens,
      words,
      attachments
    };

    setMessages(prev => [...prev, newMsg]);
    setPromptText('');
    setPromptTitle('');
    setQueuedFiles([]);

    // Scroll chat to bottom
    setTimeout(() => {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);

    // Try posting to local FastAPI backend if running
    try {
      await fetch('http://localhost:8350/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newMsg)
      });
    } catch {
      // Backend not running directly, local state already updated!
    }
  };

  // Copy Prompt to Clipboard
  const handleCopyPrompt = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Kill Process Action
  const handleKill = (pid: number) => {
    setKillPid(pid);
    setTimeout(() => {
      setProcesses(prev => prev.filter(p => p.pid !== pid));
      setKillPid(null);
    }, 500);
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
          <No0bzLogo mode={logoStyle} size="normal" />
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

          {/* Device Profile Tag */}
          <div className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-zinc-400 flex items-center gap-1.5">
            <Monitor className="w-3.5 h-3.5 text-zinc-300" />
            <span className="hidden sm:inline font-semibold text-zinc-200">{myDeviceName}</span>
          </div>
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
                  onClick={() => setActiveTab('dashboard')}
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

                {/* 2. CHAT & PROMPT SYNC (NEW FEATURE!) */}
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

                {/* 3. DATEIBROWSER / CHAT VAULT (NEW FEATURE!) */}
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

                {/* 4. PROZESSE */}
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

                {/* 5. HISTORIE */}
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

                {/* 6. EINSTELLUNGEN */}
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

                {/* 4. NETWORK & LATENCY CARD */}
                <div className={`rounded-xl p-4 flex flex-col justify-between ${cardBg}`}>
                  <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Wifi className="w-4 h-4 text-emerald-400" />
                      <span className="font-mono font-bold text-xs tracking-wider">NETWORK I/O</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-300">
                      LAN 10 GbE
                    </span>
                  </div>

                  <div className="flex flex-col items-center justify-center py-2 space-y-3">
                    <div className="w-full bg-black/40 p-2.5 rounded-lg border border-zinc-800/80 flex items-center justify-between font-mono">
                      <div className="flex items-center gap-2 text-cyan-400">
                        <ArrowDown className="w-4 h-4" />
                        <span className="text-xs font-semibold">DOWNLOAD</span>
                      </div>
                      <span className="text-base font-bold text-white">{metrics.net_recv_mbps} <span className="text-xs text-zinc-400">Mbps</span></span>
                    </div>

                    <div className="w-full bg-black/40 p-2.5 rounded-lg border border-zinc-800/80 flex items-center justify-between font-mono">
                      <div className="flex items-center gap-2 text-amber-400">
                        <ArrowUp className="w-4 h-4" />
                        <span className="text-xs font-semibold">UPLOAD</span>
                      </div>
                      <span className="text-base font-bold text-white">{metrics.net_sent_mbps} <span className="text-xs text-zinc-400">Mbps</span></span>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                    <span>STATUS: 0% LOSS</span>
                    <span className="text-emerald-400 font-bold">PING: 4ms</span>
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
          {/* TAB 2: P2P PROMPT & CHAT + DRAG & DROP FILE SHARING  */}
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

                {/* Device Selector */}
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="text-zinc-400 text-xs">Absender:</span>
                  <select
                    value={myDeviceName}
                    onChange={(e) => setMyDeviceName(e.target.value)}
                    className="bg-black/60 border border-zinc-700 text-white rounded px-2.5 py-1 text-xs focus:outline-none focus:border-red-500"
                  >
                    <option value="PC-A (Main Rig)">PC-A (Main Rig)</option>
                    <option value="PC-B (Gaming-Notebook)">PC-B (Gaming-Notebook)</option>
                    <option value="Workstation (Linux Server)">Workstation (Linux Server)</option>
                    <option value="Secondary Testbench">Secondary Testbench</option>
                  </select>
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

                {/* Upload Button */}
                <div className="flex items-center gap-2">
                  <input
                    type="file"
                    id="vault-upload"
                    multiple
                    onChange={handleFileSelect}
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
                  <p className="text-xs">Lade Dateien hoch oder droppe sie im Chat-Tab!</p>
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
                          <span>{file.sender.split(' ')[0]}</span>
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
                            onClick={() => {
                              setMessages(prev => prev.map(m => ({
                                ...m,
                                attachments: (m.attachments || []).filter(a => a.name !== file.name)
                              })));
                            }}
                            className="text-zinc-500 hover:text-red-400 text-xs transition-colors"
                            title="Löschen"
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
                  <span>SYSTEM- &amp; NCC-EINSTELLUNGEN</span>
                </h2>
                <p className="text-xs text-zinc-400 mt-1">
                  Passe Hardware-Sensoren, Schwellenwert-Alarme, P2P-Netzwerk-Optionen und die Telemetrie an.
                </p>
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
      {/* AESTHETIC FOOTER STRIP                                  */}
      {/* ======================================================== */}
      <footer className={`h-8 px-4 flex items-center justify-between border-t text-[10px] font-mono ${
        isNightmare ? 'bg-black/95 border-red-950/40 text-zinc-500' : 'bg-slate-950/95 border-slate-800 text-zinc-400'
      }`}>
        <div className="flex items-center gap-3">
          <span className="font-bold text-zinc-300">no0bz COMMAND CENTER</span>
          <span>|</span>
          <span className="text-red-400 font-semibold">v3.6.0</span>
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
