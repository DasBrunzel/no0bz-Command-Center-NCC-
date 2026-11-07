import type { SVGProps } from "react";

/** Small pictogram set in the style of control-panel engravings: 1.75 px strokes on a 24 grid. */
const paths = {
  overview: "M3 12h4l2-5 3 10 2-5h7",
  fleet: "M4 6h16M4 12h16M4 18h16M8 4v4M14 10v4M10 16v4",
  hardware: "M8 8h8v8H8zM10 3v3M14 3v3M10 18v3M14 18v3M3 10h3M3 14h3M18 10h3M18 14h3",
  games: "M7 9v4M5 11h4M15 10.5h.01M17.5 12.5h.01M8 6h8a5 5 0 0 1 5 5v1.5a3.5 3.5 0 0 1-6.3 2.1L14 14h-4l-.7.6A3.5 3.5 0 0 1 3 12.5V11a5 5 0 0 1 5-5Z",
  chat: "M4 5h16v11H9l-5 4z",
  enroll: "M12 4v16M4 12h16M7 7l10 10",
  releases: "M12 3v12M7 10l5 5 5-5M5 20h14",
  settings: "M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7ZM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  search: "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM20 20l-4.8-4.8",
  close: "M6 6l12 12M18 6 6 18",
  plus: "M12 5v14M5 12h14",
  check: "M5 12.5 10 17 19 7",
  copy: "M9 9h10v11H9zM5 15V4h10",
  chevron: "M9 6l6 6-6 6",
  back: "M15 6l-6 6 6 6",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 20h4",
  gamepad: "M6 12h4M8 10v4M15 11h.01M18 13h.01M7 6h10a5 5 0 0 1 0 12H7A5 5 0 0 1 7 6Z",
  power: "M12 3v8M7 6.5a7 7 0 1 0 10 0",
  refresh: "M20 6v5h-5M4 18v-5h5M18.5 9A7 7 0 0 0 6 7.5M5.5 15a7 7 0 0 0 12.5 1.5",
  upload: "M12 16V4M7 9l5-5 5 5M5 20h14",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  edit: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  unlink: "M15.5 15.5 18.6 12.4a4 4 0 0 0-5.7-5.7L12 7.5M8.5 8.5 5.4 11.6a4 4 0 0 0 5.7 5.7l.9-.8M4 4l16 16",
  attach: "M20 11.5 12 19.5a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.7 17.2a1.7 1.7 0 0 1-2.4-2.4L15 7",
  send: "M4 12 20 4l-6 16-3-7z",
  sun: "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10ZM12 1v3M12 20v3M1 12h3M20 12h3",
  moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z",
  network: "M12 20V8M8 12l4-4 4 4M5 4h14",
  server: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  warning: "M12 4 2.5 20h19zM12 10v4M12 17h.01",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 11v5M12 8h.01",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21a8 8 0 0 1 16 0",
  switch: "M4 7h10l6 10M4 17h6M14 7l-4 10",
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 20, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={paths[name]} />
    </svg>
  );
}
