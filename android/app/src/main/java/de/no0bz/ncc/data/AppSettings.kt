package de.no0bz.ncc.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.security.SecureRandom
import java.util.Base64

private val Context.nccStore: DataStore<Preferences> by preferencesDataStore(name = "ncc")

enum class PairingState { UNPAIRED, WAITING, PAIRED }

enum class UploadRule(val label: String) {
    WIFI_CHARGING("WLAN + Laden"),
    IMMEDIATE("Sofort"),
}

/** Erlaubte Messintervalle in Sekunden (30 s bis 5 min). */
val INTERVAL_CHOICES = listOf(30, 60, 120, 300)

data class Settings(
    val serverUrl: String,
    val displayName: String?,
    val machineId: String?,
    val pairingState: PairingState,
    val pairingId: String?,
    val pairingSecret: String?,
    val pairingExpiresAt: String?,
    val nodeId: String?,
    val hasToken: Boolean,
    val intervalSeconds: Int,
    val uploadRule: UploadRule,
    val serviceEnabled: Boolean,
    val lastSampleAt: Long?,
    val lastHeartbeatAt: Long?,
    val lastUploadAt: Long?,
    val lastError: String?,
)

/** Einstellungen und Zustand der App, gespeichert in DataStore. Das Token liegt verschlüsselt. */
class AppSettings(context: Context) {
    private val store = context.applicationContext.nccStore

    val settings: Flow<Settings> = store.data.map { p ->
        Settings(
            serverUrl = p[SERVER_URL] ?: "",
            displayName = p[DISPLAY_NAME],
            machineId = p[MACHINE_ID],
            pairingState = p[PAIRING_STATE]?.let { runCatching { PairingState.valueOf(it) }.getOrNull() } ?: PairingState.UNPAIRED,
            pairingId = p[PAIRING_ID],
            pairingSecret = p[PAIRING_SECRET],
            pairingExpiresAt = p[PAIRING_EXPIRES],
            nodeId = p[NODE_ID],
            hasToken = p[TOKEN] != null,
            intervalSeconds = p[INTERVAL]?.takeIf { it in INTERVAL_CHOICES } ?: 60,
            uploadRule = p[UPLOAD_RULE]?.let { runCatching { UploadRule.valueOf(it) }.getOrNull() } ?: UploadRule.WIFI_CHARGING,
            serviceEnabled = p[SERVICE_ENABLED] ?: false,
            lastSampleAt = p[LAST_SAMPLE],
            lastHeartbeatAt = p[LAST_HEARTBEAT],
            lastUploadAt = p[LAST_UPLOAD],
            lastError = p[LAST_ERROR],
        )
    }

    suspend fun current(): Settings = settings.first()

    suspend fun token(): String? = store.data.first()[TOKEN]?.let { TokenCipher.decrypt(it) }

    /** Stabile Gerätekennung dieser Installation; „android-“ sortiert den Node in die Gruppe „Mobil“. */
    suspend fun machineId(): String {
        store.data.first()[MACHINE_ID]?.let { return it }
        val id = "android-" + randomHex(8)
        store.edit { it[MACHINE_ID] = id }
        return id
    }

    suspend fun setServer(url: String, displayName: String) = store.edit {
        it[SERVER_URL] = url
        it[DISPLAY_NAME] = displayName
    }

    suspend fun startPairing(pairingId: String, secret: String, expiresAt: String) = store.edit {
        it[PAIRING_STATE] = PairingState.WAITING.name
        it[PAIRING_ID] = pairingId
        it[PAIRING_SECRET] = secret
        it[PAIRING_EXPIRES] = expiresAt
        it.remove(LAST_ERROR)
    }

    suspend fun updatePairingExpiry(expiresAt: String) = store.edit { it[PAIRING_EXPIRES] = expiresAt }

    suspend fun completePairing(token: String, nodeId: String) = store.edit {
        it[TOKEN] = TokenCipher.encrypt(token)
        it[NODE_ID] = nodeId
        it[PAIRING_STATE] = PairingState.PAIRED.name
        it.remove(PAIRING_SECRET)
        it.remove(LAST_ERROR)
    }

    /** Vergisst Token und Kopplung (z. B. nach Entkoppeln oder wenn der Server das Token ablehnt). */
    suspend fun unpair(reason: String? = null) = store.edit {
        it.remove(TOKEN)
        it.remove(NODE_ID)
        it.remove(PAIRING_ID)
        it.remove(PAIRING_SECRET)
        it.remove(PAIRING_EXPIRES)
        it[PAIRING_STATE] = PairingState.UNPAIRED.name
        if (reason != null) it[LAST_ERROR] = reason else it.remove(LAST_ERROR)
    }

    suspend fun setInterval(seconds: Int) = store.edit { it[INTERVAL] = seconds }
    suspend fun setUploadRule(rule: UploadRule) = store.edit { it[UPLOAD_RULE] = rule.name }
    suspend fun setServiceEnabled(enabled: Boolean) = store.edit { it[SERVICE_ENABLED] = enabled }
    suspend fun markSample(at: Long) = store.edit { it[LAST_SAMPLE] = at }
    suspend fun markHeartbeat(at: Long) = store.edit { it[LAST_HEARTBEAT] = at; it.remove(LAST_ERROR) }
    suspend fun markUpload(at: Long) = store.edit { it[LAST_UPLOAD] = at }
    suspend fun setError(message: String?) = store.edit { if (message == null) it.remove(LAST_ERROR) else it[LAST_ERROR] = message }

    companion object {
        private val SERVER_URL = stringPreferencesKey("server_url")
        private val DISPLAY_NAME = stringPreferencesKey("display_name")
        private val MACHINE_ID = stringPreferencesKey("machine_id")
        private val PAIRING_STATE = stringPreferencesKey("pairing_state")
        private val PAIRING_ID = stringPreferencesKey("pairing_id")
        private val PAIRING_SECRET = stringPreferencesKey("pairing_secret")
        private val PAIRING_EXPIRES = stringPreferencesKey("pairing_expires")
        private val NODE_ID = stringPreferencesKey("node_id")
        private val TOKEN = stringPreferencesKey("agent_token")
        private val INTERVAL = intPreferencesKey("interval_seconds")
        private val UPLOAD_RULE = stringPreferencesKey("upload_rule")
        private val SERVICE_ENABLED = booleanPreferencesKey("service_enabled")
        private val LAST_SAMPLE = longPreferencesKey("last_sample_at")
        private val LAST_HEARTBEAT = longPreferencesKey("last_heartbeat_at")
        private val LAST_UPLOAD = longPreferencesKey("last_upload_at")
        private val LAST_ERROR = stringPreferencesKey("last_error")

        private val random = SecureRandom()

        fun randomHex(bytes: Int): String =
            ByteArray(bytes).also { random.nextBytes(it) }.joinToString("") { "%02x".format(it) }

        fun randomUrlSafe(bytes: Int): String =
            Base64.getUrlEncoder().withoutPadding().encodeToString(ByteArray(bytes).also { random.nextBytes(it) })
    }
}
