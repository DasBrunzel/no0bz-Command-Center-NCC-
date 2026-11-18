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
        // Mit aktivem VPN (Tailscale) steckt das echte Netz dahinter. Oft sind WLAN und Mobilfunk
        // gleichzeitig verbunden – Android leitet dann über das WLAN, also zählt das WLAN.
        val underlying = if (vpn) {
            pickUnderlying(
                connectivity.allNetworksCapabilities()
                    .filter { !it.hasTransport(NetworkCapabilities.TRANSPORT_VPN) && it.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) }
                    .map { it.toLink() },
            )
        } else {
            caps.toLink()
        }
        return NetworkState(type = underlying?.type ?: "unknown", vpn = vpn, unmetered = underlying?.unmetered == true)
    }

    private fun NetworkCapabilities.toLink() = Link(
        type = when {
            hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
            hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
            else -> "other"
        },
        unmetered = hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED),
        validated = hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED),
    )

    /** Ein Netz unter dem VPN, auf das Nötigste reduziert (testbar ohne Android). */
    data class Link(val type: String, val unmetered: Boolean, val validated: Boolean)

    companion object {
        private val PREFERENCE = listOf("ethernet", "wifi", "cellular", "other")

        /** Das Netz, über das Android den Verkehr tatsächlich leitet: geprüfte Netze zuerst, dann LAN vor WLAN vor Mobilfunk. */
        fun pickUnderlying(links: List<Link>): Link? =
            links.minWithOrNull(compareBy<Link>({ !it.validated }, { PREFERENCE.indexOf(it.type) }))
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
