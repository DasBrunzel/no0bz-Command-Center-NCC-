package de.no0bz.ncc.service

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Zustand des Live-Kanals, geteilt zwischen Hintergrunddienst und Oberfläche (gleicher Prozess). */
object LiveState {
    private val _connected = MutableStateFlow(false)
    val connected: StateFlow<Boolean> = _connected.asStateFlow()

    /** Ein Dashboard schaut gerade zu – das Handy streamt alle paar Sekunden. */
    private val _watched = MutableStateFlow(false)
    val watched: StateFlow<Boolean> = _watched.asStateFlow()

    private val _activeAlerts = MutableStateFlow(0)
    val activeAlerts: StateFlow<Int> = _activeAlerts.asStateFlow()

    internal fun setConnected(value: Boolean) {
        _connected.value = value
        if (!value) _watched.value = false
    }

    internal fun setWatched(value: Boolean) {
        _watched.value = value
    }

    internal fun setActiveAlerts(count: Int) {
        _activeAlerts.value = count
    }
}
