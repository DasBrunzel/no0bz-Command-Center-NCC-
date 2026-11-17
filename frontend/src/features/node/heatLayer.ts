import L from "leaflet";

/**
 * Minimal heatmap layer for Leaflet: every cell is drawn as a soft dot whose
 * alpha adds up, then the alpha is mapped onto a colour ramp. Same technique
 * as simpleheat, without an extra dependency.
 */
export type HeatCell = [number, number, number];

const RAMP: Array<[number, string]> = [
  [0.0, "rgba(46,98,201,0)"],
  [0.25, "#2e62c9"],
  [0.5, "#258f33"],
  [0.75, "#f2ab19"],
  [1.0, "#d42320"],
];

function palette(): Uint8ClampedArray {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 1;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createLinearGradient(0, 0, 256, 0);
  for (const [stop, color] of RAMP) gradient.addColorStop(stop, color);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 256, 1);
  return ctx.getImageData(0, 0, 256, 1).data;
}

export class HeatLayer extends L.Layer {
  private cells: HeatCell[];
  private canvas: HTMLCanvasElement | null = null;
  private colors: Uint8ClampedArray | null = null;

  constructor(cells: HeatCell[]) {
    super();
    this.cells = cells;
  }

  setCells(cells: HeatCell[]): void {
    this.cells = cells;
    this.redraw();
  }

  onAdd(map: L.Map): this {
    this.canvas = L.DomUtil.create("canvas", "heat-layer leaflet-zoom-hide") as HTMLCanvasElement;
    this.canvas.style.pointerEvents = "none";
    // The dashboard caps images and canvases at 100 % width; Leaflet's pane is 0 px wide.
    this.canvas.style.maxWidth = "none";
    this.canvas.style.maxHeight = "none";
    map.getPanes().overlayPane.appendChild(this.canvas);
    map.on("moveend zoomend resize", this.redraw, this);
    this.redraw();
    return this;
  }

  onRemove(map: L.Map): this {
    map.off("moveend zoomend resize", this.redraw, this);
    this.canvas?.remove();
    this.canvas = null;
    return this;
  }

  private redraw(): void {
    const map = this._map as L.Map | undefined;
    const canvas = this.canvas;
    if (!map || !canvas) return;
    const size = map.getSize();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = size.x * ratio;
    canvas.height = size.y * ratio;
    canvas.style.width = `${size.x}px`;
    canvas.style.height = `${size.y}px`;
    L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]));
    const ctx = canvas.getContext("2d");
    if (!ctx || this.cells.length === 0) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);

    // Dots grow a little with zoom so streets stay readable when zoomed in.
    const radius = Math.max(8, Math.min(28, (map.getZoom() - 6) * 2.4));
    const max = Math.max(...this.cells.map((cell) => cell[2]));
    const bounds = map.getBounds().pad(0.1);
    for (const [lat, lon, count] of this.cells) {
      if (!bounds.contains([lat, lon])) continue;
      const p = map.latLngToContainerPoint([lat, lon]);
      const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius);
      // Square root keeps rarely visited places visible next to home.
      const weight = Math.min(1, 0.15 + 0.85 * Math.sqrt(count / max));
      gradient.addColorStop(0, `rgba(0,0,0,${weight})`);
      gradient.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(p.x - radius, p.y - radius, radius * 2, radius * 2);
    }

    this.colors ??= palette();
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = image.data;
    for (let i = 3; i < data.length; i += 4) {
      const alpha = data[i]!;
      if (alpha === 0) continue;
      const offset = alpha * 4;
      data[i - 3] = this.colors[offset]!;
      data[i - 2] = this.colors[offset + 1]!;
      data[i - 1] = this.colors[offset + 2]!;
      data[i] = Math.min(230, alpha * 1.6);
    }
    ctx.putImageData(image, 0, 0);
  }
}
