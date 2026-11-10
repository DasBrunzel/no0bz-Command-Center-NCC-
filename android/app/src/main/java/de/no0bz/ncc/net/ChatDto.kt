package de.no0bz.ncc.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/** Fleet-Chat und Geräteliste, wie der Server sie App-Nodes liefert (`/api/v1/nodes/chat`, `/nodes/fleet`). */

@Serializable
data class ChatAttachment(
    val name: String,
    @SerialName("content_type") val contentType: String,
    val size: Long,
) {
    val isImage: Boolean get() = contentType.startsWith("image/")
}

@Serializable
data class ChatMessage(
    @SerialName("message_id") val messageId: String,
    @SerialName("sender_node_id") val senderNodeId: String? = null,
    @SerialName("sender_user_id") val senderUserId: String? = null,
    @SerialName("sender_name") val senderName: String,
    val body: String = "",
    @SerialName("body_format") val bodyFormat: String = "plain",
    val attachment: ChatAttachment? = null,
    @SerialName("created_at") val createdAt: String,
) {
    val markdown: Boolean get() = bodyFormat == "markdown"
}

@Serializable
data class ChatSendRequest(
    val body: String,
    @SerialName("body_format") val bodyFormat: String,
)

@Serializable
data class FleetLatest(
    @SerialName("recorded_at") val recordedAt: String,
    val metrics: JsonObject,
)

@Serializable
data class FleetNode(
    @SerialName("node_id") val nodeId: String,
    @SerialName("display_name") val displayName: String,
    val platform: String,
    val online: Boolean,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
    @SerialName("agent_version") val agentVersion: String? = null,
    @SerialName("owner_name") val ownerName: String? = null,
    val metadata: JsonObject = JsonObject(emptyMap()),
    val latest: FleetLatest? = null,
)
