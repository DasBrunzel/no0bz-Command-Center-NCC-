package de.no0bz.ncc.ui.chat

import android.app.Application
import android.content.Intent
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.AttachmentFiles
import de.no0bz.ncc.data.ChatStore
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.data.PendingAttachment
import de.no0bz.ncc.net.ChatMessage
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.pairing.PairingManager
import de.no0bz.ncc.service.AlertNotifier
import de.no0bz.ncc.service.LiveState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

data class ChatUi(
    val paired: Boolean? = null,
    val nodeId: String? = null,
    val loading: Boolean = false,
    val loadingOlder: Boolean = false,
    val hasOlder: Boolean = true,
    val sending: Boolean = false,
    val error: String? = null,
    val pending: PendingAttachment? = null,
)

class ChatViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application
    private val settings = AppSettings(application)
    private val files = AttachmentFiles(application)
    private val notifier = AlertNotifier(application, settings)

    val messages: StateFlow<List<ChatMessage>> = ChatStore.messages

    private val _ui = MutableStateFlow(ChatUi())
    val ui: StateFlow<ChatUi> = _ui.asStateFlow()

    val chatNotifications: StateFlow<Boolean> =
        settings.settings.map { it.chatNotifications }.stateIn(viewModelScope, SharingStarted.Eagerly, true)

    private var cameraFile: File? = null

    init {
        viewModelScope.launch(Dispatchers.IO) { files.prune() }
        viewModelScope.launch {
            settings.settings.collect { s ->
                val paired = s.pairingState == PairingState.PAIRED
                if (_ui.value.paired == true && !paired) ChatStore.clear()
                _ui.value = _ui.value.copy(paired = paired, nodeId = s.nodeId)
            }
        }
        viewModelScope.launch {
            // Ohne Live-Kanal (Überwachung aus) alle 5 s nachsehen; mit Live-Kanal nur als Sicherheitsnetz.
            while (isActive) {
                if (_ui.value.paired == true && ChatStore.visible) refresh()
                delay(if (LiveState.connected.value) 30_000 else 5_000)
            }
        }
    }

    private suspend fun session(): Pair<NccApi, String>? {
        val s = settings.current()
        val token = settings.token() ?: return null
        if (s.pairingState != PairingState.PAIRED) return null
        return NccApi(s.serverUrl) to token
    }

    /** Lädt beim ersten Mal die neuesten Nachrichten, danach nur, was seit der letzten dazukam. */
    suspend fun refresh() {
        val (api, token) = session() ?: return
        val first = ChatStore.newestId == null
        if (first) _ui.value = _ui.value.copy(loading = true)
        try {
            val newer = api.chatMessages(token, after = ChatStore.newestId)
            ChatStore.append(newer)
            _ui.value = _ui.value.copy(loading = false, error = null, hasOlder = if (first) newer.size >= PAGE else _ui.value.hasOlder)
        } catch (e: Exception) {
            _ui.value = _ui.value.copy(loading = false, error = PairingManager.describe(e))
        }
    }

    fun onVisible(visible: Boolean) {
        ChatStore.visible = visible
        if (visible) {
            notifier.clearChat()
            viewModelScope.launch { refresh() }
        }
    }

    fun loadOlder() {
        val oldest = ChatStore.oldestId ?: return
        if (_ui.value.loadingOlder || !_ui.value.hasOlder) return
        _ui.value = _ui.value.copy(loadingOlder = true)
        viewModelScope.launch {
            try {
                val (api, token) = session() ?: return@launch
                val older = api.chatMessages(token, before = oldest)
                ChatStore.prepend(older)
                _ui.value = _ui.value.copy(loadingOlder = false, hasOlder = older.size >= PAGE)
            } catch (e: Exception) {
                _ui.value = _ui.value.copy(loadingOlder = false, error = PairingManager.describe(e))
            }
        }
    }

    /** Sendet Text und/oder den vorbereiteten Anhang. [onSent] läuft nur bei Erfolg (Eingabefeld leeren). */
    fun send(text: String, markdown: Boolean, onSent: () -> Unit) {
        val pending = _ui.value.pending
        val body = text.trim()
        if (_ui.value.sending || (body.isEmpty() && pending == null)) return
        _ui.value = _ui.value.copy(sending = true, error = null)
        viewModelScope.launch {
            try {
                val (api, token) = session() ?: throw IllegalStateException("Nicht gekoppelt.")
                val message = if (pending != null) {
                    api.uploadChat(token, pending.file, pending.name, pending.contentType, body, markdown)
                } else {
                    api.sendChat(token, body, markdown)
                }
                if (pending != null) {
                    // Das eigene Bild steht sofort als Vorschau bereit, ohne erneuten Download.
                    val cached = files.downloaded(message.messageId, pending.name)
                    withContext(Dispatchers.IO) { if (!pending.file.renameTo(cached)) pending.file.delete() }
                }
                ChatStore.append(listOf(message))
                _ui.value = _ui.value.copy(sending = false, pending = null)
                onSent()
            } catch (e: Exception) {
                _ui.value = _ui.value.copy(sending = false, error = PairingManager.describe(e))
            }
        }
    }

    fun attach(uri: Uri) {
        viewModelScope.launch {
            val attachment = withContext(Dispatchers.IO) { runCatching { files.fromUri(uri) }.getOrNull() }
            setPending(attachment, "Die Datei konnte nicht gelesen werden.")
        }
    }

    /** Ziel für die Kamera-App; das Ergebnis meldet [onPhotoTaken]. */
    fun newCameraUri(): Uri = files.newCameraFile().also { cameraFile = it }.let(files::uriFor)

    fun onPhotoTaken(success: Boolean) {
        val file = cameraFile ?: return
        cameraFile = null
        if (!success) {
            file.delete()
            return
        }
        viewModelScope.launch {
            val attachment = withContext(Dispatchers.IO) { files.fromCamera(file) }
            setPending(attachment, "Das Foto konnte nicht gelesen werden.")
        }
    }

    private fun setPending(attachment: PendingAttachment?, failure: String) {
        _ui.value.pending?.let(files::discard)
        _ui.value = if (attachment == null) {
            _ui.value.copy(pending = null, error = failure)
        } else if (attachment.file.length() > MAX_UPLOAD_BYTES) {
            files.discard(attachment)
            _ui.value.copy(pending = null, error = "Der Anhang ist größer als 100 MB.")
        } else {
            _ui.value.copy(pending = attachment, error = null)
        }
    }

    fun removePending() {
        _ui.value.pending?.let(files::discard)
        _ui.value = _ui.value.copy(pending = null)
    }

    fun dismissError() {
        _ui.value = _ui.value.copy(error = null)
    }

    fun setChatNotifications(enabled: Boolean) {
        viewModelScope.launch { settings.setChatNotifications(enabled) }
    }

    /** Lokale Datei eines Anhangs; lädt ihn bei Bedarf herunter. */
    suspend fun attachmentFile(message: ChatMessage): File? {
        val attachment = message.attachment ?: return null
        val target = files.downloaded(message.messageId, attachment.name)
        if (target.exists() && target.length() > 0) return target
        val (api, token) = session() ?: return null
        return runCatching { api.downloadAttachment(token, message.messageId, target); target }.getOrNull()
    }

    /** Öffnet einen Anhang in einer passenden App (Bildbetrachter, PDF-Anzeige …). */
    fun open(message: ChatMessage) {
        val attachment = message.attachment ?: return
        viewModelScope.launch {
            val file = attachmentFile(message)
            if (file == null) {
                _ui.value = _ui.value.copy(error = "Der Anhang konnte nicht geladen werden.")
                return@launch
            }
            val view = Intent(Intent.ACTION_VIEW)
                .setDataAndType(files.uriFor(file), attachment.contentType)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            runCatching { app.startActivity(view) }.onFailure {
                _ui.value = _ui.value.copy(error = "Keine App zum Öffnen von „${attachment.name}“ gefunden.")
            }
        }
    }

    override fun onCleared() {
        ChatStore.visible = false
    }

    companion object {
        private const val PAGE = 60
        private const val MAX_UPLOAD_BYTES = 100L * 1024 * 1024
    }
}
