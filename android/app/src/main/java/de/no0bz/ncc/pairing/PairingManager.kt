package de.no0bz.ncc.pairing

import de.no0bz.ncc.BuildConfig
import de.no0bz.ncc.collect.DeviceReader
import de.no0bz.ncc.collect.MetricsMapper
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.net.ApiException
import de.no0bz.ncc.net.EnrollRequest
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.PairingRegisterRequest

/**
 * Kopplung mit dem NCC-Server – derselbe Ablauf wie beim PC-Agent:
 * 1. Anfrage registrieren → erscheint im Dashboard unter „Kopplungsanfragen“
 * 2. Commander gibt frei
 * 3. App holt ihr Agent-Token ab und meldet sich als Node an
 */
class PairingManager(
    private val settings: AppSettings,
    private val reader: DeviceReader,
    private val apiFactory: (String) -> NccApi = { NccApi(it) },
) {
    sealed interface Step {
        data object Waiting : Step
        data class Paired(val nodeId: String) : Step
        data class Failed(val message: String) : Step
    }

    suspend fun request(serverUrl: String, displayName: String): Step {
        settings.setServer(serverUrl, displayName)
        val pairingId = "android_" + AppSettings.randomUrlSafe(18)
        val secret = AppSettings.randomUrlSafe(32)
        return try {
            val response = register(serverUrl, displayName, pairingId, secret)
            settings.startPairing(pairingId, secret, response.expiresAt)
            Step.Waiting
        } catch (e: Exception) {
            Step.Failed(describe(e))
        }
    }

    /** Fragt einmal nach, ob die Freigabe erteilt ist. Abgelaufene Anfragen werden erneuert. */
    suspend fun poll(): Step {
        val s = settings.current()
        if (s.pairingState != PairingState.WAITING) return Step.Failed("Keine Kopplung offen.")
        val pairingId = s.pairingId ?: return Step.Failed("Kopplung unvollständig.")
        val secret = s.pairingSecret ?: return Step.Failed("Kopplung unvollständig.")
        val api = apiFactory(s.serverUrl)
        return try {
            val token = api.claimPairing(pairingId, secret) ?: return Step.Waiting
            enroll(api, token, s.displayName ?: reader.read().device.name, s.intervalSeconds)
        } catch (e: ApiException) {
            if (e.code == 410) {
                // Abgelaufen: Mit derselben Kennung neu anfragen (Server öffnet sie wieder).
                runCatching { register(s.serverUrl, s.displayName ?: "Android", pairingId, secret) }
                    .onSuccess { settings.updatePairingExpiry(it.expiresAt) }
                Step.Waiting
            } else {
                Step.Failed(describe(e))
            }
        } catch (e: Exception) {
            Step.Failed(describe(e))
        }
    }

    suspend fun cancel() = settings.unpair()

    private suspend fun register(serverUrl: String, displayName: String, pairingId: String, secret: String) =
        apiFactory(serverUrl).registerPairing(
            PairingRegisterRequest(
                pairingId = pairingId,
                pairingSecret = secret,
                machineId = settings.machineId(),
                displayName = displayName.take(128),
                agentVersion = BuildConfig.VERSION_NAME,
                metadata = MetricsMapper.metadata(reader.read(), settings.current().intervalSeconds, BuildConfig.VERSION_NAME),
            ),
        )

    private suspend fun enroll(api: NccApi, token: String, displayName: String, interval: Int): Step {
        val node = api.enroll(
            token,
            EnrollRequest(
                machineId = settings.machineId(),
                displayName = displayName.take(128),
                agentVersion = BuildConfig.VERSION_NAME,
                metadata = MetricsMapper.metadata(reader.read(), interval, BuildConfig.VERSION_NAME),
            ),
        )
        settings.completePairing(token, node.nodeId)
        return Step.Paired(node.nodeId)
    }

    companion object {
        fun describe(e: Exception): String = when (e) {
            is ApiException -> when (e.code) {
                401 -> "Server lehnt den Zugang ab."
                403 -> "Gerät ist im NCC nicht freigegeben."
                409 -> "Gerät ist bereits einem anderen Zugang zugeordnet."
                410 -> "Kopplungsanfrage ist abgelaufen."
                422 -> "Server kennt die Plattform „android“ noch nicht (Server-Update nötig)."
                429 -> "Zu viele Anfragen – bitte kurz warten."
                else -> "Serverfehler ${e.code}."
            }
            is java.net.UnknownHostException, is java.net.ConnectException, is java.net.SocketTimeoutException ->
                "Server nicht erreichbar – ist Tailscale verbunden?"
            else -> e.message ?: e.javaClass.simpleName
        }
    }
}
