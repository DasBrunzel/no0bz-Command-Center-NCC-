package de.no0bz.ncc.ui.chat

import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import de.no0bz.ncc.data.PendingAttachment
import de.no0bz.ncc.net.ChatMessage
import de.no0bz.ncc.ui.Format
import de.no0bz.ncc.ui.components.Lamp
import de.no0bz.ncc.ui.theme.LocalNccColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun ChatRoute(contentPadding: PaddingValues, viewModel: ChatViewModel = viewModel()) {
    val ui by viewModel.ui.collectAsStateWithLifecycle()
    val messages by viewModel.messages.collectAsStateWithLifecycle()
    val notify by viewModel.chatNotifications.collectAsStateWithLifecycle()

    // „Sichtbar“ nur, solange der Tab offen und die App im Vordergrund ist.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> viewModel.onVisible(true)
                Lifecycle.Event.ON_PAUSE -> viewModel.onVisible(false)
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        if (lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) viewModel.onVisible(true)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.onVisible(false)
        }
    }

    val ncc = LocalNccColors.current
    Column(
        Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .consumeWindowInsets(contentPadding)
            .imePadding(),
    ) {
        Row(Modifier.padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("NCC · CHAT", style = MaterialTheme.typography.titleSmall, color = ncc.ink3)
                Text("Fleet-Chat", style = MaterialTheme.typography.displayMedium, color = ncc.ink)
            }
            if (ui.paired == true) {
                Chip(if (notify) "🔔 an" else "🔕 aus", "Chat-Benachrichtigungen umschalten") { viewModel.setChatNotifications(!notify) }
            }
        }
        Spacer(Modifier.height(8.dp))
        when {
            ui.paired == false -> Notice("Der Chat ist verfügbar, sobald das Handy mit dem NCC-Server gekoppelt ist (Tab „Verbindung“).")
            else -> {
                MessageList(
                    messages = messages,
                    ui = ui,
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                    onLoadOlder = viewModel::loadOlder,
                    onOpen = viewModel::open,
                    thumbnail = { message -> loadThumbnail(viewModel, message) },
                )
                ui.error?.let { ErrorBar(it, viewModel::dismissError) }
                Composer(ui, viewModel)
            }
        }
    }
}

private suspend fun loadThumbnail(viewModel: ChatViewModel, message: ChatMessage): ImageBitmap? = withContext(Dispatchers.IO) {
    val file = viewModel.attachmentFile(message) ?: return@withContext null
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.path, bounds)
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 900) sample *= 2
    BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample })?.asImageBitmap()
}

@Composable
private fun MessageList(
    messages: List<ChatMessage>,
    ui: ChatUi,
    modifier: Modifier,
    onLoadOlder: () -> Unit,
    onOpen: (ChatMessage) -> Unit,
    thumbnail: suspend (ChatMessage) -> ImageBitmap?,
) {
    val ncc = LocalNccColors.current
    val state = rememberLazyListState()
    // Neueste Nachricht steht unten (reverseLayout), Index 0 = neueste.
    val reversed = remember(messages) { messages.asReversed() }
    val nearTop by remember(reversed.size) {
        derivedStateOf { (state.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0) >= reversed.size - 5 }
    }
    LaunchedEffect(nearTop, reversed.size) { if (nearTop && reversed.isNotEmpty()) onLoadOlder() }
    // Bei neuer Nachricht nach unten springen, wenn man ohnehin unten war.
    LaunchedEffect(reversed.firstOrNull()?.messageId) {
        if (state.firstVisibleItemIndex <= 2) state.animateScrollToItem(0)
    }

    Box(modifier) {
        if (messages.isEmpty()) {
            if (ui.loading) CircularProgressIndicator(Modifier.align(Alignment.Center), color = ncc.shunt)
            else Text("Noch keine Nachrichten.", Modifier.align(Alignment.Center), color = ncc.ink3, style = MaterialTheme.typography.bodyLarge)
            return@Box
        }
        LazyColumn(
            state = state,
            reverseLayout = true,
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(6.dp),
            contentPadding = PaddingValues(vertical = 8.dp),
        ) {
            items(reversed.size, key = { reversed[it].messageId }) { index ->
                val message = reversed[index]
                val older = reversed.getOrNull(index + 1)
                val day = dayOf(message.createdAt)
                val newDay = older == null || dayOf(older.createdAt) != day
                Column {
                    if (newDay && day != null) DayDivider(day)
                    Bubble(
                        message = message,
                        mine = message.senderNodeId != null && message.senderNodeId == ui.nodeId,
                        showSender = newDay || older?.senderName != message.senderName || older.senderNodeId != message.senderNodeId,
                        onOpen = onOpen,
                        thumbnail = thumbnail,
                    )
                }
            }
            if (ui.loadingOlder) {
                item(key = "older") {
                    Box(Modifier.fillMaxWidth().padding(8.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(Modifier.size(20.dp), color = ncc.shunt, strokeWidth = 2.dp)
                    }
                }
            }
        }
    }
}

@Composable
private fun DayDivider(day: LocalDate) {
    val ncc = LocalNccColors.current
    val label = when (day) {
        LocalDate.now() -> "Heute"
        LocalDate.now().minusDays(1) -> "Gestern"
        else -> day.format(DAY)
    }
    Box(Modifier.fillMaxWidth().padding(vertical = 8.dp), contentAlignment = Alignment.Center) {
        Text(label.uppercase(), style = MaterialTheme.typography.titleSmall, color = ncc.ink3)
    }
}

@Composable
private fun Bubble(
    message: ChatMessage,
    mine: Boolean,
    showSender: Boolean,
    onOpen: (ChatMessage) -> Unit,
    thumbnail: suspend (ChatMessage) -> ImageBitmap?,
) {
    val ncc = LocalNccColors.current
    val shape = RoundedCornerShape(7.dp)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
        Column(
            Modifier
                .widthIn(max = 320.dp)
                .clip(shape)
                .background(if (mine) ncc.shunt.copy(alpha = 0.16f) else ncc.panelRaised)
                .border(1.dp, if (mine) ncc.shunt.copy(alpha = 0.45f) else ncc.line, shape)
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            if (showSender) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        if (mine) "Du" else message.senderName,
                        style = MaterialTheme.typography.labelLarge,
                        color = if (mine) ncc.shuntInk else ncc.ink,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    if (message.senderNodeId != null && !mine) {
                        Spacer(Modifier.width(6.dp))
                        Text(
                            "GERÄT",
                            style = MaterialTheme.typography.titleSmall,
                            color = ncc.ink3,
                            modifier = Modifier.border(1.dp, ncc.line, RoundedCornerShape(4.dp)).padding(horizontal = 4.dp),
                        )
                    }
                }
            }
            message.attachment?.let { attachment ->
                if (attachment.isImage) {
                    val bitmap by produceState<ImageBitmap?>(null, message.messageId) { value = thumbnail(message) }
                    val image = bitmap
                    if (image != null) {
                        Image(
                            bitmap = image,
                            contentDescription = "Bild ${attachment.name} öffnen",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .fillMaxWidth()
                                .aspectRatio((image.width.toFloat() / image.height).coerceIn(0.6f, 2.2f))
                                .clip(RoundedCornerShape(4.dp))
                                .clickable(role = Role.Image) { onOpen(message) },
                        )
                    } else {
                        Box(
                            Modifier.fillMaxWidth().height(120.dp).clip(RoundedCornerShape(4.dp)).background(ncc.panelSunken),
                            contentAlignment = Alignment.Center,
                        ) { CircularProgressIndicator(Modifier.size(20.dp), color = ncc.shunt, strokeWidth = 2.dp) }
                    }
                } else {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(4.dp))
                            .background(ncc.panelSunken)
                            .clickable(role = Role.Button) { onOpen(message) }
                            .padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("📎", style = MaterialTheme.typography.bodyLarge)
                        Spacer(Modifier.width(8.dp))
                        Column(Modifier.weight(1f)) {
                            Text(attachment.name, style = MaterialTheme.typography.labelLarge, color = ncc.ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(Format.bytes(attachment.size, binary = true), style = MaterialTheme.typography.bodySmall, color = ncc.ink3)
                        }
                    }
                }
            }
            if (message.body.isNotBlank()) {
                if (message.markdown) {
                    Text(
                        Markdown.render(message.body, ncc.shuntInk, ncc.panelSunken),
                        style = MaterialTheme.typography.bodyLarge,
                        color = ncc.ink,
                    )
                } else {
                    Text(message.body, style = MaterialTheme.typography.bodyLarge, color = ncc.ink)
                }
            }
            Text(
                timeOf(message.createdAt),
                style = MaterialTheme.typography.bodySmall,
                color = ncc.ink3,
                modifier = Modifier.align(Alignment.End),
            )
        }
    }
}

@Composable
private fun Composer(ui: ChatUi, viewModel: ChatViewModel) {
    val ncc = LocalNccColors.current
    var text by rememberSaveable { mutableStateOf("") }
    var markdown by rememberSaveable { mutableStateOf(false) }

    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { viewModel.onPhotoTaken(it) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let(viewModel::attach) }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        ui.pending?.let { PendingRow(it, viewModel::removePending) }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Chip("📷", "Foto aufnehmen") { camera.launch(viewModel.newCameraUri()) }
            Chip("📎", "Datei anhängen") { picker.launch("*/*") }
            Chip(if (markdown) "MD ✓" else "MD", "Markdown umschalten", active = markdown) { markdown = !markdown }
        }
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = text,
                onValueChange = { if (it.length <= 20_000) text = it },
                placeholder = { Text(if (ui.pending != null) "Beschreibung (optional)" else "Nachricht", color = ncc.ink3) },
                maxLines = 5,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ncc.shunt, unfocusedBorderColor = ncc.line,
                    focusedTextColor = ncc.ink, unfocusedTextColor = ncc.ink, cursorColor = ncc.shunt,
                    focusedContainerColor = ncc.panelRaised, unfocusedContainerColor = ncc.panelRaised,
                ),
                modifier = Modifier.weight(1f).heightIn(min = 52.dp),
            )
            val canSend = !ui.sending && (text.isNotBlank() || ui.pending != null)
            Box(
                Modifier
                    .size(52.dp)
                    .clip(CircleShape)
                    .background(if (canSend) ncc.shunt else ncc.unlit)
                    .clickable(enabled = canSend, role = Role.Button) { viewModel.send(text, markdown) { text = "" } }
                    .semantics { contentDescription = "Senden" },
                contentAlignment = Alignment.Center,
            ) {
                if (ui.sending) CircularProgressIndicator(Modifier.size(22.dp), color = ncc.panelRaised, strokeWidth = 2.dp)
                else Text("➤", color = ncc.panelRaised, style = MaterialTheme.typography.headlineMedium)
            }
        }
    }
}

@Composable
private fun PendingRow(attachment: PendingAttachment, onRemove: () -> Unit) {
    val ncc = LocalNccColors.current
    val preview by produceState<ImageBitmap?>(null, attachment.file.path) {
        value = if (!attachment.isImage) null else withContext(Dispatchers.IO) {
            BitmapFactory.decodeFile(attachment.file.path, BitmapFactory.Options().apply { inSampleSize = 8 })?.asImageBitmap()
        }
    }
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(7.dp)).background(ncc.panelRaised).border(1.dp, ncc.line, RoundedCornerShape(7.dp)).padding(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        preview?.let {
            Image(it, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.size(44.dp).clip(RoundedCornerShape(4.dp)))
        } ?: Text("📎", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(attachment.name, style = MaterialTheme.typography.labelLarge, color = ncc.ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(Format.bytes(attachment.file.length(), binary = true), style = MaterialTheme.typography.bodySmall, color = ncc.ink3)
        }
        Chip("✕", "Anhang entfernen", onClick = onRemove)
    }
}

@Composable
private fun Chip(label: String, description: String, active: Boolean = false, onClick: () -> Unit) {
    val ncc = LocalNccColors.current
    val shape = RoundedCornerShape(999.dp)
    Box(
        Modifier
            .heightIn(min = 40.dp)
            .widthIn(min = 48.dp)
            .clip(shape)
            .background(if (active) ncc.shunt.copy(alpha = 0.18f) else ncc.panelRaised)
            .border(1.dp, if (active) ncc.shunt else ncc.line, shape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description }
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) { Text(label, style = MaterialTheme.typography.labelLarge, color = ncc.ink) }
}

@Composable
private fun ErrorBar(text: String, onDismiss: () -> Unit) {
    val ncc = LocalNccColors.current
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Lamp(ncc.stop, lit = true, size = 10.dp)
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium, color = ncc.stopInk, modifier = Modifier.weight(1f))
        Chip("OK", "Hinweis schließen", onClick = onDismiss)
    }
}

@Composable
private fun Notice(text: String) {
    val ncc = LocalNccColors.current
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(text, style = MaterialTheme.typography.bodyLarge, color = ncc.ink2)
    }
}

private val TIME = DateTimeFormatter.ofPattern("HH:mm")
private val DAY = DateTimeFormatter.ofPattern("EEEE, d. MMMM", Locale.GERMANY)

/** Zeitstempel des Servers; ohne Zeitzone (SQLite) gilt UTC. */
internal fun parseInstant(iso: String): Instant? =
    runCatching { OffsetDateTime.parse(iso).toInstant() }
        .recoverCatching { LocalDateTime.parse(iso).toInstant(ZoneOffset.UTC) }
        .getOrNull()

private fun timeOf(iso: String): String = parseInstant(iso)?.atZone(ZoneId.systemDefault())?.format(TIME) ?: ""

private fun dayOf(iso: String): LocalDate? = parseInstant(iso)?.atZone(ZoneId.systemDefault())?.toLocalDate()
