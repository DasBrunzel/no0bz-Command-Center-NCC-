package de.no0bz.ncc.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import de.no0bz.ncc.data.AppSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** Startet die Überwachung nach einem Neustart oder App-Update wieder, wenn sie eingeschaltet war. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                if (AppSettings(context).current().serviceEnabled) MonitorService.start(context)
            } finally {
                pending.finish()
            }
        }
    }
}
