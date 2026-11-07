import { lazy, Suspense } from "react";
import { useCan, type Can } from "../../app/auth";
import { Loading, PageHead } from "../../components/ui";
import { href, navigate, type Route } from "../../lib/router";
import { AccountTab } from "./AccountTab";
import "./settings.css";

const UsersTab = lazy(() => import("./UsersTab"));
const AlertPolicyTab = lazy(() => import("./AlertPolicyTab"));
const TelegramTab = lazy(() => import("./TelegramTab"));
const AboutTab = lazy(() => import("./AboutTab"));

const TABS: Array<{ key: string; label: string; visible: (can: Can) => boolean }> = [
  { key: "konto", label: "Mein Konto", visible: () => true },
  { key: "konten", label: "Konten & Einladungen", visible: (can) => can.commander },
  { key: "warnregeln", label: "Warnregeln", visible: () => true },
  { key: "telegram", label: "Telegram", visible: (can) => can.team },
  { key: "ueber", label: "Über", visible: () => true },
];

export default function Settings({ route }: { route: Route }) {
  const can = useCan();
  const tabs = TABS.filter((tab) => tab.visible(can));
  const requested = route.path[1] ?? "konto";
  const tab = tabs.find((item) => item.key === requested)?.key ?? "konto";
  return (
    <div>
      <PageHead title="Einstellungen" />
      <nav className="tabs" aria-label="Einstellungen">
        {tabs.map((item) => (
          <a
            key={item.key}
            href={href(`einstellungen/${item.key}`)}
            aria-current={tab === item.key ? "page" : undefined}
            onClick={(event) => { event.preventDefault(); navigate(`einstellungen/${item.key}`, { replace: true }); }}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <Suspense fallback={<Loading />}>
        {tab === "konto" && <AccountTab />}
        {tab === "konten" && <UsersTab />}
        {tab === "warnregeln" && <AlertPolicyTab />}
        {tab === "telegram" && <TelegramTab />}
        {tab === "ueber" && <AboutTab />}
      </Suspense>
    </div>
  );
}
