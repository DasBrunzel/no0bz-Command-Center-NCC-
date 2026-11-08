package de.no0bz.ncc.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.util.Log
import de.no0bz.ncc.BuildConfig
import de.no0bz.ncc.MainActivity
import de.no0bz.ncc.R
import de.no0bz.ncc.collect.DeviceReader
import de.no0bz.ncc.collect.MetricsMapper
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.data.TelemetryLog
import de.no0bz.ncc.net.ApiException
import de.no0bz.ncc.net.HeartbeatRequest
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.TelemetryPoint
import de.no0bz.ncc.pairing.PairingManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File
import java.time.Instant
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * Stufe „Hintergrund“: misst im eingestellten Intervall (30 s – 5 min), schreibt jeden Messpunkt
 * ins Tageslog, sendet ein Lebenszeichen und lädt den Puffer nach der Upload-Regel hoch.
 * Läuft als Foreground Service, weil WorkManager-Jobs frühestens alle 15 Minuten laufen.
 */
class MonitorService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var loop: Job? = null
    private val wake = Channel<Boolean>(Channel.CONFLATED)

    private lateinit var settings: AppSettings
    private lateinit var reader: DeviceReader
    private lateinit var conditions: Conditions
    private lateinit var log: TelemetryLog

    override fun onCreate() {
        super.onCreate()
        settings = AppSettings(this)
        reader = DeviceReader(this)
        conditions = Conditions(this)
        log = logFor(this)
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, notification("Startet …"), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        when (intent?.action) {
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_UPLOAD_NOW -> wake.trySend(true)
            ACTION_RESCHEDULE -> wake.trySend(false)
        }
        if (loop?.isActive != true) loop = scope.launch { run() }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private suspend fun run() {
        var forceUpload = false
        while (scope.isActive) {
            val s = settings.current()
            if (!s.serviceEnabled) {
                stopSelf()
                return
            }
            runCatching { tick(forceUpload) }.onFailure { Log.w(TAG, "Messzyklus fehlgeschlagen", it) }
            // Bis zum nächsten Intervall warten – oder früher, wenn „Jetzt hochladen“ gedrückt wird.
            forceUpload = withTimeoutOrNull(s.intervalSeconds * 1000L) { wake.receive() } ?: false
        }
    }

    private suspend fun tick(forceUpload: Boolean) {
        val s = settings.current()
        val snapshot = reader.read()
        val network = conditions.network()
        val now = Instant.ofEpochMilli(snapshot.recordedAtMillis)
        log.append(TelemetryPoint(UUID.randomUUID().toString(), now.toString(), MetricsMapper.map(snapshot, network)))
        settings.markSample(snapshot.recordedAtMillis)

        var status = "Gemessen ${TIME.format(LocalTime.now())}"
        val token = if (s.pairingState == PairingState.PAIRED) settings.token() else null
        if (token != null && network != null) {
            val api = NccApi(s.serverUrl)
            try {
                api.heartbeat(token, HeartbeatRequest(BuildConfig.VERSION_NAME, MetricsMapper.metadata(snapshot, s.intervalSeconds, BuildConfig.VERSION_NAME)))
                settings.markHeartbeat(System.currentTimeMillis())
                if (forceUpload || conditions.uploadAllowed(s.uploadRule)) {
                    val sent = upload(api, token)
                    if (sent > 0) status += " · $sent hochgeladen"
                }
            } catch (e: ApiException) {
                if (e.code == 401) {
                    settings.unpair("Der Server hat den Zugang widerrufen. Bitte neu koppeln.")
                } else {
                    settings.setError(PairingManager.describe(e))
                }
            } catch (e: Exception) {
                settings.setError(PairingManager.describe(e))
            }
        }
        val pending = log.pendingCount()
        if (pending > 0) status += " · $pending im Puffer"
        notify(status)
    }

    /** Lädt den Puffer in Paketen zu 100 Messpunkten hoch, bis er leer ist. */
    private suspend fun upload(api: NccApi, token: String): Int {
        var sent = 0
        repeat(MAX_BATCHES_PER_TICK) {
            val batch = log.nextBatch() ?: return sent
            api.telemetry(token, batch.points)
            log.commit(batch.next)
            sent += batch.points.size
            settings.markUpload(System.currentTimeMillis())
        }
        return sent
    }

    private fun createChannel() {
        val channel = NotificationChannel(CHANNEL_ID, "NCC Überwachung", NotificationManager.IMPORTANCE_LOW).apply {
            description = "Dauerhafte Anzeige, solange NCC Gerätedaten sammelt."
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_ncc)
            .setContentTitle("NCC überwacht dieses Gerät")
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun notify(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }

    companion object {
        private const val TAG = "NccMonitor"
        private const val CHANNEL_ID = "monitor"
        private const val NOTIFICATION_ID = 1
        private const val MAX_BATCHES_PER_TICK = 50
        private val TIME = DateTimeFormatter.ofPattern("HH:mm:ss")

        const val ACTION_UPLOAD_NOW = "de.no0bz.ncc.UPLOAD_NOW"
        const val ACTION_RESCHEDULE = "de.no0bz.ncc.RESCHEDULE"
        const val ACTION_STOP = "de.no0bz.ncc.STOP"

        fun logFor(context: Context) = TelemetryLog(File(context.filesDir, "logs"))

        fun start(context: Context, action: String? = null) {
            context.startForegroundService(Intent(context, MonitorService::class.java).setAction(action))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, MonitorService::class.java))
        }
    }
}
