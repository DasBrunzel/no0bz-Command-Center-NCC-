import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, lazy, Suspense, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { hasLegacyToken } from "../../api/client";
import { POLL, api, qk } from "../../api/endpoints";
import type { ChatAttachment, ChatMessage } from "../../api/types";
import { roleLabel, useAuth } from "../../app/auth";
import { Icon } from "../../components/Icon";
import { useToast } from "../../components/toast";
import { ErrorState, Lamp, Loading } from "../../components/ui";
import { fmtBytes, fmtTime } from "../../lib/format";
import type { Route } from "../../lib/router";
import "./chat.css";

const Markdown = lazy(() => import("./Markdown"));
const PAGE = 50;
const KEEP = 600;

function merge(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const seen = new Set(current.map((message) => message.message_id));
  const added = incoming.filter((message) => !seen.has(message.message_id));
  return added.length ? [...current, ...added].slice(-KEEP) : current;
}

/** Messages: first the newest page, then only those after the last one. */
function useMessages() {
  const client = useQueryClient();
  return useQuery({
    queryKey: qk.chat,
    refetchInterval: POLL.chat,
    queryFn: async () => {
      const previous = client.getQueryData<ChatMessage[]>(qk.chat);
      const last = previous?.[previous.length - 1];
      if (!previous || !last) return api.chat.messages({ limit: PAGE });
      const fresh = await api.chat.messages({ after: last.message_id, limit: 200 });
      return merge(previous, fresh);
    },
  });
}

export default function Chat(_: { route: Route }) {
  const { identity } = useAuth();
  const client = useQueryClient();
  const messages = useMessages();
  const participants = useQuery({ queryKey: qk.participants, queryFn: api.chat.participants, refetchInterval: 60_000 });
  const [olderDone, setOlderDone] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [unseen, setUnseen] = useState(0);
  const log = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const lastCount = useRef(0);
  const restoreFrom = useRef<number | null>(null);
  const list = messages.data ?? [];

  // Keep the view at the bottom unless the reader scrolled up.
  useLayoutEffect(() => {
    const element = log.current;
    if (!element) return;
    if (restoreFrom.current !== null) {
      element.scrollTop = element.scrollHeight - restoreFrom.current;
      restoreFrom.current = null;
    } else if (stick.current) {
      element.scrollTop = element.scrollHeight;
      setUnseen(0);
    } else if (list.length > lastCount.current) {
      setUnseen((value) => value + list.length - lastCount.current);
    }
    lastCount.current = list.length;
  }, [list.length]);

  const onScroll = () => {
    const element = log.current;
    if (!element) return;
    stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
    if (stick.current) setUnseen(0);
  };

  const loadOlder = async () => {
    const first = list[0];
    if (!first || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const older = await api.chat.messages({ before: first.message_id, limit: PAGE });
      if (older.length < PAGE) setOlderDone(true);
      if (log.current) restoreFrom.current = log.current.scrollHeight - log.current.scrollTop;
      client.setQueryData<ChatMessage[]>(qk.chat, (current = []) => {
        const seen = new Set(current.map((message) => message.message_id));
        return [...older.filter((message) => !seen.has(message.message_id)), ...current];
      });
    } finally {
      setLoadingOlder(false);
    }
  };

  const jump = () => {
    stick.current = true;
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
    setUnseen(0);
  };

  return (
    <div className="chat">
      <div className="chat-main">
        <header className="chat-head">
          <h1>Fleet-Chat</h1>
          <details className="chat-people-mobile">
            <summary>{participants.data ? `${participants.data.length} dabei` : "Teilnehmer"}</summary>
            <People list={participants.data} />
          </details>
        </header>

        <div className="chat-log" ref={log} onScroll={onScroll} role="log" aria-live="polite" aria-relevant="additions" aria-label="Nachrichten" tabIndex={0}>
          {messages.isPending ? (
            <Loading label="Nachrichten werden geladen" />
          ) : messages.isError && !messages.data ? (
            <ErrorState onRetry={() => void messages.refetch()}>Der Chat ist gerade nicht erreichbar.</ErrorState>
          ) : list.length === 0 ? (
            <div className="chat-empty">
              <p><b>Funkstille.</b> Noch hat niemand etwas geschrieben – mach den Anfang.</p>
            </div>
          ) : (
            <>
              <div className="chat-older">
                {olderDone || list.length < PAGE ? (
                  <span className="ink-3 xsmall">Anfang des Verlaufs</span>
                ) : (
                  <button type="button" className="btn btn-s" onClick={() => void loadOlder()} disabled={loadingOlder}>{loadingOlder ? "Lädt …" : "Ältere Nachrichten laden"}</button>
                )}
              </div>
              <ol className="plain chat-list" role="list">
                {list.map((message, index) => {
                  const previous = list[index - 1];
                  const day = dayLabel(message.created_at);
                  const newDay = !previous || dayLabel(previous.created_at) !== day;
                  const grouped = !newDay && previous?.sender_name === message.sender_name && new Date(message.created_at).getTime() - new Date(previous.created_at).getTime() < 5 * 60_000;
                  const mine = !!identity && (message.sender_user_id ? message.sender_user_id === identity.userId : message.sender_name === identity.username);
                  return (
                    <Fragment key={message.message_id}>
                      {newDay && <li className="chat-day" aria-hidden="false"><span>{day}</span></li>}
                      <Message message={message} grouped={grouped} mine={mine} />
                    </Fragment>
                  );
                })}
              </ol>
            </>
          )}
        </div>
        {unseen > 0 && (
          <button type="button" className="btn btn-s chat-unseen" onClick={jump}>
            {unseen} neue {unseen === 1 ? "Nachricht" : "Nachrichten"} ↓
          </button>
        )}
        <Composer onSent={(message) => { stick.current = true; client.setQueryData<ChatMessage[]>(qk.chat, (current = []) => merge(current, [message])); }} />
      </div>
      <aside className="chat-people" aria-labelledby="people-title">
        <h2 id="people-title">Dabei</h2>
        <People list={participants.data} />
      </aside>
    </div>
  );
}

function People({ list }: { list: Awaited<ReturnType<typeof api.chat.participants>> | undefined }) {
  if (!list) return <Loading />;
  if (!list.length) return <p className="ink-3 small">Noch niemand.</p>;
  return (
    <ul className="plain people" role="list">
      {list.map((person) => (
        <li key={person.user_id ?? person.display_name}>
          <span className="avatar" aria-hidden="true">{person.display_name.slice(0, 1).toUpperCase()}</span>
          <span>{person.display_name}<small>{roleLabel(person.role)}</small></span>
        </li>
      ))}
    </ul>
  );
}

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(Date.now() - 86_400_000);
  if (date.toDateString() === today.toDateString()) return "Heute";
  if (date.toDateString() === yesterday.toDateString()) return "Gestern";
  return date.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
}

function Message({ message, grouped, mine }: { message: ChatMessage; grouped: boolean; mine: boolean }) {
  return (
    <li className="chat-message" data-grouped={grouped || undefined} data-mine={mine || undefined}>
      <time dateTime={message.created_at} className="chat-time">{fmtTime(message.created_at)}</time>
      <div className="chat-body">
        {!grouped && <b className="chat-sender">{message.sender_name}{message.sender_node_id && <span className="badge">Gerät</span>}</b>}
        {message.body && (
          message.body_format === "markdown" ? (
            <Suspense fallback={<p className="chat-text">{message.body}</p>}>
              <div className="chat-text chat-md"><Markdown text={message.body} /></div>
            </Suspense>
          ) : (
            <p className="chat-text">{message.body}</p>
          )
        )}
        {message.attachment && <Attachment messageId={message.message_id} attachment={message.attachment} />}
      </div>
    </li>
  );
}

function Attachment({ messageId, attachment }: { messageId: string; attachment: ChatAttachment }) {
  const image = /^image\/(png|jpeg|gif|webp)$/.test(attachment.content_type);
  const [blob, setBlob] = useState<string | null>(null);
  const token = hasLegacyToken();
  useEffect(() => {
    if (!token || !image) return;
    let url: string | null = null;
    const controller = new AbortController();
    api.chat.attachment(messageId, controller.signal).then((response) => response.blob()).then((data) => { url = URL.createObjectURL(data); setBlob(url); }).catch(() => undefined);
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [messageId, token, image]);
  const src = token ? blob : attachment.url;
  const download = async () => {
    if (!token) return;
    const response = await api.chat.attachment(messageId);
    const url = URL.createObjectURL(await response.blob());
    const link = Object.assign(document.createElement("a"), { href: url, download: attachment.name });
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div className="chat-attachment">
      {image && src && <a href={src} target="_blank" rel="noopener"><img src={src} alt={attachment.name} loading="lazy" /></a>}
      <a
        className="chat-file"
        href={token ? "#" : attachment.url}
        download={attachment.name}
        onClick={(event) => { if (token) { event.preventDefault(); void download(); } }}
      >
        <Icon name="attach" size={16} /> {attachment.name} <span className="ink-3">· {fmtBytes(attachment.size)}</span>
      </a>
    </div>
  );
}

function Composer({ onSent }: { onSent: (message: ChatMessage) => void }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [markdown, setMarkdown] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);

  const send = async (event?: FormEvent) => {
    event?.preventDefault();
    const body = text.trimEnd();
    if (!body && !file) return;
    setBusy(true);
    try {
      const format = markdown ? "markdown" : "plain";
      const message = file ? await api.chat.upload(file, body, format) : await api.chat.send(body, format);
      onSent(message);
      setText("");
      setFile(null);
      if (input.current) input.current.value = "";
      area.current?.focus();
    } catch (error) {
      toast.fail(error, "Die Nachricht wurde nicht gesendet.");
    } finally {
      setBusy(false);
    }
  };

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  };

  return (
    <form className="composer" onSubmit={(event) => void send(event)}>
      {file && (
        <p className="composer-file">
          <Icon name="attach" size={16} /> {file.name} <span className="ink-3">({fmtBytes(file.size)})</span>
          <button type="button" className="btn btn-quiet btn-icon btn-s" onClick={() => { setFile(null); if (input.current) input.current.value = ""; }} aria-label="Anhang entfernen"><Icon name="close" /></button>
        </p>
      )}
      <label className="visually-hidden" htmlFor="chat-input">Nachricht</label>
      <textarea id="chat-input" ref={area} className="textarea" rows={1} maxLength={20_000} placeholder="Nachricht an alle – Enter sendet, Umschalt+Enter macht eine neue Zeile" value={text} onChange={(event) => setText(event.target.value)} onKeyDown={onKey} />
      <div className="composer-bar">
        <input ref={input} type="file" hidden onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <button type="button" className="btn btn-quiet btn-s" onClick={() => input.current?.click()}><Icon name="attach" /> Datei</button>
        <label className="switch small"><input type="checkbox" checked={markdown} onChange={(event) => setMarkdown(event.target.checked)} /> Markdown</label>
        <span className="grow" />
        <span className="ink-3 xsmall composer-count" aria-live="off">{text.length > 18_000 ? `${20_000 - text.length} Zeichen übrig` : ""}</span>
        <button type="submit" className="btn btn-primary" disabled={busy || (!text.trim() && !file)}>
          {busy ? <Lamp state="shunt" size="s" blink /> : <Icon name="send" />} Senden
        </button>
      </div>
    </form>
  );
}
