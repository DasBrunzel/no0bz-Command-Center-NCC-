package de.no0bz.ncc.collect

/** Ein vollständiger Messpunkt aller lokal gelesenen Gerätedaten. */
data class DeviceSnapshot(
    val recordedAtMillis: Long,
    val device: DeviceInfo,
    val memory: MemoryInfo,
    val storage: StorageInfo,
    val soc: SocInfo,
    val cpu: CpuState,
    val battery: BatteryInfo,
    val thermal: ThermalStatus,
)

data class DeviceInfo(
    val name: String,
    val manufacturer: String,
    val model: String,
    val androidRelease: String,
    val sdkInt: Int,
    val securityPatch: String,
    val isEmulator: Boolean,
)

data class MemoryInfo(
    /** Für das System nutzbarer RAM (Byte). */
    val totalBytes: Long,
    val availableBytes: Long,
    /** Vom Hersteller beworbener RAM (z. B. 12 GB), falls bekannt. */
    val advertisedBytes: Long?,
    val lowMemory: Boolean,
) {
    val usedBytes: Long get() = (totalBytes - availableBytes).coerceAtLeast(0)
    val usedFraction: Float get() = if (totalBytes > 0) usedBytes.toFloat() / totalBytes else 0f
}

data class StorageInfo(
    val totalBytes: Long,
    val freeBytes: Long,
) {
    val usedBytes: Long get() = (totalBytes - freeBytes).coerceAtLeast(0)
    val usedFraction: Float get() = if (totalBytes > 0) usedBytes.toFloat() / totalBytes else 0f
}

data class SocInfo(
    val manufacturer: String?,
    val model: String?,
    /** Lesbarer Name, z. B. „Google Tensor G2“. */
    val displayName: String,
    val abis: List<String>,
)

data class BatteryInfo(
    val levelPercent: Int?,
    val charging: Boolean,
    val full: Boolean,
    val source: PowerSource,
    val temperatureCelsius: Float?,
    val voltageMillivolts: Int?,
    val health: BatteryHealth,
    val cycleCount: Int?,
)

enum class PowerSource { NONE, AC, USB, WIRELESS, DOCK }

enum class BatteryHealth { UNKNOWN, GOOD, OVERHEAT, DEAD, OVER_VOLTAGE, COLD, FAILURE }

enum class ThermalStatus { NONE, LIGHT, MODERATE, SEVERE, CRITICAL, EMERGENCY, SHUTDOWN }
