package de.no0bz.ncc.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import de.no0bz.ncc.BuildConfig
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.net.AppRelease
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.pairing.PairingManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

/** Zustand des App-Updates, geteilt zwischen Dienst und Oberfläche. */
sealed interface UpdateState {
    data object Unknown : UpdateState
    data object Checking : UpdateState
    data object UpToDate : UpdateState
    data class Available(val release: AppRelease) : UpdateState
    data class Downloading(val release: AppRelease, val progress: Float) : UpdateState
    data class Ready(val release: AppRelease, val apk: File) : UpdateState
    data class Failed(val message: String, val release: AppRelease? = null) : UpdateState
}

/**
 * Private Updates über den NCC-Server: prüfen, laden, Prüfsumme kontrollieren und den
 * System-Installer öffnen. Android installiert nur, wenn die Signatur zur installierten App passt.
 */
class AppUpdater(context: Context, private val settings: AppSettings = AppSettings(context)) {
    private val app = context.applicationContext
    private val dir = File(app.cacheDir, "update").apply { mkdirs() }

    suspend fun check(): UpdateState {
        val session = session() ?: return UpdateState.Unknown.also { state.value = it }
        state.value = UpdateState.Checking
        val result = try {
            offer(session.first.appRelease(session.second))
        } catch (e: Exception) {
            UpdateState.Failed(PairingManager.describe(e))
        }
        state.value = result
        return result
    }

    /** Wertet eine (z. B. über den Live-Kanal gemeldete) Version aus. */
    fun offer(release: AppRelease?): UpdateState {
        val next = if (release != null && isNewer(release.versionCode)) UpdateState.Available(release) else UpdateState.UpToDate
        // Ein laufender oder fertiger Download derselben Version bleibt erhalten.
        val current = state.value
        val keep = (current is UpdateState.Downloading && next is UpdateState.Available && current.release == next.release) ||
            (current is UpdateState.Ready && next is UpdateState.Available && current.release == next.release)
        if (!keep) state.value = next
        return state.value
    }

    suspend fun download(release: AppRelease): UpdateState {
        val (api, token) = session() ?: return UpdateState.Failed("Nicht gekoppelt.", release).also { state.value = it }
        val apk = File(dir, "ncc-android-${release.versionCode}.apk")
        state.value = UpdateState.Downloading(release, 0f)
        val result = try {
            api.downloadApk(token, apk) { progress -> state.value = UpdateState.Downloading(release, progress) }
            when {
                apk.length() != release.size -> UpdateState.Failed("Download unvollständig.", release)
                !sha256(apk).equals(release.sha256, ignoreCase = true) -> UpdateState.Failed("Prüfsumme stimmt nicht – Update verworfen.", release)
                else -> UpdateState.Ready(release, apk)
            }
        } catch (e: Exception) {
            UpdateState.Failed(PairingManager.describe(e), release)
        }
        if (result !is UpdateState.Ready) apk.delete()
        state.value = result
        return result
    }

    /** Darf NCC Apps installieren? Sonst muss der Nutzer es einmal in den Einstellungen erlauben. */
    fun canInstall(): Boolean = app.packageManager.canRequestPackageInstalls()

    fun allowInstallIntent(): Intent =
        Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${app.packageName}"))

    fun installIntent(apk: File): Intent {
        val uri = FileProvider.getUriForFile(app, "${app.packageName}.files", apk)
        return Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    private suspend fun session(): Pair<NccApi, String>? {
        val s = settings.current()
        val token = settings.token() ?: return null
        if (s.pairingState != PairingState.PAIRED) return null
        return NccApi(s.serverUrl) to token
    }

    companion object {
        private val state = MutableStateFlow<UpdateState>(UpdateState.Unknown)
        val updates: StateFlow<UpdateState> = state.asStateFlow()

        fun isNewer(versionCode: Int, installed: Int = BuildConfig.VERSION_CODE): Boolean = versionCode > installed

        suspend fun sha256(file: File): String = withContext(Dispatchers.IO) {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
            digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
