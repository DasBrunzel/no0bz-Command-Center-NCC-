package de.no0bz.ncc.ui.chat

import de.no0bz.ncc.data.AttachmentFiles
import de.no0bz.ncc.data.ChatStore
import de.no0bz.ncc.net.ChatMessage
import de.no0bz.ncc.net.FleetNode
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.StreamEvent
import de.no0bz.ncc.net.StreamProtocol
import de.no0bz.ncc.ui.chat.Markdown.Span
import de.no0bz.ncc.ui.fleet.FleetSummary
import kotlinx.coroutines.runBlocking
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.time.Instant

class ChatLogicTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun message(id: String) = ChatMessage(messageId = id, senderName = "Tower", createdAt = "2026-11-10T10:00:00+00:00")

    @Test
    fun markdownInlineSpans() {
        assertEquals(
            listOf(Span.Text("Das ist "), Span.Text("fett", bold = true), Span.Text(", "), Span.Text("kursiv", italic = true), Span.Text(" und "), Span.Code("code")),
            Markdown.inline("Das ist **fett**, *kursiv* und `code`"),
        )
        assertEquals(listOf(Span.Text("weg", strike = true)), Markdown.inline("~~weg~~"))
        assertEquals(
            listOf(Span.Link("NCC", "https://example.net/a"), Span.Text(" "), Span.Link("https://example.net/b", "https://example.net/b")),
            Markdown.inline("[NCC](https://example.net/a) https://example.net/b"),
        )
    }

    @Test
    fun markdownNeverLinksUnsafeSchemes() {
        assertEquals(listOf(Span.Text("klick")), Markdown.inline("[klick](javascript:alert(1))").take(1))
        assertEquals(listOf(Span.Text("datei_name_mit_unterstrich")), Markdown.inline("datei_name_mit_unterstrich"))
        assertEquals(listOf(Span.Text("2 * 3 * 4")), Markdown.inline("2 * 3 * 4"))
    }

    @Test
    fun storeMergesWithoutDuplicates() {
        val current = listOf(message("b"), message("c"))
        assertEquals(listOf("b", "c", "d"), ChatStore.merge(current, listOf(message("c"), message("d")), atEnd = true).map { it.messageId })
        assertEquals(listOf("a", "b", "c"), ChatStore.merge(current, listOf(message("a"), message("b")), atEnd = false).map { it.messageId })
        assertTrue(ChatStore.merge(current, listOf(message("b")), atEnd = true) === current)
    }

    @Test
    fun parsesChatEventAndTimestamps() {
        val event = StreamProtocol.parse(
            """{"type":"chat.new","message":{"message_id":"m1","sender_node_id":null,"sender_user_id":"u1","sender_name":"Commander","body":"Hi","body_format":"markdown","attachment":{"name":"a.jpg","content_type":"image/jpeg","size":12,"url":"/x"},"created_at":"2026-11-10T10:00:00+00:00"}}""",
        ) as StreamEvent.ChatNew
        assertTrue(event.message.markdown)
        assertTrue(event.message.attachment!!.isImage)
        assertEquals(Instant.parse("2026-11-10T10:00:00Z"), parseInstant("2026-11-10T10:00:00+00:00"))
        // SQLite liefert Zeitstempel ohne Zeitzone – sie gelten als UTC.
        assertEquals(Instant.parse("2026-11-10T10:00:00Z"), parseInstant("2026-11-10T10:00:00"))
        assertNull(parseInstant("kaputt"))
    }

    @Test
    fun fleetSummaryReadsPcAndPhoneMetrics() {
        val pc = NccApi.json.decodeFromString(
            FleetNode.serializer(),
            """{"node_id":"n1","display_name":"HomePC","platform":"windows","online":true,"latest":{"recorded_at":"x","metrics":{"cpu":{"percent":12.5,"temperature_c":48,"model":"Ryzen 7"},"memory":{"percent":40},"gpus":[{"percent":7,"temperature_c":50}],"lhm_gpus":[{"temperature_c":55}],"disks":[{"percent":30},{"percent":81.2}]}}}""",
        )
        val s = FleetSummary.of(pc)
        assertEquals("Windows", s.platformLabel)
        assertEquals(12.5, s.cpuPercent!!, 0.001)
        assertEquals(81.2, s.diskPercent!!, 0.001)
        assertEquals(55.0, s.gpuTemp!!, 0.001)
        assertEquals("Ryzen 7", s.model)

        val phone = NccApi.json.decodeFromString(
            FleetNode.serializer(),
            """{"node_id":"n2","display_name":"Pixel","platform":"android","online":false,"metadata":{},"latest":{"recorded_at":"x","metrics":{"battery":{"percent":21,"plugged":true},"android":{"soc":"Google Tensor G2"}}}}""",
        )
        val p = FleetSummary.of(phone)
        assertEquals("Android", p.platformLabel)
        assertEquals(21.0, p.batteryPercent!!, 0.001)
        assertEquals(true, p.batteryPlugged)
        assertNull(p.cpuPercent)
        assertEquals("Google Tensor G2", p.model)

        val unraid = NccApi.json.decodeFromString(
            FleetNode.serializer(),
            """{"node_id":"n3","display_name":"Tower","platform":"linux","online":true,"metadata":{"source":"unraid-api"}}""",
        )
        assertEquals("Unraid", FleetSummary.of(unraid).platformLabel)
    }

    @Test
    fun apiUploadsMultipartAndDownloadsAttachment() = runBlocking {
        MockWebServer().use { server ->
            server.enqueue(
                MockResponse(
                    code = 201,
                    body = """{"message_id":"m9","sender_node_id":"n1","sender_user_id":null,"sender_name":"Pixel","body":"Foto","body_format":"plain","attachment":{"name":"IMG.jpg","content_type":"image/jpeg","size":4,"url":"/x"},"created_at":"2026-11-10T10:00:00+00:00"}""",
                ),
            )
            server.enqueue(MockResponse(code = 200, body = "JPEG"))
            server.enqueue(MockResponse(code = 404))
            server.start()
            val api = NccApi(server.url("/").toString().trimEnd('/'))

            val source = tmp.newFile("IMG.jpg").apply { writeText("JPEG") }
            val sent = api.uploadChat("ncc_agent_x", source, "IMG.jpg", "image/jpeg", "Foto", markdown = false)
            assertEquals("m9", sent.messageId)
            val upload = server.takeRequest()
            assertEquals("/api/v1/nodes/chat/uploads", upload.url.encodedPath)
            assertEquals("Bearer ncc_agent_x", upload.headers["Authorization"])
            val body = upload.body!!.utf8()
            assertTrue(body.contains("name=\"file\"; filename=\"IMG.jpg\""))
            assertTrue(body.contains("name=\"body_format\""))

            val target = java.io.File(tmp.root, "out.jpg")
            api.downloadAttachment("ncc_agent_x", "m9", target)
            assertEquals("JPEG", target.readText())
            assertEquals("/api/v1/nodes/chat/messages/m9/attachment", server.takeRequest().url.encodedPath)

            // Ein fehlgeschlagener Download hinterlässt keine halbe Datei.
            val missing = java.io.File(tmp.root, "missing.bin")
            assertTrue(runCatching { api.downloadAttachment("ncc_agent_x", "nope", missing) }.isFailure)
            assertTrue(!missing.exists() && !java.io.File(tmp.root, "missing.bin.part").exists())
        }
    }

    @Test
    fun attachmentNamesAreSanitised() {
        assertEquals("Foto _1_.jpg", AttachmentFiles.safe("Foto (1).jpg"))
        assertEquals("_etc_passwd", AttachmentFiles.safe("../etc/passwd").removePrefix(".."))
        assertEquals("Anhang", AttachmentFiles.safe(""))
    }
}
