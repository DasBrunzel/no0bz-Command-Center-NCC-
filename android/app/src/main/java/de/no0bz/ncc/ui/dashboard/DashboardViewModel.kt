package de.no0bz.ncc.ui.dashboard

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.no0bz.ncc.collect.DeviceReader
import de.no0bz.ncc.collect.DeviceSnapshot
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.stateIn

/**
 * Stufe „Lokal live“: solange das Dashboard sichtbar ist, wird jede Sekunde neu gemessen.
 * Ist die App im Hintergrund, stoppt die Messung nach 5 s (WhileSubscribed).
 */
class DashboardViewModel(application: Application) : AndroidViewModel(application) {
    private val reader = DeviceReader(application)

    val snapshot: StateFlow<DeviceSnapshot?> = flow {
        while (true) {
            emit(reader.read())
            delay(LIVE_INTERVAL_MS)
        }
    }
        .flowOn(Dispatchers.IO)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    companion object {
        const val LIVE_INTERVAL_MS = 1_000L
    }
}
