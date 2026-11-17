package de.no0bz.ncc.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/** HTTP-Fehler des Servers mit Statuscode (z. B. 401 Token ungültig, 409 Freigabe ausstehend). */
class ApiException(val code: Int, message: String) : IOException(message)

/** Schlanker Client für die NCC-API v1. Alle Aufrufe sind suspend und laufen auf Dispatchers.IO. */
class NccApi(
    private val baseUrl: String,
    private val client: OkHttpClient = defaultClient,
) {
    suspend fun live(): Boolean = withContext(Dispatchers.IO) {
        runCatching {
            client.newCall(Request.Builder().url("$baseUrl/api/v1/status/live").get().build()).execute().use { it.isSuccessful }
        }.getOrDefault(false)
    }

    suspend fun registerPairing(request: PairingRegisterRequest): PairingResponse =
        post("/api/v1/agent-pairings/register", request, PairingRegisterRequest.serializer(), PairingResponse.serializer())

    /** Liefert das Agent-Token, oder null solange die Freigabe im Dashboard aussteht (409). */
    suspend fun claimPairing(pairingId: String, secret: String): String? = try {
        post(
            "/api/v1/agent-pairings/$pairingId/claim",
            PairingClaimRequest(secret),
            PairingClaimRequest.serializer(),
            PairingClaimResponse.serializer(),
        ).token
    } catch (e: ApiException) {
        if (e.code == 409) null else throw e
    }

    suspend fun enroll(token: String, request: EnrollRequest): NodeResponse =
        post("/api/v1/nodes/enroll", request, EnrollRequest.serializer(), NodeResponse.serializer(), token)

    suspend fun heartbeat(token: String, request: HeartbeatRequest): HeartbeatResponse =
        post("/api/v1/nodes/heartbeat", request, HeartbeatRequest.serializer(), HeartbeatResponse.serializer(), token)

    suspend fun telemetry(token: String, points: List<TelemetryPoint>): TelemetryBatchResponse =
        post(
            "/api/v1/nodes/telemetry",
            TelemetryBatchRequest(points),
            TelemetryBatchRequest.serializer(),
            TelemetryBatchResponse.serializer(),
            token,
        )

    /** Neueste Nachrichten, oder die vor [before] bzw. nach [after] (Nachrichten-ID). */
    suspend fun chatMessages(token: String, limit: Int = 60, before: String? = null, after: String? = null): List<ChatMessage> {
        val query = buildString {
            append("?limit=$limit")
            if (before != null) append("&before=$before")
            if (after != null) append("&after=$after")
        }
        return get("/api/v1/nodes/chat/messages$query", ListSerializer(ChatMessage.serializer()), token)
    }

    suspend fun sendChat(token: String, body: String, markdown: Boolean): ChatMessage =
        post(
            "/api/v1/nodes/chat/messages",
            ChatSendRequest(body, if (markdown) "markdown" else "plain"),
            ChatSendRequest.serializer(),
            ChatMessage.serializer(),
            token,
        )

    suspend fun uploadChat(
        token: String,
        file: File,
        fileName: String,
        contentType: String,
        body: String,
        markdown: Boolean,
    ): ChatMessage = withContext(Dispatchers.IO) {
        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("body", body)
            .addFormDataPart("body_format", if (markdown) "markdown" else "plain")
            .addFormDataPart("file", fileName, file.asRequestBody(contentType.toMediaType()))
            .build()
        val request = Request.Builder().url("$baseUrl/api/v1/nodes/chat/uploads").post(form)
            .header("Authorization", "Bearer $token").build()
        uploadClient.newCall(request).execute().use { response ->
            val text = response.body.string()
            if (!response.isSuccessful) throw ApiException(response.code, "HTTP ${response.code}: ${text.take(200)}")
            json.decodeFromString(ChatMessage.serializer(), text)
        }
    }

    /** Lädt einen Anhang in [target]; unvollständige Dateien werden entfernt. */
    suspend fun downloadAttachment(token: String, messageId: String, target: File): Unit = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$baseUrl/api/v1/nodes/chat/messages/$messageId/attachment")
            .header("Authorization", "Bearer $token").get().build()
        uploadClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw ApiException(response.code, "HTTP ${response.code}")
            val partial = File(target.parentFile, target.name + ".part")
            try {
                partial.outputStream().use { out -> response.body.byteStream().copyTo(out) }
                if (!partial.renameTo(target)) throw IOException("Anhang konnte nicht gespeichert werden")
            } finally {
                partial.delete()
            }
        }
    }

    suspend fun fleet(token: String): List<FleetNode> =
        get("/api/v1/nodes/fleet", ListSerializer(FleetNode.serializer()), token)

    private suspend fun <Res> get(path: String, responseSerializer: KSerializer<Res>, token: String): Res =
        withContext(Dispatchers.IO) {
            val request = Request.Builder().url(baseUrl + path).get().header("Authorization", "Bearer $token").build()
            client.newCall(request).execute().use { response ->
                val text = response.body.string()
                if (!response.isSuccessful) throw ApiException(response.code, "HTTP ${response.code}: ${text.take(200)}")
                json.decodeFromString(responseSerializer, text)
            }
        }

    private suspend fun <Req, Res> post(
        path: String,
        body: Req,
        requestSerializer: KSerializer<Req>,
        responseSerializer: KSerializer<Res>,
        token: String? = null,
    ): Res = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(baseUrl + path)
            .post(json.encodeToString(requestSerializer, body).toRequestBody(JSON))
            .apply { if (token != null) header("Authorization", "Bearer $token") }
            .build()
        client.newCall(request).execute().use { response ->
            val text = response.body.string()
            if (!response.isSuccessful) throw ApiException(response.code, "HTTP ${response.code}: ${text.take(200)}")
            json.decodeFromString(responseSerializer, text)
        }
    }

    companion object {
        val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            explicitNulls = false
        }
        private val JSON = "application/json".toMediaType()
        private val defaultClient: OkHttpClient by lazy {
            OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(20, TimeUnit.SECONDS)
                .writeTimeout(20, TimeUnit.SECONDS)
                .build()
        }

        /** Für Anhänge: große Dateien über Mobilfunk brauchen deutlich länger. */
        private val uploadClient: OkHttpClient by lazy {
            defaultClient.newBuilder()
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(120, TimeUnit.SECONDS)
                .build()
        }
    }
}
