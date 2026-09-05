plugins {
    id("com.android.application")
}

android {
    namespace = "com.m10r.diagnostic"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.m10r.diagnostic"
        minSdk = 26
        targetSdk = 36
        versionCode = 5
        versionName = "0.5.0-leica-linear-reference"

        testInstrumentationRunner = "android.test.InstrumentationTestRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
