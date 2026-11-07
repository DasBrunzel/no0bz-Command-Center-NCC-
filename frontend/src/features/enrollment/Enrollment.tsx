import type { Route } from "../../lib/router";

export default function Enrollment({ route }: { route: Route }) {
  return <p>{route.raw}</p>;
}
