package de.no0bz.ncc.net

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.selects.select
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Live-Kanal zum NCC-Server (WebSocket). [run] verbindet, liefert alle Nachrichten an [onEvent] und
 * kehrt zurück, wenn die Verbindung endet. Während sie offen ist, schickt [send] Live-Messwerte hoch.
 */
class LiveSocket(private val client: OkHttpClient = streamClient) {
    @Volatile
    private var socket: WebSocket? = null

    val isOpen: Boolean get() = socket != null

    suspend fun run(baseUrl: String, token: String, onOpen: () -> Unit = {}, onEvent: suspend (StreamEvent) -> Unit) {
        val messages = Channel<String>(Channel.UNLIMITED)
        val closed = CompletableDeferred<Throwable?>()
        val request = Request.Builder()
            .url("$baseUrl/api/v1/nodes/stream")
            .header("Authorization", "Bearer $token")
            .build()
        val ws = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                socket = webSocket
                onOpen()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                messages.trySend(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                closed.complete(if (code == 1000) null else IOException("Live-Kanal geschlossen ($code)"))
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                val code = response?.code
                closed.complete(if (code == 401 || code == 403) ApiException(401, "Live-Kanal abgelehnt") else t)
            }
        })
        try {
            while (true) {
                val next = select {
                    messages.onReceive { it }
                    closed.onAwait { null }
                }
                if (next == null) break
                StreamProtocol.parse(next)?.let { onEvent(it) }
            }
            closed.await()?.let { throw it }
        } finally {
            socket = null
            ws.cancel()
            messages.close()
        }
    }

    /** Sendet eine Textnachricht; false, wenn gerade keine Verbindung besteht. */
    fun send(text: String): Boolean = socket?.send(text) ?: false

    companion object {
        private val streamClient: OkHttpClient by lazy {
            OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(0, TimeUnit.MILLISECONDS)
                // Hält NAT/VPN-Wege offen und erkennt tote Verbindungen.
                .pingInterval(25, TimeUnit.SECONDS)
                .build()
        }
    }
}
