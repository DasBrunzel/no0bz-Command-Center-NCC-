package de.no0bz.ncc.collect

import org.junit.Assert.assertEquals
import org.junit.Test

class SocNamesTest {
    @Test
    fun mapsPixel7ProSoc() {
        assertEquals("Google Tensor G2", SocNames.displayName("Google", "GS201", "gs201"))
    }

    @Test
    fun unknownCodeKeepsManufacturerAndCode() {
        assertEquals("Mediatek MT6989", SocNames.displayName("Mediatek", "MT6989", "mt6989"))
    }

    @Test
    fun emulatorIsNamed() {
        assertEquals("Emulator (ranchu)", SocNames.displayName("unknown", "unknown", "ranchu"))
        assertEquals("Emulator (ranchu)", SocNames.displayName("AOSP", "ranchu", "ranchu"))
    }

    @Test
    fun nothingKnownFallsBack() {
        assertEquals("Unbekannt", SocNames.displayName(null, null, null))
    }
}
