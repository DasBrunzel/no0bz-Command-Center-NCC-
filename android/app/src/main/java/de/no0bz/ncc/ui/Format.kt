package de.no0bz.ncc.ui

import java.util.Locale

/** Anzeigeformate im deutschen Stil (Komma als Dezimaltrenner). */
object Format {
    private val de: Locale = Locale.GERMANY

    /**
     * Bytes als GB/MB/KB. [binary] = true rechnet mit 1024 (RAM), false mit 1000 (Speicher,
     * so wie Hersteller „128 GB“ angeben).
     */
    fun bytes(bytes: Long, binary: Boolean): String {
        val unit = if (binary) 1024.0 else 1000.0
        val units = listOf("B", "KB", "MB", "GB", "TB")
        var value = bytes.toDouble().coerceAtLeast(0.0)
        var index = 0
        while (value >= unit && index < units.lastIndex) {
            value /= unit
            index++
        }
        val pattern = if (index == 0 || value >= 100) "%.0f" else "%.1f"
        return String.format(de, pattern, value) + " " + units[index]
    }

    /** Gerundeter Wert in ganzen GB, z. B. für beworbenen RAM („12 GB“). */
    fun wholeGigabytes(bytes: Long, binary: Boolean): String {
        val unit = if (binary) 1024.0 * 1024 * 1024 else 1e9
        return String.format(de, "%.0f GB", bytes / unit)
    }

    /** kHz-Wert aus sysfs als „2,85 GHz“ bzw. „850 MHz“. */
    fun frequency(khz: Long): String =
        if (khz >= 1_000_000) String.format(de, "%.2f GHz", khz / 1_000_000.0)
        else String.format(de, "%.0f MHz", khz / 1_000.0)

    fun percent(fraction: Float): String = String.format(de, "%.0f %%", fraction * 100)

    fun celsius(value: Float): String = String.format(de, "%.1f °C", value)

    fun volts(millivolts: Int): String = String.format(de, "%.2f V", millivolts / 1000.0)
}
