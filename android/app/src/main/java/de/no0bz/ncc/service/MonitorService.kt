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
import de.no0bz.ncc.collect.LocationReader
import de.no0bz.ncc.collect.MetricsMapper
import de.no0bz.ncc.data.AppSettings
import de.no0bz.ncc.data.ChatStore
import de.no0bz.ncc.data.INTERVAL_CHOICES
import de.no0bz.ncc.data.UploadRule
import de.no0bz.ncc.update.AppUpdater
import de.no0bz.ncc.update.UpdateState
import de.no0bz.ncc.widget.NccTileService
import de.no0bz.ncc.widget.NccWidget
import de.no0bz.ncc.widget.WidgetData
import de.no0bz.ncc.widget.WidgetStore
import de.no0bz.ncc.data.PairingState
import de.no0bz.ncc.data.TelemetryLog
import de.no0bz.ncc.net.ApiException
import de.no0bz.ncc.net.HeartbeatRequest
import de.no0bz.ncc.net.LiveSocket
import de.no0bz.ncc.net.NccApi
import de.no0bz.ncc.net.StreamEvent
import de.no0bz.ncc.net.StreamProtocol
import de.no0bz.ncc.net.TelemetryPoint
import de.no0bz.ncc.pairing.PairingManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
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
    private lateinit var alerts: AlertNotifier
    private lateinit var locations: LocationReader
    private lateinit var updater: AppUpdater
    private var lastUpdateCheck = 0L

    private val socket = LiveSocket()
    private var streamJob: Job? = null
    private var liveJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        settings = AppSettings(this)
        reader = DeviceReader(this)
        conditions = Conditions(this)
        log = logFor(this)
        alerts = AlertNotifier(this, settings)
        locations = LocationReader(this)
        updater = AppUpdater(this, settings)
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForegroundWithTypes()
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

    /**
     * Mit Standort-Berechtigung läuft der Dienst zusätzlich als „location“-Dienst, damit Android
     * ihm im Hintergrund Standorte liefert. Ohne Berechtigung (oder wenn Android es ablehnt) nur „specialUse“.
     */
    private fun startForegroundWithTypes() {
        val withLocation = ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE or ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
        val notification = notification("Startet …")
        if (locations.access().any) {
            try {
                startForeground(NOTIFICATION_ID, notification, withLocation)
                return
            } catch (e: SecurityException) {
                Log.i(TAG, "Standort-Dienst nicht erlaubt, starte ohne: ${e.message}")
            } catch (e: IllegalStateException) {
                Log.i(TAG, "Standort-Dienst nicht erlaubt, starte ohne: ${e.message}")
            }
        }
        startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        scope.cancel()
        LiveState.setConnected(false)
        NccWidget.refresh(this, WidgetStore.load(this).copy(monitoring = false, connected = false))
        NccTileService.requestUpdate(this)
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
            ensureStream(s.pairingState == PairingState.PAIRED)
            // Bis zum nächsten Intervall warten – oder früher, wenn „Jetzt hochladen“ gedrückt wird.
            forceUpload = withTimeoutOrNull(s.intervalSeconds * 1000L) { wake.receive() } ?: false
        }
    }

    private suspend fun tick(forceUpload: Boolean) {
        val s = settings.current()
        val snapshot = reader.read()
        val network = conditions.network()
        val now = Instant.ofEpochMilli(snapshot.recordedAtMillis)
        // Standort nur bei eingeschaltetem Verlauf – sonst wird er gar nicht erst abgefragt.
        val fix = if (s.locationTracking) locations.current() else null
        log.append(TelemetryPoint(UUID.randomUUID().toString(), now.toString(), MetricsMapper.map(snapshot, network, fix)))
        settings.markSample(snapshot.recordedAtMillis)

        var status = "Gemessen ${TIME.format(LocalTime.now())}"
        val token = if (s.pairingState == PairingState.PAIRED) settings.token() else null
        if (token != null && network != null) {
            val api = NccApi(s.serverUrl)
            try {
                val beat = api.heartbeat(token, HeartbeatRequest(BuildConfig.VERSION_NAME, MetricsMapper.metadata(snapshot, s.intervalSeconds, BuildConfig.VERSION_NAME, s.uploadRule.wire)))
                // Der Server ist maßgeblich: Schalter im Dashboard kommt spätestens hier an.
                if (beat.locationTracking != s.locationTracking) settings.setLocationTracking(beat.locationTracking)
                settings.markHeartbeat(System.currentTimeMillis())
                if (System.currentTimeMillis() - lastUpdateCheck > UPDATE_CHECK_MS) {
                    lastUpdateCheck = System.currentTimeMillis()
                    val before = AppUpdater.updates.value
                    val checked = updater.check()
                    if (checked is UpdateState.Available && before !is UpdateState.Available) alerts.appUpdate(checked.release)
                }
                refreshWidget(api, token, snapshot.battery.levelPercent, snapshot.battery.charging || snapshot.battery.full)
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

    /** Hält den Live-Kanal offen, solange das Gerät gekoppelt ist. */
    private fun ensureStream(paired: Boolean) {
        if (!paired) {
            streamJob?.cancel()
            streamJob = null
            stopLive()
            LiveState.setConnected(false)
            return
        }
        if (streamJob?.isActive == true) return
        streamJob = scope.launch { streamLoop() }
    }

    private suspend fun streamLoop() {
        var backoffMs = 1_000L
        while (scope.isActive) {
            val s = settings.current()
            val token = settings.token()
            if (s.pairingState != PairingState.PAIRED || token == null) return
            try {
                socket.run(
                    s.serverUrl,
                    token,
                    onOpen = {
                        LiveState.setConnected(true)
                        markWidgetConnected(true)
                    },
                ) { event ->
                    backoffMs = 1_000L
                    handle(event)
                }
            } catch (e: ApiException) {
                Log.w(TAG, "Live-Kanal abgelehnt", e)
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Log.i(TAG, "Live-Kanal getrennt: ${e.message}")
            }
            LiveState.setConnected(false)
            markWidgetConnected(false)
            stopLive()
            delay(backoffMs)
            backoffMs = (backoffMs * 2).coerceAtMost(60_000L)
        }
    }

    private suspend fun handle(event: StreamEvent) {
        when (event) {
            is StreamEvent.ViewerPresent -> startLive(event.intervalMs)
            StreamEvent.ViewerGone -> stopLive()
            is StreamEvent.AlertSnapshot -> alerts.snapshot(event.alerts)
            is StreamEvent.AlertNew -> alerts.opened(event.alert)
            is StreamEvent.AlertResolved -> alerts.resolved(event.alert)
            is StreamEvent.ConfigUpdate -> {
                // Vom Dashboard geändert: übernehmen und sofort mit den neuen Werten weitermessen.
                event.locationTracking?.let { settings.setLocationTracking(it) }
                event.intervalSeconds?.takeIf { it in INTERVAL_CHOICES }?.let { settings.setInterval(it) }
                UploadRule.fromWire(event.uploadRule)?.let { settings.setUploadRule(it) }
                wake.trySend(false)
            }
            is StreamEvent.AppUpdate -> {
                val result = updater.offer(event.release)
                if (result is UpdateState.Available) alerts.appUpdate(event.release)
            }
            is StreamEvent.ChatNew -> {
                ChatStore.append(listOf(event.message))
                val own = event.message.senderNodeId == settings.current().nodeId
                if (!own && !ChatStore.visible) alerts.chat(event.message)
            }
            StreamEvent.Ping -> Unit
        }
    }

    /** Stufe „Server live“: solange ein Dashboard zuschaut, alle [intervalMs] einen Messpunkt senden. */
    private fun startLive(intervalMs: Long) {
        LiveState.setWatched(true)
        liveJob?.cancel()
        liveJob = scope.launch {
            while (isActive) {
                val network = conditions.network()
                val wifi = network?.type == "wifi" || network?.type == "ethernet"
                if (!settings.current().liveWifiOnly || wifi) {
                    val snapshot = reader.read()
                    socket.send(
                        StreamProtocol.liveMessage(
                            Instant.ofEpochMilli(snapshot.recordedAtMillis).toString(),
                            MetricsMapper.map(snapshot, network),
                        ),
                    )
                }
                delay(intervalMs)
            }
        }
    }

    private fun stopLive() {
        liveJob?.cancel()
        liveJob = null
        LiveState.setWatched(false)
    }

    /** Verbindungsstatus sofort ins Widget und in die Kachel übernehmen, nicht erst bei der nächsten Messung. */
    private fun markWidgetConnected(connected: Boolean) {
        val stored = WidgetStore.load(this)
        if (stored.connected != connected || !stored.monitoring) {
            NccWidget.refresh(this, stored.copy(connected = connected, monitoring = true))
            NccTileService.requestUpdate(this)
        }
    }

    /** Widget und Schnelleinstellungs-Kachel mit Flotte, Warnungen und Akku versorgen. */
    private suspend fun refreshWidget(api: NccApi, token: String, battery: Int?, charging: Boolean) {
        val previous = WidgetStore.load(this)
        // Die Geräteliste nur laden, wenn auch ein Widget auf dem Startbildschirm liegt.
        val fleet = if (NccWidget.placed(this)) runCatching { api.fleet(token) }.getOrNull() else null
        NccWidget.refresh(
            this,
            WidgetData(
                fleetOnline = fleet?.count { it.online } ?: previous.fleetOnline,
                fleetTotal = fleet?.size ?: previous.fleetTotal,
                alerts = LiveState.activeAlerts.value,
                batteryPercent = battery,
                charging = charging,
                monitoring = true,
                connected = LiveState.connected.value,
                updatedAtMillis = System.currentTimeMillis(),
            ),
        )
        NccTileService.requestUpdate(this)
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
        private const val UPDATE_CHECK_MS = 6 * 60 * 60 * 1000L
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
