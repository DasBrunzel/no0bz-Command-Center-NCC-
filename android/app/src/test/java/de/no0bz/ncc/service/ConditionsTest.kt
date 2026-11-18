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

class PoweredTest {
    private val discharging = android.os.BatteryManager.BATTERY_STATUS_DISCHARGING

    @Test
    fun pluggedIntoPcCountsEvenIfLevelDoesNotRise() {
        // Pixel am PC-USB: angesteckt, aber isCharging=false und Status „entlädt“.
        org.junit.Assert.assertTrue(Conditions.powered(plugged = android.os.BatteryManager.BATTERY_PLUGGED_USB, status = discharging, isCharging = false))
    }

    @Test
    fun adaptiveChargingPauseStillCounts() {
        org.junit.Assert.assertTrue(Conditions.powered(plugged = android.os.BatteryManager.BATTERY_PLUGGED_AC, status = android.os.BatteryManager.BATTERY_STATUS_NOT_CHARGING, isCharging = false))
    }

    @Test
    fun unpluggedDoesNotCount() {
        org.junit.Assert.assertFalse(Conditions.powered(plugged = 0, status = discharging, isCharging = false))
    }
}
