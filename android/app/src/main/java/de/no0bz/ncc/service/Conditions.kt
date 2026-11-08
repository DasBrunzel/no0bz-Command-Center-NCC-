package de.no0bz.ncc.service

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import de.no0bz.ncc.collect.NetworkState
import de.no0bz.ncc.data.UploadRule

/** Liest Netz- und Ladezustand für die Upload-Regel und die Tailscale-Prüfung. */
class Conditions(context: Context) {
    private val connectivity = context.applicationContext.getSystemService(ConnectivityManager::class.java)
    private val battery = context.applicationContext.getSystemService(BatteryManager::class.java)

    fun network(): NetworkState? {
        val caps = connectivity.getNetworkCapabilities(connectivity.activeNetwork) ?: return null
        val vpn = caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
        // Mit aktivem VPN steckt das echte Netz dahinter; der Typ kommt dann aus allen Netzen.
        val underlying = if (vpn) {
            connectivity.allNetworksCapabilities().firstOrNull { !it.hasTransport(NetworkCapabilities.TRANSPORT_VPN) && it.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) }
        } else {
            caps
        }
        val type = when {
            underlying == null -> "unknown"
            underlying.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            underlying.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            underlying.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            else -> "other"
        }
        val unmetered = underlying?.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED) == true
        return NetworkState(type = type, vpn = vpn, unmetered = unmetered)
    }

    fun vpnActive(): Boolean = network()?.vpn == true

    fun charging(): Boolean = battery.isCharging

    fun uploadAllowed(rule: UploadRule): Boolean = when (rule) {
        UploadRule.IMMEDIATE -> network() != null
        UploadRule.WIFI_CHARGING -> network()?.let { it.unmetered && (it.type == "wifi" || it.type == "ethernet") } == true && charging()
    }

    @Suppress("DEPRECATION")
    private fun ConnectivityManager.allNetworksCapabilities(): List<NetworkCapabilities> =
        allNetworks.mapNotNull { getNetworkCapabilities(it) }
}
