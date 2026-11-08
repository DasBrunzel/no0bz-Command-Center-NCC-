package de.no0bz.ncc.collect

import android.app.ActivityManager
import android.app.usage.StorageStatsManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.PowerManager
import android.os.StatFs
import android.os.storage.StorageManager
import android.provider.Settings

/** Liest alle lokal verfügbaren Gerätedaten. Ohne Berechtigungen nutzbar. */
class DeviceReader(
    context: Context,
    private val cpuReader: CpuReader = CpuReader(),
) {
    private val app = context.applicationContext
    private val activityManager = app.getSystemService(ActivityManager::class.java)
    private val storageStats = app.getSystemService(StorageStatsManager::class.java)
    private val powerManager = app.getSystemService(PowerManager::class.java)
    private val batteryManager = app.getSystemService(BatteryManager::class.java)

    private val staticDevice: DeviceInfo by lazy { readDeviceInfo() }
    private val staticSoc: SocInfo by lazy { readSoc() }

    fun read(): DeviceSnapshot = DeviceSnapshot(
        recordedAtMillis = System.currentTimeMillis(),
        device = staticDevice.copy(name = deviceName()),
        memory = readMemory(),
        storage = readStorage(),
        soc = staticSoc,
        cpu = cpuReader.read(),
        battery = readBattery(),
        thermal = readThermal(),
    )

    private fun deviceName(): String =
        Settings.Global.getString(app.contentResolver, Settings.Global.DEVICE_NAME)?.takeUnless { it.isBlank() }
            ?: Build.MODEL

    private fun readDeviceInfo() = DeviceInfo(
        name = deviceName(),
        manufacturer = Build.MANUFACTURER,
        model = Build.MODEL,
        androidRelease = Build.VERSION.RELEASE,
        sdkInt = Build.VERSION.SDK_INT,
        securityPatch = Build.VERSION.SECURITY_PATCH,
        isEmulator = Build.HARDWARE.lowercase() in SocNames.EMULATOR_HARDWARE || Build.FINGERPRINT.contains("generic"),
    )

    private fun readSoc() = SocInfo(
        manufacturer = Build.SOC_MANUFACTURER,
        model = Build.SOC_MODEL,
        displayName = SocNames.displayName(Build.SOC_MANUFACTURER, Build.SOC_MODEL, Build.HARDWARE),
        abis = Build.SUPPORTED_ABIS.toList(),
    )

    private fun readMemory(): MemoryInfo {
        val info = ActivityManager.MemoryInfo()
        activityManager.getMemoryInfo(info)
        return MemoryInfo(
            totalBytes = info.totalMem,
            availableBytes = info.availMem,
            advertisedBytes = info.advertisedMem.takeIf { it > 0 },
            lowMemory = info.lowMemory,
        )
    }

    private fun readStorage(): StorageInfo = runCatching {
        StorageInfo(
            totalBytes = storageStats.getTotalBytes(StorageManager.UUID_DEFAULT),
            freeBytes = storageStats.getFreeBytes(StorageManager.UUID_DEFAULT),
        )
    }.getOrElse {
        val fs = StatFs(Environment.getDataDirectory().path)
        StorageInfo(totalBytes = fs.totalBytes, freeBytes = fs.availableBytes)
    }

    private fun readBattery(): BatteryInfo {
        val intent: Intent? = app.registerReceiver(
            null,
            IntentFilter(Intent.ACTION_BATTERY_CHANGED),
            Context.RECEIVER_NOT_EXPORTED,
        )
        if (intent == null) {
            return BatteryInfo(null, false, false, PowerSource.NONE, null, null, BatteryHealth.UNKNOWN, null)
        }
        val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, BatteryManager.BATTERY_STATUS_UNKNOWN)
        val temp = intent.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
        val voltage = intent.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1)
        val cycles = intent.getIntExtra(BatteryManager.EXTRA_CYCLE_COUNT, -1)
        return BatteryInfo(
            levelPercent = if (level >= 0 && scale > 0) level * 100 / scale else null,
            // EXTRA_STATUS meldet am PC-USB oft „lädt nicht“, obwohl Strom fließt – isCharging ist genauer.
            charging = status == BatteryManager.BATTERY_STATUS_CHARGING || batteryManager.isCharging,
            full = status == BatteryManager.BATTERY_STATUS_FULL,
            source = when (intent.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0)) {
                BatteryManager.BATTERY_PLUGGED_AC -> PowerSource.AC
                BatteryManager.BATTERY_PLUGGED_USB -> PowerSource.USB
                BatteryManager.BATTERY_PLUGGED_WIRELESS -> PowerSource.WIRELESS
                BatteryManager.BATTERY_PLUGGED_DOCK -> PowerSource.DOCK
                else -> PowerSource.NONE
            },
            temperatureCelsius = if (temp != Int.MIN_VALUE) temp / 10f else null,
            voltageMillivolts = voltage.takeIf { it > 0 },
            health = when (intent.getIntExtra(BatteryManager.EXTRA_HEALTH, BatteryManager.BATTERY_HEALTH_UNKNOWN)) {
                BatteryManager.BATTERY_HEALTH_GOOD -> BatteryHealth.GOOD
                BatteryManager.BATTERY_HEALTH_OVERHEAT -> BatteryHealth.OVERHEAT
                BatteryManager.BATTERY_HEALTH_DEAD -> BatteryHealth.DEAD
                BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> BatteryHealth.OVER_VOLTAGE
                BatteryManager.BATTERY_HEALTH_COLD -> BatteryHealth.COLD
                BatteryManager.BATTERY_HEALTH_UNSPECIFIED_FAILURE -> BatteryHealth.FAILURE
                else -> BatteryHealth.UNKNOWN
            },
            cycleCount = cycles.takeIf { it >= 0 },
        )
    }

    private fun readThermal(): ThermalStatus = when (powerManager.currentThermalStatus) {
        PowerManager.THERMAL_STATUS_LIGHT -> ThermalStatus.LIGHT
        PowerManager.THERMAL_STATUS_MODERATE -> ThermalStatus.MODERATE
        PowerManager.THERMAL_STATUS_SEVERE -> ThermalStatus.SEVERE
        PowerManager.THERMAL_STATUS_CRITICAL -> ThermalStatus.CRITICAL
        PowerManager.THERMAL_STATUS_EMERGENCY -> ThermalStatus.EMERGENCY
        PowerManager.THERMAL_STATUS_SHUTDOWN -> ThermalStatus.SHUTDOWN
        else -> ThermalStatus.NONE
    }
}
