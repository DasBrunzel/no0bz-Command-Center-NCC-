package de.no0bz.ncc.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** Datenmodelle der NCC-Server-API v1 (ncc_server/schemas.py). */

@Serializable
data class PairingRegisterRequest(
    @SerialName("pairing_id") val pairingId: String,
    @SerialName("pairing_secret") val pairingSecret: String,
    @SerialName("machine_id") val machineId: String,
    @SerialName("display_name") val displayName: String,
    val platform: String = "android",
    @SerialName("agent_version") val agentVersion: String,
    val metadata: Map<String, JsonPrimitive> = emptyMap(),
)

@Serializable
data class PairingResponse(
    @SerialName("pairing_id") val pairingId: String,
    @SerialName("display_name") val displayName: String,
    val status: String,
    @SerialName("expires_at") val expiresAt: String,
)

@Serializable
data class PairingClaimRequest(@SerialName("pairing_secret") val pairingSecret: String)

@Serializable
data class PairingClaimResponse(val token: String)

@Serializable
data class EnrollRequest(
    @SerialName("machine_id") val machineId: String,
    @SerialName("display_name") val displayName: String,
    val platform: String = "android",
    @SerialName("agent_version") val agentVersion: String,
    val metadata: Map<String, JsonPrimitive> = emptyMap(),
)

@Serializable
data class NodeResponse(
    @SerialName("node_id") val nodeId: String,
    @SerialName("display_name") val displayName: String,
    val approved: Boolean,
    @SerialName("heartbeat_interval_seconds") val heartbeatIntervalSeconds: Int,
)

@Serializable
data class HeartbeatRequest(
    @SerialName("agent_version") val agentVersion: String,
    val metadata: Map<String, JsonPrimitive> = emptyMap(),
)

@Serializable
data class HeartbeatResponse(
    val accepted: Boolean,
    @SerialName("node_id") val nodeId: String,
    @SerialName("location_tracking") val locationTracking: Boolean = false,
)

@Serializable
data class LocationTrackingRequest(val enabled: Boolean)

/** Die App-Version, die der NCC-Server zum Installieren anbietet. */
@Serializable
data class AppRelease(
    @SerialName("version_code") val versionCode: Int,
    @SerialName("version_name") val versionName: String,
    val size: Long,
    val sha256: String,
    val notes: String = "",
    @SerialName("uploaded_at") val uploadedAt: String = "",
)

@Serializable
data class DeletedResponse(val deleted: Int)

@Serializable
data class TelemetryPoint(
    @SerialName("sample_id") val sampleId: String,
    @SerialName("recorded_at") val recordedAt: String,
    val metrics: JsonObject,
)

@Serializable
data class TelemetryBatchRequest(val points: List<TelemetryPoint>)

@Serializable
data class TelemetryBatchResponse(val accepted: Int, val duplicates: Int)
