package de.no0bz.ncc.update

import de.no0bz.ncc.data.UploadRule
import de.no0bz.ncc.widget.WidgetData
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class AppUpdaterTest {
    @Test
    fun onlyHigherVersionCodesAreNewer() {
        assertTrue(AppUpdater.isNewer(7, installed = 6))
        assertFalse(AppUpdater.isNewer(6, installed = 6))
        assertFalse(AppUpdater.isNewer(5, installed = 6))
    }

    @Test
    fun sha256MatchesKnownDigest() = runBlocking {
        val file = File.createTempFile("ncc", ".apk").apply { writeText("abc"); deleteOnExit() }
        assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", AppUpdater.sha256(file))
    }

    @Test
    fun uploadRuleFromWire() {
        assertEquals(UploadRule.IMMEDIATE, UploadRule.fromWire("immediate"))
        assertEquals(UploadRule.WIFI_CHARGING, UploadRule.fromWire("wifi_charging"))
        assertNull(UploadRule.fromWire("sometimes"))
        assertNull(UploadRule.fromWire(null))
    }

    @Test
    fun widgetTexts() {
        val data = WidgetData(3, 4, 0, 80, false, true, true, null)
        assertEquals("3/4", data.fleetText())
        assertEquals("keine Warnungen", data.alertText())
        assertEquals("1 Warnung", data.copy(alerts = 1).alertText())
        assertEquals("2 Warnungen", data.copy(alerts = 2).alertText())
        assertEquals("–", data.copy(fleetTotal = null).fleetText())
    }
}
