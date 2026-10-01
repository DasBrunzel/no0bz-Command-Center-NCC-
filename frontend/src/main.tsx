import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, Ban, Bell, Boxes, Check, ChevronRight, CircleGauge, Clock3, Copy, Cpu,
  HardDrive, KeyRound, LayoutDashboard, MemoryStick, Menu, MonitorCog,
  Moon, Network, RefreshCw, Search, Server, Settings, ShieldCheck,
  Signal, Trash2, UserPlus, Wifi, WifiOff, X,
} from "lucide-react";
import "./index.css";
import "./enrollment.css";
import "./device-lifecycle.css";

type Metrics = Record<string, any>;
type Telemetry = {sample_id:string|null;recorded_at:string;metrics:Metrics};
type Node = {
  node_id:string;machine_id:string;display_name:string;platform:string;approved:boolean;
  online:boolean;agent_version:string|null;metadata:Record<string,unknown>;
  created_at:string;last_seen_at:string|null;latest:Telemetry|null;
};
type Summary = {total_nodes:number;online_nodes:number;offline_nodes:number;pending_nodes:number;telemetry_points:number;server_time:string};
type Theme = "nightmare"|"cachyos"|"cyber"|"oled"|"light"|"matrix"|"dracula"|"nordic"|"amber";
type Invitation = {token_id:string;name:string;status:"ready"|"bound"|"expired"|"revoked";node_id:string|null;node_name:string|null;created_at:string;expires_at:string|null;last_used_at:string|null;revoked_at:string|null};
type IssuedInvitation = Invitation & {token:string};
type Page = "fleet"|"telemetry"|"onboarding"|"settings";

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
async function postJson<T>(url:string,token:string,body?:unknown):Promise<T>{
  const response=await fetch(url,{method:"POST",headers:{...headers(token),"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok){const error=new Error("REQUEST") as Error&{status:number};error.status=response.status;throw error}
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
  const [forgetting,setForgetting]=useState(false);
  if(!node)return <section className="surface empty-stage"><Server size={45}/><h2>Noch kein Gerät verbunden</h2><p>Sobald ein Agent Daten sendet, erscheint er automatisch in dieser Fleet.</p></section>;
  const m=node.latest?.metrics||{},cpu=m.cpu||{},memory=m.memory||{},gpu=m.gpus?.[0]||{},network=m.network||{};
  const forget=async()=>{
    if(!window.confirm(`„${node.display_name}“ wirklich vergessen? Alle gespeicherten Messwerte und die zugehörigen Agent-Tokens werden entfernt.`))return;
    setForgetting(true);
    const dashboardToken=localStorage.getItem("ncc-dashboard-token")||"";
    const response=await fetch(`/api/v1/fleet/nodes/${node.node_id}`,{method:"DELETE",headers:headers(dashboardToken)});
    if(response.ok){window.location.reload();return}
    setForgetting(false);window.alert("Das Gerät konnte nicht entfernt werden. Bitte erneut versuchen.");
  };
  return <section className="node-overview"><div className="surface hero"><div><span className="eyebrow">AUSGEWÄHLTER NODE</span><h1>{node.display_name}</h1><p>{node.platform.toUpperCase()} · {String(node.metadata.architecture||"Architektur unbekannt")} · {node.machine_id}</p></div><div className="hero-status"><StatusDot online={node.online}/><small>{ago(node.last_seen_at)}</small></div></div><div className="gauge-grid"><Gauge label="CPU" value={num(cpu.percent)} detail={cpu.model||"Processor"}/><Gauge label="ARBEITSSPEICHER" value={num(memory.percent)} tone="blue" detail={`${num(memory.used_gb).toFixed(1)} / ${num(memory.total_gb).toFixed(1)} GB`}/><Gauge label="GPU" value={num(gpu.percent)} tone="purple" detail={gpu.name||"Nicht erkannt"}/></div><div className="detail-grid"><article className="surface compact"><header><Network size={16}/><span>NETZWERK</span></header><div className="rate-pair"><div><small>DOWNLOAD</small><strong>{num(network.download_mbps).toFixed(1)}</strong><span>Mbps</span></div><div><small>UPLOAD</small><strong>{num(network.upload_mbps).toFixed(1)}</strong><span>Mbps</span></div></div><footer>{network.interface||"Automatische Schnittstelle"}</footer></article><article className="surface compact"><header><HardDrive size={16}/><span>LAUFWERKE</span></header><div className="disk-list">{(m.disks||[]).slice(0,3).map((disk:Metrics,index:number)=><div key={`${disk.mount}-${index}`}><span>{disk.mount||disk.name||`Disk ${index+1}`}</span><div><i style={{width:`${num(disk.percent)}%`}}/></div><b>{num(disk.percent).toFixed(0)}%</b></div>)}{!(m.disks||[]).length&&<p>Keine Laufwerksdaten</p>}</div></article></div><button className="forget-node" disabled={forgetting} onClick={()=>void forget()}><Trash2 size={15}/>{forgetting?"Gerät wird entfernt …":"Gerät vergessen"}</button></section>
}

function TelemetryPage({node,points}:{node:Node|null;points:Telemetry[]}){
  if(!node)return <section className="surface empty-stage"><Activity size={44}/><h2>Keine Telemetrie verfügbar</h2></section>;
  const latest=node.latest?.metrics||{},cpu=latest.cpu||{},memory=latest.memory||{},gpu=latest.gpus?.[0]||{};
  return <div className="telemetry-page"><div className="surface telemetry-title"><div><span className="eyebrow">LIVE TELEMETRIE</span><h1>{node.display_name}</h1><p>{points.length} Messpunkte im aktuellen Diagramm</p></div><StatusDot online={node.online}/></div><div className="chart-grid"><article className="surface chart-card"><header><div className="chart-icon red"><Cpu size={17}/></div><div><span>CPU-LAST</span><strong>{num(cpu.percent).toFixed(1)}%</strong></div></header><Sparkline points={points} metric={m=>num(m.cpu?.percent)}/></article><article className="surface chart-card"><header><div className="chart-icon blue"><MemoryStick size={17}/></div><div><span>RAM-AUSLASTUNG</span><strong>{num(memory.percent).toFixed(1)}%</strong></div></header><Sparkline points={points} metric={m=>num(m.memory?.percent)} color="var(--blue)"/></article><article className="surface chart-card"><header><div className="chart-icon purple"><MonitorCog size={17}/></div><div><span>GPU-LAST</span><strong>{num(gpu.percent).toFixed(1)}%</strong></div></header><Sparkline points={points} metric={m=>num(m.gpus?.[0]?.percent)} color="var(--purple)"/></article></div><section className="surface metadata"><header className="section-head"><div><span className="eyebrow">NODE INFORMATION</span><h2>Systemdetails</h2></div></header><dl><dt>Geräte-ID</dt><dd>{node.machine_id}</dd><dt>Plattform</dt><dd>{node.platform}</dd><dt>Agent-Version</dt><dd>{node.agent_version||"Unbekannt"}</dd><dt>Erster Kontakt</dt><dd>{new Date(node.created_at).toLocaleString("de-DE")}</dd><dt>Letzter Kontakt</dt><dd>{node.last_seen_at?new Date(node.last_seen_at).toLocaleString("de-DE"):"Noch nie"}</dd><dt>Status</dt><dd><StatusDot online={node.online}/></dd></dl></section></div>
}

function SettingsPage({theme,onTheme,onToken}:{theme:Theme;onTheme:(v:Theme)=>void;onToken:()=>void}){
  return <div className="settings-page"><section className="surface settings-card"><header className="section-head"><div><span className="eyebrow">DARSTELLUNG</span><h2>Theme auswählen</h2></div><Moon size={19}/></header><div className="theme-grid">{THEMES.map(item=><button key={item.id} className={theme===item.id?"active":""} onClick={()=>onTheme(item.id)}><i style={{background:item.color}}/><span>{item.name}</span>{theme===item.id&&<Check size={15}/>}</button>)}</div></section><section className="surface settings-card"><header className="section-head"><div><span className="eyebrow">SICHERHEIT</span><h2>Dashboard-Zugang</h2></div><ShieldCheck size={19}/></header><p>Der Dashboard-Token ist vom Agent-Token getrennt und bleibt ausschließlich in diesem Browser gespeichert.</p><button className="primary" onClick={onToken}><KeyRound size={16}/> Dashboard-Token ändern</button></section></div>
}

function EnrollmentPage({invitations,onCreate,onRevoke,busy}:{invitations:Invitation[];onCreate:(name:string,hours:number)=>Promise<IssuedInvitation>;onRevoke:(id:string)=>Promise<void>;busy:boolean}){
  const [name,setName]=useState(""),[hours,setHours]=useState("168"),[platform,setPlatform]=useState<"windows"|"linux">("linux"),[issued,setIssued]=useState<IssuedInvitation|null>(null),[error,setError]=useState("");
  const create=async(event:React.FormEvent)=>{event.preventDefault();setError("");try{setIssued(await onCreate(name,Number(hours)))}catch{setError("Die Einladung konnte nicht erstellt werden. Bitte erneut versuchen.")}};
  const copy=async(value:string,label:string)=>{try{await navigator.clipboard.writeText(value)}catch{setError(`${label} konnte nicht automatisch kopiert werden. Bitte manuell kopieren.`)}};
  const expires=(item:Invitation)=>item.expires_at?new Date(item.expires_at).toLocaleString("de-DE"):"Läuft nicht ab";
  const server=window.location.hostname;
  const command=platform==="linux"?`cd ~/ncc && sudo ./scripts/install_ncc_agent_service.sh --tailscale ${server}`:`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\install_ncc_service.ps1 -Component Agent -Tailscale -ServerUrl ${server}`;
  const platformName=platform==="linux"?"Linux / CachyOS":"Windows";
  return <div className="enrollment-page">
    <section className="surface enrollment-intro"><div><span className="eyebrow">GERÄT AUFNEHMEN</span><h1>Agent-Einladung erstellen</h1><p>Erstelle einen Token, wähle das Zielsystem und folge den drei klaren Schritten. Der Klartext wird nur einmal angezeigt; der Server speichert ausschließlich einen sicheren Prüfwert.</p></div><UserPlus size={28}/></section>
    <div className="enrollment-grid">
      <section className="surface enrollment-form"><header className="section-head"><div><span className="eyebrow">NEUE EINLADUNG</span><h2>Gerät vorbereiten</h2></div></header><form onSubmit={create}>
        <label>Gerätename<input required maxLength={128} value={name} onChange={event=>setName(event.target.value)} placeholder="z. B. CachyOS Laptop"/></label>
        <label>Zielsystem<select value={platform} onChange={event=>setPlatform(event.target.value as "windows"|"linux")}><option value="linux">Linux / CachyOS</option><option value="windows">Windows</option></select></label>
        <label>Gültigkeit<select value={hours} onChange={event=>setHours(event.target.value)}><option value="24">24 Stunden</option><option value="168">7 Tage</option><option value="720">30 Tage</option><option value="0">Läuft nicht ab</option></select></label>
        {error&&<small className="form-error">{error}</small>}<button className="primary" disabled={busy} type="submit"><KeyRound size={16}/> Einladung erzeugen</button>
      </form></section>
      {issued?<section className="surface token-reveal"><span className="eyebrow">SCHRITT 1 · NUR JETZT SICHTBAR</span><h2>{platformName} für {issued.name} einrichten</h2><p>Erst den Token kopieren. Auf dem Zielgerät wird er anschließend verdeckt abgefragt.</p><div><code>{issued.token}</code><button onClick={()=>void copy(issued.token,"Der Token")} aria-label="Token kopieren"><Copy size={17}/></button></div><div className="setup-step"><span>SCHRITT 2 · AUF DEM ZIELGERÄT AUSFÜHREN</span><div><code>{command}</code><button onClick={()=>void copy(command,"Der Installationsbefehl")} aria-label="Installationsbefehl kopieren"><Copy size={17}/></button></div></div><ol className="setup-guide"><li>Im NCC-Projektordner ausführen. Unter Linux liegt er normalerweise in <code>~/ncc</code>.</li><li>Administratorfreigabe bestätigen und den kopierten Agent-Token einfügen. Die Eingabe bleibt unsichtbar.</li><li>Der Dienst startet automatisch; das Gerät erscheint kurz darauf in der Fleet.</li></ol><small>Der Token ist nicht Bestandteil des Befehls und bleibt somit aus der Shell-Historie heraus.</small></section>:<section className="surface enrollment-help"><KeyRound size={27}/><h2>So funktioniert es</h2><ol><li>Gerät und Zielsystem wählen.</li><li>Einladungstoken einmalig kopieren.</li><li>Passenden Befehl auf dem Zielgerät ausführen und Token verdeckt einfügen.</li></ol></section>}
    </div>
    <section className="surface invitation-list"><header className="section-head"><div><span className="eyebrow">EINLADUNGEN</span><h2>Token-Verwaltung</h2></div><b>{invitations.filter(item=>item.status==="ready").length} AKTIV</b></header><div className="invitation-rows">{invitations.map(item=><article key={item.token_id}><div><strong>{item.name}</strong><span>Erstellt: {new Date(item.created_at).toLocaleString("de-DE")} · {expires(item)}</span>{item.node_name&&<small>Verbunden mit: {item.node_name}</small>}</div><span className={`invitation-status ${item.status}`}>{item.status==="ready"?"Bereit":item.status==="bound"?"Gebunden":item.status==="expired"?"Abgelaufen":"Widerrufen"}</span>{(item.status==="ready"||item.status==="bound")&&<button onClick={()=>void onRevoke(item.token_id)} disabled={busy} title="Einladung widerrufen"><Ban size={15}/></button>}</article>)}{!invitations.length&&<div className="empty"><UserPlus size={30}/><strong>Noch keine Einladungen</strong><span>Erstelle den ersten Token für ein weiteres Gerät.</span></div>}</div></section>
  </div>
}

function Login({onSave,error}:{onSave:(value:string)=>void;error:boolean}){
  const [value,setValue]=useState("");
  return <div className="login"><div className="login-glow"/><section><Brand/><div className="login-icon"><KeyRound size={26}/></div><span className="eyebrow">GESCHÜTZTER ZUGANG</span><h1>Willkommen, Commander.</h1><p>Gib den Dashboard-Token deines NCC-Servers ein. Beim lokalen Zugriff kann das Feld leer bleiben.</p><form onSubmit={event=>{event.preventDefault();onSave(value)}}><label>Dashboard-Token<input autoFocus type="password" value={value} onChange={e=>setValue(e.target.value)} placeholder="Token eingeben"/></label>{error&&<small className="form-error">Der Token wurde nicht akzeptiert.</small>}<button className="primary" type="submit"><ShieldCheck size={17}/> Verbindung herstellen</button></form></section></div>
}

function App(){
  const [theme,setTheme]=useState<Theme>(()=>(localStorage.getItem("ncc-fleet-theme") as Theme)||"nightmare");
  const [token,setToken]=useState(()=>localStorage.getItem("ncc-dashboard-token")||"");
  const [authenticated,setAuthenticated]=useState<boolean|null>(null),[authError,setAuthError]=useState(false);
  const [nodes,setNodes]=useState<Node[]>([]),[summary,setSummary]=useState<Summary|null>(null),[invitations,setInvitations]=useState<Invitation[]>([]),[selectedId,setSelectedId]=useState(""),[points,setPoints]=useState<Telemetry[]>([]);
  const [page,setPage]=useState<Page>("fleet"),[query,setQuery]=useState(""),[loading,setLoading]=useState(true),[sidebar,setSidebar]=useState(false),[clock,setClock]=useState(new Date());
  const selected=nodes.find(node=>node.node_id===selectedId)||nodes[0]||null;
  const load=useCallback(async(silent=false)=>{if(!silent)setLoading(true);try{const [nextNodes,nextSummary,nextInvitations]=await Promise.all([getJson<Node[]>("/api/v1/fleet/nodes",token),getJson<Summary>("/api/v1/fleet/summary",token),getJson<Invitation[]>("/api/v1/agent-invitations",token)]);setNodes(nextNodes);setSummary(nextSummary);setInvitations(nextInvitations);setAuthenticated(true);setAuthError(false);setSelectedId(current=>nextNodes.some(node=>node.node_id===current)?current:(nextNodes[0]?.node_id||""))}catch(error){if((error as Error&{status?:number}).status===401){setAuthenticated(false);setAuthError(true)}}finally{setLoading(false)}},[token]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;localStorage.setItem("ncc-fleet-theme",theme)},[theme]);
  useEffect(()=>{void load();const poll=window.setInterval(()=>void load(true),5000);return()=>clearInterval(poll)},[load]);
  useEffect(()=>{const timer=window.setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(timer)},[]);
  useEffect(()=>{if(!selected)return;getJson<Telemetry[]>(`/api/v1/fleet/nodes/${selected.node_id}/telemetry?limit=120`,token).then(setPoints).catch(()=>setPoints([]))},[selected?.node_id,selected?.latest?.recorded_at,token]);
  const saveToken=(value:string)=>{localStorage.setItem("ncc-dashboard-token",value);setToken(value);setAuthenticated(null);setAuthError(false)};
  const createInvitation=async(name:string,hours:number)=>{const created=await postJson<IssuedInvitation>("/api/v1/agent-invitations",token,{name,expires_hours:hours});const {token:_,...stored}=created;setInvitations(current=>[stored,...current]);return created};
  const revokeInvitation=async(id:string)=>{await postJson<Invitation>(`/api/v1/agent-invitations/${id}/revoke`,token);const response=await fetch(`/api/v1/agent-invitations/${id}`,{method:"DELETE",headers:headers(token)});if(!response.ok)throw new Error("REQUEST");setInvitations(current=>current.filter(item=>item.token_id!==id))};
  const nav=useMemo(()=>[{id:"fleet" as Page,label:"Fleet Übersicht",icon:<LayoutDashboard size={17}/>},{id:"telemetry" as Page,label:"Telemetrie",icon:<CircleGauge size={17}/>},{id:"onboarding" as Page,label:"Gerät hinzufügen",icon:<UserPlus size={17}/>},{id:"settings" as Page,label:"Einstellungen",icon:<Settings size={17}/>}],[]);
  if(authenticated!==true)return <Login onSave={saveToken} error={authenticated===false&&authError}/>;
  const title=page==="fleet"?"Fleet Command":page==="telemetry"?"Telemetry Center":page==="onboarding"?"Gerät hinzufügen":"System Settings";
  return <div className="shell"><aside className={sidebar?"open":""}><div className="aside-top"><Brand/><button className="close-menu" onClick={()=>setSidebar(false)}><X size={19}/></button></div><nav><span>COMMAND CENTER</span>{nav.map(item=><button key={item.id} className={page===item.id?"active":""} onClick={()=>{setPage(item.id);setSidebar(false)}}>{item.icon}<b>{item.label}</b>{page===item.id&&<i/>}</button>)}</nav><div className="server-health"><header><span>SERVER STATUS</span><b><i/> BEREIT</b></header><dl><dt>Nodes online</dt><dd>{summary?.online_nodes||0}</dd><dt>Messpunkte</dt><dd>{summary?.telemetry_points.toLocaleString("de-DE")||0}</dd><dt>API</dt><dd>v1</dd></dl></div><footer><ShieldCheck size={14}/><span>GESICHERTE VERBINDUNG</span><b>v0.5.0-beta.7</b></footer></aside><div className="mobile-scrim" onClick={()=>setSidebar(false)}/><div className="content"><header className="topbar"><button className="menu" onClick={()=>setSidebar(true)}><Menu size={20}/></button><div><span className="eyebrow">NO0BZ INFRASTRUCTURE</span><strong>{title}</strong></div><div className="top-actions"><div className="clock"><Clock3 size={14}/><span>{clock.toLocaleTimeString("de-DE")}</span></div><button aria-label="Benachrichtigungen"><Bell size={17}/><i/></button><button className="refresh" onClick={()=>void load()} aria-label="Aktualisieren"><RefreshCw size={17} className={loading?"spin":""}/></button><div className="commander"><span>C</span><div><b>Commander</b><small>Administrator</small></div></div></div></header><main><div className="summary-grid"><StatCard label="GESAMTE NODES" value={summary?.total_nodes||0} detail="Registrierte Agenten" icon={<Server size={20}/>} /><StatCard label="ONLINE" value={summary?.online_nodes||0} detail="Aktiv verbunden" icon={<Wifi size={20}/>} tone="green"/><StatCard label="OFFLINE" value={summary?.offline_nodes||0} detail="Verbindung getrennt" icon={<WifiOff size={20}/>} tone="muted"/><StatCard label="MESSPUNKTE" value={(summary?.telemetry_points||0).toLocaleString("de-DE")} detail="In der Datenbank" icon={<Activity size={20}/>} tone="blue"/></div>{page==="fleet"?<Fleet nodes={nodes} selected={selected} onSelect={setSelectedId} query={query} onQuery={setQuery}/>:page==="telemetry"?<TelemetryPage node={selected} points={points}/>:page==="onboarding"?<EnrollmentPage invitations={invitations} onCreate={createInvitation} onRevoke={revokeInvitation} busy={loading}/>:<SettingsPage theme={theme} onTheme={setTheme} onToken={()=>setAuthenticated(false)}/>}</main><footer className="statusbar"><span><i/> NCC SERVER VERBUNDEN</span><b>{selected?`${selected.display_name} · ${ago(selected.last_seen_at)}`:"WARTE AUF AGENTEN"}</b><span>{clock.toLocaleDateString("de-DE")}</span></footer></div></div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
