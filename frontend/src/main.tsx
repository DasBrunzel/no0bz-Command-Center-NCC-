import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, Bell, Boxes, Check, ChevronRight, CircleGauge, Clock3, Cpu,
  HardDrive, KeyRound, LayoutDashboard, MemoryStick, Menu, MonitorCog,
  Moon, Network, RefreshCw, Search, Server, Settings, ShieldCheck,
  Signal, Wifi, WifiOff, X,
} from "lucide-react";
import "./index.css";

type Metrics = Record<string, any>;
type Telemetry = {sample_id:string|null;recorded_at:string;metrics:Metrics};
type Node = {
  node_id:string;machine_id:string;display_name:string;platform:string;approved:boolean;
  online:boolean;agent_version:string|null;metadata:Record<string,unknown>;
  created_at:string;last_seen_at:string|null;latest:Telemetry|null;
};
type Summary = {total_nodes:number;online_nodes:number;offline_nodes:number;pending_nodes:number;telemetry_points:number;server_time:string};
type Theme = "nightmare"|"cachyos"|"cyber"|"oled"|"light"|"matrix"|"dracula"|"nordic"|"amber";
type Page = "fleet"|"telemetry"|"settings";

const THEMES:{id:Theme;name:string;color:string}[] = [
  {id:"nightmare",name:"Nightmare Red",color:"#ff334f"},{id:"cachyos",name:"CachyOS Cyan",color:"#18d7ec"},
  {id:"cyber",name:"Cyber Neon",color:"#ff35d3"},{id:"oled",name:"Dark Matter OLED",color:"#e8edf5"},
  {id:"light",name:"Clean Light",color:"#d52f4b"},{id:"matrix",name:"Matrix Hacker",color:"#36f276"},
  {id:"dracula",name:"Dracula",color:"#ff6680"},{id:"nordic",name:"Nordic Frost",color:"#88c0d0"},
  {id:"amber",name:"Retro Amber",color:"#ffb52e"},
];
const num=(value:unknown)=>typeof value==="number"&&Number.isFinite(value)?value:0;
const ago=(value:string|null)=>{
  if(!value)return "Noch nie"; const seconds=Math.max(0,Math.floor((Date.now()-new Date(value).getTime())/1000));
  if(seconds<10)return "Gerade eben"; if(seconds<60)return `Vor ${seconds} Sek.`; if(seconds<3600)return `Vor ${Math.floor(seconds/60)} Min.`;
  if(seconds<86400)return `Vor ${Math.floor(seconds/3600)} Std.`; return new Date(value).toLocaleDateString("de-DE");
};
const headers=(token:string):Record<string,string>=>token?{"X-NCC-Dashboard-Token":token}:{};
async function getJson<T>(url:string,token:string):Promise<T>{
  const response=await fetch(url,{headers:headers(token)});
  if(!response.ok){const error=new Error(response.status===401?"AUTH":"REQUEST") as Error&{status:number};error.status=response.status;throw error}
  return response.json() as Promise<T>;
}

function Brand(){return <div className="brand"><div className="brand-mark"><Signal size={22}/></div><div><strong>no<span>0</span>bz</strong><small>COMMAND CENTER</small></div></div>}
function StatusDot({online}:{online:boolean}){return <span className={`status-dot ${online?"is-online":"is-offline"}`}><i/>{online?"ONLINE":"OFFLINE"}</span>}

function StatCard({label,value,detail,icon,tone="accent"}:{label:string;value:string|number;detail:string;icon:React.ReactNode;tone?:string}){
  return <article className={`stat-card tone-${tone}`}><div className="stat-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></article>
}

function Gauge({label,value,tone="accent",detail}:{label:string;value:number;tone?:string;detail:string}){
  const safe=Math.max(0,Math.min(100,value));
  return <article className={`gauge-card tone-${tone}`}><header><span>{label}</span><b>{detail}</b></header><div className="gauge"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="48" className="gauge-track"/><circle cx="60" cy="60" r="48" className="gauge-value" strokeDasharray="301.6" strokeDashoffset={301.6*(1-safe/100)}/></svg><div><strong>{safe.toFixed(1)}%</strong><small>AUSLASTUNG</small></div></div></article>
}

function Sparkline({points,metric,color="var(--accent)"}:{points:Telemetry[];metric:(m:Metrics)=>number;color?:string}){
  const values=points.map(point=>Math.max(0,Math.min(100,metric(point.metrics))));
  const line=values.length>1?values.map((value,index)=>`${index?"L":"M"} ${(index/(values.length-1))*100} ${100-value}`).join(" "):"";
  const gradient=`fill-${color.replace(/\W/g,"")}`;
  return <div className="sparkline"><svg viewBox="0 0 100 100" preserveAspectRatio="none"><defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".35"/><stop offset="1" stopColor={color} stopOpacity="0"/></linearGradient></defs>{line&&<><path d={`${line} L 100 100 L 0 100 Z`} fill={`url(#${gradient})`}/><path d={line} fill="none" stroke={color} strokeWidth="1.7" vectorEffect="non-scaling-stroke"/></>}</svg>{!line&&<span>Noch nicht genug Messwerte</span>}</div>
}

function Fleet({nodes,selected,onSelect,query,onQuery}:{nodes:Node[];selected:Node|null;onSelect:(id:string)=>void;query:string;onQuery:(v:string)=>void}){
  const filtered=nodes.filter(node=>`${node.display_name} ${node.platform} ${node.machine_id}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="fleet-layout"><section className="surface node-browser"><header className="section-head"><div><span className="eyebrow">INFRASTRUKTUR</span><h2>Deine Geräte</h2></div><b>{nodes.filter(n=>n.online).length}/{nodes.length} AKTIV</b></header><label className="search"><Search size={15}/><input value={query} onChange={e=>onQuery(e.target.value)} placeholder="Gerät suchen …"/></label><div className="node-stack">{filtered.map(node=>{const m=node.latest?.metrics||{};return <button key={node.node_id} className={selected?.node_id===node.node_id?"selected":""} onClick={()=>onSelect(node.node_id)}><div className={`device-icon ${node.online?"online":""}`}><Server size={20}/></div><div className="node-copy"><strong>{node.display_name}</strong><span>{node.platform} · {node.agent_version||"Agent unbekannt"}</span><div><i style={{width:`${num(m.cpu?.percent)}%`}}/><small>CPU {num(m.cpu?.percent).toFixed(0)}%</small></div></div><StatusDot online={node.online}/><ChevronRight size={16}/></button>})}{!filtered.length&&<div className="empty"><Boxes size={30}/><strong>Keine Geräte gefunden</strong><span>Starte einen NCC-Agenten oder ändere die Suche.</span></div>}</div></section><NodeOverview node={selected}/></div>
}

function NodeOverview({node}:{node:Node|null}){
  if(!node)return <section className="surface empty-stage"><Server size={45}/><h2>Noch kein Gerät verbunden</h2><p>Sobald ein Agent Daten sendet, erscheint er automatisch in dieser Fleet.</p></section>;
  const m=node.latest?.metrics||{},cpu=m.cpu||{},memory=m.memory||{},gpu=m.gpus?.[0]||{},network=m.network||{};
  return <section className="node-overview"><div className="surface hero"><div><span className="eyebrow">AUSGEWÄHLTER NODE</span><h1>{node.display_name}</h1><p>{node.platform.toUpperCase()} · {String(node.metadata.architecture||"Architektur unbekannt")} · {node.machine_id}</p></div><div className="hero-status"><StatusDot online={node.online}/><small>{ago(node.last_seen_at)}</small></div></div><div className="gauge-grid"><Gauge label="CPU" value={num(cpu.percent)} detail={cpu.model||"Processor"}/><Gauge label="ARBEITSSPEICHER" value={num(memory.percent)} tone="blue" detail={`${num(memory.used_gb).toFixed(1)} / ${num(memory.total_gb).toFixed(1)} GB`}/><Gauge label="GPU" value={num(gpu.percent)} tone="purple" detail={gpu.name||"Nicht erkannt"}/></div><div className="detail-grid"><article className="surface compact"><header><Network size={16}/><span>NETZWERK</span></header><div className="rate-pair"><div><small>DOWNLOAD</small><strong>{num(network.download_mbps).toFixed(1)}</strong><span>Mbps</span></div><div><small>UPLOAD</small><strong>{num(network.upload_mbps).toFixed(1)}</strong><span>Mbps</span></div></div><footer>{network.interface||"Automatische Schnittstelle"}</footer></article><article className="surface compact"><header><HardDrive size={16}/><span>LAUFWERKE</span></header><div className="disk-list">{(m.disks||[]).slice(0,3).map((disk:Metrics,index:number)=><div key={`${disk.mount}-${index}`}><span>{disk.mount||disk.name||`Disk ${index+1}`}</span><div><i style={{width:`${num(disk.percent)}%`}}/></div><b>{num(disk.percent).toFixed(0)}%</b></div>)}{!(m.disks||[]).length&&<p>Keine Laufwerksdaten</p>}</div></article></div></section>
}

function TelemetryPage({node,points}:{node:Node|null;points:Telemetry[]}){
  if(!node)return <section className="surface empty-stage"><Activity size={44}/><h2>Keine Telemetrie verfügbar</h2></section>;
  const latest=node.latest?.metrics||{},cpu=latest.cpu||{},memory=latest.memory||{},gpu=latest.gpus?.[0]||{};
  return <div className="telemetry-page"><div className="surface telemetry-title"><div><span className="eyebrow">LIVE TELEMETRIE</span><h1>{node.display_name}</h1><p>{points.length} Messpunkte im aktuellen Diagramm</p></div><StatusDot online={node.online}/></div><div className="chart-grid"><article className="surface chart-card"><header><div className="chart-icon red"><Cpu size={17}/></div><div><span>CPU-LAST</span><strong>{num(cpu.percent).toFixed(1)}%</strong></div></header><Sparkline points={points} metric={m=>num(m.cpu?.percent)}/></article><article className="surface chart-card"><header><div className="chart-icon blue"><MemoryStick size={17}/></div><div><span>RAM-AUSLASTUNG</span><strong>{num(memory.percent).toFixed(1)}%</strong></div></header><Sparkline points={points} metric={m=>num(m.memory?.percent)} color="var(--blue)"/></article><article className="surface chart-card"><header><div className="chart-icon purple"><MonitorCog size={17}/></div><div><span>GPU-LAST</span><strong>{num(gpu.percent).toFixed(1)}%</strong></div></header><Sparkline points={points} metric={m=>num(m.gpus?.[0]?.percent)} color="var(--purple)"/></article></div><section className="surface metadata"><header className="section-head"><div><span className="eyebrow">NODE INFORMATION</span><h2>Systemdetails</h2></div></header><dl><dt>Geräte-ID</dt><dd>{node.machine_id}</dd><dt>Plattform</dt><dd>{node.platform}</dd><dt>Agent-Version</dt><dd>{node.agent_version||"Unbekannt"}</dd><dt>Erster Kontakt</dt><dd>{new Date(node.created_at).toLocaleString("de-DE")}</dd><dt>Letzter Kontakt</dt><dd>{node.last_seen_at?new Date(node.last_seen_at).toLocaleString("de-DE"):"Noch nie"}</dd><dt>Status</dt><dd><StatusDot online={node.online}/></dd></dl></section></div>
}

function SettingsPage({theme,onTheme,onToken}:{theme:Theme;onTheme:(v:Theme)=>void;onToken:()=>void}){
  return <div className="settings-page"><section className="surface settings-card"><header className="section-head"><div><span className="eyebrow">DARSTELLUNG</span><h2>Theme auswählen</h2></div><Moon size={19}/></header><div className="theme-grid">{THEMES.map(item=><button key={item.id} className={theme===item.id?"active":""} onClick={()=>onTheme(item.id)}><i style={{background:item.color}}/><span>{item.name}</span>{theme===item.id&&<Check size={15}/>}</button>)}</div></section><section className="surface settings-card"><header className="section-head"><div><span className="eyebrow">SICHERHEIT</span><h2>Dashboard-Zugang</h2></div><ShieldCheck size={19}/></header><p>Der Dashboard-Token ist vom Agent-Token getrennt und bleibt ausschließlich in diesem Browser gespeichert.</p><button className="primary" onClick={onToken}><KeyRound size={16}/> Dashboard-Token ändern</button></section></div>
}

function Login({onSave,error}:{onSave:(value:string)=>void;error:boolean}){
  const [value,setValue]=useState("");
  return <div className="login"><div className="login-glow"/><section><Brand/><div className="login-icon"><KeyRound size={26}/></div><span className="eyebrow">GESCHÜTZTER ZUGANG</span><h1>Willkommen, Commander.</h1><p>Gib den Dashboard-Token deines NCC-Servers ein. Beim lokalen Zugriff kann das Feld leer bleiben.</p><form onSubmit={event=>{event.preventDefault();onSave(value)}}><label>Dashboard-Token<input autoFocus type="password" value={value} onChange={e=>setValue(e.target.value)} placeholder="Token eingeben"/></label>{error&&<small className="form-error">Der Token wurde nicht akzeptiert.</small>}<button className="primary" type="submit"><ShieldCheck size={17}/> Verbindung herstellen</button></form></section></div>
}

function App(){
  const [theme,setTheme]=useState<Theme>(()=>(localStorage.getItem("ncc-fleet-theme") as Theme)||"nightmare");
  const [token,setToken]=useState(()=>localStorage.getItem("ncc-dashboard-token")||"");
  const [authenticated,setAuthenticated]=useState<boolean|null>(null),[authError,setAuthError]=useState(false);
  const [nodes,setNodes]=useState<Node[]>([]),[summary,setSummary]=useState<Summary|null>(null),[selectedId,setSelectedId]=useState(""),[points,setPoints]=useState<Telemetry[]>([]);
  const [page,setPage]=useState<Page>("fleet"),[query,setQuery]=useState(""),[loading,setLoading]=useState(true),[sidebar,setSidebar]=useState(false),[clock,setClock]=useState(new Date());
  const selected=nodes.find(node=>node.node_id===selectedId)||nodes[0]||null;
  const load=useCallback(async(silent=false)=>{if(!silent)setLoading(true);try{const [nextNodes,nextSummary]=await Promise.all([getJson<Node[]>("/api/v1/fleet/nodes",token),getJson<Summary>("/api/v1/fleet/summary",token)]);setNodes(nextNodes);setSummary(nextSummary);setAuthenticated(true);setAuthError(false);setSelectedId(current=>nextNodes.some(node=>node.node_id===current)?current:(nextNodes[0]?.node_id||""))}catch(error){if((error as Error&{status?:number}).status===401){setAuthenticated(false);setAuthError(true)}}finally{setLoading(false)}},[token]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem("ncc-fleet-theme",theme)},[theme]);
  useEffect(()=>{void load();const poll=window.setInterval(()=>void load(true),5000);return()=>clearInterval(poll)},[load]);
  useEffect(()=>{const timer=window.setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(timer)},[]);
  useEffect(()=>{if(!selected)return;getJson<Telemetry[]>(`/api/v1/fleet/nodes/${selected.node_id}/telemetry?limit=120`,token).then(setPoints).catch(()=>setPoints([]))},[selected?.node_id,selected?.latest?.recorded_at,token]);
  const saveToken=(value:string)=>{localStorage.setItem("ncc-dashboard-token",value);setToken(value);setAuthenticated(null);setAuthError(false)};
  const nav=useMemo(()=>[{id:"fleet" as Page,label:"Fleet Übersicht",icon:<LayoutDashboard size={17}/>},{id:"telemetry" as Page,label:"Telemetrie",icon:<CircleGauge size={17}/>},{id:"settings" as Page,label:"Einstellungen",icon:<Settings size={17}/>}],[]);
  if(authenticated!==true)return <Login onSave={saveToken} error={authenticated===false&&authError}/>;
  return <div className="shell"><aside className={sidebar?"open":""}><div className="aside-top"><Brand/><button className="close-menu" onClick={()=>setSidebar(false)}><X size={19}/></button></div><nav><span>COMMAND CENTER</span>{nav.map(item=><button key={item.id} className={page===item.id?"active":""} onClick={()=>{setPage(item.id);setSidebar(false)}}>{item.icon}<b>{item.label}</b>{page===item.id&&<i/>}</button>)}</nav><div className="server-health"><header><span>SERVER STATUS</span><b><i/> BEREIT</b></header><dl><dt>Nodes online</dt><dd>{summary?.online_nodes||0}</dd><dt>Messpunkte</dt><dd>{summary?.telemetry_points.toLocaleString("de-DE")||0}</dd><dt>API</dt><dd>v1</dd></dl></div><footer><ShieldCheck size={14}/><span>GESICHERTE VERBINDUNG</span><b>v0.5.0-beta.2</b></footer></aside><div className="mobile-scrim" onClick={()=>setSidebar(false)}/><div className="content"><header className="topbar"><button className="menu" onClick={()=>setSidebar(true)}><Menu size={20}/></button><div><span className="eyebrow">NO0BZ INFRASTRUCTURE</span><strong>{page==="fleet"?"Fleet Command":page==="telemetry"?"Telemetry Center":"System Settings"}</strong></div><div className="top-actions"><div className="clock"><Clock3 size={14}/><span>{clock.toLocaleTimeString("de-DE")}</span></div><button aria-label="Benachrichtigungen"><Bell size={17}/><i/></button><button className="refresh" onClick={()=>void load()} aria-label="Aktualisieren"><RefreshCw size={17} className={loading?"spin":""}/></button><div className="commander"><span>C</span><div><b>Commander</b><small>Administrator</small></div></div></div></header><main><div className="summary-grid"><StatCard label="GESAMTE NODES" value={summary?.total_nodes||0} detail="Registrierte Agenten" icon={<Server size={20}/>} /><StatCard label="ONLINE" value={summary?.online_nodes||0} detail="Aktiv verbunden" icon={<Wifi size={20}/>} tone="green"/><StatCard label="OFFLINE" value={summary?.offline_nodes||0} detail="Verbindung getrennt" icon={<WifiOff size={20}/>} tone="muted"/><StatCard label="MESSPUNKTE" value={(summary?.telemetry_points||0).toLocaleString("de-DE")} detail="In der Datenbank" icon={<Activity size={20}/>} tone="blue"/></div>{page==="fleet"?<Fleet nodes={nodes} selected={selected} onSelect={setSelectedId} query={query} onQuery={setQuery}/>:page==="telemetry"?<TelemetryPage node={selected} points={points}/>:<SettingsPage theme={theme} onTheme={setTheme} onToken={()=>setAuthenticated(false)}/>}</main><footer className="statusbar"><span><i/> NCC SERVER VERBUNDEN</span><b>{selected?`${selected.display_name} · ${ago(selected.last_seen_at)}`:"WARTE AUF AGENTEN"}</b><span>{clock.toLocaleDateString("de-DE")}</span></footer></div></div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
