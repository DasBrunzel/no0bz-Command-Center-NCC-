package de.no0bz.ncc.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class FormatTest {
    @Test
    fun formatsStorageDecimal() {
        assertEquals("128 GB", Format.bytes(128_000_000_000, binary = false))
        assertEquals("42,5 GB", Format.bytes(42_500_000_000, binary = false))
    }

    @Test
    fun formatsRamBinary() {
        assertEquals("5,0 GB", Format.bytes(5L * 1024 * 1024 * 1024, binary = true))
        assertEquals("12 GB", Format.wholeGigabytes(12L * 1024 * 1024 * 1024, binary = true))
        assertEquals("512 B", Format.bytes(512, binary = true))
    }

    @Test
    fun formatsFrequencies() {
        assertEquals("2,85 GHz", Format.frequency(2_850_000))
        assertEquals("850 MHz", Format.frequency(850_000))
    }

    @Test
    fun formatsSmallUnits() {
        assertEquals("37 %", Format.percent(0.37f))
        assertEquals("31,4 °C", Format.celsius(31.4f))
        assertEquals("4,12 V", Format.volts(4120))
    }
}
