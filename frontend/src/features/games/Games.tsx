import type { Route } from "../../lib/router";

export default function Games({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
