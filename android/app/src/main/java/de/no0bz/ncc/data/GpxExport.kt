package de.no0bz.ncc.data

import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.TelemetryPoint
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import java.io.File
import java.util.Locale

/** Erzeugt aus den lokalen Tages-Logdateien einen GPX-Track (nur Messpunkte mit Standort). */
object GpxExport {
    data class Result(val gpx: String, val points: Int)

    fun fromLogs(files: List<File>, name: String): Result {
        val builder = StringBuilder()
        builder.append("""<?xml version="1.0" encoding="UTF-8"?>""").append('\n')
        builder.append("""<gpx version="1.1" creator="NCC Android" xmlns="http://www.topografix.com/GPX/1/1">""").append('\n')
        builder.append("  <trk><name>").append(escape(name)).append("</name>\n")
        var count = 0
        for (file in files.sortedBy { it.name }) {
            val points = file.readLines().mapNotNull { line ->
                runCatching { NccApi.json.decodeFromString(TelemetryPoint.serializer(), line) }.getOrNull()
            }.mapNotNull { point ->
                val location = point.metrics["location"] as? JsonObject ?: return@mapNotNull null
                val lat = (location["lat"] as? JsonPrimitive)?.doubleOrNull ?: return@mapNotNull null
                val lon = (location["lon"] as? JsonPrimitive)?.doubleOrNull ?: return@mapNotNull null
                Triple(lat, lon, point.recordedAt)
            }
            if (points.isEmpty()) continue
            builder.append("    <trkseg>\n")
            for ((lat, lon, time) in points) {
                builder.append(String.format(Locale.ROOT, "      <trkpt lat=\"%.6f\" lon=\"%.6f\"><time>%s</time></trkpt>\n", lat, lon, escape(time)))
                count++
            }
            builder.append("    </trkseg>\n")
        }
        builder.append("  </trk>\n</gpx>\n")
        return Result(builder.toString(), count)
    }

    private fun escape(text: String): String =
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
}
