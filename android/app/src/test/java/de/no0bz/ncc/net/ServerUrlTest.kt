package de.no0bz.ncc.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerUrlTest {
    private fun valid(input: String) = (ServerUrl.validate(input) as? ServerUrl.Result.Valid)?.baseUrl

    @Test
    fun acceptsTailscaleHttpAndHttps() {
        assertEquals("http://100.101.102.103:8350", valid("  http://100.101.102.103:8350/ "))
        assertEquals("http://ncc-server.tail0000.ts.net:8350", valid("http://ncc-server.tail0000.ts.net:8350"))
        assertEquals("https://ncc.example.net", valid("https://ncc.example.net"))
        assertEquals("http://10.0.2.2:8350", valid("http://10.0.2.2:8350"))
    }

    @Test
    fun rejectsPlainHttpOutsideTailscale() {
        assertTrue(ServerUrl.validate("http://ncc.example.net") is ServerUrl.Result.Invalid)
        assertTrue(ServerUrl.validate("http://192.168.1.10:8350") is ServerUrl.Result.Invalid)
        // 100.128.x.x liegt außerhalb von 100.64.0.0/10
        assertTrue(ServerUrl.validate("http://100.128.0.1:8350") is ServerUrl.Result.Invalid)
    }

    @Test
    fun rejectsMalformedInput() {
        assertTrue(ServerUrl.validate("100.101.102.103:8350") is ServerUrl.Result.Invalid)
        assertTrue(ServerUrl.validate("ftp://100.101.102.103") is ServerUrl.Result.Invalid)
        assertTrue(ServerUrl.validate("http://100.101.102.103:8350/api/v1") is ServerUrl.Result.Invalid)
        assertTrue(ServerUrl.validate("") is ServerUrl.Result.Invalid)
    }

    @Test
    fun tailscaleRangeBoundaries() {
        assertTrue(ServerUrl.isTrustedPlainHost("100.64.0.1"))
        assertTrue(ServerUrl.isTrustedPlainHost("100.127.255.254"))
        assertFalse(ServerUrl.isTrustedPlainHost("100.63.255.255"))
        assertFalse(ServerUrl.isTrustedPlainHost("100.101.102"))
    }
}
