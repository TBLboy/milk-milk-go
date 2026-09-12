pluginManagement {
    resolutionStrategy {
        eachPlugin {
            when (requested.id.id) {
                "com.android.application" -> useModule("com.android.tools.build:gradle:8.7.3")
                "org.jetbrains.kotlin.android" -> useModule("org.jetbrains.kotlin:kotlin-gradle-plugin:2.0.21")
                "org.jetbrains.kotlin.plugin.compose" -> useModule("org.jetbrains.kotlin:compose-compiler-gradle-plugin:2.0.21")
            }
        }
    }
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "MilkWeighApp"
include(":app")
