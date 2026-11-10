package de.no0bz.ncc.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import de.no0bz.ncc.MainActivity
import de.no0bz.ncc.R
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.net.AppAlert
import de.no0bz.ncc.net.ChatMessage

/**
 * Zeigt NCC-Warnungen als Benachrichtigung. Schon gemeldete Warnungen werden nach einem
 * Neuverbinden nicht noch einmal gemeldet (gemerkte IDs in den Einstellungen).
 */
class AlertNotifier(context: Context, private val settings: AppSettings) {
    private val app = context.applicationContext
    private val manager = app.getSystemService(NotificationManager::class.java)

    init {
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ALERTS, "NCC-Warnungen", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Warnungen deines NCC-Servers (Last, Temperatur, Speicher, offline …)."
                enableVibration(true)
            },
        )
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_RESOLVED, "NCC-Warnungen behoben", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Meldet leise, wenn eine Warnung vorbei ist."
            },
        )
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_CHAT, "NCC-Chat", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "Neue Nachrichten im Fleet-Chat."
            },
        )
    }

    /** Vollständiger Stand nach dem Verbinden: nur Neues melden, Vergangenes still entfernen. */
    suspend fun snapshot(alerts: List<AppAlert>) {
        val seen = settings.seenAlerts()
        val active = alerts.map { it.alertId }.toSet()
        if (settings.current().alertsEnabled) {
            alerts.filter { it.alertId !in seen }.forEach { post(it) }
        }
        (seen - active).forEach { manager.cancel(notificationId(it)) }
        settings.setSeenAlerts(active)
        LiveState.setActiveAlerts(active.size)
    }

    suspend fun opened(alert: AppAlert) {
        val seen = settings.seenAlerts()
        if (alert.alertId in seen) return
        if (settings.current().alertsEnabled) post(alert)
        settings.setSeenAlerts(seen + alert.alertId)
        LiveState.setActiveAlerts(seen.size + 1)
    }

    suspend fun resolved(alert: AppAlert) {
        val seen = settings.seenAlerts()
        if (settings.current().alertsEnabled && alert.alertId in seen) {
            manager.notify(
                notificationId(alert.alertId),
                builder(CHANNEL_RESOLVED)
                    .setContentTitle("✅ Behoben · ${alert.nodeName}")
                    .setContentText(alert.message)
                    .setTimeoutAfter(RESOLVED_VISIBLE_MS)
                    .build(),
            )
        }
        settings.setSeenAlerts(seen - alert.alertId)
        LiveState.setActiveAlerts((seen - alert.alertId).size)
    }

    /** Neue Chat-Nachricht von jemand anderem, während der Chat nicht offen ist. */
    suspend fun chat(message: ChatMessage) {
        if (!settings.current().chatNotifications) return
        val text = message.body.ifBlank { message.attachment?.let { "📎 ${it.name}" } ?: "" }
        manager.notify(
            CHAT_NOTIFICATION_ID,
            builder(CHANNEL_CHAT, MainActivity.OPEN_CHAT)
                .setGroup(null)
                .setContentTitle("💬 ${message.senderName}")
                .setContentText(text)
                .setStyle(Notification.BigTextStyle().bigText(text))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .build(),
        )
    }

    fun clearChat() = manager.cancel(CHAT_NOTIFICATION_ID)

    private fun post(alert: AppAlert) {
        val title = if (alert.critical) "🔴 Kritisch · ${alert.nodeName}" else "⚠️ Warnung · ${alert.nodeName}"
        manager.notify(
            notificationId(alert.alertId),
            builder(CHANNEL_ALERTS)
                .setContentTitle(title)
                .setContentText(alert.message)
                .setStyle(Notification.BigTextStyle().bigText(alert.message))
                .setCategory(Notification.CATEGORY_ALARM.takeIf { alert.critical } ?: Notification.CATEGORY_STATUS)
                .build(),
        )
    }

    private fun builder(channel: String, action: String? = null): Notification.Builder {
        val open = PendingIntent.getActivity(
            app,
            if (action == null) 1 else 2,
            Intent(app, MainActivity::class.java).setAction(action).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return Notification.Builder(app, channel)
            .setSmallIcon(R.drawable.ic_stat_ncc)
            .setContentIntent(open)
            .setAutoCancel(true)
            .setGroup(GROUP)
    }

    companion object {
        private const val CHANNEL_ALERTS = "alerts"
        private const val CHANNEL_RESOLVED = "alerts_resolved"
        private const val CHANNEL_CHAT = "chat"
        private const val CHAT_NOTIFICATION_ID = 2
        private const val GROUP = "ncc_alerts"
        private const val RESOLVED_VISIBLE_MS = 60 * 60 * 1000L

        /** Feste ID je Warnung, damit „behoben“ die ursprüngliche Meldung ersetzt (1 = Dienst). */
        fun notificationId(alertId: String): Int = 1000 + (alertId.hashCode() and 0x3fffffff)
    }
}
