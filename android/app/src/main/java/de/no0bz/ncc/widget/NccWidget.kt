package de.no0bz.ncc.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import de.no0bz.ncc.MainActivity
import de.no0bz.ncc.R
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Was das Widget zeigt; vom Hintergrunddienst nach jeder Messung geschrieben. */
data class WidgetData(
    val fleetOnline: Int?,
    val fleetTotal: Int?,
    val alerts: Int,
    val batteryPercent: Int?,
    val charging: Boolean,
    val monitoring: Boolean,
    val connected: Boolean,
    val updatedAtMillis: Long?,
) {
    fun fleetText(): String = if (fleetOnline == null || fleetTotal == null) "–" else "$fleetOnline/$fleetTotal"
    fun alertText(): String = when (alerts) {
        0 -> "keine Warnungen"
        1 -> "1 Warnung"
        else -> "$alerts Warnungen"
    }
}

/** Homescreen-Widget: Flotte online, aktive Warnungen und der eigene Akku auf einen Blick. */
class NccWidget : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        val data = WidgetStore.load(context)
        ids.forEach { manager.updateAppWidget(it, views(context, data)) }
    }

    companion object {
        private val TIME = DateTimeFormatter.ofPattern("HH:mm")

        /** Bittet den Launcher, das Widget anzulegen (Android zeigt dazu einen eigenen Dialog). */
        fun requestPin(context: Context): Boolean {
            val manager = AppWidgetManager.getInstance(context)
            if (!manager.isRequestPinAppWidgetSupported) return false
            return manager.requestPinAppWidget(ComponentName(context, NccWidget::class.java), null, null)
        }

        fun placed(context: Context): Boolean =
            AppWidgetManager.getInstance(context).getAppWidgetIds(ComponentName(context, NccWidget::class.java)).isNotEmpty()

        /** Alle platzierten Widgets mit neuen Daten zeichnen. */
        fun refresh(context: Context, data: WidgetData) {
            WidgetStore.save(context, data)
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, NccWidget::class.java))
            if (ids.isEmpty()) return
            val remote = views(context, data)
            ids.forEach { manager.updateAppWidget(it, remote) }
        }

        fun views(context: Context, data: WidgetData): RemoteViews = RemoteViews(context.packageName, R.layout.widget_ncc).apply {
            setTextViewText(R.id.widget_fleet, data.fleetText())
            setTextViewText(R.id.widget_alerts, data.alertText())
            setTextViewText(R.id.widget_battery, data.batteryPercent?.let { "$it %" + if (data.charging) " ⚡" else "" } ?: "–")
            setTextViewText(
                R.id.widget_status,
                when {
                    !data.monitoring -> "Überwachung aus"
                    data.connected -> "verbunden · " + (data.updatedAtMillis?.let { TIME.format(Instant.ofEpochMilli(it).atZone(ZoneId.systemDefault())) } ?: "")
                    else -> "nicht verbunden"
                },
            )
            setImageViewResource(
                R.id.widget_lamp,
                when {
                    !data.monitoring || !data.connected -> R.drawable.lamp_off
                    data.alerts > 0 -> R.drawable.lamp_caution
                    else -> R.drawable.lamp_go
                },
            )
            val open = PendingIntent.getActivity(
                context, 3, Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            setOnClickPendingIntent(R.id.widget_root, open)
        }
    }
}

/** Speichert die Widget-Daten, damit das Widget auch nach einem Neustart sofort etwas zeigt. */
object WidgetStore {
    private const val PREFS = "ncc_widget"

    fun save(context: Context, data: WidgetData) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putInt("online", data.fleetOnline ?: -1)
            .putInt("total", data.fleetTotal ?: -1)
            .putInt("alerts", data.alerts)
            .putInt("battery", data.batteryPercent ?: -1)
            .putBoolean("charging", data.charging)
            .putBoolean("monitoring", data.monitoring)
            .putBoolean("connected", data.connected)
            .putLong("updated", data.updatedAtMillis ?: -1)
            .apply()
    }

    fun load(context: Context): WidgetData {
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return WidgetData(
            fleetOnline = p.getInt("online", -1).takeIf { it >= 0 },
            fleetTotal = p.getInt("total", -1).takeIf { it >= 0 },
            alerts = p.getInt("alerts", 0),
            batteryPercent = p.getInt("battery", -1).takeIf { it >= 0 },
            charging = p.getBoolean("charging", false),
            monitoring = p.getBoolean("monitoring", false),
            connected = p.getBoolean("connected", false),
            updatedAtMillis = p.getLong("updated", -1).takeIf { it >= 0 },
        )
    }
}
