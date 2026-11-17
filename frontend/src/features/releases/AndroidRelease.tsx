import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, qk } from "../../api/endpoints";
import { useCan } from "../../app/auth";
import { useToast } from "../../components/toast";
import { CopyButton, ErrorState, Loading, RelTime } from "../../components/ui";
import { fmtBytes } from "../../lib/format";

/** Reads "ncc-android-0.6.0-6.apk" as version 0.6.0 with version code 6 (the build script names files this way). */
export function versionFromFileName(name: string): { versionName: string; versionCode: number } | null {
  const match = /ncc-android-([0-9A-Za-z.+_]+)-(\d+)\.apk$/i.exec(name);
  return match ? { versionName: match[1]!, versionCode: Number(match[2]) } : null;
}

/** Private distribution of the NCC Android app: the newest APK the phones may install. */
export function AndroidReleasePanel() {
  const can = useCan();
  const toast = useToast();
  const client = useQueryClient();
  const release = useQuery({ queryKey: qk.androidRelease, queryFn: api.android.release });
  const [file, setFile] = useState<File | null>(null);
  const [versionName, setVersionName] = useState("");
  const [versionCode, setVersionCode] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const choose = (picked: File | null) => {
    setFile(picked);
    const parsed = picked ? versionFromFileName(picked.name) : null;
    if (parsed) {
      setVersionName(parsed.versionName);
      setVersionCode(String(parsed.versionCode));
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    try {
      const stored = await api.android.upload(file, Number(versionCode), versionName.trim(), notes);
      client.setQueryData(qk.androidRelease, stored);
      toast.ok(`NCC-App ${stored.version_name} ist verteilt. Verbundene Handys melden das Update sofort.`);
      setFile(null);
      setNotes("");
    } catch (error) {
      toast.fail(error);
    } finally {
      setBusy(false);
    }
  };

  const current = release.data;
  return (
    <section className="panel section" aria-labelledby="android-release-title">
      <div className="panel-head">
        <h2 id="android-release-title">Android-App</h2>
        <p>Updates für die NCC-App, direkt über diesen Server</p>
      </div>
      {release.isPending ? <Loading /> : release.isError && !release.data ? (
        <ErrorState onRetry={() => void release.refetch()}>Die App-Version konnte nicht geladen werden.</ErrorState>
      ) : current ? (
        <dl className="android-release-facts">
          <div><dt>Verteilt</dt><dd><b>{current.version_name}</b> (Build {current.version_code}) · {fmtBytes(current.size)} · <RelTime iso={current.uploaded_at} /></dd></div>
          <div><dt>SHA-256</dt><dd className="code small">{current.sha256.slice(0, 16)}… <CopyButton value={current.sha256} label="SHA-256 kopieren" /></dd></div>
          {current.notes && <div><dt>Notizen</dt><dd>{current.notes}</dd></div>}
        </dl>
      ) : (
        <p className="ink-3 small">Noch keine App-Version hochgeladen.</p>
      )}

      {can.commander && (
        <form className="android-release-form mt-4" onSubmit={(event) => void submit(event)}>
          <label className="field">
            <span>APK-Datei</span>
            <input className="input" type="file" accept=".apk,application/vnd.android.package-archive" onChange={(event) => choose(event.target.files?.[0] ?? null)} />
          </label>
          <div className="android-release-row">
            <label className="field"><span>Version</span><input className="input" value={versionName} onChange={(event) => setVersionName(event.target.value)} placeholder="0.6.0" required /></label>
            <label className="field"><span>Build-Nummer</span><input className="input" value={versionCode} onChange={(event) => setVersionCode(event.target.value.replace(/\D/g, ""))} inputMode="numeric" placeholder="6" required /></label>
          </div>
          <label className="field"><span>Notizen (optional)</span><input className="input" value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={2000} placeholder="Was ist neu?" /></label>
          <p className="form-hint">
            Die Build-Nummer muss höher sein als die verteilte. Android installiert das Update nur, wenn es mit demselben Schlüssel signiert ist wie die App auf dem Handy.
          </p>
          <div className="actions">
            <button type="submit" className="btn btn-primary" disabled={busy || !file || !versionName || !versionCode}>App-Version verteilen</button>
          </div>
        </form>
      )}
    </section>
  );
}
