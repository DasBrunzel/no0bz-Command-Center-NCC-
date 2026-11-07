import type { Route } from "../../lib/router";

export default function Chat({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
