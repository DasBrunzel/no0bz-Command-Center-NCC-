package de.no0bz.ncc.collect

import java.io.File

data class CpuCore(
    val id: Int,
    val online: Boolean,
    val curKhz: Long?,
    val minKhz: Long?,
    val maxKhz: Long?,
    /** Kerntyp aus /proc/cpuinfo, z. B. „Cortex-A55“. */
    val coreType: String?,
) {
    /**
     * Taktlast: aktueller Takt im Verhältnis zum Maximaltakt (0..1).
     * Android erlaubt Apps seit Version 8 keine echte Kernauslastung mehr (/proc/stat ist gesperrt).
     */
    val clockLoad: Float?
        get() = if (curKhz != null && maxKhz != null && maxKhz > 0) {
            (curKhz.toFloat() / maxKhz).coerceIn(0f, 1f)
        } else {
            null
        }
}

data class CpuCluster(
    val index: Int,
    val coreIds: List<Int>,
    val name: String,
    val maxKhz: Long?,
)

data class CpuState(
    val cores: List<CpuCore>,
    val clusters: List<CpuCluster>,
) {
    val coreCount: Int get() = cores.size
    val hasClockData: Boolean get() = cores.any { it.curKhz != null }

    /** Zum Beispiel „1× Cortex-X1 · 2× Cortex-A78 · 4× Cortex-A55“. */
    val architectureSummary: String
        get() = clusters
            .sortedByDescending { it.maxKhz ?: 0 }
            .joinToString(" · ") { "${it.coreIds.size}× ${it.name}" }

    /** Durchschnittliche Taktlast aller Kerne mit Taktdaten. */
    val averageClockLoad: Float?
        get() = cores.mapNotNull { it.clockLoad }.takeIf { it.isNotEmpty() }?.average()?.toFloat()
}

/**
 * Liest CPU-Topologie und Takt aus sysfs. Pfade sind austauschbar, damit sich der Leser
 * mit nachgebauten Verzeichnissen testen lässt.
 */
class CpuReader(
    private val cpuRoot: File = File("/sys/devices/system/cpu"),
    private val cpuInfo: File = File("/proc/cpuinfo"),
) {
    private val coreTypes: Map<Int, String> by lazy { parseCoreTypes(readText(cpuInfo).orEmpty()) }

    fun read(): CpuState {
        val ids = coreIds()
        val cores = ids.map { id -> readCore(id) }
        return CpuState(cores = cores, clusters = clusters(cores))
    }

    private fun coreIds(): List<Int> {
        readText(File(cpuRoot, "possible"))?.let { parseCpuList(it) }?.takeIf { it.isNotEmpty() }?.let { return it }
        return cpuRoot.listFiles()
            ?.mapNotNull { CORE_DIR.matchEntire(it.name)?.groupValues?.get(1)?.toIntOrNull() }
            ?.sorted()
            .orEmpty()
    }

    private fun readCore(id: Int): CpuCore {
        val dir = File(cpuRoot, "cpu$id")
        val freq = File(dir, "cpufreq")
        // cpu0 hat meist keine "online"-Datei und ist immer aktiv.
        val online = readText(File(dir, "online"))?.trim()?.let { it == "1" } ?: true
        return CpuCore(
            id = id,
            online = online,
            curKhz = if (online) readLong(File(freq, "scaling_cur_freq")) else null,
            minKhz = readLong(File(freq, "cpuinfo_min_freq")),
            // Werte unter 100 MHz sind unplausibel (Emulator meldet z. B. 0 oder 1).
            maxKhz = readLong(File(freq, "cpuinfo_max_freq"))?.takeIf { it >= MIN_PLAUSIBLE_KHZ },
            coreType = coreTypes[id],
        )
    }

    private fun clusters(cores: List<CpuCore>): List<CpuCluster> {
        val byId = cores.associateBy { it.id }
        val groups: List<List<Int>> = policyGroups(byId.keys)
            ?: cores.groupBy { it.maxKhz }.values.map { group -> group.map { it.id } }
        // Gleichartige Gruppen (gleicher Kerntyp und Maximaltakt) zusammenlegen – z. B. im Emulator,
        // wo jeder Kern eine eigene Policy hat.
        val merged = groups
            .map { it.sorted() }
            .groupBy { ids -> ids.firstNotNullOfOrNull { byId[it]?.coreType } to ids.firstNotNullOfOrNull { byId[it]?.maxKhz } }
            .values
            .map { same -> same.flatten().sorted() }
        return merged
            .sortedBy { it.first() }
            .mapIndexed { index, ids ->
                val members = ids.mapNotNull { byId[it] }
                CpuCluster(
                    index = index,
                    coreIds = ids,
                    name = members.firstNotNullOfOrNull { it.coreType } ?: "Cluster ${index + 1}",
                    maxKhz = members.mapNotNull { it.maxKhz }.maxOrNull(),
                )
            }
    }

    /** Gruppen aus cpufreq/policyN/related_cpus, sofern vorhanden. */
    private fun policyGroups(known: Set<Int>): List<List<Int>>? {
        val policies = File(cpuRoot, "cpufreq").listFiles { f -> f.name.startsWith("policy") } ?: return null
        val groups = policies.mapNotNull { policy ->
            readText(File(policy, "related_cpus"))?.let { parseCpuList(it) }?.filter { it in known }?.takeIf { it.isNotEmpty() }
        }
        val covered = groups.flatten().toSet()
        return groups.takeIf { it.isNotEmpty() && covered == known }
    }

    companion object {
        private val CORE_DIR = Regex("cpu(\\d+)")
        private const val MIN_PLAUSIBLE_KHZ = 100_000L

        /** Wandelt „0-3,6“ bzw. „0 1 2 3“ in eine Liste von Kern-IDs. */
        fun parseCpuList(text: String): List<Int> =
            text.trim().split(',', ' ', '\n').filter { it.isNotBlank() }.flatMap { part ->
                val range = part.split('-')
                if (range.size == 2) {
                    val start = range[0].trim().toIntOrNull()
                    val end = range[1].trim().toIntOrNull()
                    if (start != null && end != null && end >= start) (start..end).toList() else emptyList()
                } else {
                    listOfNotNull(part.trim().toIntOrNull())
                }
            }.distinct().sorted()

        /** Liest „processor“ + „CPU part“ aus /proc/cpuinfo und übersetzt den Teilecode in einen Kernnamen. */
        fun parseCoreTypes(cpuinfo: String): Map<Int, String> {
            val result = mutableMapOf<Int, String>()
            var processor: Int? = null
            var implementer: String? = null
            for (line in cpuinfo.lineSequence()) {
                val key = line.substringBefore(':').trim().lowercase()
                val value = line.substringAfter(':', "").trim()
                when (key) {
                    "processor" -> { processor = value.toIntOrNull(); implementer = null }
                    "cpu implementer" -> implementer = value.lowercase()
                    "cpu part" -> {
                        val id = processor ?: continue
                        coreName(implementer, value.lowercase())?.let { result[id] = it }
                    }
                }
            }
            return result
        }

        private fun coreName(implementer: String?, part: String): String? {
            if (implementer != null && implementer != "0x41") return null // nur ARM-Kerne bekannt
            return ARM_PARTS[part]
        }

        private val ARM_PARTS = mapOf(
            "0xd03" to "Cortex-A53", "0xd04" to "Cortex-A35", "0xd05" to "Cortex-A55",
            "0xd07" to "Cortex-A57", "0xd08" to "Cortex-A72", "0xd09" to "Cortex-A73",
            "0xd0a" to "Cortex-A75", "0xd0b" to "Cortex-A76", "0xd0d" to "Cortex-A77",
            "0xd41" to "Cortex-A78", "0xd44" to "Cortex-X1", "0xd46" to "Cortex-A510",
            "0xd47" to "Cortex-A710", "0xd48" to "Cortex-X2", "0xd4d" to "Cortex-A715",
            "0xd4e" to "Cortex-X3", "0xd80" to "Cortex-A520", "0xd81" to "Cortex-A720",
            "0xd82" to "Cortex-X4", "0xd85" to "Cortex-X925", "0xd87" to "Cortex-A725",
        )

        private fun readText(file: File): String? = runCatching { file.readText() }.getOrNull()

        private fun readLong(file: File): Long? = readText(file)?.trim()?.toLongOrNull()
    }
}
