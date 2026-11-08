package de.no0bz.ncc.collect

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class CpuReaderTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun parsesCpuLists() {
        assertEquals(listOf(0, 1, 2, 3, 4, 5, 6, 7), CpuReader.parseCpuList("0-7\n"))
        assertEquals(listOf(0, 1, 2, 3, 6), CpuReader.parseCpuList("0-3,6"))
        assertEquals(listOf(4, 5), CpuReader.parseCpuList("4 5"))
        assertEquals(emptyList<Int>(), CpuReader.parseCpuList(""))
    }

    @Test
    fun parsesCoreTypesFromCpuinfo() {
        val types = CpuReader.parseCoreTypes(tensorG2CpuInfo())
        assertEquals("Cortex-A55", types[0])
        assertEquals("Cortex-A78", types[4])
        assertEquals("Cortex-X1", types[7])
    }

    @Test
    fun buildsTensorG2Topology() {
        val root = tensorG2Sysfs()
        val cpuinfo = tmp.newFile("cpuinfo").apply { writeText(tensorG2CpuInfo()) }

        val state = CpuReader(root, cpuinfo).read()

        assertEquals(8, state.coreCount)
        assertEquals(3, state.clusters.size)
        assertEquals("2× Cortex-X1 · 2× Cortex-A78 · 4× Cortex-A55", state.architectureSummary)
        assertEquals(2_850_000L, state.clusters.last().maxKhz)
        assertTrue(state.hasClockData)
        assertEquals(0.5f, state.cores[7].clockLoad!!, 0.001f)
    }

    @Test
    fun offlineCoreHasNoClock() {
        val root = tensorG2Sysfs()
        File(root, "cpu5/online").writeText("0\n")

        val core = CpuReader(root, File(root, "missing")).read().cores[5]

        assertFalse(core.online)
        assertNull(core.curKhz)
        assertNull(core.clockLoad)
    }

    @Test
    fun mergesIdenticalSingleCorePolicies() {
        // Emulator: jeder Kern hat eine eigene Policy, aber gleiche Werte.
        val root = tmp.newFolder("emu")
        File(root, "possible").writeText("0-5\n")
        for (id in 0..5) {
            val freq = File(root, "cpu$id/cpufreq").apply { mkdirs() }
            File(freq, "cpuinfo_max_freq").writeText("0\n")
            File(freq, "scaling_cur_freq").writeText("4650000\n")
            File(root, "cpufreq/policy$id").apply { mkdirs() }.resolve("related_cpus").writeText("$id\n")
        }
        val state = CpuReader(root, File(root, "missing")).read()
        assertEquals(1, state.clusters.size)
        assertEquals("6× Cluster 1", state.architectureSummary)
        // Unplausibler Maximaltakt → keine Taktlast statt falscher 100 %.
        assertNull(state.clusters.single().maxKhz)
        assertNull(state.averageClockLoad)
        assertTrue(state.hasClockData)
    }

    @Test
    fun withoutSysfsFallsBackGracefully() {
        val empty = tmp.newFolder("empty")
        val state = CpuReader(empty, File(empty, "missing")).read()
        assertEquals(0, state.coreCount)
        assertFalse(state.hasClockData)
        assertNull(state.averageClockLoad)
    }

    @Test
    fun clustersByMaxFrequencyWhenPoliciesMissing() {
        val root = tensorG2Sysfs()
        File(root, "cpufreq").deleteRecursively()
        val state = CpuReader(root, File(root, "missing")).read()
        assertEquals(3, state.clusters.size)
        assertEquals("2× Cluster 3 · 2× Cluster 2 · 4× Cluster 1", state.architectureSummary)
    }

    /** Nachbau von /sys/devices/system/cpu eines Pixel 7 Pro. */
    private fun tensorG2Sysfs(): File {
        val root = tmp.newFolder("cpu")
        File(root, "possible").writeText("0-7\n")
        val max = mapOf(0..3 to 1_803_000L, 4..5 to 2_348_000L, 6..7 to 2_850_000L)
        for ((range, maxKhz) in max) for (id in range) {
            val freq = File(root, "cpu$id/cpufreq").apply { mkdirs() }
            File(freq, "cpuinfo_max_freq").writeText("$maxKhz\n")
            File(freq, "cpuinfo_min_freq").writeText("300000\n")
            File(freq, "scaling_cur_freq").writeText("${maxKhz / 2}\n")
            if (id != 0) File(root, "cpu$id/online").writeText("1\n")
        }
        // Tensor G2: 4× A55 (cpu0–3), 2× A78 (cpu4–5), 2× X1 (cpu6–7), je Cluster eine Policy.
        listOf("policy0" to "0 1 2 3", "policy4" to "4 5", "policy6" to "6 7")
            .forEach { (name, cpus) -> File(root, "cpufreq/$name").apply { mkdirs() }.resolve("related_cpus").writeText("$cpus\n") }
        return root
    }

    private fun tensorG2CpuInfo(): String = buildString {
        for (id in 0..7) {
            val part = when (id) { in 0..3 -> "0xd05"; in 4..5 -> "0xd41"; else -> "0xd44" }
            appendLine("processor\t: $id")
            appendLine("CPU implementer\t: 0x41")
            appendLine("CPU part\t: $part")
            appendLine()
        }
    }
}
