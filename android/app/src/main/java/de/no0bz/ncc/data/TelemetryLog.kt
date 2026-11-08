package de.no0bz.ncc.data

import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.TelemetryPoint
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import java.io.RandomAccessFile
import java.time.LocalDate
import java.time.ZoneId

/**
 * Tages-Logdateien (`YYYY-MM-DD.jsonl`, eine Zeile pro Messpunkt) – gleichzeitig der Upload-Puffer.
 * Ein Cursor (Datei + Byte-Position) merkt sich, bis wohin der Server alles bestätigt hat.
 * Doppeltes Senden ist harmlos: Der Server erkennt Messpunkte an ihrer sample_id.
 */
class TelemetryLog(
    private val dir: File,
    private val zone: ZoneId = ZoneId.systemDefault(),
    private val retentionDays: Long = 30,
) {
    private val mutex = Mutex()
    private val cursorFile = File(dir, "upload.cursor")

    data class Cursor(val file: String, val offset: Long)

    data class Batch(val points: List<TelemetryPoint>, val next: Cursor)

    init {
        dir.mkdirs()
    }

    suspend fun append(point: TelemetryPoint, day: LocalDate = LocalDate.now(zone)) = mutex.withLock {
        File(dir, "$day.jsonl").appendText(NccApi.json.encodeToString(TelemetryPoint.serializer(), point) + "\n")
    }

    /** Liest bis zu [max] noch nicht bestätigte Messpunkte ab dem Cursor. */
    suspend fun nextBatch(max: Int = 100): Batch? = mutex.withLock { readBatch(max) }

    suspend fun commit(cursor: Cursor) = mutex.withLock {
        cursorFile.writeText("${cursor.file}\t${cursor.offset}")
        prune()
    }

    suspend fun pendingCount(): Int = mutex.withLock {
        val cursor = readCursor()
        logFiles().filter { it.name >= cursor.file }.sumOf { file ->
            val start = if (file.name == cursor.file) cursor.offset else 0L
            countLines(file, start)
        }
    }

    suspend fun totalBytes(): Long = mutex.withLock { logFiles().sumOf { it.length() } }

    suspend fun fileCount(): Int = mutex.withLock { logFiles().size }

    private fun readBatch(max: Int): Batch? {
        var cursor = readCursor()
        val points = mutableListOf<TelemetryPoint>()
        for (file in logFiles().filter { it.name >= cursor.file }) {
            var offset = if (file.name == cursor.file) cursor.offset else 0L
            RandomAccessFile(file, "r").use { raf ->
                if (offset > raf.length()) offset = raf.length()
                raf.seek(offset)
                while (points.size < max) {
                    val lineStart = raf.filePointer
                    val raw = raf.readLine() ?: break
                    // Unvollständige letzte Zeile (Schreibvorgang läuft gerade) später erneut lesen.
                    if (raf.filePointer == raf.length() && !endsWithNewline(raf)) {
                        raf.seek(lineStart)
                        break
                    }
                    // RandomAccessFile.readLine liest Latin-1; JSON-Zeilen sind UTF-8.
                    val line = String(raw.toByteArray(Charsets.ISO_8859_1), Charsets.UTF_8)
                    runCatching { NccApi.json.decodeFromString(TelemetryPoint.serializer(), line) }
                        .onSuccess { points += it }
                }
                cursor = Cursor(file.name, raf.filePointer)
            }
            if (points.size >= max) break
        }
        return if (points.isEmpty()) null else Batch(points, cursor)
    }

    private fun endsWithNewline(raf: RandomAccessFile): Boolean {
        if (raf.length() == 0L) return true
        val position = raf.filePointer
        raf.seek(raf.length() - 1)
        val last = raf.read()
        raf.seek(position)
        return last == '\n'.code
    }

    private fun readCursor(): Cursor {
        val parts = runCatching { cursorFile.readText().split('\t') }.getOrNull()
        val file = parts?.getOrNull(0)?.takeIf { it.endsWith(".jsonl") } ?: ""
        val offset = parts?.getOrNull(1)?.toLongOrNull() ?: 0L
        return Cursor(file, offset)
    }

    private fun logFiles(): List<File> =
        dir.listFiles { f -> f.isFile && f.name.matches(LOG_NAME) }?.sortedBy { it.name }.orEmpty()

    /** Entfernt bestätigte Logdateien, die älter als die Aufbewahrungsfrist sind. */
    private fun prune() {
        val cursor = readCursor()
        val oldest = LocalDate.now(zone).minusDays(retentionDays).toString()
        logFiles().filter { it.name < cursor.file && it.name.removeSuffix(".jsonl") < oldest }.forEach { it.delete() }
    }

    private fun countLines(file: File, from: Long): Int {
        var count = 0
        file.inputStream().use { input ->
            input.skip(from)
            val buffer = ByteArray(8192)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                for (i in 0 until read) if (buffer[i] == '\n'.code.toByte()) count++
            }
        }
        return count
    }

    companion object {
        private val LOG_NAME = Regex("\\d{4}-\\d{2}-\\d{2}\\.jsonl")
    }
}
