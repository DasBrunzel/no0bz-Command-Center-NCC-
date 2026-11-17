package de.no0bz.ncc.widget

import android.app.PendingIntent
import android.content.Intent
import android.graphics.drawable.Icon
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import de.no0bz.ncc.MainActivity
import de.no0bz.ncc.R
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.service.MonitorService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Schnelleinstellungs-Kachel „NCC“: zeigt, ob die Überwachung läuft und wie viele Warnungen aktiv
 * sind; Antippen schaltet die Überwachung an oder aus.
 */
class NccTileService : TileService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private lateinit var settings: AppSettings

    override fun onCreate() {
        super.onCreate()
        settings = AppSettings(this)
    }

    override fun onStartListening() {
        render()
    }

    override fun onClick() {
        scope.launch {
            val enabled = settings.current().serviceEnabled
            if (enabled) {
                settings.setServiceEnabled(false)
                MonitorService.stop(this@NccTileService)
            } else {
                settings.setServiceEnabled(true)
                try {
                    MonitorService.start(this@NccTileService)
                } catch (_: Exception) {
                    // Android lässt den Dienst hier nicht starten: App öffnen, sie startet ihn selbst.
                    openApp()
                }
            }
            render()
        }
    }

    private fun render() {
        scope.launch {
            val tile = qsTile ?: return@launch
            val enabled = settings.current().serviceEnabled
            val data = WidgetStore.load(this@NccTileService)
            tile.label = "NCC"
            tile.icon = Icon.createWithResource(this@NccTileService, R.drawable.ic_stat_ncc)
            tile.state = if (enabled) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
            tile.subtitle = when {
                !enabled -> "aus"
                data.alerts > 0 -> data.alertText()
                else -> "Flotte ${data.fleetText()}"
            }
            tile.updateTile()
        }
    }

    private fun openApp() {
        val intent = Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivityAndCollapse(PendingIntent.getActivity(this, 4, intent, PendingIntent.FLAG_IMMUTABLE))
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        /** Bittet das System, die Kachel neu zu zeichnen (z. B. nach neuen Warnungen). */
        fun requestUpdate(context: android.content.Context) {
            requestListeningState(context, android.content.ComponentName(context, NccTileService::class.java))
        }
    }
}
