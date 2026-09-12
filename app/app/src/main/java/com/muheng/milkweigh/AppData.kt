package com.muheng.milkweigh

import android.content.Context
import org.json.JSONObject

enum class UserRole { OPERATOR, ADMIN }

data class AppUser(
    val displayName: String,
    val username: String,
    val role: UserRole,
    val token: String = "",
)

enum class WorkOrderStatus(val label: String) {
    PENDING_APPROVAL("待审批"),
    APPROVED("已批准"),
    IN_PROGRESS("执行中"),
    COMPLETED("已完成"),
    CANCELLED("已撤销"),
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

data class Product(
    val id: Int,
    val name: String,
    val materialCount: Int,
)

interface MilkRepository {
    suspend fun login(username: String, password: String): AppUser
    suspend fun register(username: String, displayName: String, password: String): AppUser
    suspend fun listWorkOrders(): List<WorkOrder>
    suspend fun listProducts(): List<Product>
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

    fun save(user: AppUser) {
        val json = JSONObject()
            .put("display_name", user.displayName)
            .put("username", user.username)
            .put("role", user.role.name)
            .put("token", user.token)
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
            )
        }.getOrNull()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }
}

class MockMilkRepository : MilkRepository {
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

    private val products = listOf(
        Product(1, "高钙纯牛奶 1L", 9),
        Product(2, "草莓风味酸奶", 8),
        Product(3, "原味发酵乳", 10),
    )

    override suspend fun login(username: String, password: String): AppUser {
        if (username.isBlank() || password.isBlank()) error("请输入账号和密码")
        val role = if (username == "admin") UserRole.ADMIN else UserRole.OPERATOR
        return AppUser(if (username == "admin") "系统管理员" else "现场操作员", username, role, "mock-${username}-${System.currentTimeMillis()}")
    }

    override suspend fun register(username: String, displayName: String, password: String): AppUser {
        if (username.length < 3 || displayName.isBlank() || password.length < 8) error("请检查注册信息")
        return AppUser(displayName, username, UserRole.OPERATOR, "mock-${username}-${System.currentTimeMillis()}")
    }

    override suspend fun listWorkOrders(): List<WorkOrder> = orderStore.toList()

    override suspend fun listProducts(): List<Product> = products

    override suspend fun createWorkOrder(productId: Int, targetWeightKg: Double): WorkOrder {
        val product = products.firstOrNull { it.id == productId } ?: error("产品不存在")
        if (targetWeightKg <= 0 || targetWeightKg > 100000) error("请输入正确的目标生产重量")
        val order = WorkOrder(
            orderNo = "WO-202609${System.currentTimeMillis().toString().takeLast(6)}",
            productName = product.name,
            targetWeightKg = targetWeightKg,
            completedSteps = 0,
            totalSteps = product.materialCount,
            operatorName = "现场操作员",
            status = WorkOrderStatus.PENDING_APPROVAL,
            updatedAt = "刚刚",
            steps = (1..product.materialCount).map { step ->
                WorkOrderStep(
                    stepNo = step,
                    materialId = "MAT-40$step",
                    materialCode = "MAT-40$step",
                    materialName = "新建辅料 $step",
                    requiredWeightKg = step * 0.5,
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
