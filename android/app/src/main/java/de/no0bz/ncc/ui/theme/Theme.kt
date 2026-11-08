package de.no0bz.ncc.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import de.no0bz.ncc.R

/**
 * Farben aus dem NCC-Dashboard (frontend/src/styles/tokens.css), von oklch nach sRGB umgerechnet.
 * Signalfarben: go = grün, caution = gelb, stop = rot, shunt = blau.
 */
@Immutable
data class NccColors(
    val panel: Color,
    val panelRaised: Color,
    val panelSunken: Color,
    val line: Color,
    val lineStrong: Color,
    val ink: Color,
    val ink2: Color,
    val ink3: Color,
    val go: Color,
    val caution: Color,
    val stop: Color,
    val shunt: Color,
    val unlit: Color,
    val goInk: Color,
    val cautionInk: Color,
    val stopInk: Color,
    val shuntInk: Color,
    val series: List<Color>,
)

val LightNcc = NccColors(
    panel = Color(0xFFE3EAE3), panelRaised = Color(0xFFF2F6F2), panelSunken = Color(0xFFD5DDD5),
    line = Color(0xFFBBC4BC), lineStrong = Color(0xFF8A958F),
    ink = Color(0xFF182230), ink2 = Color(0xFF394350), ink3 = Color(0xFF535C66),
    go = Color(0xFF258F33), caution = Color(0xFFF2AB19), stop = Color(0xFFD42320), shunt = Color(0xFF2E62C9),
    unlit = Color(0xFFB0B6B1),
    goInk = Color(0xFF09611A), cautionInk = Color(0xFF845000), stopInk = Color(0xFFAC040C), shuntInk = Color(0xFF194CB1),
    series = listOf(Color(0xFF2E69B2), Color(0xFFD67523), Color(0xFF00876D), Color(0xFF993F94)),
)

val DarkNcc = NccColors(
    panel = Color(0xFF151A20), panelRaised = Color(0xFF1D242A), panelSunken = Color(0xFF0E1318),
    line = Color(0xFF323940), lineStrong = Color(0xFF515961),
    ink = Color(0xFFE7EDE7), ink2 = Color(0xFFBFC6BF), ink3 = Color(0xFF99A19A),
    go = Color(0xFF5BC663), caution = Color(0xFFF8BD40), stop = Color(0xFFF45B4E), shunt = Color(0xFF77A4F6),
    unlit = Color(0xFF43484E),
    goInk = Color(0xFF7BD77F), cautionInk = Color(0xFFF8C562), stopInk = Color(0xFFFF887A), shuntInk = Color(0xFF97BEFF),
    series = listOf(Color(0xFF4F8BD6), Color(0xFFCE7C22), Color(0xFF258E6A), Color(0xFFC66AAA)),
)

val LocalNccColors = staticCompositionLocalOf { DarkNcc }

val BarlowText = FontFamily(
    Font(R.font.barlow_regular, FontWeight.Normal),
    Font(R.font.barlow_medium, FontWeight.Medium),
    Font(R.font.barlow_semibold, FontWeight.SemiBold),
)

val BarlowDisplay = FontFamily(
    Font(R.font.barlow_condensed_semibold, FontWeight.SemiBold),
    Font(R.font.barlow_condensed_bold, FontWeight.Bold),
)

/** Ziffern gleich breit, damit Live-Werte nicht springen. */
private const val TABULAR = "tnum"

private val NccTypography = Typography(
    displayLarge = TextStyle(fontFamily = BarlowDisplay, fontWeight = FontWeight.Bold, fontSize = 48.sp, lineHeight = 50.sp, fontFeatureSettings = TABULAR),
    displayMedium = TextStyle(fontFamily = BarlowDisplay, fontWeight = FontWeight.Bold, fontSize = 36.sp, lineHeight = 38.sp, fontFeatureSettings = TABULAR),
    headlineMedium = TextStyle(fontFamily = BarlowDisplay, fontWeight = FontWeight.SemiBold, fontSize = 24.sp, lineHeight = 28.sp, fontFeatureSettings = TABULAR),
    titleMedium = TextStyle(fontFamily = BarlowDisplay, fontWeight = FontWeight.SemiBold, fontSize = 15.sp, lineHeight = 18.sp, letterSpacing = 0.08.em),
    titleSmall = TextStyle(fontFamily = BarlowDisplay, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, lineHeight = 16.sp, letterSpacing = 0.08.em),
    bodyLarge = TextStyle(fontFamily = BarlowText, fontWeight = FontWeight.Normal, fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontFamily = BarlowText, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 20.sp, fontFeatureSettings = TABULAR),
    bodySmall = TextStyle(fontFamily = BarlowText, fontWeight = FontWeight.Normal, fontSize = 12.sp, lineHeight = 16.sp, fontFeatureSettings = TABULAR),
    labelLarge = TextStyle(fontFamily = BarlowText, fontWeight = FontWeight.SemiBold, fontSize = 14.sp, lineHeight = 18.sp, fontFeatureSettings = TABULAR),
    labelMedium = TextStyle(fontFamily = BarlowText, fontWeight = FontWeight.Medium, fontSize = 12.sp, lineHeight = 16.sp, fontFeatureSettings = TABULAR),
)

@Composable
fun NccTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val ncc = if (dark) DarkNcc else LightNcc
    val scheme = if (dark) {
        darkColorScheme(
            primary = ncc.shunt, onPrimary = ncc.panelSunken, secondary = ncc.go, tertiary = ncc.caution,
            background = ncc.panel, onBackground = ncc.ink, surface = ncc.panelRaised, onSurface = ncc.ink,
            surfaceVariant = ncc.panelSunken, onSurfaceVariant = ncc.ink2, outline = ncc.lineStrong,
            outlineVariant = ncc.line, error = ncc.stop,
        )
    } else {
        lightColorScheme(
            primary = ncc.shunt, onPrimary = Color(0xFFF6F9F6), secondary = ncc.go, tertiary = ncc.caution,
            background = ncc.panel, onBackground = ncc.ink, surface = ncc.panelRaised, onSurface = ncc.ink,
            surfaceVariant = ncc.panelSunken, onSurfaceVariant = ncc.ink2, outline = ncc.lineStrong,
            outlineVariant = ncc.line, error = ncc.stop,
        )
    }
    CompositionLocalProvider(LocalNccColors provides ncc) {
        MaterialTheme(colorScheme = scheme, typography = NccTypography, content = content)
    }
}
