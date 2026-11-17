package de.no0bz.ncc.ui.fleet

import android.app.Application
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.net.FleetNode
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.pairing.PairingManager
import de.no0bz.ncc.ui.chat.parseInstant
import de.no0bz.ncc.ui.components.Lamp
import de.no0bz.ncc.ui.components.Meter
import de.no0bz.ncc.ui.components.Panel
import de.no0bz.ncc.ui.components.StatRow
import de.no0bz.ncc.ui.theme.LocalNccColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.stateIn
import java.time.Duration
import java.time.Instant
import java.util.Locale

data class FleetUi(
    val paired: Boolean = true,
    val nodes: List<FleetNode>? = null,
    val ownNodeId: String? = null,
    val error: String? = null,
)

/** Lädt die Geräteliste alle 5 s, solange der Tab sichtbar ist. */
class FleetViewModel(application: Application) : AndroidViewModel(application) {
    private val settings = AppSettings(application)

    val ui: StateFlow<FleetUi> = flow {
        var last = FleetUi()
        while (true) {
            val s = settings.current()
            val token = settings.token()
            last = if (s.pairingState != PairingState.PAIRED || token == null) {
                FleetUi(paired = false)
            } else {
                try {
                    FleetUi(nodes = NccApi(s.serverUrl).fleet(token), ownNodeId = s.nodeId)
                } catch (e: Exception) {
                    // Bei einem Aussetzer die letzte Liste behalten und nur den Fehler zeigen.
                    last.copy(paired = true, error = PairingManager.describe(e))
                }
            }
            emit(last)
            delay(REFRESH_MS)
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(2_000), FleetUi())

    companion object {
        private const val REFRESH_MS = 5_000L
    }
}

@Composable
fun FleetRoute(contentPadding: PaddingValues, viewModel: FleetViewModel = viewModel()) {
    val ui by viewModel.ui.collectAsStateWithLifecycle()
    val ncc = LocalNccColors.current
    val nodes = ui.nodes
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        LazyColumn(
            modifier = Modifier.widthIn(max = 640.dp).fillMaxSize(),
            contentPadding = contentPadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(key = "title") {
                Column(Modifier.padding(horizontal = 4.dp, vertical = 4.dp)) {
                    Text("NCC · FLOTTE", style = MaterialTheme.typography.titleSmall, color = ncc.ink3)
                    Text("Alle Systeme", style = MaterialTheme.typography.displayMedium, color = ncc.ink)
                    if (nodes != null) {
                        val online = nodes.count { it.online }
                        Text("$online von ${nodes.size} online", style = MaterialTheme.typography.bodyMedium, color = ncc.ink2)
                    }
                }
            }
            ui.error?.let { error ->
                item(key = "error") { Text(error, style = MaterialTheme.typography.bodyMedium, color = ncc.stopInk) }
            }
            when {
                !ui.paired -> item(key = "unpaired") {
                    Text(
                        "Die anderen Systeme siehst du, sobald das Handy mit dem NCC-Server gekoppelt ist (Tab „Verbindung“).",
                        style = MaterialTheme.typography.bodyLarge,
                        color = ncc.ink2,
                        modifier = Modifier.padding(4.dp),
                    )
                }
                nodes == null -> item(key = "loading") {
                    Box(Modifier.fillMaxSize().padding(48.dp), contentAlignment = Alignment.Center) {
                        if (ui.error == null) CircularProgressIndicator(color = ncc.shunt)
                    }
                }
                else -> items(nodes, key = { it.nodeId }) { node -> NodeCard(node, own = node.nodeId == ui.ownNodeId) }
            }
        }
    }
}

@Composable
private fun NodeCard(node: FleetNode, own: Boolean) {
    val ncc = LocalNccColors.current
    val s = FleetSummary.of(node)
    Panel(
        title = s.platformLabel + if (own) " · dieses Gerät" else "",
        trailing = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Lamp(ncc.go, lit = node.online, size = 10.dp)
                Spacer(Modifier.width(6.dp))
                Text(
                    if (node.online) "ONLINE" else "OFFLINE",
                    style = MaterialTheme.typography.titleSmall,
                    color = if (node.online) ncc.goInk else ncc.ink3,
                )
            }
        },
    ) {
        Text(node.displayName, style = MaterialTheme.typography.headlineMedium, color = ncc.ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
        s.model?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = ncc.ink3, maxLines = 1, overflow = TextOverflow.Ellipsis) }
        if (node.latest == null) {
            Text("Noch keine Messwerte.", style = MaterialTheme.typography.bodyMedium, color = ncc.ink3)
        } else {
            if (!node.online) {
                Text("Letzte bekannte Werte · zuletzt gesehen ${ago(node.lastSeenAt)}", style = MaterialTheme.typography.bodySmall, color = ncc.ink3)
            }
            s.cpuPercent?.let { Gauge("CPU", it) }
            s.gpuPercent?.let { Gauge("GPU", it) }
            s.memoryPercent?.let { Gauge("RAM", it) }
            s.diskPercent?.let { Gauge("Laufwerk", it) }
            s.batteryPercent?.let { Gauge("Akku" + if (s.batteryPlugged == true) " ⚡" else "", it, battery = true) }
            s.cpuTemp?.let { StatRow("CPU-Temperatur", degrees(it), valueColor = if (it >= 85) ncc.stopInk else null) }
            s.gpuTemp?.let { StatRow("GPU-Temperatur", degrees(it), valueColor = if (it >= 85) ncc.stopInk else null) }
        }
        node.ownerName?.let { StatRow("Gehört", it) }
    }
}

@Composable
private fun Gauge(label: String, percent: Double, battery: Boolean = false) {
    val ncc = LocalNccColors.current
    val fraction = (percent / 100.0).toFloat().coerceIn(0f, 1f)
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = ncc.ink3, modifier = Modifier.width(76.dp))
        val color = when {
            // Beim Akku ist wenig schlecht, bei Last ist viel schlecht.
            battery -> if (percent <= 15) ncc.stop else if (percent <= 30) ncc.caution else ncc.go
            percent >= 90 -> ncc.stop
            percent >= 75 -> ncc.caution
            else -> ncc.go
        }
        Meter(fraction, color = color, modifier = Modifier.weight(1f), label = "$label ${percent.toInt()} Prozent")
        Text(
            "${percent.toInt()} %",
            style = MaterialTheme.typography.labelMedium,
            color = ncc.ink,
            modifier = Modifier.width(52.dp).padding(start = 8.dp),
        )
    }
}

private fun degrees(value: Double): String = String.format(Locale.GERMANY, "%.0f °C", value)

private fun ago(iso: String?): String {
    val instant = iso?.let(::parseInstant) ?: return "nie"
    val seconds = Duration.between(instant, Instant.now()).seconds.coerceAtLeast(0)
    return when {
        seconds < 60 -> "gerade eben"
        seconds < 3600 -> "vor ${seconds / 60} min"
        seconds < 86_400 -> "vor ${seconds / 3600} h"
        else -> "vor ${seconds / 86_400} d"
    }
}
