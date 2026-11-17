package de.no0bz.ncc.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StreamProtocolM6Test {
    @Test
    fun parsesConfigUpdateWithOnlyTheChangedFields() {
        assertEquals(
            StreamEvent.ConfigUpdate(intervalSeconds = 120, uploadRule = "immediate"),
            StreamProtocol.parse("""{"type":"config.update","interval_seconds":120,"upload_rule":"immediate"}"""),
        )
        assertEquals(
            StreamEvent.ConfigUpdate(locationTracking = true),
            StreamProtocol.parse("""{"type":"config.update","location_tracking":true}"""),
        )
    }

    @Test
    fun parsesAppUpdate() {
        val event = StreamProtocol.parse(
            """{"type":"app.update","release":{"version_code":7,"version_name":"0.7.0","size":1234,"sha256":"ab","notes":"Neu","uploaded_at":"2026-11-17T00:00:00+00:00"}}""",
        )
        assertEquals(StreamEvent.AppUpdate(AppRelease(7, "0.7.0", 1234, "ab", "Neu", "2026-11-17T00:00:00+00:00")), event)
    }

    @Test
    fun brokenAppUpdateIsIgnored() {
        assertNull(StreamProtocol.parse("""{"type":"app.update"}"""))
        assertNull(StreamProtocol.parse("""{"type":"app.update","release":{"version_code":"x"}}"""))
    }
}
