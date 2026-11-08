package de.no0bz.ncc.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import de.no0bz.ncc.ui.theme.LocalNccColors

/** Kachel im Stil der Dashboard-Panels. */
@Composable
fun Panel(
    title: String,
    modifier: Modifier = Modifier,
    trailing: (@Composable () -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val ncc = LocalNccColors.current
    val shape = RoundedCornerShape(7.dp)
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .background(ncc.panelRaised)
            .border(1.dp, ncc.line, shape)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = title.uppercase(),
                style = MaterialTheme.typography.titleMedium,
                color = ncc.ink3,
                modifier = Modifier.weight(1f),
            )
            trailing?.invoke()
        }
        content()
    }
}

/** Signallampe; leuchtet mit weichem Schein, aus = „unlit“. */
@Composable
fun Lamp(color: Color, lit: Boolean, modifier: Modifier = Modifier, size: Dp = 12.dp) {
    val ncc = LocalNccColors.current
    val fill by animateColorAsState(if (lit) color else ncc.unlit, tween(260), label = "lamp")
    Box(
        modifier = modifier
            .size(size)
            .drawBehind {
                if (lit) {
                    drawCircle(
                        brush = Brush.radialGradient(listOf(fill.copy(alpha = 0.45f), Color.Transparent)),
                        radius = this.size.minDimension,
                    )
                }
            }
            .clip(CircleShape)
            .background(fill)
            .border(1.dp, ncc.lineStrong.copy(alpha = 0.6f), CircleShape),
    )
}

/** Füllbalken 0..1 mit Ampelfarbe nach Schwellwerten. */
@Composable
fun Meter(
    fraction: Float,
    modifier: Modifier = Modifier,
    color: Color = meterColor(fraction),
    height: Dp = 8.dp,
    label: String? = null,
) {
    val ncc = LocalNccColors.current
    val animated by animateFloatAsState(fraction.coerceIn(0f, 1f), tween(420), label = "meter")
    val shape = RoundedCornerShape(2.dp)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(height)
            .clip(shape)
            .background(ncc.panelSunken)
            .then(if (label != null) Modifier.semantics { contentDescription = label } else Modifier),
    ) {
        Box(
            Modifier
                .fillMaxHeight()
                .fillMaxWidth(animated)
                .background(color),
        )
    }
}

@Composable
fun meterColor(fraction: Float): Color {
    val ncc = LocalNccColors.current
    return when {
        fraction >= 0.9f -> ncc.stop
        fraction >= 0.7f -> ncc.caution
        else -> ncc.go
    }
}

/** Beschriftung links, Wert rechts. */
@Composable
fun StatRow(label: String, value: String, modifier: Modifier = Modifier, valueColor: Color? = null) {
    val ncc = LocalNccColors.current
    // Beschriftung behält ihre Breite; lange Werte brechen rechtsbündig um.
    Row(modifier = modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = ncc.ink3,
            maxLines = 1,
            modifier = Modifier.padding(end = 16.dp),
        )
        Text(
            value,
            style = MaterialTheme.typography.labelLarge,
            color = valueColor ?: ncc.ink,
            textAlign = TextAlign.End,
            modifier = Modifier.weight(1f).padding(top = 1.dp),
        )
    }
}

/** Großer Zahlenwert mit kleiner Einheit/Zusatz daneben. */
@Composable
fun BigValue(value: String, suffix: String? = null, color: Color? = null) {
    val ncc = LocalNccColors.current
    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(value, style = MaterialTheme.typography.displayMedium, color = color ?: ncc.ink)
        if (suffix != null) {
            Text(
                suffix,
                style = MaterialTheme.typography.bodyMedium,
                color = ncc.ink3,
                modifier = Modifier.padding(bottom = 5.dp),
            )
        }
    }
}
