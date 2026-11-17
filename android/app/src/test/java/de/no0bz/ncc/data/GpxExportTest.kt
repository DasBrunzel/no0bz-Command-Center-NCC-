package de.no0bz.ncc.data

import de.no0bz.ncc.collect.LocationFix
import de.no0bz.ncc.collect.MetricsMapper
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.TelemetryPoint
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import javax.xml.parsers.DocumentBuilderFactory

class GpxExportTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun line(id: String, time: String, lat: Double?, lon: Double?): String {
        val metrics = buildJsonObject {
            put("battery", buildJsonObject { put("percent", 50) })
            if (lat != null && lon != null) putJsonObject("location") { put("lat", lat); put("lon", lon) }
        }
        return NccApi.json.encodeToString(TelemetryPoint.serializer(), TelemetryPoint(id, time, metrics))
    }

    @Test
    fun buildsValidGpxFromLogsAndSkipsPointsWithoutLocation() {
        val day1 = tmp.newFile("2026-11-16.jsonl").apply {
            writeText(listOf(line("a", "2026-11-16T08:00:00Z", 52.52, 13.405), line("b", "2026-11-16T08:01:00Z", null, null), "kaputt").joinToString("\n") + "\n")
        }
        val day2 = tmp.newFile("2026-11-17.jsonl").apply {
            writeText(line("c", "2026-11-17T09:00:00Z", 48.137, 11.575) + "\n")
        }
        val result = GpxExport.fromLogs(listOf(day2, day1), "Handy <Test> & Co")
        assertEquals(2, result.points)

        val doc = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }.newDocumentBuilder()
            .parse(result.gpx.byteInputStream())
        val points = doc.getElementsByTagName("trkpt")
        assertEquals(2, points.length)
        assertEquals("52.520000", points.item(0).attributes.getNamedItem("lat").nodeValue)
        assertEquals(2, doc.getElementsByTagName("trkseg").length)
        assertEquals("Handy <Test> & Co", doc.getElementsByTagName("name").item(0).textContent)
    }

    @Test
    fun noLocationsMeansNoPoints() {
        val day = tmp.newFile("2026-11-17.jsonl").apply { writeText(line("a", "2026-11-17T08:00:00Z", null, null) + "\n") }
        assertEquals(0, GpxExport.fromLogs(listOf(day), "x").points)
    }

    @Test
    fun metricsCarryLocationOnlyWhenGiven() {
        val snapshot = de.no0bz.ncc.collect.MetricsMapperTest().let { test ->
            test.javaClass.getDeclaredMethod("snapshot").apply { isAccessible = true }.invoke(test) as de.no0bz.ncc.collect.DeviceSnapshot
        }
        assertFalse(MetricsMapper.map(snapshot, null).containsKey("location"))
        val withFix = MetricsMapper.map(snapshot, null, LocationFix(52.52, 13.405, 7.25f, 0))
        val location = withFix["location"]!!.jsonObject
        assertEquals(52.52, location["lat"]!!.jsonPrimitive.double, 0.0)
        assertEquals(7.3, location["accuracy_m"]!!.jsonPrimitive.double, 0.001)
        assertTrue(withFix["android"] is JsonObject)
    }
}
