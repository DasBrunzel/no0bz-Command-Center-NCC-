package de.no0bz.ncc.ui.dashboard

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.no0bz.ncc.collect.BatteryHealth
import de.no0bz.ncc.collect.BatteryInfo
import de.no0bz.ncc.collect.CpuCluster
import de.no0bz.ncc.collect.CpuState
import de.no0bz.ncc.collect.DeviceSnapshot
import de.no0bz.ncc.collect.PowerSource
import de.no0bz.ncc.collect.ThermalStatus
import de.no0bz.ncc.service.LiveState
import de.no0bz.ncc.ui.Format
import de.no0bz.ncc.ui.components.BigValue
import de.no0bz.ncc.ui.components.Lamp
import de.no0bz.ncc.ui.components.Meter
import de.no0bz.ncc.ui.components.Panel
import de.no0bz.ncc.ui.components.StatRow
import de.no0bz.ncc.ui.theme.LocalNccColors

@Composable
fun DashboardRoute(contentPadding: PaddingValues, viewModel: DashboardViewModel = viewModel()) {
    val snapshot by viewModel.snapshot.collectAsStateWithLifecycle()
    val watched by LiveState.watched.collectAsStateWithLifecycle()
    DashboardScreen(snapshot, contentPadding, watched)
}

@Composable
fun DashboardScreen(snapshot: DeviceSnapshot?, contentPadding: PaddingValues, watched: Boolean = false) {
    val ncc = LocalNccColors.current
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        if (snapshot == null) {
            CircularProgressIndicator(Modifier.align(Alignment.Center), color = ncc.shunt)
            return@Box
        }
        LazyColumn(
            modifier = Modifier.widthIn(max = 640.dp).fillMaxSize(),
            contentPadding = contentPadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { Header(snapshot, watched) }
            item { MemoryPanel(snapshot) }
            item { StoragePanel(snapshot) }
            item { SocPanel(snapshot) }
            item { CoresPanel(snapshot.cpu) }
            item { BatteryPanel(snapshot.battery, snapshot.thermal) }
        }
    }
}

@Composable
private fun Header(s: DeviceSnapshot, watched: Boolean) {
    val ncc = LocalNccColors.current
    Column(Modifier.padding(horizontal = 4.dp, vertical = 4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("NCC · NODE", style = MaterialTheme.typography.titleSmall, color = ncc.ink3, modifier = Modifier.weight(1f))
            LiveBadge(watched)
        }
        Text(
            s.device.name,
            style = MaterialTheme.typography.displayMedium,
            color = ncc.ink,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            "Android ${s.device.androidRelease} · SDK ${s.device.sdkInt} · Patch ${s.device.securityPatch}",
            style = MaterialTheme.typography.bodyMedium,
            color = ncc.ink2,
        )
        Text(
            "${s.device.manufacturer} ${s.device.model}" + if (s.device.isEmulator) " · Emulator" else "",
            style = MaterialTheme.typography.bodySmall,
            color = ncc.ink3,
        )
    }
}

@Composable
private fun LiveBadge(watched: Boolean) {
    val ncc = LocalNccColors.current
    val pulse by rememberInfiniteTransition(label = "live").animateFloat(
        initialValue = 1f, targetValue = 0.35f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse), label = "pulse",
    )
    Row(verticalAlignment = Alignment.CenterVertically) {
        Lamp(if (watched) ncc.shunt else ncc.go, lit = true, modifier = Modifier.alpha(pulse), size = 10.dp)
        Spacer(Modifier.width(6.dp))
        // Blau = das NCC-Dashboard schaut gerade zu und bekommt die Werte live.
        Text(
            if (watched) "LIVE · DASHBOARD" else "LIVE · 1 s",
            style = MaterialTheme.typography.titleSmall,
            color = if (watched) ncc.shuntInk else ncc.goInk,
        )
    }
}

@Composable
private fun MemoryPanel(s: DeviceSnapshot) {
    val ncc = LocalNccColors.current
    val m = s.memory
    Panel(
        "Arbeitsspeicher",
        trailing = { Text(Format.percent(m.usedFraction), style = MaterialTheme.typography.labelLarge, color = ncc.ink2) },
    ) {
        BigValue(
            Format.bytes(m.usedBytes, binary = true),
            "von " + (m.advertisedBytes?.let { Format.wholeGigabytes(it, binary = true) } ?: Format.bytes(m.totalBytes, binary = true)),
        )
        Meter(m.usedFraction, label = "RAM belegt ${Format.percent(m.usedFraction)}")
        StatRow("Frei", Format.bytes(m.availableBytes, binary = true))
        StatRow("Nutzbar für Android", Format.bytes(m.totalBytes, binary = true))
        if (m.lowMemory) StatRow("Zustand", "Speicher knapp", valueColor = ncc.stopInk)
    }
}

@Composable
private fun StoragePanel(s: DeviceSnapshot) {
    val ncc = LocalNccColors.current
    val st = s.storage
    Panel(
        "Speicherplatz",
        trailing = { Text(Format.percent(st.usedFraction), style = MaterialTheme.typography.labelLarge, color = ncc.ink2) },
    ) {
        BigValue(Format.bytes(st.usedBytes, binary = false), "von " + Format.bytes(st.totalBytes, binary = false))
        Meter(st.usedFraction, label = "Speicher belegt ${Format.percent(st.usedFraction)}")
        StatRow("Frei", Format.bytes(st.freeBytes, binary = false))
    }
}

@Composable
private fun SocPanel(s: DeviceSnapshot) {
    val cpu = s.cpu
    Panel("SoC") {
        Text(s.soc.displayName, style = MaterialTheme.typography.headlineMedium, color = LocalNccColors.current.ink)
        if (cpu.clusters.isNotEmpty()) StatRow("Architektur", cpu.architectureSummary)
        StatRow("Kerne", cpu.coreCount.toString())
        val code = listOfNotNull(s.soc.manufacturer, s.soc.model).filter { it.isNotBlank() && it != "unknown" }
        if (code.isNotEmpty()) StatRow("Kennung", code.joinToString(" "))
        StatRow("ABI", s.soc.abis.firstOrNull() ?: "–")
    }
}

@Composable
private fun CoresPanel(cpu: CpuState) {
    val ncc = LocalNccColors.current
    Panel(
        "Kerne",
        trailing = {
            cpu.averageClockLoad?.let {
                Text("Ø " + Format.percent(it), style = MaterialTheme.typography.labelLarge, color = ncc.ink2)
            }
        },
    ) {
        if (!cpu.hasClockData) {
            Text(
                "Taktwerte sind auf diesem Gerät nicht lesbar (im Emulator normal).",
                style = MaterialTheme.typography.bodyMedium,
                color = ncc.ink3,
            )
        }
        cpu.clusters.sortedByDescending { it.maxKhz ?: 0 }.forEachIndexed { i, cluster ->
            ClusterBlock(cpu, cluster, ncc.series[i % ncc.series.size])
        }
        Text(
            "Last = aktueller Takt ÷ Maximaltakt. Echte Kernauslastung gibt Android an Apps nicht heraus.",
            style = MaterialTheme.typography.bodySmall,
            color = ncc.ink3,
        )
    }
}

@Composable
private fun ClusterBlock(cpu: CpuState, cluster: CpuCluster, accent: Color) {
    val ncc = LocalNccColors.current
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Lamp(accent, lit = true, size = 8.dp)
            Spacer(Modifier.width(8.dp))
            Text(
                "${cluster.coreIds.size}× ${cluster.name}".uppercase(),
                style = MaterialTheme.typography.titleSmall,
                color = ncc.ink2,
                modifier = Modifier.weight(1f),
            )
            cluster.maxKhz?.let { Text("max " + Format.frequency(it), style = MaterialTheme.typography.labelMedium, color = ncc.ink3) }
        }
        cluster.coreIds.forEach { id ->
            val core = cpu.cores.firstOrNull { it.id == id } ?: return@forEach
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("CPU $id", style = MaterialTheme.typography.labelMedium, color = ncc.ink3, modifier = Modifier.width(48.dp))
                Meter(
                    fraction = core.clockLoad ?: 0f,
                    color = accent,
                    modifier = Modifier.weight(1f),
                    label = "CPU $id " + (core.curKhz?.let { Format.frequency(it) } ?: "aus"),
                )
                Text(
                    when {
                        !core.online -> "aus"
                        core.curKhz != null -> Format.frequency(core.curKhz)
                        else -> "n/a"
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = ncc.ink,
                    modifier = Modifier.width(76.dp).padding(start = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun BatteryPanel(b: BatteryInfo, thermal: ThermalStatus) {
    val ncc = LocalNccColors.current
    val level = b.levelPercent
    val levelColor = when {
        level == null -> ncc.ink
        level <= 15 -> ncc.stopInk
        level <= 30 -> ncc.cautionInk
        else -> ncc.ink
    }
    Panel(
        "Akku",
        trailing = {
            val plugged = b.source != PowerSource.NONE
            val (label, lampColor, textColor) = when {
                b.full -> Triple("VOLL", ncc.go, ncc.goInk)
                b.charging -> Triple("LÄDT", ncc.go, ncc.goInk)
                plugged -> Triple("ANGESTECKT", ncc.caution, ncc.cautionInk)
                else -> Triple("ENTLÄDT", ncc.unlit, ncc.ink3)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Lamp(lampColor, lit = b.charging || b.full || plugged, size = 10.dp)
                Spacer(Modifier.width(6.dp))
                Text(label, style = MaterialTheme.typography.titleSmall, color = textColor)
            }
        },
    ) {
        BigValue(level?.let { "$it %" } ?: "–", color = levelColor)
        Meter(
            (level ?: 0) / 100f,
            color = when {
                level == null -> ncc.unlit
                level <= 15 -> ncc.stop
                level <= 30 -> ncc.caution
                else -> ncc.go
            },
            label = "Akkustand ${level ?: "unbekannt"} Prozent",
        )
        b.temperatureCelsius?.let { t ->
            StatRow(
                "Temperatur",
                Format.celsius(t),
                valueColor = when {
                    t >= 45f -> ncc.stopInk
                    t >= 40f -> ncc.cautionInk
                    else -> null
                },
            )
        }
        StatRow("Quelle", b.source.label())
        StatRow("Zustand", b.health.label(), valueColor = if (b.health == BatteryHealth.GOOD) ncc.goInk else null)
        b.voltageMillivolts?.let { StatRow("Spannung", Format.volts(it)) }
        b.cycleCount?.let { StatRow("Ladezyklen", it.toString()) }
        StatRow(
            "Thermik",
            thermal.label(),
            valueColor = when (thermal) {
                ThermalStatus.NONE, ThermalStatus.LIGHT -> null
                ThermalStatus.MODERATE -> ncc.cautionInk
                else -> ncc.stopInk
            },
        )
    }
}

private fun PowerSource.label() = when (this) {
    PowerSource.NONE -> "Akku"
    PowerSource.AC -> "Netzteil"
    PowerSource.USB -> "USB"
    PowerSource.WIRELESS -> "Kabellos"
    PowerSource.DOCK -> "Dock"
}

private fun BatteryHealth.label() = when (this) {
    BatteryHealth.GOOD -> "Gut"
    BatteryHealth.OVERHEAT -> "Überhitzt"
    BatteryHealth.DEAD -> "Defekt"
    BatteryHealth.OVER_VOLTAGE -> "Überspannung"
    BatteryHealth.COLD -> "Zu kalt"
    BatteryHealth.FAILURE -> "Fehler"
    BatteryHealth.UNKNOWN -> "Unbekannt"
}

private fun ThermalStatus.label() = when (this) {
    ThermalStatus.NONE -> "Normal"
    ThermalStatus.LIGHT -> "Leicht warm"
    ThermalStatus.MODERATE -> "Warm"
    ThermalStatus.SEVERE -> "Heiß"
    ThermalStatus.CRITICAL -> "Kritisch"
    ThermalStatus.EMERGENCY -> "Notfall"
    ThermalStatus.SHUTDOWN -> "Abschaltung"
}
