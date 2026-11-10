package de.no0bz.ncc.ui.fleet

import de.no0bz.ncc.net.FleetNode
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull

/** Die wichtigsten Werte eines Geräts für die Flotten-Übersicht, aus seinen letzten Messwerten gelesen. */
data class FleetSummary(
    val platformLabel: String,
    val cpuPercent: Double?,
    val memoryPercent: Double?,
    val gpuPercent: Double?,
    val diskPercent: Double?,
    val cpuTemp: Double?,
    val gpuTemp: Double?,
    val batteryPercent: Double?,
    val batteryPlugged: Boolean?,
    val model: String?,
) {
    companion object {
        fun of(node: FleetNode): FleetSummary {
            val m = node.latest?.metrics ?: JsonObject(emptyMap())
            val unraid = m["unraid"] is JsonObject || node.metadata.string("source") == "unraid-api"
            val gpu = (m["gpus"] as? JsonArray)?.firstOrNull() as? JsonObject
            val lhmGpu = (m["lhm_gpus"] as? JsonArray)?.firstOrNull() as? JsonObject
            val android = m["android"] as? JsonObject
            return FleetSummary(
                platformLabel = when {
                    unraid -> "Unraid"
                    node.platform == "android" -> "Android"
                    node.platform.startsWith("win") -> "Windows"
                    node.platform.startsWith("linux") -> "Linux"
                    node.platform.startsWith("darwin") -> "macOS"
                    else -> node.platform
                },
                cpuPercent = m.obj("cpu").number("percent"),
                memoryPercent = m.obj("memory").number("percent"),
                gpuPercent = gpu.number("percent"),
                // Das vollste Laufwerk ist das interessante.
                diskPercent = (m["disks"] as? JsonArray)?.mapNotNull { (it as? JsonObject).number("percent") }?.maxOrNull(),
                cpuTemp = m.obj("cpu").number("temperature_c"),
                gpuTemp = lhmGpu.number("temperature_c") ?: gpu.number("temperature_c"),
                batteryPercent = m.obj("battery").number("percent"),
                batteryPlugged = (m.obj("battery")?.get("plugged") as? JsonPrimitive)?.booleanOrNull,
                model = android.string("soc") ?: m.obj("cpu").string("model"),
            )
        }

        private fun JsonObject?.obj(key: String): JsonObject? = this?.get(key) as? JsonObject
        private fun JsonObject?.number(key: String): Double? = (this?.get(key) as? JsonPrimitive)?.doubleOrNull
        private fun JsonObject?.string(key: String): String? =
            (this?.get(key) as? JsonPrimitive)?.takeIf { it.isString }?.content?.takeIf { it.isNotBlank() }
    }
}
