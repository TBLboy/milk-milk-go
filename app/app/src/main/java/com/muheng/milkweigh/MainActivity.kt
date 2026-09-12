package com.muheng.milkweigh

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

private val Green = Color(0xFF1F9469)
private val Ink = Color(0xFF17202B)
private val Muted = Color(0xFF77858F)
private val Page = Color(0xFFF5F7F9)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MilkWeighApp() }
    }
}

@Composable
fun MilkWeighApp(repository: MilkRepository = remember { MockMilkRepository() }) {
    val context = LocalContext.current
    val sessionStore = remember { SessionStore(context.applicationContext) }
    var user by remember { mutableStateOf(sessionStore.load()) }
    Surface(modifier = Modifier.fillMaxSize(), color = Page) {
        if (user == null) LoginScreen(repository, sessionStore) { user = it } else MainShell(user!!, repository) { sessionStore.clear(); user = null }
    }
}

@Composable
private fun LoginScreen(repository: MilkRepository, sessionStore: SessionStore, onLoggedIn: (AppUser) -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var displayName by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var registerMode by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var agreed by remember { mutableStateOf(false) }
    var showForgotDialog by remember { mutableStateOf(false) }
    var showAgreementDialog by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    Box(modifier = Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(R.drawable.app_main_bg),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop,
        )
        Box(modifier = Modifier.fillMaxSize().background(Color.White.copy(alpha = 0.58f)))
        Row(modifier = Modifier.fillMaxSize().padding(48.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f).padding(end = 72.dp)) {
                Text("牧衡", color = Green, fontSize = 34.sp, fontWeight = FontWeight.Bold)
                Text("辅料称重防错系统", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(16.dp))
                Text("让每一次辅料称量都有依据、有记录、可追溯。", color = Muted, fontSize = 18.sp)
            }
            Card(modifier = Modifier.width(420.dp), colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(12.dp)) {
                Column(modifier = Modifier.padding(30.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Text(if (registerMode) "注册普通账号" else "登录工作台", color = Ink, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                    Text(if (registerMode) "创建现场操作员账号" else "使用现场账号进入称量任务", color = Muted, fontSize = 15.sp)
                    OutlinedTextField(username, { username = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("账号") }, singleLine = true)
                    if (registerMode) {
                        OutlinedTextField(displayName, { displayName = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("姓名") }, singleLine = true)
                    }
                    OutlinedTextField(password, { password = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("密码") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                    if (registerMode) {
                        OutlinedTextField(confirmPassword, { confirmPassword = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("确认密码") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                    }
                    error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        if (registerMode) {
                            TextButton(onClick = { registerMode = false; error = null }, modifier = Modifier.padding(start = 0.dp)) { Text("已有账号？返回登录", color = Green) }
                        } else {
                            TextButton(onClick = { showForgotDialog = true }, modifier = Modifier.padding(start = 0.dp)) { Text("忘记密码", color = Green) }
                        }
                        TextButton(onClick = { showAgreementDialog = true }) { Text("用户协议", color = Green) }
                    }
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = agreed, onCheckedChange = { agreed = it })
                        Text("我已阅读并同意《用户协议》", color = Muted, fontSize = 14.sp, modifier = Modifier.clickable { agreed = !agreed })
                    }
                    Button(onClick = {
                        if (!agreed) {
                            error = "请先阅读并同意《用户协议》"
                            return@Button
                        }
                        error = null
                        if (registerMode) {
                            if (username.length < 3 || displayName.isBlank() || password.length < 8) {
                                error = "请完整填写注册信息，密码至少 8 位"
                                return@Button
                            }
                            if (password != confirmPassword) {
                                error = "两次输入的密码不一致"
                                return@Button
                            }
                            scope.launch {
                                runCatching { repository.register(username.trim(), displayName.trim(), password) }
                                    .onSuccess { sessionStore.save(it); onLoggedIn(it) }
                                    .onFailure { error = it.message }
                            }
                        } else {
                            scope.launch {
                                runCatching { repository.login(username.trim(), password) }
                                    .onSuccess { sessionStore.save(it); onLoggedIn(it) }
                                    .onFailure { error = it.message }
                            }
                        }
                    }, modifier = Modifier.fillMaxWidth()) { Text(if (registerMode) "注册并登录" else "登录") }
                    if (!registerMode) {
                        TextButton(onClick = { registerMode = true; error = null }, modifier = Modifier.align(Alignment.End)) { Text("没有账号？注册普通账号", color = Green) }
                    }
                    Text(if (registerMode) "注册成功后自动登录，账号为普通操作员" else "测试账号：operator / 任意密码；管理员：admin / 任意密码", color = Muted, fontSize = 12.sp)
                }
            }
        }
    }
    if (showForgotDialog) {
        AlertDialog(
            onDismissRequest = { showForgotDialog = false },
            title = { Text("忘记密码") },
            text = { Text("请联系系统管理员重置密码。管理员在后台可以创建和管理普通账户。") },
            confirmButton = { TextButton(onClick = { showForgotDialog = false }) { Text("知道了") } }
        )
    }
    if (showAgreementDialog) {
        AlertDialog(
            onDismissRequest = { showAgreementDialog = false },
            title = { Text("用户协议") },
            text = { Text("本系统用于辅料称重防错记录，请按现场作业规范操作。操作记录将长期保存，用于生产追溯和异常核查。") },
            confirmButton = { TextButton(onClick = { showAgreementDialog = false }) { Text("知道了") } }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainShell(user: AppUser, repository: MilkRepository, onLogout: () -> Unit) {
    var selected by remember { mutableStateOf("工作台") }
    var selectedOrderNo by remember { mutableStateOf<String?>(null) }
    var orders by remember { mutableStateOf<List<WorkOrder>>(emptyList()) }
    var products by remember { mutableStateOf<List<Product>>(emptyList()) }
    var showCreateDialog by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    androidx.compose.runtime.LaunchedEffect(Unit) {
        orders = repository.listWorkOrders()
        products = repository.listProducts()
    }
    Scaffold(topBar = { TopAppBar(title = { Text("牧衡辅料称重", fontWeight = FontWeight.Bold) }, colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White), actions = { Text(user.displayName, color = Muted); IconButton(onClick = onLogout) { Icon(Icons.Default.Close, "退出") } }) }, containerColor = Page) { padding ->
        Row(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(modifier = Modifier.width(230.dp).fillMaxSize().background(Color.White).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("现场操作", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(8.dp))
                NavItem("工作台", Icons.Default.Assignment, selected == "工作台") { selected = "工作台" }
                NavItem("工单", Icons.Default.Inventory2, selected == "工单") { selected = "工单" }
                if (user.role == UserRole.ADMIN) {
                    Spacer(Modifier.height(12.dp)); Text("管理员", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(8.dp))
                    NavItem("辅料与配方", Icons.Default.Settings, selected == "辅料与配方") { selected = "辅料与配方" }
                }
                Spacer(Modifier.weight(1f)); Text("局域网模式 · Mock 数据", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(8.dp))
            }
            when (selected) {
                "工单" -> OrderListScreen(orders, onCreate = { showCreateDialog = true }) { order ->
                    selectedOrderNo = order.orderNo
                    selected = "详情"
                }
                "详情" -> OrderDetailScreen(
                    order = orders.firstOrNull { it.orderNo == selectedOrderNo },
                    repository = repository,
                    onBack = { selected = "工单" },
                    onUpdated = { updated -> orders = orders.map { if (it.orderNo == updated.orderNo) updated else it } },
                )
                "辅料与配方" -> AdminPlaceholder()
                else -> DashboardScreen(
                    orders,
                    onRefresh = { scope.launch { orders = repository.listWorkOrders() } },
                    onCreate = { showCreateDialog = true },
                    openOrders = { selected = "工单" },
                    openOrder = { order ->
                        selectedOrderNo = order.orderNo
                        selected = "详情"
                    },
                )
            }
        }
    }
    if (showCreateDialog && products.isNotEmpty()) {
        CreateWorkOrderDialog(
            repository = repository,
            products = products,
            onDismiss = { showCreateDialog = false },
            onCreated = { order ->
                orders = listOf(order) + orders
                selectedOrderNo = order.orderNo
                showCreateDialog = false
                selected = "详情"
            },
        )
    }
}

@Composable
private fun NavItem(label: String, icon: androidx.compose.ui.graphics.vector.ImageVector, active: Boolean, onClick: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).background(if (active) Color(0xFFEAF6F0) else Color.Transparent, RoundedCornerShape(8.dp)).padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (active) Green else Muted); Spacer(Modifier.width(12.dp)); Text(label, color = if (active) Green else Ink, fontWeight = if (active) FontWeight.Bold else FontWeight.Normal)
    }
}

@Composable
private fun DashboardScreen(orders: List<WorkOrder>, onRefresh: () -> Unit, onCreate: () -> Unit, openOrders: () -> Unit, openOrder: (WorkOrder) -> Unit) {
    Column(modifier = Modifier.fillMaxSize().padding(30.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Column { Text("工作台", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold); Text("今天的称量任务概览", color = Muted, fontSize = 15.sp) }; Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { Button(onClick = onCreate) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("新建工单") }; OutlinedButton(onClick = onRefresh) { Text("刷新") } } }
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) { StatCard("今日工单", orders.count { it.status != WorkOrderStatus.CANCELLED }.toString(), "生产称量任务"); StatCard("执行中", orders.count { it.status == WorkOrderStatus.IN_PROGRESS }.toString(), "现场正在称重"); StatCard("待审批", orders.count { it.status == WorkOrderStatus.PENDING_APPROVAL }.toString(), "需要及时处理") }
        Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) { Column(modifier = Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { Row(verticalAlignment = Alignment.CenterVertically) { Text("最近工单", color = Ink, fontSize = 20.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.weight(1f)); Text("查看全部", color = Green, modifier = Modifier.clickable(onClick = openOrders)) }; orders.filter { it.status != WorkOrderStatus.CANCELLED }.take(3).forEach { OrderRow(it) { openOrder(it) } } } }
}
}

@Composable private fun StatCard(title: String, value: String, detail: String) { Card(modifier = Modifier.width(220.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) { Column(Modifier.padding(18.dp)) { Text(title, color = Muted); Text(value, color = Ink, fontSize = 30.sp, fontWeight = FontWeight.Bold); Text(detail, color = Green, fontSize = 13.sp) } } }

@Composable
private fun OrderListScreen(orders: List<WorkOrder>, onCreate: () -> Unit, openDetail: (WorkOrder) -> Unit) {
    var filter by remember { mutableStateOf<String?>(null) }
    val filterOptions = listOf("全部") + WorkOrderStatus.entries.map { it.label }
    val filteredOrders = orders
        .sortedBy { it.status == WorkOrderStatus.CANCELLED }
        .filter { filter == null || filter == "全部" || it.status.label == filter }
    Column(modifier = Modifier.fillMaxSize().padding(30.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text("工单管理", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                Text("查看和继续现场称量任务", color = Muted, modifier = Modifier.padding(top = 6.dp))
            }
            Button(onClick = onCreate) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("新建工单") }
        }
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(top = 18.dp, bottom = 18.dp),
        ) {
            filterOptions.forEach { option ->
                val selected = (filter ?: "全部") == option
                Text(
                    option,
                    modifier = Modifier
                        .clickable { filter = if (option == "全部") null else option }
                        .background(if (selected) Green.copy(alpha = 0.12f) else Color.White, RoundedCornerShape(50))
                        .border(1.dp, if (selected) Green.copy(alpha = 0.45f) else Color(0xFFE3E8EA), RoundedCornerShape(50))
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    color = if (selected) Green else Muted,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                )
            }
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            items(filteredOrders.take(8)) { order -> OrderRow(order) { openDetail(order) } }
        }
        Row(modifier = Modifier.fillMaxWidth().padding(top = 16.dp), horizontalArrangement = Arrangement.Center) {
            Text("第 1 页 / 共 ${((filteredOrders.size - 1) / 8) + 1} 页 · 展示前 ${minOf(8, filteredOrders.size)} 条", color = Muted, fontSize = 13.sp)
        }
    }
}

@Composable
private fun OrderRow(order: WorkOrder, onClick: () -> Unit = {}) { Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick), colors = CardDefaults.cardColors(containerColor = Color.White)) { Row(modifier = Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(42.dp).background(Color(0xFFEAF6F0), RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Default.Assignment, null, tint = Green) }; Column(Modifier.padding(start = 14.dp).weight(1f)) { Text(order.productName, color = Ink, fontWeight = FontWeight.Bold, fontSize = 16.sp); Text("${order.orderNo} · ${order.targetWeightKg.toInt()} kg · ${order.operatorName}", color = Muted, fontSize = 13.sp); Text("进度 ${order.completedSteps}/${order.totalSteps} · ${order.updatedAt}", color = Muted, fontSize = 13.sp) }; StatusPill(order.status); Icon(Icons.Default.ArrowForward, null, tint = Muted, modifier = Modifier.padding(start = 12.dp)) } } }

@Composable private fun StatusPill(status: WorkOrderStatus) { val color = when (status) { WorkOrderStatus.IN_PROGRESS -> Color(0xFFC9854C); WorkOrderStatus.COMPLETED -> Green; WorkOrderStatus.CANCELLED -> Color(0xFFC7473C); else -> Color(0xFF68808E) }; Text(status.label, color = color, fontWeight = FontWeight.Bold, modifier = Modifier.background(color.copy(alpha = .1f), RoundedCornerShape(50)).padding(horizontal = 12.dp, vertical = 7.dp)) }

@Composable
private fun OrderDetailScreen(order: WorkOrder?, repository: MilkRepository, onBack: () -> Unit, onUpdated: (WorkOrder) -> Unit) {
    val scope = rememberCoroutineScope()
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    var actionStepNo by remember { mutableStateOf<Int?>(null) }
    var requestAction by remember { mutableStateOf<String?>(null) }
    Column(modifier = Modifier.fillMaxSize().padding(30.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text("工单详情", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold)
            OutlinedButton(onClick = onBack) { Text("返回工单") }
        }
        if (order == null) {
            Text("暂无工单", color = Muted)
        } else {
            val currentStepNo = order.steps.firstOrNull { it.status != StepStatus.COMPLETED }?.stepNo ?: order.totalSteps + 1
            Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(modifier = Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(order.productName, color = Ink, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        StatusPill(order.status)
                    }
                    Text("目标重量 ${order.targetWeightKg.toInt()} kg · 执行人 ${order.operatorName}", color = Muted)
                    Text("进度 ${order.completedSteps}/${order.totalSteps}", color = Green, fontWeight = FontWeight.Bold)
                    order.pendingRequest?.let { Text(it, color = Color(0xFFC9854C), fontSize = 14.sp, fontWeight = FontWeight.Bold) }
                }
            }
            Text("辅料称量步骤", color = Ink, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            order.steps.forEach { step ->
                StepCard(step, order.status, currentStepNo, onAction = { actionStepNo = step.stepNo })
            }
            error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            when {
                order.status == WorkOrderStatus.PENDING_APPROVAL -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.startWorkOrder(order.orderNo) }
                                .onSuccess(onUpdated)
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working) { Text("开始执行") }
                order.status == WorkOrderStatus.IN_PROGRESS && order.completedSteps == order.totalSteps -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.completeWorkOrder(order.orderNo) }
                                .onSuccess(onUpdated)
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working) { Text("提交完成") }
                order.status == WorkOrderStatus.IN_PROGRESS -> Text("请按顺序完成所有辅料步骤后再提交完成", color = Muted)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (order.pendingRequest == null && order.status != WorkOrderStatus.COMPLETED && order.status != WorkOrderStatus.CANCELLED) {
                    OutlinedButton(onClick = { requestAction = "接管" }) { Text("申请接管") }
                    OutlinedButton(onClick = { requestAction = "撤销" }) { Text("申请撤销") }
                    OutlinedButton(onClick = { requestAction = "删除" }) { Text("申请删除") }
                } else if (order.pendingRequest != null) {
                    Text("已提交申请，等待后台审批", color = Muted)
                }
            }
        }
    }
    val actionStep = actionStepNo?.let { no -> order?.steps?.firstOrNull { it.stepNo == no } }
    if (order != null && actionStep != null) {
        when (actionStep.status) {
            StepStatus.PENDING, StepStatus.TYPE_CONFIRMATION -> TypeConfirmationDialog(
                order = order,
                step = actionStep,
                repository = repository,
                onDismiss = { actionStepNo = null },
                onUpdated = { updated -> onUpdated(updated); actionStepNo = null },
            )
            StepStatus.WEIGHING -> WeightDialog(
                order = order,
                step = actionStep,
                repository = repository,
                onDismiss = { actionStepNo = null },
                onUpdated = { updated -> onUpdated(updated); actionStepNo = null },
            )
            StepStatus.COMPLETED -> actionStepNo = null
        }
    }
    if (order != null && requestAction != null) {
        RequestDialog(
            order = order,
            requestType = requestAction ?: "",
            repository = repository,
            onDismiss = { requestAction = null },
            onUpdated = { updated -> onUpdated(updated); requestAction = null },
        )
    }
}

@Composable
private fun StepCard(step: WorkOrderStep, orderStatus: WorkOrderStatus, currentStepNo: Int, onAction: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(
                when (step.status) {
                    StepStatus.COMPLETED -> Icons.Default.CheckCircle
                    StepStatus.WEIGHING -> Icons.Default.QrCodeScanner
                    StepStatus.TYPE_CONFIRMATION -> Icons.Default.CameraAlt
                    StepStatus.PENDING -> Icons.Default.Inventory2
                },
                null,
                tint = if (step.status == StepStatus.COMPLETED) Green else Muted,
                modifier = Modifier.size(30.dp),
            )
            Column(Modifier.padding(start = 14.dp).weight(1f)) {
                Text("步骤 ${step.stepNo} · ${step.materialCode} ${step.materialName}", color = Ink, fontWeight = FontWeight.Bold)
                Text("应称 ${step.requiredWeightKg} kg · 允差 ±${step.toleranceKg} kg", color = Muted, fontSize = 14.sp)
                Text(step.status.label, color = if (step.status == StepStatus.COMPLETED) Green else Muted, fontSize = 13.sp)
            }
            if (orderStatus == WorkOrderStatus.IN_PROGRESS && step.stepNo == currentStepNo && step.status != StepStatus.COMPLETED) {
                when (step.status) {
                    StepStatus.PENDING -> Button(onClick = onAction) { Text("类型确认") }
                    StepStatus.TYPE_CONFIRMATION -> Button(onClick = onAction) { Text("模拟审批") }
                    StepStatus.WEIGHING -> Button(onClick = onAction) { Text("填写称重") }
                    StepStatus.COMPLETED -> {}
                }
            }
        }
    }
}

@Composable
private fun TypeConfirmationDialog(
    order: WorkOrder,
    step: WorkOrderStep,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    var mode by remember { mutableStateOf(if (step.status == StepStatus.TYPE_CONFIRMATION) "approve" else "scan") }
    var materialId by remember { mutableStateOf(step.materialId) }
    var reason by remember { mutableStateOf("") }
    var photoName by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        photoName = uri?.lastPathSegment ?: "现场包装照片"
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text("类型确认 · 步骤 ${step.stepNo}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("${step.materialName} · ${step.materialCode}", color = Ink, fontWeight = FontWeight.Bold)
                Text("应称 ${step.requiredWeightKg} kg · 允差 ±${step.toleranceKg} kg", color = Muted)
                when (mode) {
                    "approve" -> {
                        Text("已提交无码拍照申请，等待后台审批。", color = Muted)
                    }
                    "scan" -> {
                        OutlinedTextField(materialId, { materialId = it }, modifier = Modifier.fillMaxWidth(), label = { Text("模拟扫码辅料 ID") }, singleLine = true)
                        OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (photoName.isBlank()) "选择无码包装照片" else "已选择：$photoName")
                        }
                    }
                    else -> {
                        OutlinedTextField(reason, { reason = it }, modifier = Modifier.fillMaxWidth(), label = { Text("放行原因") }, singleLine = true)
                        OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (photoName.isBlank()) "选择无码包装照片" else "已选择：$photoName")
                        }
                    }
                }
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            when {
                mode == "approve" -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.approveStepPhotoApproval(order.orderNo, step.stepNo) }
                                .onSuccess { onUpdated(it) }
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working) { Text("测试审批通过") }
                mode == "scan" -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.confirmStepQr(order.orderNo, step.stepNo, materialId) }
                                .onSuccess { onUpdated(it) }
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working) { Text("确认类型") }
                else -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.requestStepPhotoApproval(order.orderNo, step.stepNo, reason, photoName) }
                                .onSuccess { onUpdated(it) }
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working) { Text("提交拍照申请") }
            }
        },
        dismissButton = {
            TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") }
            if (mode != "approve") {
                TextButton(onClick = {
                    mode = if (mode == "scan") "photo" else "scan"
                    error = null
                }) { Text(if (mode == "scan") "无码拍照" else "扫码确认") }
            }
        },
    )
}

@Composable
private fun WeightDialog(
    order: WorkOrder,
    step: WorkOrderStep,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    var weightText by remember { mutableStateOf("") }
    var photoName by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var result by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        photoName = uri?.lastPathSegment ?: "电子秤读数照片"
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text("称重记录 · 步骤 ${step.stepNo}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("${step.materialName} · ${step.materialCode}", color = Ink, fontWeight = FontWeight.Bold)
                Text("应称 ${step.requiredWeightKg} kg · 允差 ±${step.toleranceKg} kg", color = Muted)
                OutlinedTextField(weightText, { weightText = it.filter { c -> c.isDigit() || c == '.' } }, modifier = Modifier.fillMaxWidth(), label = { Text("电子秤读数 (kg)") }, singleLine = true)
                OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.fillMaxWidth()) {
                    Text(if (photoName.isBlank()) "选择电子秤读数照片" else "已选择：$photoName")
                }
                result?.let { Text(it, color = if (result?.startsWith("称重通过") == true) Green else Color(0xFFC7473C), fontSize = 14.sp) }
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(onClick = {
                if (!working) {
                    val weight = weightText.toDoubleOrNull()
                    if (weight == null || weight <= 0) {
                        error = "请输入正确的电子秤读数"
                        return@Button
                    }
                    working = true
                    error = null
                    result = null
                    scope.launch {
                        runCatching { repository.submitStepWeight(order.orderNo, step.stepNo, weight, photoName) }
                            .onSuccess { submitResult ->
                                result = submitResult.message
                                if (submitResult.passed) onUpdated(submitResult.order)
                            }
                            .onFailure { error = it.message }
                            .also { working = false }
                    }
                }
            }, enabled = !working) { Text("提交称重") }
        },
        dismissButton = { TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") } },
    )
}

@Composable
private fun RequestDialog(
    order: WorkOrder,
    requestType: String,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    var reason by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val title = when (requestType) {
        "接管" -> "申请接管工单"
        "撤销" -> "申请撤销工单"
        else -> "申请删除工单"
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("${order.orderNo} · ${order.productName}", color = Ink, fontWeight = FontWeight.Bold)
                Text("当前执行人：${order.operatorName}", color = Muted)
                OutlinedTextField(reason, { reason = it }, modifier = Modifier.fillMaxWidth(), label = { Text("申请原因") }, singleLine = true)
                Text("提交后进入后台审批，审批结果会同步到平板。", color = Muted, fontSize = 13.sp)
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(onClick = {
                if (!working) {
                    working = true
                    error = null
                    scope.launch {
                        val result = runCatching {
                            when (requestType) {
                                "接管" -> repository.requestTakeover(order.orderNo, reason)
                                "撤销" -> repository.requestCancel(order.orderNo, reason)
                                else -> repository.requestDelete(order.orderNo, reason)
                            }
                        }
                        result.onSuccess(onUpdated).onFailure { error = it.message }
                        working = false
                    }
                }
            }, enabled = !working) { Text("提交申请") }
        },
        dismissButton = { TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") } },
    )
}

@Composable
private fun CreateWorkOrderDialog(repository: MilkRepository, products: List<Product>, onDismiss: () -> Unit, onCreated: (WorkOrder) -> Unit) {
    var selectedProduct by remember { mutableStateOf(products.firstOrNull()) }
    var targetWeight by remember { mutableStateOf("1000") }
    var productMenuExpanded by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建工单") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("选择产品", color = Muted, fontSize = 14.sp)
                Box {
                    OutlinedButton(onClick = { productMenuExpanded = true }, modifier = Modifier.fillMaxWidth()) {
                        Text(selectedProduct?.name ?: "请选择产品", modifier = Modifier.weight(1f), color = Ink)
                        Icon(Icons.Default.KeyboardArrowDown, null, tint = Muted)
                    }
                    DropdownMenu(expanded = productMenuExpanded, onDismissRequest = { productMenuExpanded = false }) {
                        products.forEach { product ->
                            DropdownMenuItem(
                                text = { Text("${product.name} · ${product.materialCount} 种辅料") },
                                onClick = { selectedProduct = product; productMenuExpanded = false },
                            )
                        }
                    }
                }
                OutlinedTextField(
                    value = targetWeight,
                    onValueChange = { targetWeight = it.filter(Char::isDigit) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("目标生产重量 (kg)") },
                    singleLine = true,
                )
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(onClick = {
                val product = selectedProduct ?: return@Button
                val weight = targetWeight.toDoubleOrNull()
                if (weight == null || weight <= 0) {
                    error = "请选择产品并输入正确的目标生产重量"
                    return@Button
                }
                error = null
                scope.launch {
                    runCatching { repository.createWorkOrder(product.id, weight) }
                        .onSuccess { onCreated(it) }
                        .onFailure { error = it.message }
                }
            }) { Text("提交") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable private fun AdminPlaceholder() { Column(Modifier.fillMaxSize().padding(30.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) { Text("辅料与配方", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold); Text("管理员可以在平板维护辅料包装图片和产品配方。", color = Muted); Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) { Button(onClick = {}) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("新建辅料") }; OutlinedButton(onClick = {}) { Icon(Icons.Default.CameraAlt, null); Spacer(Modifier.width(6.dp)); Text("拍摄包装图片") } } } }
