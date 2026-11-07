import type { Route } from "../../lib/router";

export default function Releases({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
