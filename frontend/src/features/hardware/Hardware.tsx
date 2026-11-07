import type { Route } from "../../lib/router";

export default function Hardware({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
