package com.muheng.milkweigh

import android.content.Context
import org.json.JSONObject

enum class UserRole { OPERATOR, ADMIN }

data class AppUser(
    val displayName: String,
    val username: String,
    val role: UserRole,
    val token: String = "",
    val avatarFileId: String? = null,
    val phone: String = "",
    val idCard: String = "",
    val accountStatus: String = "active",
    val mustChangePassword: Boolean = false,
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
)

interface MilkRepository {
    suspend fun login(username: String, password: String): AppUser
    suspend fun register(username: String, displayName: String, password: String): RegistrationResult
    suspend fun refreshUser(): AppUser
    suspend fun uploadAvatar(uri: String): String
    suspend fun updateProfile(displayName: String, phone: String, avatarFileId: String?): AppUser
    suspend fun changePassword(currentPassword: String, newPassword: String)
    suspend fun loadFileBytes(fileId: String): ByteArray
    suspend fun listWorkOrders(): List<WorkOrder>
    suspend fun listProducts(): List<Product>
    suspend fun listMaterials(): List<Material>
    suspend fun saveMaterial(material: Material): Material
    suspend fun listRecipes(): List<ProductRecipe>
    suspend fun saveProductRecipe(recipe: ProductRecipe): ProductRecipe
    suspend fun setProductActive(productId: Int, enabled: Boolean): ProductRecipe
    suspend fun createWorkOrder(productId: Int, targetWeightKg: Double): WorkOrder
    suspend fun startWorkOrder(orderNo: String): WorkOrder
    suspend fun confirmStepQr(orderNo: String, stepNo: Int, materialId: String): WorkOrder
    suspend fun requestStepPhotoApproval(orderNo: String, stepNo: Int, reason: String, photoName: String): WorkOrder
    suspend fun approveStepPhotoApproval(orderNo: String, stepNo: Int): WorkOrder
    suspend fun submitStepWeight(orderNo: String, stepNo: Int, weightKg: Double, photoName: String): WeightSubmitResult
    suspend fun requestTakeover(orderNo: String, reason: String): WorkOrder
    suspend fun requestCancel(orderNo: String, reason: String): WorkOrder
    suspend fun requestDelete(orderNo: String, reason: String): WorkOrder
    suspend fun completeWorkOrder(orderNo: String): WorkOrder
}

class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("milk_session", Context.MODE_PRIVATE)
    private val settings = context.getSharedPreferences("milk_settings", Context.MODE_PRIVATE)

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
        val json = JSONObject()
            .put("display_name", user.displayName)
            .put("username", user.username)
            .put("role", user.role.name)
            .put("token", user.token)
            .put("avatar_file_id", user.avatarFileId ?: JSONObject.NULL)
            .put("phone", user.phone)
            .put("id_card", user.idCard)
            .put("account_status", user.accountStatus)
            .put("must_change_password", user.mustChangePassword)
        prefs.edit().putString("user", json.toString()).apply()
    }

    fun load(): AppUser? {
        val raw = prefs.getString("user", null) ?: return null
        return runCatching {
            val json = JSONObject(raw)
            AppUser(
                displayName = json.getString("display_name"),
                username = json.getString("username"),
                role = UserRole.valueOf(json.getString("role")),
                token = json.optString("token"),
                avatarFileId = if (json.isNull("avatar_file_id")) null else json.optString("avatar_file_id").ifBlank { null },
                phone = json.optString("phone"),
                idCard = json.optString("id_card"),
                accountStatus = json.optString("account_status", "active"),
                mustChangePassword = json.optBoolean("must_change_password"),
            )
        }.getOrNull()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }

    private companion object {
        const val SERVER_URL_KEY = "server_url"
    }
}

class MockMilkRepository : MilkRepository {
    private var mockUser: AppUser? = null
    private val orderStore = mutableListOf(
        WorkOrder(
            orderNo = "WO-20260911-018",
            productName = "高钙纯牛奶 1L",
            targetWeightKg = 2000.0,
            completedSteps = 7,
            totalSteps = 9,
            operatorName = "李师傅",
            status = WorkOrderStatus.IN_PROGRESS,
            updatedAt = "10:42",
            steps = (1..9).map { step ->
                WorkOrderStep(
                    stepNo = step,
                    materialId = "MAT-10${step}",
                    materialCode = "MAT-10${step}",
                    materialName = if (step == 1) "维生素 D3" else "牛奶辅料 $step",
                    requiredWeightKg = (step * 0.6),
                    toleranceKg = 0.05,
                    status = if (step <= 7) StepStatus.COMPLETED else StepStatus.PENDING,
                )
            },
        ),
        WorkOrder(
            orderNo = "WO-20260911-017",
            productName = "草莓风味酸奶",
            targetWeightKg = 1000.0,
            completedSteps = 8,
            totalSteps = 8,
            operatorName = "王师傅",
            status = WorkOrderStatus.COMPLETED,
            updatedAt = "10:18",
            steps = (1..8).map { step ->
                WorkOrderStep(
                    stepNo = step,
                    materialId = "MAT-20${step}",
                    materialCode = "MAT-20${step}",
                    materialName = if (step == 2) "蔗糖" else "酸奶辅料 $step",
                    requiredWeightKg = (step * 0.5),
                    toleranceKg = 0.05,
                    status = StepStatus.COMPLETED,
                )
            },
        ),
        WorkOrder(
            orderNo = "WO-20260911-016",
            productName = "原味发酵乳",
            targetWeightKg = 1500.0,
            completedSteps = 0,
            totalSteps = 10,
            operatorName = "赵师傅",
            status = WorkOrderStatus.PENDING_APPROVAL,
            updatedAt = "09:56",
            steps = (1..10).map { step ->
                WorkOrderStep(
                    stepNo = step,
                    materialId = "MAT-30${step}",
                    materialCode = "MAT-30${step}",
                    materialName = if (step == 3) "稳定剂" else "发酵乳辅料 $step",
                    requiredWeightKg = (step * 0.4),
                    toleranceKg = 0.05,
                    status = StepStatus.PENDING,
                )
            },
        ),
    )

    private val materials = mutableListOf(
        Material("MAT-0001", "A1", "维生素 D3", "Vitamin D3", 36, listOf("A1 包装正面", "A1 包装侧面")),
        Material("MAT-0002", "F-02", "西番莲香精", "Passion Fruit Flavor", 24, listOf("F-02 包装")),
        Material("MAT-0003", "E2", "精制白砂糖", "White Sugar", 24, listOf("E2 蛇皮袋")),
    )

    private val products = mutableListOf(
        Product(
            id = 1,
            name = "高钙纯牛奶 1L",
            materialCount = 3,
            items = listOf(
                RecipeItem("MAT-0001", 4.0),
                RecipeItem("MAT-0002", 1.5),
                RecipeItem("MAT-0003", 80.0),
            ),
        ),
        Product(
            id = 2,
            name = "草莓风味酸奶",
            materialCount = 2,
            items = listOf(
                RecipeItem("MAT-0003", 60.0),
                RecipeItem("MAT-0002", 2.2),
            ),
        ),
        Product(
            id = 3,
            name = "原味发酵乳",
            materialCount = 2,
            items = listOf(
                RecipeItem("MAT-0001", 3.0),
                RecipeItem("MAT-0003", 50.0),
            ),
        ),
    )

    override suspend fun login(username: String, password: String): AppUser {
        if (username.isBlank() || password.isBlank()) error("请输入账号和密码")
        val role = if (username == "admin") UserRole.ADMIN else UserRole.OPERATOR
        return AppUser(
            displayName = if (username == "admin") "系统管理员" else "现场操作员",
            username = username,
            role = role,
            token = "mock-${username}-${System.currentTimeMillis()}",
        ).also { mockUser = it }
    }

    override suspend fun register(username: String, displayName: String, password: String): RegistrationResult {
        if (username.length < 3 || displayName.isBlank() || password.length < 8) error("请检查注册信息")
        return RegistrationResult(username, "pending", "注册申请已提交，等待管理员审批")
    }

    override suspend fun refreshUser(): AppUser {
        return mockUser ?: AppUser("现场操作员", "operator", UserRole.OPERATOR, "mock-${System.currentTimeMillis()}")
    }

    override suspend fun uploadAvatar(uri: String): String = uri

    override suspend fun updateProfile(displayName: String, phone: String, avatarFileId: String?): AppUser {
        val current = mockUser ?: AppUser(displayName, "operator", UserRole.OPERATOR, "mock-${System.currentTimeMillis()}")
        return current.copy(displayName = displayName, phone = phone, avatarFileId = avatarFileId).also { mockUser = it }
    }

    override suspend fun changePassword(currentPassword: String, newPassword: String) {
        if (newPassword.length < 8) error("新密码至少 8 位")
    }

    override suspend fun loadFileBytes(fileId: String): ByteArray = ByteArray(0)

    override suspend fun listWorkOrders(): List<WorkOrder> = orderStore.toList()

    override suspend fun listProducts(): List<Product> = products

    override suspend fun listMaterials(): List<Material> = materials.toList()

    override suspend fun saveMaterial(material: Material): Material {
        if (material.materialCode.isBlank() || material.nameZh.isBlank() || material.shelfLifeMonths <= 0) {
            error("请完整填写辅料信息")
        }
        val existing = materials.firstOrNull { it.materialId == material.materialId }
        val saved = if (existing != null) {
            existing.copy(
                materialCode = material.materialCode.uppercase(),
                nameZh = material.nameZh.trim(),
                nameEn = material.nameEn.trim(),
                shelfLifeMonths = material.shelfLifeMonths,
                imageNames = material.imageNames,
            )
        } else {
            Material(
                materialId = "MAT-${(materials.size + 1).toString().padStart(4, '0')}",
                materialCode = material.materialCode.uppercase(),
                nameZh = material.nameZh.trim(),
                nameEn = material.nameEn.trim(),
                shelfLifeMonths = material.shelfLifeMonths,
                imageNames = material.imageNames,
            )
        }
        if (existing != null) {
            val index = materials.indexOfFirst { it.materialId == existing.materialId }
            materials[index] = saved
        } else {
            materials.add(saved)
        }
        return saved
    }

    override suspend fun listRecipes(): List<ProductRecipe> = products.map {
        ProductRecipe(it.id, it.name, it.enabled, it.items)
    }

    override suspend fun saveProductRecipe(recipe: ProductRecipe): ProductRecipe {
        if (recipe.name.isBlank() || recipe.items.isEmpty()) error("请填写产品名称并至少添加一种辅料")
        if (recipe.items.map { it.materialId }.distinct().size != recipe.items.size) error("配方中不能重复添加同一辅料")
        recipe.items.forEach { item ->
            if (item.quantityPerTonKg <= 0 || materials.none { it.materialId == item.materialId }) {
                error("辅料不存在或用量必须大于 0")
            }
        }
        val id = if (recipe.id > 0) recipe.id else (products.maxOfOrNull { it.id } ?: 0) + 1
        val saved = recipe.copy(id = id)
        val existing = products.indexOfFirst { it.id == id }
        val product = Product(id, saved.name.trim(), saved.items.size, saved.items, saved.enabled)
        if (existing >= 0) products[existing] = product else products.add(product)
        return saved
    }

    override suspend fun setProductActive(productId: Int, enabled: Boolean): ProductRecipe {
        val index = products.indexOfFirst { it.id == productId }
        if (index < 0) error("产品不存在")
        val updated = products[index].copy(enabled = enabled)
        products[index] = updated
        return ProductRecipe(updated.id, updated.name, enabled, updated.items)
    }

    override suspend fun createWorkOrder(productId: Int, targetWeightKg: Double): WorkOrder {
        val product = products.firstOrNull { it.id == productId } ?: error("产品不存在")
        if (targetWeightKg <= 0 || targetWeightKg > 100000) error("请输入正确的目标生产重量")
        val recipeItems = product.items.ifEmpty {
            (1..product.materialCount).map { RecipeItem("MAT-40$it", 0.5) }
        }
        val tons = targetWeightKg / 1000
        val order = WorkOrder(
            orderNo = "WO-202609${System.currentTimeMillis().toString().takeLast(6)}",
            productName = product.name,
            targetWeightKg = targetWeightKg,
            completedSteps = 0,
            totalSteps = recipeItems.size,
            operatorName = "现场操作员",
            status = WorkOrderStatus.PENDING_APPROVAL,
            updatedAt = "刚刚",
            steps = recipeItems.mapIndexed { index, item ->
                val material = materials.firstOrNull { it.materialId == item.materialId }
                WorkOrderStep(
                    stepNo = index + 1,
                    materialId = item.materialId,
                    materialCode = material?.materialCode ?: item.materialId,
                    materialName = material?.nameZh ?: "新建辅料 ${index + 1}",
                    requiredWeightKg = item.quantityPerTonKg * tons,
                    toleranceKg = 0.05,
                    status = StepStatus.PENDING,
                )
            },
        )
        orderStore.add(0, order)
        return order
    }

    override suspend fun startWorkOrder(orderNo: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val updated = orderStore[index].copy(status = WorkOrderStatus.IN_PROGRESS)
        orderStore[index] = updated
        return updated
    }

    override suspend fun confirmStepQr(orderNo: String, stepNo: Int, materialId: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        val step = order.steps.firstOrNull { it.stepNo == stepNo } ?: error("步骤不存在")
        if (step.status == StepStatus.COMPLETED || step.status == StepStatus.WEIGHING) error("该辅料已完成类型确认")
        if (materialId.isBlank() || materialId.trim() != step.materialId) error("扫描到的辅料与当前步骤要求不一致")
        val steps = order.steps.map { if (it.stepNo == stepNo) it.copy(status = StepStatus.WEIGHING) else it }
        val updated = order.copy(
            steps = steps,
            completedSteps = steps.count { it.status == StepStatus.COMPLETED },
            updatedAt = "刚刚",
        )
        orderStore[index] = updated
        return updated
    }

    override suspend fun requestStepPhotoApproval(orderNo: String, stepNo: Int, reason: String, photoName: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        val step = order.steps.firstOrNull { it.stepNo == stepNo } ?: error("步骤不存在")
        if (step.status == StepStatus.COMPLETED || step.status == StepStatus.WEIGHING) error("该辅料无需拍照审批")
        if (reason.isBlank()) error("请填写放行原因")
        if (photoName.isBlank()) error("请选择包装照片")
        val steps = order.steps.map { if (it.stepNo == stepNo) it.copy(status = StepStatus.TYPE_CONFIRMATION) else it }
        val updated = order.copy(steps = steps, updatedAt = "刚刚")
        orderStore[index] = updated
        return updated
    }

    override suspend fun approveStepPhotoApproval(orderNo: String, stepNo: Int): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        val step = order.steps.firstOrNull { it.stepNo == stepNo } ?: error("步骤不存在")
        if (step.status != StepStatus.TYPE_CONFIRMATION) error("当前步骤没有待审批的拍照申请")
        val steps = order.steps.map { if (it.stepNo == stepNo) it.copy(status = StepStatus.WEIGHING) else it }
        val updated = order.copy(steps = steps, updatedAt = "刚刚")
        orderStore[index] = updated
        return updated
    }

    override suspend fun submitStepWeight(orderNo: String, stepNo: Int, weightKg: Double, photoName: String): WeightSubmitResult {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        val step = order.steps.firstOrNull { it.stepNo == stepNo } ?: error("步骤不存在")
        if (step.status != StepStatus.WEIGHING) error("请先完成辅料类型确认")
        if (weightKg <= 0) error("请输入正确的称重重量")
        if (photoName.isBlank()) error("请上传电子秤读数照片")
        val withinTolerance = weightKg >= step.requiredWeightKg - step.toleranceKg &&
            weightKg <= step.requiredWeightKg + step.toleranceKg
        if (!withinTolerance) {
            return WeightSubmitResult(
                passed = false,
                message = "称重 ${weightKg} kg，超出允差范围 ${step.requiredWeightKg} ± ${step.toleranceKg} kg，请重新称重。",
                order = order,
            )
        }
        val steps = order.steps.map { if (it.stepNo == stepNo) it.copy(status = StepStatus.COMPLETED) else it }
        val updated = order.copy(
            steps = steps,
            completedSteps = steps.count { it.status == StepStatus.COMPLETED },
            updatedAt = "刚刚",
        )
        orderStore[index] = updated
        return WeightSubmitResult(true, "称重通过，步骤已完成。", updated)
    }

    override suspend fun completeWorkOrder(orderNo: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        if (order.completedSteps != order.totalSteps) error("还有辅料步骤未完成，不能提交完成")
        val updated = order.copy(status = WorkOrderStatus.COMPLETED, updatedAt = "刚刚")
        orderStore[index] = updated
        return updated
    }

    override suspend fun requestTakeover(orderNo: String, reason: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        if (order.pendingRequest != null) error("该工单已有待审批申请")
        if (reason.isBlank()) error("请填写接管原因")
        val updated = order.copy(pendingRequest = "接管申请待审批", updatedAt = "刚刚")
        orderStore[index] = updated
        return updated
    }

    override suspend fun requestCancel(orderNo: String, reason: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        if (order.pendingRequest != null) error("该工单已有待审批申请")
        if (order.status == WorkOrderStatus.COMPLETED || order.status == WorkOrderStatus.CANCELLED) error("当前工单状态不可申请撤销")
        if (reason.isBlank()) error("请填写撤销原因")
        val updated = order.copy(pendingRequest = "撤销申请待审批", updatedAt = "刚刚")
        orderStore[index] = updated
        return updated
    }

    override suspend fun requestDelete(orderNo: String, reason: String): WorkOrder {
        val index = orderStore.indexOfFirst { it.orderNo == orderNo }
        if (index < 0) error("工单不存在")
        val order = orderStore[index]
        if (order.pendingRequest != null) error("该工单已有待审批申请")
        if (reason.isBlank()) error("请填写删除原因")
        val updated = order.copy(pendingRequest = "删除申请待审批", updatedAt = "刚刚")
        orderStore[index] = updated
        return updated
    }
}
