package de.no0bz.ncc.collect

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MetricsMapperTest {
    private val gib = 1024L * 1024 * 1024

    private fun snapshot() = DeviceSnapshot(
        recordedAtMillis = 0,
        device = DeviceInfo("Pixel 7 Pro", "Google", "Pixel 7 Pro", "17", 37, "2026-09-05", false),
        memory = MemoryInfo(totalBytes = 11 * gib, availableBytes = 4 * gib, advertisedBytes = 12 * gib, lowMemory = false),
        storage = StorageInfo(totalBytes = 128_000_000_000, freeBytes = 36_000_000_000),
        soc = SocInfo("Google", "GS201", "Google Tensor G2", listOf("arm64-v8a")),
        cpu = CpuState(
            cores = listOf(
                CpuCore(0, true, 900_000, 300_000, 1_800_000, "Cortex-A55"),
                CpuCore(6, true, 2_850_000, 500_000, 2_850_000, "Cortex-X1"),
                CpuCore(7, false, null, 500_000, 2_850_000, "Cortex-X1"),
            ),
            clusters = listOf(
                CpuCluster(0, listOf(0), "Cortex-A55", 1_800_000),
                CpuCluster(1, listOf(6, 7), "Cortex-X1", 2_850_000),
            ),
        ),
        battery = BatteryInfo(21, true, false, PowerSource.USB, 29.4f, 3790, BatteryHealth.GOOD, 807),
        thermal = ThermalStatus.NONE,
    )

    @Test
    fun usesDashboardCompatibleFields() {
        val m = MetricsMapper.map(snapshot(), NetworkState("wifi", vpn = true, unmetered = true))

        val memory = m["memory"]!!.jsonObject
        assertEquals(63.6, memory["percent"]!!.jsonPrimitive.double, 0.05)
        assertEquals(11.0, memory["total_gb"]!!.jsonPrimitive.double, 0.01)

        val disk = (m["disks"] as JsonArray)[0].jsonObject
        assertEquals(71.9, disk["percent"]!!.jsonPrimitive.double, 0.05)

        assertEquals(21, m["battery"]!!.jsonObject["percent"]!!.jsonPrimitive.int)
        assertTrue(m["battery"]!!.jsonObject["plugged"]!!.jsonPrimitive.boolean)
        assertEquals("Android 17", m["system"]!!.jsonObject["platform"]!!.jsonPrimitive.content)
    }

    @Test
    fun clockLoadIsNotReportedAsCpuPercent() {
        val cpu = MetricsMapper.map(snapshot(), null)["cpu"]!!.jsonObject
        assertFalse("cpu.percent würde CPU-Warnungen auslösen", cpu.containsKey("percent"))
        assertEquals("Google Tensor G2", cpu["model"]!!.jsonPrimitive.content)
        assertEquals(1875, cpu["frequency_mhz"]!!.jsonPrimitive.int)
    }

    @Test
    fun androidSectionCarriesDetails() {
        val android = MetricsMapper.map(snapshot(), NetworkState("wifi", true, true))["android"] as JsonObject
        assertEquals("GS201", android["soc_code"]!!.jsonPrimitive.content)
        assertEquals("2× Cortex-X1 · 1× Cortex-A55", android["architecture"]!!.jsonPrimitive.content)
        assertEquals(12, android["ram_advertised_gb"]!!.jsonPrimitive.int)
        val cores = android["cores"]!!.jsonArray
        assertEquals(3, cores.size)
        assertFalse(cores[2].jsonObject.containsKey("mhz"))
        val battery = android["battery"]!!.jsonObject
        assertEquals(29.4, battery["temperature_c"]!!.jsonPrimitive.double, 0.001)
        assertEquals(807, battery["cycles"]!!.jsonPrimitive.int)
        assertEquals("usb", battery["source"]!!.jsonPrimitive.content)
        assertTrue(android["network"]!!.jsonObject["vpn"]!!.jsonPrimitive.boolean)
    }

    @Test
    fun metadataAnnouncesHeartbeatInterval() {
        val meta = MetricsMapper.metadata(snapshot(), 120, "0.2.0")
        assertEquals(120, meta["heartbeat_interval_seconds"]!!.int)
        assertEquals("Google Tensor G2", meta["soc"]!!.content)
    }
}
