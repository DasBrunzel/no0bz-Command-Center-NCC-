package de.no0bz.ncc.ui.connection

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.no0bz.ncc.data.INTERVAL_CHOICES
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.data.Settings
import de.no0bz.ncc.data.UploadRule
import de.no0bz.ncc.net.ServerUrl
import de.no0bz.ncc.ui.Format
import de.no0bz.ncc.ui.components.Lamp
import de.no0bz.ncc.ui.components.Panel
import de.no0bz.ncc.ui.components.StatRow
import de.no0bz.ncc.ui.theme.LocalNccColors
import java.time.Duration
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
fun ConnectionRoute(
    contentPadding: PaddingValues,
    onEnableService: (enable: () -> Unit) -> Unit,
    viewModel: ConnectionViewModel = viewModel(),
) {
    val settings by viewModel.settings.collectAsStateWithLifecycle()
    val reach by viewModel.reachability.collectAsStateWithLifecycle()
    val buffer by viewModel.buffer.collectAsStateWithLifecycle()
    val busy by viewModel.busy.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    val s = settings ?: return

    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        LazyColumn(
            modifier = Modifier.widthIn(max = 640.dp).fillMaxSize(),
            contentPadding = contentPadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Feste Schlüssel: Wenn oben ein Hinweis erscheint, behalten die Eingabefelder ihren Inhalt.
            item(key = "title") { Title() }
            message?.let { item(key = "message") { MessageBar(it, onDismiss = viewModel::dismissMessage) } }
            item(key = "status") { StatusPanel(s, reach) }
            item(key = "pairing") {
                PairingPanel(
                    s = s,
                    busy = busy,
                    defaultName = viewModel.defaultDeviceName,
                    // Nach erfolgreicher Kopplung startet die Überwachung automatisch – die
                    // Benachrichtigungs-Berechtigung wird deshalb schon hier erfragt.
                    onRequest = { url, name -> onEnableService { viewModel.requestPairing(url, name) } },
                    onCancel = viewModel::cancelPairing,
                    onUnpair = viewModel::unpair,
                )
            }
            item(key = "collection") {
                CollectionPanel(
                    s = s,
                    buffer = buffer,
                    onToggleService = { enabled ->
                        if (enabled) onEnableService { viewModel.setServiceEnabled(true) } else viewModel.setServiceEnabled(false)
                    },
                    onInterval = viewModel::setInterval,
                    onRule = viewModel::setUploadRule,
                    onUploadNow = viewModel::uploadNow,
                )
            }
        }
    }
}

@Composable
private fun Title() {
    val ncc = LocalNccColors.current
    Column(Modifier.padding(horizontal = 4.dp, vertical = 4.dp)) {
        Text("NCC · VERBINDUNG", style = MaterialTheme.typography.titleSmall, color = ncc.ink3)
        Text("Server & Upload", style = MaterialTheme.typography.displayMedium, color = ncc.ink)
    }
}

@Composable
private fun MessageBar(text: String, onDismiss: () -> Unit) {
    val ncc = LocalNccColors.current
    Panel("Hinweis") {
        Text(text, style = MaterialTheme.typography.bodyLarge, color = ncc.ink)
        OutlinedButton(onClick = onDismiss) { Text("Schließen") }
    }
}

@Composable
private fun StatusPanel(s: Settings, reach: Reachability) {
    val ncc = LocalNccColors.current
    Panel("Status") {
        LampRow("Tailscale-VPN", if (reach.vpn) "aktiv" else "nicht verbunden", if (reach.vpn) ncc.go else ncc.stop, true)
        LampRow(
            "NCC-Server",
            when (reach.server) { true -> "erreichbar"; false -> "nicht erreichbar"; null -> "prüfe …" },
            when (reach.server) { true -> ncc.go; false -> ncc.stop; null -> ncc.caution },
            reach.server != null,
        )
        LampRow(
            "Kopplung",
            when (s.pairingState) {
                PairingState.PAIRED -> "gekoppelt"
                PairingState.WAITING -> "wartet auf Freigabe"
                PairingState.UNPAIRED -> "nicht gekoppelt"
            },
            when (s.pairingState) { PairingState.PAIRED -> ncc.go; PairingState.WAITING -> ncc.caution; PairingState.UNPAIRED -> ncc.unlit },
            s.pairingState != PairingState.UNPAIRED,
        )
        s.lastError?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = ncc.stopInk) }
        StatRow("Server", s.serverUrl.removePrefix("http://").removePrefix("https://").ifBlank { "nicht eingetragen" })
    }
}

@Composable
private fun LampRow(label: String, value: String, color: androidx.compose.ui.graphics.Color, lit: Boolean) {
    val ncc = LocalNccColors.current
    Row(verticalAlignment = Alignment.CenterVertically) {
        Lamp(color, lit = lit, size = 10.dp)
        Spacer(Modifier.width(10.dp))
        Text(label, style = MaterialTheme.typography.bodyMedium, color = ncc.ink3, modifier = Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.labelLarge, color = ncc.ink)
    }
}

@Composable
private fun PairingPanel(
    s: Settings,
    busy: Boolean,
    defaultName: String,
    onRequest: (String, String) -> Unit,
    onCancel: () -> Unit,
    onUnpair: () -> Unit,
) {
    val ncc = LocalNccColors.current
    Panel("Kopplung") {
        when (s.pairingState) {
            PairingState.UNPAIRED -> {
                var url by rememberSaveable { mutableStateOf(s.serverUrl) }
                var name by rememberSaveable { mutableStateOf(s.displayName ?: defaultName) }
                Text(
                    "Fragt beim NCC-Server eine Kopplung an. Du gibst sie danach im Dashboard unter „Aufnahme → Kopplungsanfragen“ frei.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = ncc.ink2,
                )
                NccField("Server-Adresse", url, { url = it }, KeyboardType.Uri, placeholder = ServerUrl.EXAMPLE)
                NccField("Gerätename im NCC", name, { name = it }, KeyboardType.Text)
                Button(
                    onClick = { onRequest(url, name) },
                    enabled = !busy,
                    colors = ButtonDefaults.buttonColors(containerColor = ncc.shunt),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Frage an …" else "Kopplung anfragen") }
            }
            PairingState.WAITING -> {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Lamp(ncc.caution, lit = true, size = 12.dp)
                    Spacer(Modifier.width(10.dp))
                    Text("Warte auf Freigabe", style = MaterialTheme.typography.headlineMedium, color = ncc.ink)
                }
                Text(
                    "Öffne das NCC-Dashboard → Aufnahme → Kopplungsanfragen und gib „${s.displayName ?: defaultName}“ frei. Die App holt sich den Zugang dann automatisch.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = ncc.ink2,
                )
                s.pairingExpiresAt?.let { StatRow("Anfrage gültig bis", clock(it)) }
                OutlinedButton(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text("Abbrechen") }
            }
            PairingState.PAIRED -> {
                StatRow("Name", s.displayName ?: defaultName)
                s.nodeId?.let { StatRow("Node-ID", it.take(8) + "…") }
                OutlinedButton(onClick = onUnpair, modifier = Modifier.fillMaxWidth()) { Text("Entkoppeln") }
            }
        }
    }
}

@Composable
private fun NccField(label: String, value: String, onChange: (String) -> Unit, type: KeyboardType, placeholder: String? = null) {
    val ncc = LocalNccColors.current
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        placeholder = placeholder?.let { { Text(it, color = ncc.ink3) } },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = type, imeAction = ImeAction.Next),
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = ncc.shunt, unfocusedBorderColor = ncc.line,
            focusedLabelColor = ncc.shuntInk, unfocusedLabelColor = ncc.ink3,
            focusedTextColor = ncc.ink, unfocusedTextColor = ncc.ink, cursorColor = ncc.shunt,
        ),
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun CollectionPanel(
    s: Settings,
    buffer: BufferInfo,
    onToggleService: (Boolean) -> Unit,
    onInterval: (Int) -> Unit,
    onRule: (UploadRule) -> Unit,
    onUploadNow: () -> Unit,
) {
    val ncc = LocalNccColors.current
    Panel("Erfassung") {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Überwachung im Hintergrund", style = MaterialTheme.typography.bodyLarge, color = ncc.ink)
                Text(
                    if (s.serviceEnabled) "läuft – Anzeige in der Benachrichtigungsleiste" else "aus",
                    style = MaterialTheme.typography.bodySmall,
                    color = ncc.ink3,
                )
            }
            Switch(
                checked = s.serviceEnabled,
                onCheckedChange = onToggleService,
                colors = SwitchDefaults.colors(checkedTrackColor = ncc.go, checkedThumbColor = ncc.panelRaised),
            )
        }
        Text("INTERVALL", style = MaterialTheme.typography.titleSmall, color = ncc.ink3)
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            INTERVAL_CHOICES.forEachIndexed { index, seconds ->
                SegmentedButton(
                    selected = s.intervalSeconds == seconds,
                    onClick = { onInterval(seconds) },
                    shape = SegmentedButtonDefaults.itemShape(index, INTERVAL_CHOICES.size),
                    colors = segmentColors(),
                ) { Text(if (seconds < 60) "${seconds}s" else "${seconds / 60} min") }
            }
        }
        Text("UPLOAD", style = MaterialTheme.typography.titleSmall, color = ncc.ink3)
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            UploadRule.entries.forEachIndexed { index, rule ->
                SegmentedButton(
                    selected = s.uploadRule == rule,
                    onClick = { onRule(rule) },
                    shape = SegmentedButtonDefaults.itemShape(index, UploadRule.entries.size),
                    colors = segmentColors(),
                ) { Text(rule.label) }
            }
        }
        Text(
            when (s.uploadRule) {
                UploadRule.WIFI_CHARGING -> "Messwerte werden immer lokal gespeichert und nur hochgeladen, wenn das Handy im WLAN ist und lädt. Lebenszeichen gehen trotzdem raus."
                UploadRule.IMMEDIATE -> "Messwerte werden bei jeder Messung hochgeladen, auch über mobile Daten."
            },
            style = MaterialTheme.typography.bodySmall,
            color = ncc.ink3,
        )
        StatRow("Letzte Messung", ago(s.lastSampleAt))
        StatRow("Letztes Lebenszeichen", ago(s.lastHeartbeatAt))
        StatRow("Letzter Upload", ago(s.lastUploadAt))
        StatRow(
            "Im Puffer",
            "${buffer.pending} Messpunkte",
            valueColor = if (buffer.pending > 0) ncc.cautionInk else null,
        )
        StatRow("Logdateien", "${buffer.files} · ${Format.bytes(buffer.bytes, binary = true)}")
        Button(
            onClick = onUploadNow,
            enabled = s.pairingState == PairingState.PAIRED,
            colors = ButtonDefaults.buttonColors(containerColor = ncc.shunt),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Jetzt hochladen") }
    }
}

@Composable
private fun segmentColors() = LocalNccColors.current.let { ncc ->
    SegmentedButtonDefaults.colors(
        activeContainerColor = ncc.shunt.copy(alpha = 0.18f),
        activeContentColor = ncc.ink,
        activeBorderColor = ncc.shunt,
        inactiveContainerColor = ncc.panelRaised,
        inactiveContentColor = ncc.ink2,
        inactiveBorderColor = ncc.line,
    )
}

private val CLOCK = DateTimeFormatter.ofPattern("HH:mm")

private fun clock(iso: String): String = runCatching {
    Instant.parse(iso).atZone(ZoneId.systemDefault()).format(CLOCK) + " Uhr"
}.getOrDefault("–")

private fun ago(millis: Long?): String {
    if (millis == null) return "–"
    val seconds = Duration.between(Instant.ofEpochMilli(millis), Instant.now()).seconds.coerceAtLeast(0)
    return when {
        seconds < 60 -> "vor $seconds s"
        seconds < 3600 -> "vor ${seconds / 60} min"
        seconds < 86_400 -> "vor ${seconds / 3600} h"
        else -> "vor ${seconds / 86_400} d"
    }
}
