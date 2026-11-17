package de.no0bz.ncc.collect

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.CancellationSignal
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.Executors
import kotlin.coroutines.resume

/** Ein Standort zum Zeitpunkt einer Messung. */
data class LocationFix(val latitude: Double, val longitude: Double, val accuracyMeters: Float?, val timeMillis: Long)

/** Status der Standort-Berechtigungen. */
data class LocationAccess(val precise: Boolean, val approximate: Boolean, val background: Boolean) {
    val any: Boolean get() = precise || approximate
}

/**
 * Holt einen aktuellen Standort über den LocationManager des Systems (ohne Google-Play-Bibliothek).
 * Nimmt einen frischen letzten Standort, wenn einer da ist, sonst wird kurz neu geortet.
 */
class LocationReader(context: Context) {
    private val app = context.applicationContext
    private val manager = app.getSystemService(LocationManager::class.java)
    private val executor = Executors.newSingleThreadExecutor()

    fun access(): LocationAccess = LocationAccess(
        precise = granted(Manifest.permission.ACCESS_FINE_LOCATION),
        approximate = granted(Manifest.permission.ACCESS_COARSE_LOCATION),
        background = granted(Manifest.permission.ACCESS_BACKGROUND_LOCATION),
    )

    fun enabled(): Boolean = manager.isLocationEnabled

    /** Aktueller Standort oder null (keine Berechtigung, Standort aus, kein Fix innerhalb von [timeoutMs]). */
    /** [maxAgeMs] klein halten: unterwegs wäre ein älterer Standort schon woanders. */
    suspend fun current(timeoutMs: Long = 10_000, maxAgeMs: Long = 15_000): LocationFix? {
        if (!access().any || !manager.isLocationEnabled) return null
        val providers = providers()
        val now = System.currentTimeMillis()
        try {
            // Ein frischer letzter Standort spart Akku.
            providers.mapNotNull { manager.getLastKnownLocation(it) }
                .filter { now - it.time <= maxAgeMs }
                .minByOrNull { if (it.hasAccuracy()) it.accuracy else Float.MAX_VALUE }
                ?.let { return it.toFix() }
            // Sonst der Reihe nach orten: fused (Play-Dienste) liefert nicht überall, GPS braucht freien Himmel.
            for (provider in providers) {
                val fix = withTimeoutOrNull(timeoutMs) {
                    suspendCancellableCoroutine { continuation ->
                        val cancel = CancellationSignal()
                        continuation.invokeOnCancellation { cancel.cancel() }
                        manager.getCurrentLocation(provider, cancel, executor) { location ->
                            if (continuation.isActive) continuation.resume(location?.toFix())
                        }
                    }
                }
                if (fix != null) return fix
            }
            return null
        } catch (_: SecurityException) {
            return null
        }
    }

    private fun providers(): List<String> {
        val available = manager.getProviders(true)
        return listOf(LocationManager.FUSED_PROVIDER, LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .filter { it in available }
    }

    private fun granted(permission: String): Boolean =
        app.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED

    private fun Location.toFix() = LocationFix(latitude, longitude, if (hasAccuracy()) accuracy else null, time)
}
