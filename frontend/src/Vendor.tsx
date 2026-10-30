import React from "react";
import {
  siAcer, siAmd, siApple, siAsus, siCorsair, siDell, siDeepcool, siHp, siIntel, siLenovo, siLg, siMsi,
  siNvidia, siNzxt, siQualcomm, siRaspberrypi, siSamsung, siSeagate, siToshiba,
} from "simple-icons";

type SimpleIcon = { title: string; hex: string; path: string };
type Vendor = { label: string; icon?: SimpleIcon; short?: string };

// Ordered: the first match wins, so "AMD Radeon" is AMD rather than a board maker.
const VENDORS: [RegExp, Vendor][] = [
  [/\bnvidia|geforce|quadro\b/i, { label: "NVIDIA", icon: siNvidia }],
  [/\bamd\b|ryzen|radeon|threadripper|epyc/i, { label: "AMD", icon: siAmd }],
  [/\bintel\b|core\(tm\)|\bcore i\d|\bxeon\b|\barc a\d/i, { label: "Intel", icon: siIntel }],
  [/\bqualcomm|snapdragon/i, { label: "Qualcomm", icon: siQualcomm }],
  [/\bapple\b|\bm[1-4] (pro|max|ultra)?/i, { label: "Apple", icon: siApple }],
  [/\basus|\brog\b|\btuf\b|\bprime [abxz]\d/i, { label: "ASUS", icon: siAsus }],
  [/\bmsi\b|micro-star/i, { label: "MSI", icon: siMsi }],
  [/gigabyte|\baorus\b/i, { label: "Gigabyte", short: "GB" }],
  [/asrock/i, { label: "ASRock", short: "AR" }],
  [/samsung/i, { label: "Samsung", icon: siSamsung }],
  [/seagate/i, { label: "Seagate", icon: siSeagate }],
  [/toshiba|kioxia/i, { label: "Toshiba", icon: siToshiba }],
  [/corsair/i, { label: "Corsair", icon: siCorsair }],
  [/crucial|^ct\d{3,}|micron/i, { label: "Crucial", short: "CR" }],
  [/sandisk|^sdssd/i, { label: "SanDisk", short: "SD" }],
  [/western digital|^wdc?\b|^wd[a-z0-9]/i, { label: "WD", short: "WD" }],
  [/kingston|hyperx/i, { label: "Kingston", short: "KG" }],
  [/g\.?\s?skill/i, { label: "G.Skill", short: "GS" }],
  [/\bnzxt\b/i, { label: "NZXT", icon: siNzxt }],
  [/deepcool/i, { label: "DeepCool", icon: siDeepcool }],
  [/\blenovo\b|thinkpad/i, { label: "Lenovo", icon: siLenovo }],
  [/\bdell\b|alienware/i, { label: "Dell", icon: siDell }],
  [/\bhp\b|hewlett|omen\b|victus/i, { label: "HP", icon: siHp }],
  [/\bacer\b|predator/i, { label: "Acer", icon: siAcer }],
  [/\blg\b/i, { label: "LG", icon: siLg }],
  [/raspberry/i, { label: "Raspberry Pi", icon: siRaspberrypi }],
];

export function vendorOf(name: unknown): Vendor | null {
  const text = typeof name === "string" ? name.trim() : "";
  if (!text) return null;
  return VENDORS.find(([pattern]) => pattern.test(text))?.[1] ?? null;
}

// Several brand colours are black or very dark; in the dark theme those would
// disappear, so they fall back to the text colour.
const tooDark = (hex: string) => {
  const value = parseInt(hex, 16);
  const [r, g, b] = [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 70;
};

export function VendorLogo({ name, size = 18 }: { name: unknown; size?: number }) {
  const vendor = vendorOf(name);
  if (!vendor) return null;
  if (!vendor.icon) {
    return <span className="vendor-badge" title={vendor.label} style={{ fontSize: Math.max(9, size * 0.5), height: size, minWidth: size }}>{vendor.short}</span>;
  }
  const color = tooDark(vendor.icon.hex) ? "var(--text)" : `#${vendor.icon.hex}`;
  return <svg className="vendor-logo" role="img" aria-label={vendor.label} width={size} height={size} viewBox="0 0 24 24">
    <title>{vendor.label}</title>
    <path d={vendor.icon.path} fill={color} />
  </svg>;
}
