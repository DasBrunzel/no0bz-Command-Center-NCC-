import type { Route } from "../../lib/router";

export default function NodeDetail({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
