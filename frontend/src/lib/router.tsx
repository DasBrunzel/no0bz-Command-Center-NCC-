import { useSyncExternalStore, type AnchorHTMLAttributes, type MouseEvent } from "react";
import { flushSync } from "react-dom";

/**
 * Hash router (FastAPI serves only "/"). Navigation runs inside
 * document.startViewTransition where available, so shared elements with a
 * view-transition-name morph between views.
 */

export interface Route {
  path: string[];
  params: URLSearchParams;
  raw: string;
}

function parse(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const [pathPart = "", queryPart = ""] = hash.split("?");
  return {
    path: pathPart.split("/").filter(Boolean).map(decodeURIComponent),
    params: new URLSearchParams(queryPart),
    raw: hash,
  };
}

let current = parse();
const listeners = new Set<() => void>();

function emit(): void {
  current = parse();
  for (const listener of listeners) listener();
}

window.addEventListener("hashchange", () => {
  // Back/forward: animate too, but the DOM must update synchronously inside.
  withTransition(emit);
});

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useRoute(): Route {
  return useSyncExternalStore(subscribe, () => current);
}

interface ViewTransitionLike {
  ready: Promise<void>;
  finished: Promise<void>;
  updateCallbackDone: Promise<void>;
}
type TransitionDocument = Document & { startViewTransition?: (callback: () => void) => ViewTransitionLike };

export function withTransition(update: () => void): void {
  const doc = document as TransitionDocument;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!doc.startViewTransition || reduce || document.visibilityState !== "visible") {
    update();
    return;
  }
  const transition = doc.startViewTransition(() => flushSync(update));
  // A quick second navigation skips the running animation. The view has
  // already updated, so the rejected promises carry no error worth reporting.
  const ignore = () => undefined;
  transition.ready.catch(ignore);
  transition.finished.catch(ignore);
  transition.updateCallbackDone.catch(ignore);
}

export function href(path: string): string {
  return `#/${path.replace(/^\/+/, "")}`;
}

export function navigate(path: string, options: { replace?: boolean } = {}): void {
  const target = href(path);
  if (window.location.hash === target) return;
  // pushState does not fire hashchange, so this runs exactly one transition.
  withTransition(() => {
    if (options.replace) window.history.replaceState(null, "", target);
    else window.history.pushState(null, "", target);
    emit();
  });
}

interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string;
}

export function Link({ to, onClick, ...rest }: LinkProps) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  };
  return <a href={href(to)} onClick={handle} {...rest} />;
}

export function isActive(route: Route, section: string): boolean {
  return (route.path[0] ?? "") === section;
}
