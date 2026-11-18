package de.no0bz.ncc.service

import de.no0bz.ncc.service.Conditions.Link
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ConditionsTest {
    private val lte = Link("cellular", unmetered = false, validated = true)
    private val wifi = Link("wifi", unmetered = true, validated = true)

    @Test
    fun wifiWinsOverMobileDataBehindVpn() {
        // So meldet es das Pixel: Mobilfunk steht in der Liste vor dem WLAN.
        assertEquals(wifi, Conditions.pickUnderlying(listOf(lte, wifi)))
        assertEquals(wifi, Conditions.pickUnderlying(listOf(wifi, lte)))
    }

    @Test
    fun unvalidatedWifiDoesNotCount() {
        // WLAN ohne Internet (z. B. Captive Portal): Android leitet über Mobilfunk.
        val portal = Link("wifi", unmetered = true, validated = false)
        assertEquals(lte, Conditions.pickUnderlying(listOf(portal, lte)))
    }

    @Test
    fun onlyMobileOrNothing() {
        assertEquals(lte, Conditions.pickUnderlying(listOf(lte)))
        assertNull(Conditions.pickUnderlying(emptyList()))
    }
}
