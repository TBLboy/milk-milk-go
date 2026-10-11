package com.muheng.milkweigh

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

enum class UserRole { OPERATOR, ADMIN }

data class AppUser(
    val displayName: String,
    val username: String,
    val role: UserRole,
    val token: String = "",
    val avatarFileId: String? = null,
    val phone: String = "",
    val employeeNo: String = "",
    val accountStatus: String = "active",
    val mustChangePassword: Boolean = false,
    val id: Int = 0,
)

data class RegistrationResult(
    val username: String,
    val status: String,
    val message: String,
)

enum class WorkOrderStatus(val label: String) {
    PENDING_APPROVAL("待审批"),
    APPROVED("已批准"),
    IN_PROGRESS("执行中"),
    COMPLETED("已完成"),
    CANCELLED("已撤销"),
    DELETED("已删除"),
}

data class WorkOrder(
    val orderNo: String,
    val productName: String,
    val targetWeightKg: Double,
    val completedSteps: Int,
    val totalSteps: Int,
    val operatorName: String,
    val status: WorkOrderStatus,
    val updatedAt: String,
    val steps: List<WorkOrderStep> = emptyList(),
    val pendingRequest: String? = null,
    val operatorId: Int? = null,
    val createdBy: Int? = null,
)

enum class StepStatus(val label: String) {
    PENDING("待确认"),
    TYPE_CONFIRMATION("待审批"),
    WEIGHING("待称重"),
    COMPLETED("已完成"),
}

data class WorkOrderStep(
    val stepNo: Int,
    val materialId: String,
    val materialCode: String,
    val materialName: String,
    val requiredWeightKg: Double,
    val toleranceKg: Double,
    val status: StepStatus,
)

data class WeightSubmitResult(
    val passed: Boolean,
    val message: String,
    val order: WorkOrder,
)

data class RecipeItem(
    val materialId: String,
    val quantityPerTonKg: Double,
)

data class Product(
    val id: Int,
    val name: String,
    val materialCount: Int = 0,
    val items: List<RecipeItem> = emptyList(),
    val enabled: Boolean = true,
    val imageFileId: String? = null,
    val version: Int = 1,
)

data class Material(
    val materialId: String,
    val materialCode: String,
    val nameZh: String,
    val nameEn: String = "",
    val shelfLifeMonths: Int = 24,
    val imageNames: List<String> = emptyList(),
    val existingImageFileIds: List<String> = emptyList(),
)

data class ProductRecipe(
    val id: Int,
    val name: String,
    val enabled: Boolean = true,
    val items: List<RecipeItem> = emptyList(),
    val imageFileId: String? = null,
    val version: Int = 1,
)

data class RecipeVersionItem(
    val materialId: String,
    val materialCode: String,
    val nameZh: String,
    val quantityPerTonKg: Double,
)

data class RecipeVersion(
    val version: Int,
    val createdAt: String,
    val createdByName: String,
    val isCurrent: Boolean,
    val items: List<RecipeVersionItem>,
)

data class LicenseStatus(
    val mode: String = "active",
    val source: String = "trial",
    val licensee: String? = null,
    val expiresAt: String? = null,
    val deadline: String? = null,
    val daysRemaining: Int = 0,
    val graceDaysRemaining: Int = 0,
    val warn: Boolean = false,
    val warnDays: Int = 30,
    val graceDays: Int = 15,
    val trialMonths: Int = 2,
    val clockRollbackDetected: Boolean = false,
) {
    val isLocked: Boolean get() = mode == "locked"
    val isReadOnly: Boolean get() = mode == "read_only"
    val writesEnabled: Boolean get() = mode == "active"
}

interface MilkRepository {
    suspend fun login(username: String, password: String): AppUser
    suspend fun register(username: String, displayName: String, employeeNo: String, password: String): RegistrationResult
    suspend fun refreshUser(): AppUser
    suspend fun uploadAvatar(uri: String): String
    suspend fun uploadImage(uri: String): String
    suspend fun validateStepQr(orderNo: String, stepNo: Int, labelId: String, materialId: String)
    suspend fun submitBugReport(description: String, imageUris: List<String>)
    suspend fun updateProfile(displayName: String, phone: String, avatarFileId: String?): AppUser
    suspend fun changePassword(currentPassword: String, newPassword: String)
    suspend fun loadFileBytes(fileId: String): ByteArray
    suspend fun getLicenseStatus(): LicenseStatus
    suspend fun listWorkOrders(): List<WorkOrder>
    suspend fun listProducts(): List<Product>
    suspend fun listMaterials(): List<Material>
    suspend fun saveMaterial(material: Material): Material
    suspend fun listRecipes(): List<ProductRecipe>
    suspend fun listRecipeVersions(productId: Int): List<RecipeVersion>
    suspend fun saveProductRecipe(recipe: ProductRecipe): ProductRecipe
    suspend fun setProductActive(productId: Int, enabled: Boolean): ProductRecipe
    suspend fun createWorkOrder(productId: Int, targetWeightKg: Double): WorkOrder
    suspend fun startWorkOrder(orderNo: String): WorkOrder
    suspend fun confirmStepQr(orderNo: String, stepNo: Int, labelId: String, materialId: String, evidenceUri: String): WorkOrder
    suspend fun requestStepPhotoApproval(orderNo: String, stepNo: Int, reason: String, evidenceUri: String): WorkOrder
    suspend fun approveStepPhotoApproval(orderNo: String, stepNo: Int): WorkOrder
    suspend fun submitStepWeight(orderNo: String, stepNo: Int, weightKg: Double, evidenceUris: List<String>): WeightSubmitResult
    suspend fun requestTakeover(orderNo: String, reason: String): WorkOrder
    suspend fun requestCancel(orderNo: String, reason: String): WorkOrder
    suspend fun completeWorkOrder(orderNo: String): WorkOrder
}

class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
    private val settings = context.getSharedPreferences("milk_settings", Context.MODE_PRIVATE)

    init {
        migrateLegacyPlaintext()
    }

    fun serverUrl(): String {
        return settings.getString(SERVER_URL_KEY, null)
            ?: prefs.getString(SERVER_URL_KEY, BuildConfig.BASE_URL)
            ?: BuildConfig.BASE_URL
    }

    fun saveServerUrl(url: String) {
        val normalized = url.trim().ifBlank { BuildConfig.BASE_URL }
        settings.edit().putString(SERVER_URL_KEY, normalized).apply()
        prefs.edit().remove(SERVER_URL_KEY).apply()
    }

    fun save(user: AppUser) {
        prefs.edit()
            .putString(USER_KEY, encryptValue(appUserToJson(user).toString()))
            .remove(LEGACY_USER_KEY)
            .apply()
    }

    fun rememberedLogins(): List<RememberedLogin> {
        val encrypted = settings.getString(REMEMBERED_LOGINS_KEY, null) ?: return emptyList()
        return runCatching {
            val raw = decryptValue(encrypted)
            val array = JSONArray(raw)
            (0 until array.length()).mapNotNull { index ->
                val item = array.optJSONObject(index) ?: return@mapNotNull null
                val username = item.optString("username").trim()
                if (username.isEmpty()) {
                    null
                } else {
                    RememberedLogin(
                        username = username,
                        password = item.optString("password").ifBlank { null },
                    )
                }
            }
        }.getOrElse {
            settings.edit().remove(REMEMBERED_LOGINS_KEY).apply()
            emptyList()
        }
    }

    fun saveRememberedLogin(username: String, password: String, rememberPassword: Boolean) {
        val normalized = username.trim()
        if (normalized.isEmpty()) return
        val next = rememberedLogins().filterNot { it.username == normalized }.toMutableList()
        if (rememberPassword) {
            next.add(0, RememberedLogin(normalized, password))
        } else {
            next.add(0, RememberedLogin(normalized, null))
        }
        val array = JSONArray()
        next.take(MAX_REMEMBERED_LOGINS).forEach { item ->
            array.put(
                JSONObject()
                    .put("username", item.username)
                    .put("password", item.password ?: JSONObject.NULL)
            )
        }
        settings.edit()
            .putString(REMEMBERED_LOGINS_KEY, encryptValue(array.toString()))
            .remove(LEGACY_REMEMBERED_LOGINS_KEY)
            .apply()
    }

    fun removeRememberedLogin(username: String) {
        val normalized = username.trim()
        if (normalized.isEmpty()) return
        val next = rememberedLogins().filterNot { it.username == normalized }
        if (next.isEmpty()) {
            settings.edit()
                .remove(REMEMBERED_LOGINS_KEY)
                .remove(LEGACY_REMEMBERED_LOGINS_KEY)
                .apply()
        } else {
            val array = JSONArray()
            next.forEach { item ->
                array.put(
                    JSONObject()
                        .put("username", item.username)
                        .put("password", item.password ?: JSONObject.NULL)
                )
            }
            settings.edit()
                .putString(REMEMBERED_LOGINS_KEY, encryptValue(array.toString()))
                .remove(LEGACY_REMEMBERED_LOGINS_KEY)
                .apply()
        }
    }

    fun clearRememberedLogins() {
        settings.edit()
            .remove(REMEMBERED_LOGINS_KEY)
            .remove(LEGACY_REMEMBERED_LOGINS_KEY)
            .apply()
    }

    fun load(): AppUser? {
        val encrypted = prefs.getString(USER_KEY, null) ?: return null
        return runCatching {
            val json = JSONObject(decryptValue(encrypted))
            val user = appUserFromJson(json)
            if (json.has("id_card")) {
                prefs.edit()
                    .putString(USER_KEY, encryptValue(appUserToJson(user).toString()))
                    .apply()
            }
            user
        }.getOrElse {
            prefs.edit().remove(USER_KEY).apply()
            null
        }
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun migrateLegacyPlaintext() {
        prefs.getString(LEGACY_USER_KEY, null)?.let { raw ->
            runCatching {
                val user = appUserFromJson(JSONObject(raw))
                prefs.edit()
                    .putString(USER_KEY, encryptValue(appUserToJson(user).toString()))
                    .remove(LEGACY_USER_KEY)
                    .apply()
            }.onFailure {
                prefs.edit().remove(LEGACY_USER_KEY).apply()
            }
        }
        settings.getString(LEGACY_REMEMBERED_LOGINS_KEY, null)?.let { raw ->
            runCatching {
                settings.edit()
                    .putString(REMEMBERED_LOGINS_KEY, encryptValue(raw))
                    .remove(LEGACY_REMEMBERED_LOGINS_KEY)
                    .apply()
            }.onFailure {
                settings.edit().remove(LEGACY_REMEMBERED_LOGINS_KEY).apply()
            }
        }
    }

    private fun appUserToJson(user: AppUser): JSONObject {
        return JSONObject()
            .put("display_name", user.displayName)
            .put("username", user.username)
            .put("role", user.role.name)
            .put("token", user.token)
            .put("avatar_file_id", user.avatarFileId ?: JSONObject.NULL)
            .put("phone", user.phone)
            .put("employee_no", user.employeeNo)
            .put("account_status", user.accountStatus)
            .put("must_change_password", user.mustChangePassword)
            .put("id", user.id)
    }

    private fun appUserFromJson(json: JSONObject): AppUser {
        json.remove("id_card")
        return AppUser(
            displayName = json.getString("display_name"),
            username = json.getString("username"),
            role = UserRole.valueOf(json.getString("role")),
            token = json.optString("token"),
            avatarFileId = if (json.isNull("avatar_file_id")) null else json.optString("avatar_file_id").ifBlank { null },
            phone = json.optString("phone"),
            employeeNo = json.optString("employee_no"),
            accountStatus = json.optString("account_status", "active"),
            mustChangePassword = json.optBoolean("must_change_password"),
            id = json.optInt("id"),
        )
    }

    private fun encryptValue(plainText: String): String {
        val cipher = Cipher.getInstance(CIPHER_TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())
        val iv = cipher.iv
        require(iv.size in 1..255)
        val ciphertext = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))
        val payload = ByteArray(1 + iv.size + ciphertext.size)
        payload[0] = iv.size.toByte()
        iv.copyInto(payload, destinationOffset = 1)
        ciphertext.copyInto(payload, destinationOffset = 1 + iv.size)
        return "$CIPHER_VERSION:${Base64.encodeToString(payload, Base64.NO_WRAP)}"
    }

    private fun decryptValue(encryptedText: String): String {
        require(encryptedText.startsWith("$CIPHER_VERSION:"))
        val payload = Base64.decode(encryptedText.substringAfter(':'), Base64.NO_WRAP)
        require(payload.isNotEmpty())
        val ivSize = payload[0].toInt() and 0xFF
        require(ivSize in 1..255 && payload.size > 1 + ivSize)
        val iv = payload.copyOfRange(1, 1 + ivSize)
        val ciphertext = payload.copyOfRange(1 + ivSize, payload.size)
        val cipher = Cipher.getInstance(CIPHER_TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, getExistingSecretKey(), GCMParameterSpec(128, iv))
        return String(cipher.doFinal(ciphertext), Charsets.UTF_8)
    }

    private fun getOrCreateSecretKey(): SecretKey {
        getExistingSecretKeyOrNull()?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }

    private fun getExistingSecretKey(): SecretKey {
        return getExistingSecretKeyOrNull() ?: error("Android Keystore key is unavailable")
    }

    private fun getExistingSecretKeyOrNull(): SecretKey? {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        return keyStore.getKey(KEY_ALIAS, null) as? SecretKey
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "milk_weigh_credentials_v1"
        const val CIPHER_TRANSFORMATION = "AES/GCM/NoPadding"
        const val CIPHER_VERSION = "v1"
        const val USER_KEY = "user_encrypted"
        const val LEGACY_USER_KEY = "user"
        const val SERVER_URL_KEY = "server_url"
        const val REMEMBERED_LOGINS_KEY = "remembered_logins_encrypted"
        const val LEGACY_REMEMBERED_LOGINS_KEY = "remembered_logins"
        const val MAX_REMEMBERED_LOGINS = 5
    }
}

data class RememberedLogin(
    val username: String,
    val password: String? = null,
)

