package de.no0bz.ncc.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put

/** Eine NCC-Warnung, wie der Server sie über den Live-Kanal schickt. */
@Serializable
data class AppAlert(
    @SerialName("alert_id") val alertId: String,
    @SerialName("node_id") val nodeId: String = "",
    @SerialName("node_name") val nodeName: String,
    val kind: String,
    val severity: String,
    val message: String,
    @SerialName("opened_at") val openedAt: String = "",
) {
    val critical: Boolean get() = severity == "critical"
}

/** Nachrichten vom Server über `/api/v1/nodes/stream` (siehe docs/KONZEPT.md, Abschnitt 3.3). */
sealed interface StreamEvent {
    data class ViewerPresent(val intervalMs: Long) : StreamEvent
    data object ViewerGone : StreamEvent
    data class AlertSnapshot(val alerts: List<AppAlert>) : StreamEvent
    data class AlertNew(val alert: AppAlert) : StreamEvent
    data class AlertResolved(val alert: AppAlert) : StreamEvent
    data class ChatNew(val message: ChatMessage) : StreamEvent
    data object Ping : StreamEvent
}

object StreamProtocol {
    private const val MIN_LIVE_INTERVAL_MS = 1_000L
    private const val DEFAULT_LIVE_INTERVAL_MS = 2_000L

    /** Unbekannte oder kaputte Nachrichten ergeben null und werden ignoriert. */
    fun parse(text: String): StreamEvent? = runCatching {
        val message = NccApi.json.parseToJsonElement(text).jsonObject
        when (message["type"]?.jsonPrimitive?.content) {
            "viewer.present" -> StreamEvent.ViewerPresent(
                (message["interval_ms"]?.jsonPrimitive?.longOrNull ?: DEFAULT_LIVE_INTERVAL_MS).coerceAtLeast(MIN_LIVE_INTERVAL_MS),
            )
            "viewer.gone" -> StreamEvent.ViewerGone
            "alert.snapshot" -> StreamEvent.AlertSnapshot(
                message["alerts"]!!.jsonArray.map { NccApi.json.decodeFromJsonElement<AppAlert>(it) },
            )
            "alert.new" -> StreamEvent.AlertNew(NccApi.json.decodeFromJsonElement(message["alert"]!!))
            "alert.resolved" -> StreamEvent.AlertResolved(NccApi.json.decodeFromJsonElement(message["alert"]!!))
            "chat.new" -> StreamEvent.ChatNew(NccApi.json.decodeFromJsonElement(message["message"]!!))
            "ping" -> StreamEvent.Ping
            else -> null
        }
    }.getOrNull()

    fun liveMessage(recordedAt: String, metrics: JsonObject): String = buildJsonObject {
        put("type", "telemetry.live")
        put("recorded_at", recordedAt)
        put("metrics", metrics)
    }.toString()
}
