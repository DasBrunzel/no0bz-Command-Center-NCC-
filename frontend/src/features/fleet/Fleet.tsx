import type { Route } from "../../lib/router";

export default function Fleet({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
