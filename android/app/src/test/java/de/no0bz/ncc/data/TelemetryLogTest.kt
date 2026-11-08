package de.no0bz.ncc.data

import de.no0bz.ncc.net.TelemetryPoint
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.time.LocalDate
import java.time.ZoneOffset

class TelemetryLogTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun point(i: Int) = TelemetryPoint(
        sampleId = "id-$i",
        recordedAt = "2026-11-08T12:00:${"%02d".format(i % 60)}Z",
        metrics = buildJsonObject { put("n", i); put("text", "Grüße °C") },
    )

    @Test
    fun batchesAcrossDaysAndAdvancesCursor() = runTest {
        val log = TelemetryLog(tmp.newFolder("logs"), ZoneOffset.UTC)
        repeat(3) { log.append(point(it), LocalDate.of(2026, 11, 7)) }
        repeat(4) { log.append(point(10 + it), LocalDate.of(2026, 11, 8)) }
        assertEquals(7, log.pendingCount())

        val first = log.nextBatch(max = 5)!!
        assertEquals(listOf("id-0", "id-1", "id-2", "id-10", "id-11"), first.points.map { it.sampleId })
        // Ohne commit bleibt alles im Puffer (z. B. wenn der Upload scheitert).
        assertEquals(7, log.pendingCount())

        log.commit(first.next)
        assertEquals(2, log.pendingCount())
        val second = log.nextBatch(max = 5)!!
        assertEquals(listOf("id-12", "id-13"), second.points.map { it.sampleId })
        log.commit(second.next)
        assertEquals(0, log.pendingCount())
        assertNull(log.nextBatch())

        log.append(point(20), LocalDate.of(2026, 11, 8))
        assertEquals(listOf("id-20"), log.nextBatch()!!.points.map { it.sampleId })
    }

    @Test
    fun keepsUtf8Intact() = runTest {
        val log = TelemetryLog(tmp.newFolder("utf"), ZoneOffset.UTC)
        log.append(point(1), LocalDate.of(2026, 11, 8))
        val text = log.nextBatch()!!.points.single().metrics["text"].toString()
        assertEquals("\"Grüße °C\"", text)
    }

    @Test
    fun ignoresHalfWrittenLastLine() = runTest {
        val dir = tmp.newFolder("partial")
        val log = TelemetryLog(dir, ZoneOffset.UTC)
        log.append(point(1), LocalDate.of(2026, 11, 8))
        File(dir, "2026-11-08.jsonl").appendText("{\"sample_id\":\"id-2\",\"recor")
        val batch = log.nextBatch()!!
        assertEquals(listOf("id-1"), batch.points.map { it.sampleId })
        log.commit(batch.next)
        // Wird die Zeile fertig geschrieben, kommt sie im nächsten Paket.
        File(dir, "2026-11-08.jsonl").appendText("ded_at\":\"2026-11-08T12:00:02Z\",\"metrics\":{}}\n")
        assertEquals(listOf("id-2"), log.nextBatch()!!.points.map { it.sampleId })
    }

    @Test
    fun prunesOnlyUploadedOldFiles() = runTest {
        val dir = tmp.newFolder("prune")
        val today = LocalDate.now(ZoneOffset.UTC)
        val log = TelemetryLog(dir, ZoneOffset.UTC, retentionDays = 30)
        log.append(point(1), today.minusDays(40))
        log.append(point(2), today.minusDays(35))
        log.append(point(3), today)

        val batch = log.nextBatch(max = 1)!! // nur die älteste Datei bestätigen
        log.commit(batch.next)
        log.commit(log.nextBatch(max = 1)!!.next) // Cursor steht jetzt in der Datei von vor 35 Tagen
        assertFalse(File(dir, "${today.minusDays(40)}.jsonl").exists())
        assertTrue("noch nicht vollständig hinter dem Cursor", File(dir, "${today.minusDays(35)}.jsonl").exists())
        assertTrue(File(dir, "$today.jsonl").exists())
    }
}
