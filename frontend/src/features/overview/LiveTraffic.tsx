import { useFleetNetwork } from "../../api/queries";
import { LineChart } from "../../components/charts";
import { Empty, ErrorState, Loading, Reading } from "../../components/ui";
import { fmt1, fmtTime } from "../../lib/format";
import { Link } from "../../lib/router";

/*
 * GET /fleet/network sums the latest reading of every visible online node and
 * returns the last 30 minutes in buckets, so the chart is full on first load.
 */
const MINUTES = 30;

export function LiveTraffic() {
  const network = useFleetNetwork(MINUTES);
  const data = network.data;
  const history = data?.history ?? [];
  const talkers = (data?.nodes ?? []).filter((node) => node.download_mbps + node.upload_mbps > 0).slice(0, 5);

  return (
    <section className="panel live-traffic" aria-labelledby="traffic-title">
      <div className="panel-head">
        <h2 id="traffic-title">Live-Verkehr</h2>
        <p>Summe aller Geräte, die gerade online sind</p>
      </div>
      {network.isPending ? <Loading /> : network.isError && !data ? (
        <ErrorState onRetry={() => void network.refetch()}>Der Live-Verkehr ist gerade nicht abrufbar.</ErrorState>
      ) : (
        <>
          <div className="traffic-now">
            <div><span className="ink-3 small">Download</span><Reading value={data?.download_mbps ?? null} unit="Mbit/s" digits={1} /></div>
            <div><span className="ink-3 small">Upload</span><Reading value={data?.upload_mbps ?? null} unit="Mbit/s" digits={1} /></div>
          </div>
          {history.length < 3 ? (
            <p className="ink-3 small traffic-wait">Für die letzten {MINUTES} Minuten liegen noch zu wenige Messpunkte vor.</p>
          ) : (
            <LineChart
              title={`Verkehr der Fleet in den letzten ${MINUTES} Minuten, Mbit/s`}
              unit="Mbit/s"
              height={160}
              format={(value) => fmt1(value)}
              labels={history.map((sample) => fmtTime(new Date(sample.at)))}
              series={[
                { name: "Download", color: "var(--c-series-1)", values: history.map((sample) => sample.download_mbps) },
                { name: "Upload", color: "var(--c-series-2)", values: history.map((sample) => sample.upload_mbps) },
              ]}
            />
          )}
          {talkers.length > 0 ? (
            <table className="table mt-4">
              <caption className="visually-hidden">Geräte mit dem meisten Verkehr</caption>
              <thead><tr><th>Gerät</th><th className="r">Download</th><th className="r">Upload</th></tr></thead>
              <tbody>
                {talkers.map((node) => (
                  <tr key={node.node_id}>
                    <td><Link to={`geraete/${encodeURIComponent(node.node_id)}`}>{node.display_name}</Link></td>
                    <td className="r"><Reading value={node.download_mbps} unit="Mbit/s" digits={1} /></td>
                    <td className="r"><Reading value={node.upload_mbps} unit="Mbit/s" digits={1} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="mt-4"><Empty title="Gerade Funkstille" icon="network">Kein Gerät überträgt im Moment nennenswert Daten.</Empty></div>
          )}
        </>
      )}
    </section>
  );
}
