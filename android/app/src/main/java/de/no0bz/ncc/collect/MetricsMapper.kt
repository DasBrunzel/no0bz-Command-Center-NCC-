package de.no0bz.ncc.collect

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import kotlin.math.roundToInt

/** Netzwerkzustand zum Zeitpunkt der Messung. */
data class NetworkState(val type: String, val vpn: Boolean, val unmetered: Boolean)

/**
 * Übersetzt einen Messpunkt in das Metrik-Format des NCC-Servers.
 *
 * Die Felder `memory`, `disks`, `battery` und `system` folgen dem Schema der PC-Agents, damit das
 * Dashboard sie ohne Änderung anzeigt. Alles Android-Spezifische steht unter `android`.
 * Bewusst **ohne** `cpu.percent`: Die Taktlast ist keine echte Auslastung und würde sonst
 * CPU-Warnungen auslösen.
 */
object MetricsMapper {
    private const val GIB = 1024.0 * 1024 * 1024

    fun map(s: DeviceSnapshot, network: NetworkState?): JsonObject = buildJsonObject {
        val onlineFreqs = s.cpu.cores.mapNotNull { it.curKhz }
        putJsonObject("cpu") {
            put("model", s.soc.displayName)
            put("logical_cores", s.cpu.coreCount)
            if (onlineFreqs.isNotEmpty()) put("frequency_mhz", (onlineFreqs.average() / 1000).roundToInt())
        }
        putJsonObject("memory") {
            put("percent", round1(s.memory.usedFraction * 100.0))
            put("used_gb", gib(s.memory.usedBytes))
            put("available_gb", gib(s.memory.availableBytes))
            put("total_gb", gib(s.memory.totalBytes))
        }
        putJsonArray("disks") {
            addJsonObject {
                put("name", "Intern")
                put("mount", "/data")
                put("percent", round1(s.storage.usedFraction * 100.0))
                put("used_gb", gib(s.storage.usedBytes))
                put("total_gb", gib(s.storage.totalBytes))
            }
        }
        s.battery.levelPercent?.let { level ->
            putJsonObject("battery") {
                put("percent", level)
                put("plugged", s.battery.source != PowerSource.NONE)
            }
        }
        putJsonObject("system") {
            put("hostname", s.device.name)
            put("platform", "Android ${s.device.androidRelease}")
        }
        putJsonObject("android") {
            put("manufacturer", s.device.manufacturer)
            put("model", s.device.model)
            put("sdk", s.device.sdkInt)
            put("security_patch", s.device.securityPatch)
            put("emulator", s.device.isEmulator)
            put("soc", s.soc.displayName)
            s.soc.model?.takeIf { it.isNotBlank() }?.let { put("soc_code", it) }
            put("architecture", s.cpu.architectureSummary)
            s.memory.advertisedBytes?.let { put("ram_advertised_gb", (it / GIB).roundToInt()) }
            putJsonArray("clusters") {
                s.cpu.clusters.forEach { c ->
                    addJsonObject {
                        put("name", c.name)
                        putJsonArray("cores") { c.coreIds.forEach { add(it) } }
                        c.maxKhz?.let { put("max_mhz", (it / 1000).toInt()) }
                    }
                }
            }
            putJsonArray("cores") {
                s.cpu.cores.forEach { core ->
                    addJsonObject {
                        put("id", core.id)
                        put("online", core.online)
                        core.curKhz?.let { put("mhz", (it / 1000).toInt()) }
                        core.clockLoad?.let { put("clock_load", round1(it * 100.0)) }
                    }
                }
            }
            s.cpu.averageClockLoad?.let { put("clock_load", round1(it * 100.0)) }
            putJsonObject("battery") {
                s.battery.temperatureCelsius?.let { put("temperature_c", round1(it.toDouble())) }
                put("charging", s.battery.charging)
                put("full", s.battery.full)
                put("source", s.battery.source.name.lowercase())
                put("health", s.battery.health.name.lowercase())
                s.battery.voltageMillivolts?.let { put("voltage_mv", it) }
                s.battery.cycleCount?.let { put("cycles", it) }
            }
            put("thermal", s.thermal.name.lowercase())
            network?.let { n ->
                putJsonObject("network") {
                    put("type", n.type)
                    put("vpn", n.vpn)
                    put("unmetered", n.unmetered)
                }
            }
        }
    }

    /** Metadaten für Kopplung, Anmeldung und Lebenszeichen (nur einfache Werte erlaubt). */
    fun metadata(s: DeviceSnapshot, heartbeatIntervalSeconds: Int, appVersion: String): Map<String, JsonPrimitive> = mapOf(
        "architecture" to JsonPrimitive(s.soc.abis.firstOrNull() ?: "unknown"),
        "os_release" to JsonPrimitive("Android ${s.device.androidRelease}"),
        "model" to JsonPrimitive("${s.device.manufacturer} ${s.device.model}"),
        "soc" to JsonPrimitive(s.soc.displayName),
        "app_version" to JsonPrimitive(appVersion),
        "heartbeat_interval_seconds" to JsonPrimitive(heartbeatIntervalSeconds),
    )

    private fun gib(bytes: Long): Double = round1(bytes / GIB)

    private fun round1(value: Double): Double = (value * 10).roundToInt() / 10.0
}
