package de.no0bz.ncc

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import de.no0bz.ncc.ui.chat.ChatRoute
import de.no0bz.ncc.ui.components.Lamp
import de.no0bz.ncc.ui.connection.ConnectionRoute
import de.no0bz.ncc.ui.dashboard.DashboardRoute
import de.no0bz.ncc.ui.fleet.FleetRoute
import de.no0bz.ncc.ui.theme.LocalNccColors
import de.no0bz.ncc.ui.theme.NccTheme

class MainActivity : ComponentActivity() {
    /** Zählt hoch, wenn eine Chat-Benachrichtigung angetippt wurde. */
    private val openChatRequests = mutableIntStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        if (savedInstanceState == null && intent?.action == OPEN_CHAT) openChatRequests.intValue++
        setContent {
            NccTheme {
                Box(Modifier.fillMaxSize().background(LocalNccColors.current.panel)) {
                    NccApp(openChatRequests.intValue)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.action == OPEN_CHAT) openChatRequests.intValue++
    }

    companion object {
        const val OPEN_CHAT = "de.no0bz.ncc.OPEN_CHAT"
    }
}

private enum class Tab(val label: String) { DASHBOARD("Gerät"), FLEET("Flotte"), CHAT("Chat"), CONNECTION("Verbindung") }

@Composable
private fun NccApp(openChatRequests: Int) {
    val ncc = LocalNccColors.current
    val context = LocalContext.current
    var tab by rememberSaveable { mutableStateOf(Tab.DASHBOARD) }
    LaunchedEffect(openChatRequests) { if (openChatRequests > 0) tab = Tab.CHAT }

    // Ohne Benachrichtigungs-Berechtigung läuft der Dienst zwar, ist aber unsichtbar.
    var pendingEnable by remember { mutableStateOf<(() -> Unit)?>(null) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        pendingEnable?.invoke()
        pendingEnable = null
    }
    val requestThenEnable: (() -> Unit) -> Unit = { enable ->
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        if (granted) enable() else {
            pendingEnable = enable
            permission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    Scaffold(
        containerColor = ncc.panel,
        bottomBar = {
            NavigationBar(containerColor = ncc.panelRaised, tonalElevation = 0.dp) {
                Tab.entries.forEach { item ->
                    NavigationBarItem(
                        selected = tab == item,
                        onClick = { tab = item },
                        icon = { Lamp(lampColor(item), lit = tab == item, size = 12.dp) },
                        label = { Text(item.label.uppercase(), style = MaterialTheme.typography.titleSmall, maxLines = 1) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedTextColor = ncc.ink,
                            unselectedTextColor = ncc.ink3,
                            indicatorColor = ncc.panelSunken,
                        ),
                    )
                }
            }
        },
    ) { inner ->
        val top = WindowInsets.safeDrawing.asPaddingValues().calculateTopPadding()
        val padding = PaddingValues(start = 16.dp, end = 16.dp, top = top + 16.dp, bottom = inner.calculateBottomPadding() + 16.dp)
        when (tab) {
            Tab.DASHBOARD -> DashboardRoute(contentPadding = padding)
            Tab.FLEET -> FleetRoute(contentPadding = padding)
            // Der Chat schließt unten direkt an die Leiste an, damit das Eingabefeld Platz hat.
            Tab.CHAT -> ChatRoute(
                contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = top + 12.dp, bottom = inner.calculateBottomPadding() + 8.dp),
            )
            Tab.CONNECTION -> ConnectionRoute(contentPadding = padding, onEnableService = requestThenEnable)
        }
        // Hintergrund unter der Statusleiste, damit gescrollter Inhalt nicht mit den Symbolen kollidiert.
        Box(Modifier.fillMaxWidth().height(top).background(ncc.panel.copy(alpha = 0.94f)))
    }
}

@Composable
private fun lampColor(tab: Tab): Color {
    val ncc = LocalNccColors.current
    return when (tab) {
        Tab.DASHBOARD -> ncc.go
        Tab.FLEET -> ncc.series[2]
        Tab.CHAT -> ncc.caution
        Tab.CONNECTION -> ncc.shunt
    }
}
