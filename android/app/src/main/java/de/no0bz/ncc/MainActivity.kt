package de.no0bz.ncc

import android.Manifest
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import de.no0bz.ncc.ui.components.Lamp
import de.no0bz.ncc.ui.connection.ConnectionRoute
import de.no0bz.ncc.ui.dashboard.DashboardRoute
import de.no0bz.ncc.ui.theme.LocalNccColors
import de.no0bz.ncc.ui.theme.NccTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            NccTheme {
                Box(Modifier.fillMaxSize().background(LocalNccColors.current.panel)) {
                    NccApp()
                }
            }
        }
    }
}

private enum class Tab(val label: String) { DASHBOARD("Gerät"), CONNECTION("Verbindung") }

@Composable
private fun NccApp() {
    val ncc = LocalNccColors.current
    val context = LocalContext.current
    var tab by rememberSaveable { mutableStateOf(Tab.DASHBOARD) }

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
                        icon = { Lamp(if (item == Tab.DASHBOARD) ncc.go else ncc.shunt, lit = tab == item, size = 12.dp) },
                        label = { Text(item.label.uppercase(), style = MaterialTheme.typography.titleSmall) },
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
            Tab.CONNECTION -> ConnectionRoute(contentPadding = padding, onEnableService = requestThenEnable)
        }
        // Hintergrund unter der Statusleiste, damit gescrollter Inhalt nicht mit den Symbolen kollidiert.
        Box(Modifier.fillMaxWidth().height(top).background(ncc.panel.copy(alpha = 0.94f)))
    }
}
