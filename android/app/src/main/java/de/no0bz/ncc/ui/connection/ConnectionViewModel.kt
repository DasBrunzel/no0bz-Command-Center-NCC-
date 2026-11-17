package de.no0bz.ncc.ui.connection

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings as AndroidSettings
import androidx.core.content.FileProvider
import de.no0bz.ncc.collect.LocationAccess
import de.no0bz.ncc.collect.LocationReader
import de.no0bz.ncc.data.GpxExport
import de.no0bz.ncc.net.AppRelease
import de.no0bz.ncc.update.AppUpdater
import de.no0bz.ncc.update.UpdateState
import de.no0bz.ncc.service.LiveState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.time.LocalDate
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.no0bz.ncc.collect.DeviceReader
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.data.Settings
import de.no0bz.ncc.data.UploadRule
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.ServerUrl
import de.no0bz.ncc.pairing.PairingManager
import de.no0bz.ncc.service.Conditions
import de.no0bz.ncc.service.MonitorService
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

data class Reachability(val vpn: Boolean = false, val server: Boolean? = null, val batteryUnrestricted: Boolean = true)

data class BufferInfo(val pending: Int = 0, val files: Int = 0, val bytes: Long = 0)

class ConnectionViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application
    private val appSettings = AppSettings(application)
    private val reader = DeviceReader(application)
    private val pairing = PairingManager(appSettings, reader)
    private val conditions = Conditions(application)
    private val log = MonitorService.logFor(application)
    private val power = application.getSystemService(PowerManager::class.java)

    val liveConnected: StateFlow<Boolean> = LiveState.connected
    val watched: StateFlow<Boolean> = LiveState.watched
    val activeAlerts: StateFlow<Int> = LiveState.activeAlerts

    val settings: StateFlow<Settings?> = appSettings.settings.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    private val _reachability = MutableStateFlow(Reachability())
    val reachability: StateFlow<Reachability> = _reachability.asStateFlow()

    private val _buffer = MutableStateFlow(BufferInfo())
    val buffer: StateFlow<BufferInfo> = _buffer.asStateFlow()

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    val defaultDeviceName: String get() = reader.read().device.name

    private var pollJob: Job? = null

    init {
        viewModelScope.launch {
            // Status alle 5 s auffrischen, solange der Bildschirm offen ist.
            while (isActive) {
                refresh()
                delay(5_000)
            }
        }
        viewModelScope.launch {
            if (appSettings.current().pairingState == PairingState.WAITING) startPolling()
        }
    }

    private suspend fun refresh() {
        val url = appSettings.current().serverUrl
        _reachability.value = Reachability(
            vpn = conditions.vpnActive(),
            server = url.isNotBlank() && NccApi(url).live(),
            batteryUnrestricted = power.isIgnoringBatteryOptimizations(app.packageName),
        )
        _buffer.value = BufferInfo(log.pendingCount(), log.fileCount(), log.totalBytes())
    }

    fun requestPairing(serverInput: String, displayName: String) {
        val url = when (val result = ServerUrl.validate(serverInput)) {
            is ServerUrl.Result.Invalid -> { _message.value = result.reason; return }
            is ServerUrl.Result.Valid -> result.baseUrl
        }
        val name = displayName.trim().ifEmpty { defaultDeviceName }
        viewModelScope.launch {
            _busy.value = true
            when (val step = pairing.request(url, name)) {
                is PairingManager.Step.Failed -> _message.value = step.message
                else -> { _message.value = null; startPolling() }
            }
            _busy.value = false
            refresh()
        }
    }

    private fun startPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            while (isActive) {
                when (val step = pairing.poll()) {
                    is PairingManager.Step.Waiting -> delay(3_000)
                    is PairingManager.Step.Paired -> {
                        _message.value = "Gekoppelt. Die Überwachung läuft."
                        setServiceEnabled(true)
                        return@launch
                    }
                    is PairingManager.Step.Failed -> {
                        _message.value = step.message
                        delay(10_000)
                        if (appSettings.current().pairingState != PairingState.WAITING) return@launch
                    }
                }
            }
        }
    }

    fun cancelPairing() {
        pollJob?.cancel()
        viewModelScope.launch { pairing.cancel(); _message.value = null }
    }

    fun unpair() {
        viewModelScope.launch {
            appSettings.unpair()
            _message.value = "Entkoppelt. Der Node bleibt im Dashboard, bis du ihn dort entfernst."
        }
    }

    fun setServiceEnabled(enabled: Boolean) {
        viewModelScope.launch {
            appSettings.setServiceEnabled(enabled)
            if (enabled) MonitorService.start(app) else MonitorService.stop(app)
        }
    }

    fun setInterval(seconds: Int) {
        viewModelScope.launch {
            appSettings.setInterval(seconds)
            if (appSettings.current().serviceEnabled) MonitorService.start(app, MonitorService.ACTION_RESCHEDULE)
        }
    }

    fun setUploadRule(rule: UploadRule) {
        viewModelScope.launch { appSettings.setUploadRule(rule) }
    }

    fun setAlertsEnabled(enabled: Boolean) {
        viewModelScope.launch { appSettings.setAlertsEnabled(enabled) }
    }

    fun setLiveWifiOnly(enabled: Boolean) {
        viewModelScope.launch { appSettings.setLiveWifiOnly(enabled) }
    }

    private val updater = AppUpdater(application, appSettings)
    val updates: StateFlow<UpdateState> = AppUpdater.updates

    fun checkUpdate() {
        viewModelScope.launch { updater.check() }
    }

    fun downloadUpdate(release: AppRelease) {
        viewModelScope.launch { updater.download(release) }
    }

    /** Öffnet den Android-Installer – oder zuerst die Erlaubnis „Apps aus dieser Quelle installieren“. */
    fun installIntent(apk: File): Intent =
        if (updater.canInstall()) updater.installIntent(apk) else updater.allowInstallIntent().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    fun installAllowed(): Boolean = updater.canInstall()

    /** Nach dem Anlegen des Widgets gleich messen, damit es nicht bis zum nächsten Intervall leer bleibt. */
    fun refreshWidgetSoon() {
        viewModelScope.launch {
            delay(4_000)
            if (appSettings.current().serviceEnabled) MonitorService.start(app, MonitorService.ACTION_RESCHEDULE)
        }
    }

    private val locationReader = LocationReader(application)
    private val _locationAccess = MutableStateFlow(locationReader.access())
    val locationAccess: StateFlow<LocationAccess> = _locationAccess.asStateFlow()

    fun refreshLocationAccess() {
        _locationAccess.value = locationReader.access()
    }

    /** Schaltet den Standortverlauf am Server (maßgeblich) und lokal um. */
    fun setLocationTracking(enabled: Boolean) {
        refreshLocationAccess()
        viewModelScope.launch {
            _busy.value = true
            try {
                val s = appSettings.current()
                val token = appSettings.token() ?: throw IllegalStateException("Nicht gekoppelt.")
                val confirmed = NccApi(s.serverUrl).setLocationTracking(token, enabled)
                appSettings.setLocationTracking(confirmed)
                // Dienst neu anmelden, damit er (mit Berechtigung) als Standort-Dienst läuft.
                if (s.serviceEnabled) MonitorService.start(app, MonitorService.ACTION_RESCHEDULE)
                _message.value = if (confirmed) {
                    if (locationReader.access().background) "Standortverlauf ist an." else
                        "Standortverlauf ist an. Ohne „Immer zulassen“ kommen Standorte nur, solange die App offen ist."
                } else "Standortverlauf ist aus."
            } catch (e: Exception) {
                _message.value = PairingManager.describe(e)
            } finally {
                _busy.value = false
            }
        }
    }

    /** GPX der letzten [days] Tage aus den lokalen Logs; null, wenn darin keine Standorte sind. */
    suspend fun exportGpx(days: Long): File? = withContext(Dispatchers.IO) {
        val result = GpxExport.fromLogs(log.recentFiles(days), defaultDeviceName)
        if (result.points == 0) return@withContext null
        val dir = File(app.cacheDir, "export").apply { mkdirs() }
        File(dir, "ncc-standorte-${LocalDate.now()}.gpx").apply { writeText(result.gpx) }
    }

    fun shareIntent(file: File): Intent {
        val uri = FileProvider.getUriForFile(app, "${app.packageName}.files", file)
        val send = Intent(Intent.ACTION_SEND)
            .setType("application/gpx+xml")
            .putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return Intent.createChooser(send, "GPX teilen")
    }

    fun showMessage(text: String) {
        _message.value = text
    }

    fun deleteServerLocations() {
        viewModelScope.launch {
            _busy.value = true
            try {
                val s = appSettings.current()
                val token = appSettings.token() ?: throw IllegalStateException("Nicht gekoppelt.")
                val deleted = NccApi(s.serverUrl).deleteLocations(token)
                _message.value = "$deleted Standortpunkte auf dem Server gelöscht."
            } catch (e: Exception) {
                _message.value = PairingManager.describe(e)
            } finally {
                _busy.value = false
            }
        }
    }

    /** Öffnet den System-Dialog „Akku-Optimierung ignorieren?“ für NCC. */
    fun batteryOptimizationIntent(): Intent =
        Intent(AndroidSettings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${app.packageName}"))

    fun refreshSoon() {
        viewModelScope.launch { delay(1_000); refresh() }
    }

    fun uploadNow() {
        viewModelScope.launch {
            if (!appSettings.current().serviceEnabled) {
                _message.value = "Erst die Überwachung einschalten."
                return@launch
            }
            MonitorService.start(app, MonitorService.ACTION_UPLOAD_NOW)
            _message.value = "Upload angestoßen."
            delay(3_000)
            refresh()
        }
    }

    fun dismissMessage() = _message.update { null }
}
