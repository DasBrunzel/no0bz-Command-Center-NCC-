import { useId, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode, type RefObject } from "react";

/* Hand-built SVG charts following the dataviz mark specs: 2 px lines, 10 %
 * area wash, hairline grid, crosshair tooltip on lines, per-mark tooltip on
 * bars and cells, legend for ≥ 2 series and a table view for every chart. */

function useWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.clientWidth);
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry!.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const n = value / power;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * power;
}

const tick = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1, notation: "compact" });

/* ── Sparkline: tiny trend, no axes ───────────────────────────────── */

export function Sparkline({ values, max, label, height = 28, tone = "var(--c-ink-2)" }: { values: Array<number | null>; max?: number; label: string; height?: number; tone?: string }) {
  const clean = values.map((value) => value ?? 0);
  const width = 120;
  const top = max ?? Math.max(1, ...clean);
  if (clean.length < 2) return <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: noch kein Verlauf`} />;
  const step = width / (clean.length - 1);
  const points = clean.map((value, index) => [index * step, height - 2 - (Math.min(value, top) / top) * (height - 4)] as const);
  const line = points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const last = points[points.length - 1]!;
  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={label}>
      <path d={`${line}L${width},${height}L0,${height}Z`} fill={tone} opacity={0.1} />
      <path d={line} fill="none" stroke={tone} strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill={tone} />
    </svg>
  );
}

/* ── Line chart with crosshair ───────────────────────────────────── */

export interface Series {
  name: string;
  color: string;
  values: Array<number | null>;
}

export function LineChart({
  series, labels, unit, height = 180, format = (value) => tick.format(value), max, title, area = true,
}: {
  series: Series[]; labels: string[]; unit: string; height?: number; format?: (value: number) => string; max?: number; title: string; area?: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const tableId = useId();
  const count = labels.length;
  const pad = { top: 10, right: 12, bottom: 22, left: 44 };
  const innerW = Math.max(10, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const peak = Math.max(0, ...series.flatMap((item) => item.values.map((value) => value ?? 0)));
  const top = max ?? niceMax(peak * 1.1);
  const x = (index: number) => pad.left + (count <= 1 ? innerW / 2 : (index / (count - 1)) * innerW);
  const y = (value: number) => pad.top + innerH - (Math.min(value, top) / top) * innerH;
  const ticks = [0, top / 2, top];

  const pathOf = (values: Array<number | null>) => {
    let d = "";
    values.forEach((value, index) => {
      if (value == null) return;
      d += `${d && values[index - 1] != null ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`;
    });
    return d;
  };

  const pick = (clientX: number, element: Element) => {
    const rect = element.getBoundingClientRect();
    const rel = clientX - rect.left - pad.left;
    const index = Math.round((rel / innerW) * (count - 1));
    setHover(Math.max(0, Math.min(count - 1, index)));
  };
  const onKey = (event: KeyboardEvent) => {
    if (event.key === "ArrowLeft") setHover((value) => Math.max(0, (value ?? count) - 1));
    else if (event.key === "ArrowRight") setHover((value) => Math.min(count - 1, (value ?? -1) + 1));
    else if (event.key === "Escape") setHover(null);
    else return;
    event.preventDefault();
  };

  const tipLeft = hover != null ? Math.min(Math.max(x(hover) + 12, 0), Math.max(0, width - 170)) : 0;

  return (
    <figure className="chart">
      {series.length > 1 && <Legend items={series.map((item) => ({ name: item.name, color: item.color, kind: "line" }))} />}
      <div
        ref={ref}
        className="chart-plot"
        style={{ blockSize: height }}
        tabIndex={count ? 0 : -1}
        role="img"
        aria-label={`${title}. Pfeiltasten zeigen einzelne Werte.`}
        aria-describedby={tableId}
        onPointerMove={(event: PointerEvent) => pick(event.clientX, event.currentTarget)}
        onPointerLeave={() => setHover(null)}
        onKeyDown={onKey}
        onBlur={() => setHover(null)}
      >
        {width > 0 && (
          <svg width={width} height={height} aria-hidden="true">
            {ticks.map((value) => (
              <g key={value}>
                <line x1={pad.left} x2={width - pad.right} y1={y(value)} y2={y(value)} className="chart-grid" />
                <text x={pad.left - 6} y={y(value)} className="chart-tick" textAnchor="end" dominantBaseline="middle">{format(value)}</text>
              </g>
            ))}
            {count > 1 && [0, Math.floor((count - 1) / 2), count - 1].map((index) => (
              <text key={index} x={x(index)} y={height - 6} className="chart-tick" textAnchor={index === 0 ? "start" : index === count - 1 ? "end" : "middle"}>{labels[index]}</text>
            ))}
            {series.map((item) => {
              const d = pathOf(item.values);
              return (
                <g key={item.name}>
                  {area && series.length === 1 && d && <path d={`${d}L${x(count - 1)},${y(0)}L${x(0)},${y(0)}Z`} fill={item.color} opacity={0.1} />}
                  <path d={d} fill="none" stroke={item.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                </g>
              );
            })}
            {hover != null && (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={pad.top} y2={pad.top + innerH} className="chart-crosshair" />
                {series.map((item) => {
                  const value = item.values[hover];
                  return value == null ? null : <circle key={item.name} cx={x(hover)} cy={y(value)} r={4} fill={item.color} className="chart-dot" />;
                })}
              </g>
            )}
          </svg>
        )}
        {hover != null && (
          <div className="chart-tip" style={{ insetInlineStart: tipLeft }}>
            <span className="chart-tip-label">{labels[hover]}</span>
            {series.map((item) => (
              <span key={item.name} className="chart-tip-row">
                <i style={{ background: item.color }} />
                <b>{item.values[hover] == null ? "–" : `${format(item.values[hover]!)} ${unit}`}</b>
                {series.length > 1 && <span>{item.name}</span>}
              </span>
            ))}
          </div>
        )}
      </div>
      <ChartTable id={tableId} title={title} head={["Zeit", ...series.map((item) => `${item.name} (${unit})`)]} rows={labels.map((label, index) => [label, ...series.map((item) => (item.values[index] == null ? "–" : format(item.values[index]!)))])} />
    </figure>
  );
}

/* ── Columns: one value per category / day ───────────────────────── */

export function Columns({
  items, unit, height = 160, format = (value) => tick.format(value), title, color = "var(--c-series-1)", highlightLast,
}: {
  items: Array<{ label: string; value: number; detail?: string }>; unit: string; height?: number; format?: (value: number) => string; title: string; color?: string; highlightLast?: boolean;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const tableId = useId();
  const pad = { top: 8, right: 4, bottom: 22, left: 40 };
  const innerW = Math.max(10, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const top = niceMax(Math.max(0, ...items.map((item) => item.value)) * 1.05);
  const band = items.length ? innerW / items.length : innerW;
  const bar = Math.min(24, Math.max(2, band - 2));
  const y = (value: number) => pad.top + innerH - (value / top) * innerH;
  const labelEvery = Math.max(1, Math.ceil(items.length / Math.max(1, Math.floor(innerW / 56))));

  return (
    <figure className="chart">
      <div ref={ref} className="chart-plot" style={{ blockSize: height }} onPointerLeave={() => setHover(null)}>
        {width > 0 && (
          <svg width={width} height={height} role="group" aria-label={title} aria-describedby={tableId}>
            {[0, top / 2, top].map((value) => (
              <g key={value} aria-hidden="true">
                <line x1={pad.left} x2={width - pad.right} y1={y(value)} y2={y(value)} className="chart-grid" />
                <text x={pad.left - 6} y={y(value)} className="chart-tick" textAnchor="end" dominantBaseline="middle">{format(value)}</text>
              </g>
            ))}
            {items.map((item, index) => {
              const cx = pad.left + band * index + band / 2;
              const h = Math.max(0, y(0) - y(item.value));
              const r = Math.min(4, h, bar / 2);
              const x0 = cx - bar / 2;
              const yTop = y(item.value);
              const d = h <= 0 ? "" : `M${x0},${y(0)}V${yTop + r}Q${x0},${yTop} ${x0 + r},${yTop}H${x0 + bar - r}Q${x0 + bar},${yTop} ${x0 + bar},${yTop + r}V${y(0)}Z`;
              const active = hover === index;
              return (
                <g
                  key={item.label + index}
                  tabIndex={0}
                  role="img"
                  aria-label={`${item.label}: ${format(item.value)} ${unit}${item.detail ? `, ${item.detail}` : ""}`}
                  onPointerEnter={() => setHover(index)}
                  onFocus={() => setHover(index)}
                  onBlur={() => setHover(null)}
                  className="chart-bar"
                >
                  <rect x={pad.left + band * index} y={pad.top} width={band} height={innerH} fill="transparent" />
                  {d && <path d={d} fill={color} opacity={hover == null || active ? (highlightLast && index !== items.length - 1 && hover == null ? 0.55 : 1) : 0.45} />}
                  {index % labelEvery === 0 && <text x={cx} y={height - 6} className="chart-tick" textAnchor="middle" aria-hidden="true">{item.label}</text>}
                </g>
              );
            })}
          </svg>
        )}
        {hover != null && items[hover] && (
          <div className="chart-tip" style={{ insetInlineStart: Math.min(Math.max(pad.left + band * hover + band / 2 + 10, 0), Math.max(0, width - 170)) }}>
            <span className="chart-tip-label">{items[hover]!.label}</span>
            <span className="chart-tip-row"><i style={{ background: color }} /><b>{format(items[hover]!.value)} {unit}</b></span>
            {items[hover]!.detail && <span className="chart-tip-row"><span>{items[hover]!.detail}</span></span>}
          </div>
        )}
      </div>
      <ChartTable id={tableId} title={title} head={["", unit]} rows={items.map((item) => [item.label, format(item.value)])} />
    </figure>
  );
}

/* ── Heatmap: weekday × hour, sequential single hue ──────────────── */

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

export function Heatmap({ rows, title, format }: { rows: number[][]; title: string; format: (seconds: number) => string }) {
  const [hover, setHover] = useState<{ day: number; hour: number } | null>(null);
  const tableId = useId();
  const peak = Math.max(1, ...rows.flat());
  return (
    <figure className="chart heatmap" onPointerLeave={() => setHover(null)}>
      <div className="heatmap-grid" role="img" aria-label={title} aria-describedby={tableId}>
        <span />
        {Array.from({ length: 24 }, (_, hour) => (
          <span key={hour} className="heatmap-hour" aria-hidden="true">{hour % 6 === 0 ? hour : ""}</span>
        ))}
        {rows.map((row, day) => (
          <Row key={day} label={WEEKDAYS[day] ?? ""}>
            {row.map((value, hour) => (
              <span
                key={hour}
                className="heatmap-cell"
                data-active={hover?.day === day && hover.hour === hour || undefined}
                style={{ "--v": value / peak } as CSSProperties}
                onPointerEnter={() => setHover({ day, hour })}
              />
            ))}
          </Row>
        ))}
      </div>
      <p className="heatmap-readout" aria-live="polite">
        {hover ? `${WEEKDAYS[hover.day]} ${hover.hour}–${hover.hour + 1} Uhr: ${format(rows[hover.day]?.[hover.hour] ?? 0)}` : "Zeig auf ein Feld für die Spielzeit dieser Stunde."}
      </p>
      <ChartTable
        id={tableId}
        title={title}
        head={["Tag", ...Array.from({ length: 24 }, (_, hour) => `${hour}`)]}
        rows={rows.map((row, day) => [WEEKDAYS[day] ?? "", ...row.map((value) => (value ? format(value) : ""))])}
      />
    </figure>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <span className="heatmap-day" aria-hidden="true">{label}</span>
      {children}
    </>
  );
}

/* ── Legend & table view ─────────────────────────────────────────── */

export function Legend({ items }: { items: Array<{ name: string; color: string; kind?: "line" | "rect" }> }) {
  return (
    <ul className="legend plain" role="list">
      {items.map((item) => (
        <li key={item.name}>
          <i data-kind={item.kind ?? "rect"} style={{ background: item.color }} />
          {item.name}
        </li>
      ))}
    </ul>
  );
}

function ChartTable({ id, title, head, rows }: { id: string; title: string; head: string[]; rows: string[][] }) {
  return (
    <details className="chart-table" id={id}>
      <summary>Als Tabelle</summary>
      <div className="table-wrap">
        <table className="table">
          <caption className="visually-hidden">{title}</caption>
          <thead><tr>{head.map((cell, index) => <th key={index} className={index ? "r" : undefined}>{cell}</th>)}</tr></thead>
          <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column} className={column ? "r" : undefined}>{cell}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </details>
  );
}
