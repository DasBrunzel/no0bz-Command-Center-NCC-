package de.no0bz.ncc.ui.chat

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.em

/**
 * Kleiner Markdown-Umsetzer für Chat-Nachrichten: Überschriften, Listen, Zitate, Codeblöcke,
 * **fett**, *kursiv*, ~~durchgestrichen~~, `Code` und Links. HTML wird nie ausgewertet;
 * Links sind nur mit http(s) anklickbar.
 */
object Markdown {
    /** Zerlegt eine Zeile in Auszeichnungs-Abschnitte; getrennt von Compose testbar. */
    sealed interface Span {
        data class Text(val text: String, val bold: Boolean = false, val italic: Boolean = false, val strike: Boolean = false) : Span
        data class Code(val text: String) : Span
        data class Link(val label: String, val url: String) : Span
    }

    private val INLINE = Regex(
        """`([^`]+)`|\[([^\]]+)]\(([^)\s]+)\)|\*\*(.+?)\*\*|__(.+?)__|~~(.+?)~~|\*([^*\s][^*]*?)\*|(?<![\w])_([^_\s][^_]*?)_(?![\w])|(https?://[^\s<>)]+)""",
    )

    fun inline(line: String): List<Span> {
        val spans = mutableListOf<Span>()
        var index = 0
        for (match in INLINE.findAll(line)) {
            if (match.range.first > index) spans += Span.Text(line.substring(index, match.range.first))
            val g = match.groupValues
            spans += when {
                g[1].isNotEmpty() -> Span.Code(g[1])
                g[2].isNotEmpty() -> if (isSafeUrl(g[3])) Span.Link(g[2], g[3]) else Span.Text(g[2])
                g[4].isNotEmpty() -> Span.Text(g[4], bold = true)
                g[5].isNotEmpty() -> Span.Text(g[5], bold = true)
                g[6].isNotEmpty() -> Span.Text(g[6], strike = true)
                g[7].isNotEmpty() -> Span.Text(g[7], italic = true)
                g[8].isNotEmpty() -> Span.Text(g[8], italic = true)
                else -> Span.Link(g[9], g[9])
            }
            index = match.range.last + 1
        }
        if (index < line.length) spans += Span.Text(line.substring(index))
        return spans
    }

    fun isSafeUrl(url: String): Boolean = url.startsWith("https://") || url.startsWith("http://")

    private val HEADING = Regex("""^(#{1,6})\s+(.*)$""")
    private val BULLET = Regex("""^\s*[-*+]\s+(.*)$""")
    private val NUMBERED = Regex("""^\s*(\d+)[.)]\s+(.*)$""")

    fun render(text: String, linkColor: Color, codeBackground: Color): AnnotatedString = buildAnnotatedString {
        val code = SpanStyle(fontFamily = FontFamily.Monospace, background = codeBackground, fontSize = 0.92.em)
        val link = TextLinkStyles(SpanStyle(color = linkColor, textDecoration = TextDecoration.Underline))
        var inFence = false
        val lines = text.lines()
        lines.forEachIndexed { i, raw ->
            val last = i == lines.lastIndex
            if (raw.trimStart().startsWith("```")) {
                inFence = !inFence
                return@forEachIndexed
            }
            if (inFence) {
                withStyle(code) { append(raw) }
                if (!last) append('\n')
                return@forEachIndexed
            }
            val heading = HEADING.matchEntire(raw)
            val bullet = BULLET.matchEntire(raw)
            val numbered = NUMBERED.matchEntire(raw)
            val (prefix, content, bold) = when {
                heading != null -> Triple("", heading.groupValues[2], true)
                bullet != null -> Triple("•  ", bullet.groupValues[1], false)
                numbered != null -> Triple("${numbered.groupValues[1]}.  ", numbered.groupValues[2], false)
                raw.startsWith(">") -> Triple("▎ ", raw.removePrefix(">").trimStart(), false)
                else -> Triple("", raw, false)
            }
            append(prefix)
            for (span in inline(content)) {
                when (span) {
                    is Span.Code -> withStyle(code) { append(span.text) }
                    is Span.Link -> withLink(LinkAnnotation.Url(span.url, link)) { append(span.label) }
                    is Span.Text -> withStyle(
                        SpanStyle(
                            fontWeight = if (bold || span.bold) FontWeight.SemiBold else null,
                            fontStyle = if (span.italic) FontStyle.Italic else null,
                            textDecoration = if (span.strike) TextDecoration.LineThrough else null,
                        ),
                    ) { append(span.text) }
                }
            }
            if (!last) append('\n')
        }
    }
}
