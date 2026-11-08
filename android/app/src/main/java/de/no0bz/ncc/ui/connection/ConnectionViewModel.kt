package de.no0bz.ncc.ui.connection

import android.app.Application
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

data class Reachability(val vpn: Boolean = false, val server: Boolean? = null)

data class BufferInfo(val pending: Int = 0, val files: Int = 0, val bytes: Long = 0)

class ConnectionViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application
    private val appSettings = AppSettings(application)
    private val reader = DeviceReader(application)
    private val pairing = PairingManager(appSettings, reader)
    private val conditions = Conditions(application)
    private val log = MonitorService.logFor(application)

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
        _reachability.value = Reachability(vpn = conditions.vpnActive(), server = NccApi(url).live())
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
