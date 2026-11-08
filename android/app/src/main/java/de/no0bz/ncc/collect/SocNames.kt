package de.no0bz.ncc.collect

/** Übersetzt Build.SOC_MODEL-Codes in Marketingnamen. */
object SocNames {
    private val KNOWN = mapOf(
        // Google Tensor
        "GS101" to "Google Tensor",
        "GS201" to "Google Tensor G2",
        "ZUMA" to "Google Tensor G3",
        "ZUMAPRO" to "Google Tensor G4",
        "LAGUNA" to "Google Tensor G5",
        // Qualcomm Snapdragon
        "SM8350" to "Snapdragon 888",
        "SM8450" to "Snapdragon 8 Gen 1",
        "SM8475" to "Snapdragon 8+ Gen 1",
        "SM8550" to "Snapdragon 8 Gen 2",
        "SM8650" to "Snapdragon 8 Gen 3",
        "SM8750" to "Snapdragon 8 Elite",
        "SM8850" to "Snapdragon 8 Elite Gen 5",
        "SM7550" to "Snapdragon 7 Gen 3",
        // Samsung Exynos
        "S5E9925" to "Exynos 2200",
        "S5E9945" to "Exynos 2400",
        "S5E9955" to "Exynos 2500",
    )

    fun displayName(manufacturer: String?, model: String?, hardware: String?): String {
        val code = model?.trim()?.takeUnless { it.isEmpty() || it.equals("unknown", ignoreCase = true) }
        val emulator = listOfNotNull(code, hardware).firstOrNull { it.lowercase() in EMULATOR_HARDWARE }
        if (emulator != null) return "Emulator ($emulator)"
        if (code != null) {
            KNOWN[code.uppercase()]?.let { return it }
            val maker = manufacturer?.trim()?.takeUnless { it.isEmpty() || it.equals("unknown", ignoreCase = true) }
            return listOfNotNull(maker, code).joinToString(" ")
        }
        return hardware?.takeUnless { it.isBlank() } ?: "Unbekannt"
    }

    val EMULATOR_HARDWARE = setOf("ranchu", "goldfish", "cutf_cvm", "vsoc_x86_64")
}
