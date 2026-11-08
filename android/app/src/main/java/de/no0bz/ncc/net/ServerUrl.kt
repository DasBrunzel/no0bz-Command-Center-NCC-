package de.no0bz.ncc.net

import java.net.URI

/**
 * Prüft die Server-Adresse. HTTP ist nur erlaubt, wo der Transport selbst schon verschlüsselt
 * oder lokal ist: Tailscale (100.64.0.0/10, *.ts.net) und lokale Testadressen.
 */
object ServerUrl {
    /** Nur als Beispiel in Hinweisen – die echte Adresse trägt jeder selbst ein. */
    const val EXAMPLE = "http://100.x.y.z:8350"

    sealed interface Result {
        data class Valid(val baseUrl: String) : Result
        data class Invalid(val reason: String) : Result
    }

    fun validate(input: String): Result {
        val trimmed = input.trim().trimEnd('/')
        val uri = runCatching { URI(trimmed) }.getOrNull()
            ?: return Result.Invalid("Keine gültige Adresse.")
        val scheme = uri.scheme?.lowercase()
        val host = uri.host?.lowercase()
        if (scheme !in setOf("http", "https") || host.isNullOrEmpty()) {
            return Result.Invalid("Adresse muss mit http:// oder https:// beginnen.")
        }
        if (!uri.path.isNullOrEmpty() || uri.query != null || uri.fragment != null) {
            return Result.Invalid("Nur die Basisadresse angeben, z. B. $EXAMPLE")
        }
        if (scheme == "http" && !isTrustedPlainHost(host)) {
            return Result.Invalid("HTTP nur über Tailscale (100.x.x.x oder *.ts.net). Sonst bitte https:// nutzen.")
        }
        return Result.Valid(trimmed)
    }

    fun isTrustedPlainHost(host: String): Boolean {
        if (host == "localhost" || host == "127.0.0.1" || host == "10.0.2.2") return true
        if (host.endsWith(".ts.net")) return true
        val parts = host.split('.').map { it.toIntOrNull() ?: return false }
        if (parts.size != 4 || parts.any { it !in 0..255 }) return false
        // Tailscale-CGNAT-Bereich 100.64.0.0/10 = 100.64.x.x bis 100.127.x.x
        return parts[0] == 100 && parts[1] in 64..127
    }
}
