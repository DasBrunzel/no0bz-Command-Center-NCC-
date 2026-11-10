package de.no0bz.ncc.data

import de.no0bz.ncc.net.ChatMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * Die geladenen Chat-Nachrichten (älteste zuerst), geteilt zwischen Hintergrunddienst
 * (Live-Kanal) und Oberfläche. Jede Nachricht kommt nur einmal vor.
 */
object ChatStore {
    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    /** Der Chat-Tab ist gerade sichtbar – dann braucht es keine Benachrichtigung. */
    @Volatile
    var visible: Boolean = false

    /** Fügt neuere Nachrichten hinten an (vom Live-Kanal, nach dem Senden oder beim Nachladen). */
    fun append(newer: List<ChatMessage>) = _messages.update { merge(it, newer, atEnd = true) }

    /** Fügt ältere Nachrichten vorne an (Zurückblättern). */
    fun prepend(older: List<ChatMessage>) = _messages.update { merge(it, older, atEnd = false) }

    fun clear() {
        _messages.value = emptyList()
    }

    val newestId: String? get() = _messages.value.lastOrNull()?.messageId
    val oldestId: String? get() = _messages.value.firstOrNull()?.messageId

    internal fun merge(current: List<ChatMessage>, incoming: List<ChatMessage>, atEnd: Boolean): List<ChatMessage> {
        val known = current.mapTo(HashSet()) { it.messageId }
        val fresh = incoming.filter { known.add(it.messageId) }
        if (fresh.isEmpty()) return current
        return if (atEnd) current + fresh else fresh + current
    }
}
