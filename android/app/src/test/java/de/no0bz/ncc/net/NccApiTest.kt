package de.no0bz.ncc.net

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

class NccApiTest {
    private val server = MockWebServer()
    private lateinit var api: NccApi

    @Before
    fun setUp() {
        server.start()
        api = NccApi(server.url("/").toString().trimEnd('/'))
    }

    @After
    fun tearDown() = server.close()

    @Test
    fun claimReturnsNullWhileApprovalIsPending() = runTest {
        server.enqueue(MockResponse(code = 409, body = "{\"detail\":\"pairing approval is pending\"}"))
        assertNull(api.claimPairing("android_abc", "s".repeat(43)))
        val request = server.takeRequest()
        assertEquals("/api/v1/agent-pairings/android_abc/claim", request.url.encodedPath)
        assertTrue(request.body!!.utf8().contains("\"pairing_secret\""))
    }

    @Test
    fun claimReturnsTokenAfterApproval() = runTest {
        server.enqueue(MockResponse(code = 200, body = "{\"token\":\"ncc_agent_xyz\"}"))
        assertEquals("ncc_agent_xyz", api.claimPairing("android_abc", "s".repeat(43)))
    }

    @Test
    fun expiredClaimSurfacesAsApiException() = runTest {
        server.enqueue(MockResponse(code = 410, body = "{}"))
        try {
            api.claimPairing("android_abc", "s".repeat(43))
            fail("410 erwartet")
        } catch (e: ApiException) {
            assertEquals(410, e.code)
        }
    }

    @Test
    fun telemetrySendsBearerTokenAndSnakeCase() = runTest {
        server.enqueue(MockResponse(code = 200, body = "{\"accepted\":1,\"duplicates\":0,\"extra\":true}"))
        val result = api.telemetry("ncc_agent_xyz", listOf(TelemetryPoint("id-1", "2026-11-08T12:00:00Z", JsonObject(emptyMap()))))
        assertEquals(1, result.accepted)
        val request = server.takeRequest()
        assertEquals("Bearer ncc_agent_xyz", request.headers["Authorization"])
        val body = request.body!!.utf8()
        assertTrue(body.contains("\"sample_id\":\"id-1\""))
        assertTrue(body.contains("\"recorded_at\""))
    }

    @Test
    fun registerSendsAndroidPlatform() = runTest {
        server.enqueue(
            MockResponse(
                code = 201,
                body = "{\"pairing_id\":\"android_abc\",\"display_name\":\"Pixel\",\"platform\":\"android\",\"access_role\":\"commander\",\"status\":\"waiting\",\"created_at\":\"x\",\"expires_at\":\"2026-11-08T12:15:00Z\"}",
            ),
        )
        val response = api.registerPairing(
            PairingRegisterRequest("android_abc", "s".repeat(43), "android-0011223344556677", "Pixel", agentVersion = "0.2.0"),
        )
        assertEquals("waiting", response.status)
        assertTrue(server.takeRequest().body!!.utf8().contains("\"platform\":\"android\""))
    }

    @Test
    fun liveIsFalseWhenServerIsDown() = runTest {
        server.close()
        assertEquals(false, api.live())
    }
}
