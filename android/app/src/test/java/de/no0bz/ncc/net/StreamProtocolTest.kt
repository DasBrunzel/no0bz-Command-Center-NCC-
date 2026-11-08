package de.no0bz.ncc.net

// Echte Netzwerk-Threads (OkHttp) brauchen echte Zeit – daher runBlocking statt runTest.
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class StreamProtocolTest {
    private val alertJson =
        """{"alert_id":"a1","node_id":"n1","node_name":"Tower","kind":"disk","severity":"critical","message":"Tower: Laufwerk bei 97 %","opened_at":"2026-11-08T00:00:00+00:00"}"""

    @Test
    fun parsesServerMessages() {
        assertEquals(StreamEvent.ViewerPresent(2000), StreamProtocol.parse("""{"type":"viewer.present","interval_ms":2000}"""))
        assertEquals(StreamEvent.ViewerGone, StreamProtocol.parse("""{"type":"viewer.gone"}"""))
        assertEquals(StreamEvent.Ping, StreamProtocol.parse("""{"type":"ping"}"""))

        val snapshot = StreamProtocol.parse("""{"type":"alert.snapshot","alerts":[$alertJson]}""") as StreamEvent.AlertSnapshot
        assertEquals("Tower", snapshot.alerts.single().nodeName)
        assertTrue(snapshot.alerts.single().critical)

        val opened = StreamProtocol.parse("""{"type":"alert.new","alert":$alertJson}""") as StreamEvent.AlertNew
        assertEquals("a1", opened.alert.alertId)
        assertTrue(StreamProtocol.parse("""{"type":"alert.resolved","alert":$alertJson}""") is StreamEvent.AlertResolved)
    }

    @Test
    fun clampsTooFastLiveIntervals() {
        assertEquals(StreamEvent.ViewerPresent(1000), StreamProtocol.parse("""{"type":"viewer.present","interval_ms":10}"""))
        assertEquals(StreamEvent.ViewerPresent(2000), StreamProtocol.parse("""{"type":"viewer.present"}"""))
    }

    @Test
    fun ignoresUnknownOrBrokenMessages() {
        assertNull(StreamProtocol.parse("""{"type":"config.update","interval_s":60}"""))
        assertNull(StreamProtocol.parse("kein json"))
        assertNull(StreamProtocol.parse("""{"type":"alert.new"}"""))
    }

    @Test
    fun buildsLiveMessage() {
        val text = StreamProtocol.liveMessage("2026-11-08T12:00:00Z", buildJsonObject { put("x", 1) })
        val json = NccApi.json.parseToJsonElement(text).jsonObject
        assertEquals("telemetry.live", json["type"]!!.jsonPrimitive.content)
        assertEquals("2026-11-08T12:00:00Z", json["recorded_at"]!!.jsonPrimitive.content)
        assertEquals("1", json["metrics"]!!.jsonObject["x"]!!.jsonPrimitive.content)
    }

    @Test
    fun liveSocketDeliversEventsAndSendsWithBearerToken() = runBlocking {
        val serverSide = CompletableDeferred<WebSocket>()
        val received = CompletableDeferred<String>()
        MockWebServer().use { server ->
            server.enqueue(
                MockResponse.Builder().webSocketUpgrade(object : WebSocketListener() {
                    override fun onOpen(webSocket: WebSocket, response: Response) {
                        webSocket.send("""{"type":"alert.snapshot","alerts":[]}""")
                        webSocket.send("""{"type":"viewer.present","interval_ms":2000}""")
                        serverSide.complete(webSocket)
                    }

                    override fun onMessage(webSocket: WebSocket, text: String) {
                        received.complete(text)
                        webSocket.close(1000, null)
                    }
                }).build(),
            )
            server.start()
            val socket = LiveSocket()
            val events = mutableListOf<StreamEvent>()
            withTimeout(10_000) {
                socket.run(server.url("/").toString().trimEnd('/'), "ncc_agent_test") { event ->
                    events += event
                    if (event is StreamEvent.ViewerPresent) assertTrue(socket.send("""{"type":"telemetry.live"}"""))
                }
            }
            assertEquals(listOf(StreamEvent.AlertSnapshot(emptyList()), StreamEvent.ViewerPresent(2000)), events)
            assertEquals("""{"type":"telemetry.live"}""", received.await())
            val request = server.takeRequest()
            assertEquals("/api/v1/nodes/stream", request.url.encodedPath)
            assertEquals("Bearer ncc_agent_test", request.headers["Authorization"])
        }
    }

    @Test
    fun rejectedHandshakeSurfacesAs401() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(MockResponse(code = 403))
            server.start()
            try {
                withTimeout(10_000) { LiveSocket().run(server.url("/").toString().trimEnd('/'), "bad") { } }
                fail("Ablehnung erwartet")
            } catch (e: ApiException) {
                assertEquals(401, e.code)
            }
        }
    }
}
