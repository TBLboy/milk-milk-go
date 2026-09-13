package com.muheng.milkweigh

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.security.KeyStore

@RunWith(AndroidJUnit4::class)
class SessionStoreTest {
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        clearStorage()
    }

    @After
    fun tearDown() {
        clearStorage()
    }

    @Test
    fun sessionAndRememberedLoginAreEncryptedAtRest() {
        val store = SessionStore(context)
        store.save(testUser(token = "secret-token"))
        store.saveRememberedLogin("operator01", "secret-password", rememberPassword = true)

        val sessionPrefs = context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
        val settingsPrefs = context.getSharedPreferences("milk_settings", Context.MODE_PRIVATE)
        val encryptedSession = sessionPrefs.getString("user_encrypted", null)
        val encryptedLogins = settingsPrefs.getString("remembered_logins_encrypted", null)

        assertNull(sessionPrefs.getString("user", null))
        assertNull(settingsPrefs.getString("remembered_logins", null))
        assertFalse(encryptedSession.orEmpty().contains("secret-token"))
        assertFalse(encryptedLogins.orEmpty().contains("secret-password"))
        assertFalse(encryptedLogins.orEmpty().contains("operator01"))
        assertEquals("secret-token", SessionStore(context).load()?.token)
        assertEquals(
            "secret-password",
            SessionStore(context).rememberedLogins().single().password,
        )
    }

    @Test
    fun legacyPlaintextIsMigratedAndRemoved() {
        val legacyUser = JSONObject()
            .put("display_name", "Legacy Operator")
            .put("username", "operator01")
            .put("role", UserRole.OPERATOR.name)
            .put("token", "legacy-token")
            .put("id", 7)
            .put("id_card", "legacy-id-card")
            .toString()
        val legacyLogins = JSONArray()
            .put(
                JSONObject()
                    .put("username", "operator01")
                    .put("password", "legacy-password"),
            )
            .toString()
        context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
            .edit()
            .putString("user", legacyUser)
            .commit()
        context.getSharedPreferences("milk_settings", Context.MODE_PRIVATE)
            .edit()
            .putString("remembered_logins", legacyLogins)
            .commit()

        val store = SessionStore(context)
        val sessionPrefs = context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
        val settingsPrefs = context.getSharedPreferences("milk_settings", Context.MODE_PRIVATE)

        assertNull(sessionPrefs.getString("user", null))
        assertNull(settingsPrefs.getString("remembered_logins", null))
        assertFalse(sessionPrefs.getString("user_encrypted", null).orEmpty().contains("legacy-token"))
        assertFalse(sessionPrefs.getString("user_encrypted", null).orEmpty().contains("legacy-id-card"))
        assertFalse(settingsPrefs.getString("remembered_logins_encrypted", null).orEmpty().contains("legacy-password"))
        assertEquals("legacy-token", store.load()?.token)
        assertEquals("legacy-password", store.rememberedLogins().single().password)
    }

    @Test
    fun clearRemovesPersistentSession() {
        val store = SessionStore(context)
        store.save(testUser(token = "session-token"))

        store.clear()

        assertNull(SessionStore(context).load())
        assertNull(
            context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
                .getString("user_encrypted", null),
        )
    }

    @Test
    fun missingKeystoreKeyClearsUndecryptableSession() {
        val store = SessionStore(context)
        store.save(testUser(token = "session-token"))
        KeyStore.getInstance("AndroidKeyStore")
            .apply { load(null) }
            .deleteEntry("milk_weigh_credentials_v1")

        assertNull(SessionStore(context).load())
        assertNull(
            context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
                .getString("user_encrypted", null),
        )
    }

    private fun testUser(token: String) = AppUser(
        displayName = "Test Operator",
        username = "operator01",
        role = UserRole.OPERATOR,
        token = token,
        employeeNo = "MH1001",
        id = 7,
    )

    private fun clearStorage() {
        context.deleteSharedPreferences("milk_session")
        context.deleteSharedPreferences("milk_settings")
    }
}
