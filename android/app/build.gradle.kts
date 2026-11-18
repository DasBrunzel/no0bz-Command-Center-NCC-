plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "de.no0bz.ncc"
    compileSdk = 37

    defaultConfig {
        applicationId = "de.no0bz.ncc"
        minSdk = 34
        targetSdk = 37
        versionCode = 7
        versionName = "0.6.1"
    }

    // Release-Signatur nur aus Umgebungsvariablen (siehe scripts/build-release.ps1) –
    // Schlüssel und Passwort liegen nie im Repository.
    val releaseKeystore = providers.environmentVariable("NCC_RELEASE_KEYSTORE").orNull
    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = providers.environmentVariable("NCC_RELEASE_STORE_PASSWORD").orNull
                keyAlias = providers.environmentVariable("NCC_RELEASE_KEY_ALIAS").orNull ?: "ncc"
                keyPassword = providers.environmentVariable("NCC_RELEASE_KEY_PASSWORD").orNull ?: storePassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            signingConfig = signingConfigs.findByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.datastore.preferences)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
}
