package de.no0bz.ncc.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Ein zum Senden vorbereiteter Anhang im App-Cache. */
data class PendingAttachment(val file: File, val name: String, val contentType: String) {
    val isImage: Boolean get() = contentType.startsWith("image/")
}

/** Dateien für Chat-Anhänge: Kamera-Ziel, Upload-Vorbereitung und heruntergeladene Anhänge (alles im Cache). */
class AttachmentFiles(context: Context) {
    private val app = context.applicationContext
    private val outgoing = File(app.cacheDir, "chat-out").apply { mkdirs() }
    private val incoming = File(app.cacheDir, "chat-in").apply { mkdirs() }

    fun uriFor(file: File): Uri = FileProvider.getUriForFile(app, "${app.packageName}.files", file)

    /** Leere Zieldatei für die Kamera-App. */
    fun newCameraFile(): File = File(outgoing, "NCC_${STAMP.format(LocalDateTime.now())}.jpg")

    /** Ein Kamerafoto verkleinern und richtig herum drehen. */
    fun fromCamera(file: File): PendingAttachment? {
        if (!file.exists() || file.length() == 0L) return null
        shrinkJpeg(file, file)
        return PendingAttachment(file, file.name, "image/jpeg")
    }

    /** Eine ausgewählte Datei (Galerie, Dateien-App) in den Cache kopieren; Fotos werden verkleinert. */
    fun fromUri(uri: Uri): PendingAttachment? {
        val resolver = app.contentResolver
        val type = resolver.getType(uri) ?: "application/octet-stream"
        var name = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        } ?: "Anhang"
        if (!name.contains('.')) MimeTypeMap.getSingleton().getExtensionFromMimeType(type)?.let { name += ".$it" }
        val target = File(outgoing, "${System.currentTimeMillis()}_${safe(name)}")
        resolver.openInputStream(uri)?.use { input -> target.outputStream().use { input.copyTo(it) } } ?: return null
        if (type == "image/jpeg" || type == "image/heic" || type == "image/heif") {
            val jpeg = File(outgoing, target.nameWithoutExtension + ".jpg")
            if (shrinkJpeg(target, jpeg)) {
                if (jpeg != target) target.delete()
                return PendingAttachment(jpeg, name.substringBeforeLast('.') + ".jpg", "image/jpeg")
            }
        }
        return PendingAttachment(target, name, type)
    }

    /** Ablageort eines heruntergeladenen Anhangs (existiert evtl. noch nicht). */
    fun downloaded(messageId: String, name: String): File = File(incoming, "${messageId}_${safe(name)}")

    fun discard(attachment: PendingAttachment) {
        attachment.file.delete()
    }

    /** Entfernt alte Cache-Dateien, damit der Chat-Cache nicht unbegrenzt wächst. */
    fun prune(maxAgeMillis: Long = 14L * 24 * 3600 * 1000) {
        val limit = System.currentTimeMillis() - maxAgeMillis
        for (dir in listOf(outgoing, incoming)) {
            dir.listFiles()?.forEach { file -> if (file.lastModified() < limit) file.delete() }
        }
    }

    /** Schreibt [source] als JPEG mit höchstens [MAX_EDGE] Kantenlänge nach [target]. */
    private fun shrinkJpeg(source: File, target: File): Boolean = runCatching {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(source.path, bounds)
        if (bounds.outWidth <= 0) return false
        var sample = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_EDGE) sample *= 2
        var bitmap = BitmapFactory.decodeFile(source.path, BitmapFactory.Options().apply { inSampleSize = sample }) ?: return false
        val longest = maxOf(bitmap.width, bitmap.height)
        val scale = if (longest > MAX_EDGE) MAX_EDGE.toFloat() / longest else 1f
        val rotation = when (ExifInterface(source.path).getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
        if (scale != 1f || rotation != 0f) {
            val matrix = Matrix().apply { postScale(scale, scale); postRotate(rotation) }
            bitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        }
        val temp = File(target.parentFile, target.name + ".tmp")
        temp.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 85, it) }
        bitmap.recycle()
        if (target.exists()) target.delete()
        temp.renameTo(target)
    }.getOrDefault(false)

    companion object {
        private const val MAX_EDGE = 2560
        private val STAMP = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")

        fun safe(name: String): String = name.replace(Regex("[^A-Za-z0-9._ -]+"), "_").takeLast(80).ifBlank { "Anhang" }
    }
}
