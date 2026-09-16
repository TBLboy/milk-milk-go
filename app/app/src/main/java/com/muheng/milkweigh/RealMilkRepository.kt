package com.muheng.milkweigh

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class RealMilkRepository(
    private val context: Context,
    initialToken: String = "",
) : MilkRepository {
    private var token = initialToken
    private fun currentBaseUrl(): String = SessionStore(context).serverUrl().trimEnd('/') + "/"

    override suspend fun login(username: String, password: String): AppUser {
        val response = jsonObjectRequest(
            path = "auth/login",
            method = "POST",
            body = JSONObject().put("username", username).put("password", password),
        )
        token = response.getString("access_token")
        return refreshUser()
    }

    override suspend fun register(username: String, displayName: String, employeeNo: String, password: String): RegistrationResult {
        val body = JSONObject()
            .put("username", username)
            .put("display_name", displayName)
            .put("password", password)
        employeeNo.trim().takeIf { it.isNotEmpty() }?.let { body.put("employee_no", it) }
        val response = jsonObjectRequest(
            path = "auth/register",
            method = "POST",
            body = body,
        )
        return RegistrationResult(
            username = response.optString("username", username),
            status = response.optString("status", "pending"),
            message = response.optString("message", "注册申请已提交，等待管理员审批"),
        )
    }

    override suspend fun refreshUser(): AppUser {
        val user = jsonObjectRequest("auth/me", "GET", null).getJSONObject("user")
        return appUserFromJson(user, user.optString("username"), token)
    }

    override suspend fun uploadAvatar(uri: String): String = uploadImage(uri)

    override suspend fun uploadImage(uri: String): String = uploadFile(uri)

    override suspend fun submitBugReport(description: String, imageUris: List<String>) {
        if (description.isBlank()) error("请填写问题描述")
        if (imageUris.size > 8) error("最多上传 8 张图片")
        val fileIds = JSONArray()
        imageUris.forEach { uri ->
            fileIds.put(uploadFile(uri))
        }
        jsonObjectRequest(
            path = "bug-reports",
            method = "POST",
            body = JSONObject()
                .put("source", "app")
                .put("description", description.trim())
                .put("image_file_ids", fileIds),
        )
    }

    override suspend fun updateProfile(displayName: String, phone: String, avatarFileId: String?): AppUser {
        val body = JSONObject()
            .put("display_name", displayName)
            .put("phone", phone)
        if (avatarFileId.isNullOrBlank()) {
            body.put("avatar_file_id", JSONObject.NULL)
        } else {
            body.put("avatar_file_id", avatarFileId)
        }
        val user = jsonObjectRequest("auth/me", "PATCH", body).getJSONObject("user")
        return appUserFromJson(user, user.optString("username"), token)
    }

    override suspend fun changePassword(currentPassword: String, newPassword: String) {
        jsonObjectRequest(
            path = "auth/me/change-password",
            method = "POST",
            body = JSONObject()
                .put("current_password", currentPassword)
                .put("new_password", newPassword),
        )
    }

    override suspend fun loadFileBytes(fileId: String): ByteArray = withContext(Dispatchers.IO) {
        executeFileRequest("evidence/files/$fileId")
    }

    override suspend fun listWorkOrders(): List<WorkOrder> {
        val body = jsonArrayRequest("work-orders", "GET", null)
        return buildList {
            for (index in 0 until body.length()) {
                add(orderFromJson(body.getJSONObject(index)))
            }
        }
    }

    override suspend fun listProducts(): List<Product> {
        val body = jsonArrayRequest("master-data/products", "GET", null)
        return buildList {
            for (index in 0 until body.length()) {
                add(productFromJson(body.getJSONObject(index)))
            }
        }
    }

    override suspend fun listMaterials(): List<Material> {
        val body = jsonArrayRequest("master-data/materials", "GET", null)
        return buildList {
            for (index in 0 until body.length()) {
                add(materialFromJson(body.getJSONObject(index)))
            }
        }
    }

    override suspend fun saveMaterial(material: Material): Material {
        val imageIds = material.existingImageFileIds.toMutableList()
        material.imageNames.filter { isImageUri(it) }.forEach { uri ->
            imageIds.add(uploadFile(uri))
        }
        val payload = JSONObject()
            .put("material_code", material.materialCode.uppercase())
            .put("name_zh", material.nameZh)
            .put("name_en", material.nameEn.ifBlank { JSONObject.NULL })
            .put("shelf_life_months", material.shelfLifeMonths)
            .put("image_file_ids", JSONArray(imageIds))
        val response = if (material.materialId.isNotBlank()) {
            jsonObjectRequest("master-data/materials/${material.materialId}", "PUT", payload)
        } else {
            jsonObjectRequest("master-data/materials", "POST", payload)
        }
        return materialFromJson(response)
    }

    override suspend fun listRecipes(): List<ProductRecipe> = listProducts().map {
        ProductRecipe(it.id, it.name, it.enabled, it.items, it.imageFileId, it.version)
    }

    override suspend fun listRecipeVersions(productId: Int): List<RecipeVersion> {
        val body = jsonArrayRequest("master-data/products/$productId/recipe-versions", "GET", null)
        return buildList {
            for (index in 0 until body.length()) {
                val item = body.getJSONObject(index)
                val creator = if (item.isNull("created_by")) null else item.optJSONObject("created_by")
                val versionItems = item.optJSONArray("items") ?: JSONArray()
                add(
                    RecipeVersion(
                        version = item.optInt("version"),
                        createdAt = item.optString("created_at"),
                        createdByName = creator?.optString("display_name").orEmpty().ifBlank { "系统迁移" },
                        isCurrent = item.optBoolean("is_current"),
                        items = buildList {
                            for (itemIndex in 0 until versionItems.length()) {
                                val versionItem = versionItems.getJSONObject(itemIndex)
                                add(
                                    RecipeVersionItem(
                                        materialId = versionItem.optString("material_id"),
                                        materialCode = versionItem.optString("material_code"),
                                        nameZh = versionItem.optString("name_zh"),
                                        quantityPerTonKg = versionItem.optDouble("quantity_per_ton_kg"),
                                    ),
                                )
                            }
                        },
                    ),
                )
            }
        }
    }

    override suspend fun saveProductRecipe(recipe: ProductRecipe): ProductRecipe {
        val items = JSONArray()
        recipe.items.forEach { item ->
            items.put(
                JSONObject()
                    .put("material_id", item.materialId)
                    .put("quantity_per_ton_kg", item.quantityPerTonKg),
            )
        }
        val payload = JSONObject().put("name", recipe.name).put("items", items)
        if (recipe.imageFileId.isNullOrBlank()) {
            payload.put("image_file_id", JSONObject.NULL)
        } else {
            payload.put("image_file_id", recipe.imageFileId)
        }
        val response = if (recipe.id > 0) {
            jsonObjectRequest("master-data/products/${recipe.id}", "PUT", payload)
        } else {
            jsonObjectRequest("master-data/products", "POST", payload)
        }
        return ProductRecipe(
            id = response.optInt("id"),
            name = response.optString("name"),
            enabled = response.optBoolean("recipe_enabled", recipe.enabled),
            items = recipeItemsFromJson(response.optJSONArray("items")),
            imageFileId = response.optString("image_file_id").ifBlank { null },
            version = response.optInt("recipe_version", recipe.version),
        )
    }

    override suspend fun setProductActive(productId: Int, enabled: Boolean): ProductRecipe {
        val response = jsonObjectRequest(
            path = "master-data/products/$productId/active",
            method = "PATCH",
            body = JSONObject().put("is_active", enabled),
        )
        return ProductRecipe(
            id = response.optInt("id"),
            name = response.optString("name"),
            enabled = response.optBoolean("recipe_enabled", enabled),
            items = recipeItemsFromJson(response.optJSONArray("items")),
            imageFileId = response.optString("image_file_id").ifBlank { null },
            version = response.optInt("recipe_version", 1),
        )
    }

    override suspend fun createWorkOrder(productId: Int, targetWeightKg: Double): WorkOrder {
        val response = jsonObjectRequest(
            path = "work-orders",
            method = "POST",
            body = JSONObject().put("product_id", productId).put("target_weight_kg", targetWeightKg),
        )
        return orderFromJson(response)
    }

    override suspend fun startWorkOrder(orderNo: String): WorkOrder {
        return orderFromJson(jsonObjectRequest("work-orders/$orderNo/start", "POST", null))
    }

    override suspend fun confirmStepQr(orderNo: String, stepNo: Int, labelId: String, materialId: String, evidenceUri: String): WorkOrder {
        val fileId = uploadImage(evidenceUri)
        jsonObjectRequest(
            path = "evidence/work-orders/$orderNo/steps/$stepNo/qr",
            method = "POST",
            body = JSONObject()
                .put("label_id", labelId)
                .put("material_id", materialId)
                .put("evidence_file_id", fileId),
        )
        return getWorkOrder(orderNo)
    }

    override suspend fun requestStepPhotoApproval(orderNo: String, stepNo: Int, reason: String, evidenceUri: String): WorkOrder {
        val fileId = uploadImage(evidenceUri)
        jsonObjectRequest(
            path = "evidence/work-orders/$orderNo/steps/$stepNo/photo-request",
            method = "POST",
            body = JSONObject().put("reason", reason).put("file_id", fileId),
        )
        return getWorkOrder(orderNo)
    }

    override suspend fun approveStepPhotoApproval(orderNo: String, stepNo: Int): WorkOrder {
        val detail = jsonObjectRequest("work-orders/$orderNo", "GET", null)
        val steps = detail.optJSONArray("steps") ?: JSONArray()
        var confirmationId = 0
        for (index in 0 until steps.length()) {
            val step = steps.getJSONObject(index)
            if (step.optInt("step_no") != stepNo) continue
            val confirmations = step.optJSONArray("confirmations") ?: JSONArray()
            for (confirmIndex in 0 until confirmations.length()) {
                val confirmation = confirmations.getJSONObject(confirmIndex)
                if (confirmation.optString("status") == "pending") {
                    confirmationId = confirmation.optInt("id")
                    break
                }
            }
        }
        if (confirmationId <= 0) error("当前步骤没有待审批的拍照申请")
        jsonObjectRequest("evidence/confirmations/$confirmationId/approve", "POST", null)
        return getWorkOrder(orderNo)
    }

    override suspend fun submitStepWeight(orderNo: String, stepNo: Int, weightKg: Double, evidenceUri: String): WeightSubmitResult {
        val fileId = uploadImage(evidenceUri)
        val response = jsonObjectRequest(
            path = "evidence/work-orders/$orderNo/steps/$stepNo/weight",
            method = "POST",
            body = JSONObject().put("weight_kg", weightKg).put("scale_photo_file_id", fileId),
        )
        val passed = response.optString("status") == "passed"
        val order = getWorkOrder(orderNo)
        val message = if (passed) {
            "称重通过，步骤已完成。"
        } else {
            "称重 ${weightKg} kg，超出允差范围 ${response.optString("required_weight_kg")} ± ${response.optString("tolerance_kg")} kg，请重新称重。"
        }
        return WeightSubmitResult(passed, message, order)
    }

    override suspend fun requestTakeover(orderNo: String, reason: String): WorkOrder =
        createRequest(orderNo, "takeover", reason)

    override suspend fun requestCancel(orderNo: String, reason: String): WorkOrder =
        createRequest(orderNo, "cancel", reason)

    override suspend fun completeWorkOrder(orderNo: String): WorkOrder {
        return orderFromJson(jsonObjectRequest("work-orders/$orderNo/complete", "POST", null))
    }

    private suspend fun createRequest(orderNo: String, requestType: String, reason: String): WorkOrder {
        jsonObjectRequest(
            path = "work-orders/$orderNo/requests",
            method = "POST",
            body = JSONObject().put("request_type", requestType).put("reason", reason),
        )
        return getWorkOrder(orderNo)
    }

    private suspend fun getWorkOrder(orderNo: String): WorkOrder =
        orderFromJson(jsonObjectRequest("work-orders/$orderNo", "GET", null))

    private suspend fun jsonObjectRequest(path: String, method: String, body: JSONObject?): JSONObject =
        withContext(Dispatchers.IO) {
            val text = executeRequest(path, method, body)
            if (text.isBlank()) JSONObject() else JSONObject(text)
        }

    private suspend fun jsonArrayRequest(path: String, method: String, body: JSONObject?): JSONArray =
        withContext(Dispatchers.IO) {
            val text = executeRequest(path, method, body)
            if (text.isBlank()) JSONArray() else JSONArray(text)
        }

    private fun executeRequest(path: String, method: String, body: JSONObject?): String {
        val connection = URL(currentBaseUrl() + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 8000
            connection.readTimeout = 8000
            if (token.isNotBlank()) {
                connection.setRequestProperty("Authorization", "Bearer $token")
            }
            if (method != "GET") {
                connection.setRequestProperty("X-Request-ID", UUID.randomUUID().toString())
            }
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { output ->
                    output.write(body.toString().toByteArray(Charsets.UTF_8))
                }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) throw Exception(errorMessage(text, connection.responseMessage))
            return text
        } finally {
            connection.disconnect()
        }
    }

    private suspend fun uploadFile(uri: String): String {
        if (!isImageUri(uri)) error("请选择真实图片")
        return withContext(Dispatchers.IO) {
            val bytes = context.contentResolver.openInputStream(Uri.parse(uri))
                ?.use { it.readBytes() }
                ?: error("无法读取所选图片")
            val boundary = "MilkBoundary-${System.currentTimeMillis()}"
            val connection = URL(currentBaseUrl() + "evidence/files").openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "POST"
                connection.connectTimeout = 12000
                connection.readTimeout = 30000
                connection.doOutput = true
                if (token.isNotBlank()) {
                    connection.setRequestProperty("Authorization", "Bearer $token")
                }
                connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                val filename = "photo_${System.currentTimeMillis()}.jpg"
                val header = "--$boundary\r\n" +
                    "Content-Disposition: form-data; name=\"file\"; filename=\"$filename\"\r\n" +
                    "Content-Type: image/jpeg\r\n\r\n"
                val footer = "\r\n--$boundary--\r\n"
                connection.outputStream.use { output ->
                    output.write(header.toByteArray(Charsets.UTF_8))
                    output.write(bytes)
                    output.write(footer.toByteArray(Charsets.UTF_8))
                }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                if (code !in 200..299) throw Exception(errorMessage(text, connection.responseMessage))
                JSONObject(text).getString("file_id")
            } finally {
                connection.disconnect()
            }
        }
    }

    private fun executeFileRequest(path: String): ByteArray {
        val connection = URL(currentBaseUrl() + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = 8000
            connection.readTimeout = 12000
            if (token.isNotBlank()) {
                connection.setRequestProperty("Authorization", "Bearer $token")
            }
            val code = connection.responseCode
            if (code !in 200..299) {
                val text = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
                throw Exception(errorMessage(text, connection.responseMessage))
            }
            return connection.inputStream.use { it.readBytes() }
        } finally {
            connection.disconnect()
        }
    }

    private fun isImageUri(value: String): Boolean =
        value.startsWith("content://") || value.startsWith("file://")

    private fun errorMessage(body: String, fallback: String): String {
        return runCatching {
            val json = JSONObject(body)
            val detail = json.optJSONObject("detail")
            detail?.optString("message")?.takeIf { it.isNotBlank() }
                ?: json.optString("message").takeIf { it.isNotBlank() }
                ?: fallback
        }.getOrDefault(fallback)
    }

    private fun appUserFromJson(user: JSONObject, fallbackUsername: String, token: String): AppUser {
        val username = user.optString("username").ifBlank { fallbackUsername }
        val role = if (user.optString("role") == "admin") UserRole.ADMIN else UserRole.OPERATOR
        return AppUser(
            displayName = user.optString("display_name").ifBlank { username },
            username = username,
            role = role,
            token = token,
            avatarFileId = user.optString("avatar_file_id").ifBlank { null },
            phone = user.optString("phone"),
            employeeNo = user.optString("employee_no"),
            accountStatus = user.optString("status", "active"),
            mustChangePassword = user.optBoolean("must_change_password"),
            id = user.optInt("id"),
        )
    }

    private fun orderFromJson(json: JSONObject): WorkOrder {
        val steps = stepsFromJson(json.optJSONArray("steps"))
        val completed = steps.count { it.status == StepStatus.COMPLETED }
        val status = runCatching {
            WorkOrderStatus.valueOf(json.optString("status").uppercase())
        }.getOrDefault(WorkOrderStatus.PENDING_APPROVAL)
        val requests = json.optJSONArray("requests") ?: JSONArray()
        var pendingRequest: String? = null
        for (index in 0 until requests.length()) {
            val request = requests.getJSONObject(index)
            if (request.optString("status") == "pending") {
                pendingRequest = when (request.optString("request_type")) {
                    "takeover" -> "接管申请待审批"
                    "cancel" -> "撤销申请待审批"
                    "delete" -> "历史删除申请待审批"
                    else -> "工单申请待审批"
                }
                break
            }
        }
        return WorkOrder(
            orderNo = json.optString("order_no"),
            productName = json.optString("product_name"),
            targetWeightKg = json.optDouble("target_weight_kg"),
            completedSteps = completed,
            totalSteps = steps.size,
            operatorName = json.optString("operator_name").ifBlank { "待指派" },
            status = status,
            updatedAt = formatTime(json.optString("updated_at")),
            steps = steps,
            pendingRequest = pendingRequest,
            operatorId = if (json.isNull("operator_id")) null else json.optInt("operator_id"),
            createdBy = if (json.isNull("created_by")) null else json.optInt("created_by"),
        )
    }

    private fun stepsFromJson(array: JSONArray?): List<WorkOrderStep> {
        if (array == null) return emptyList()
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                val stepStatus = runCatching {
                    StepStatus.valueOf(item.optString("status").uppercase())
                }.getOrDefault(StepStatus.PENDING)
                add(
                    WorkOrderStep(
                        stepNo = item.optInt("step_no"),
                        materialId = item.optString("material_id"),
                        materialCode = item.optString("material_code"),
                        materialName = item.optString("material_name"),
                        requiredWeightKg = item.optDouble("required_weight_kg"),
                        toleranceKg = item.optDouble("tolerance_kg"),
                        status = stepStatus,
                    ),
                )
            }
        }
    }

    private fun productFromJson(json: JSONObject): Product {
        return Product(
            id = json.optInt("id"),
            name = json.optString("name"),
            materialCount = json.optJSONArray("items")?.length() ?: 0,
            items = recipeItemsFromJson(json.optJSONArray("items")),
            enabled = json.optBoolean("recipe_enabled", true),
            imageFileId = json.optString("image_file_id").ifBlank { null },
            version = json.optInt("recipe_version", 1),
        )
    }

    private fun recipeItemsFromJson(array: JSONArray?): List<RecipeItem> {
        if (array == null) return emptyList()
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                add(
                    RecipeItem(
                        materialId = item.optString("material_id"),
                        quantityPerTonKg = item.optDouble("quantity_per_ton_kg"),
                    ),
                )
            }
        }
    }

    private fun materialFromJson(json: JSONObject): Material {
        val images = json.optJSONArray("images") ?: JSONArray()
        val fileIds = buildList {
            for (index in 0 until images.length()) {
                val fileId = images.getJSONObject(index).optString("file_id")
                if (fileId.isNotBlank()) add(fileId)
            }
        }
        return Material(
            materialId = json.optString("material_id"),
            materialCode = json.optString("material_code"),
            nameZh = json.optString("name_zh"),
            nameEn = json.optString("name_en").takeUnless { it.isBlank() || it == "null" }.orEmpty(),
            shelfLifeMonths = json.optInt("shelf_life_months", 24),
            imageNames = fileIds.mapIndexed { index, _ -> "包装图片 ${index + 1}" },
            existingImageFileIds = fileIds,
        )
    }

    private fun formatTime(value: String): String {
        if (value.isBlank()) return "刚刚"
        return value.replace("T", " ").take(16)
    }
}
