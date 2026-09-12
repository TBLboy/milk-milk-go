package com.muheng.milkweigh

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import androidx.core.content.ContextCompat
import com.google.zxing.integration.android.IntentIntegrator
import java.io.File
import kotlinx.coroutines.launch

private fun createPhotoUri(context: Context): Uri {
    val directory = File(context.cacheDir, "evidence").apply { mkdirs() }
    val file = File.createTempFile("photo_", ".jpg", directory)
    return FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
}

@Composable
private fun cameraPermissionLauncher(onGranted: () -> Unit): () -> Unit {
    val context = LocalContext.current
    val latestOnGranted = rememberUpdatedState(onGranted)
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            latestOnGranted.value()
        } else {
            Toast.makeText(context, "需要相机权限才能拍照或扫码", Toast.LENGTH_SHORT).show()
        }
    }
    return {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            latestOnGranted.value()
        } else {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }
}

private val Green = Color(0xFF1F9469)
private val Ink = Color(0xFF17202B)
private val Muted = Color(0xFF77858F)
private val Page = Color(0xFFF5F7F9)

private fun parseIpParts(url: String): Pair<String, String> {
    val match = Regex("""^http://192\.168\.(\d{1,3})\.(\d{1,3}):\d+/api/v1/?$""", RegexOption.IGNORE_CASE)
        .find(url.trim())
    return if (match == null) {
        "" to ""
    } else {
        match.groupValues[1] to match.groupValues[2]
    }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MilkWeighApp() }
    }
}

@Composable
fun MilkWeighApp(customRepository: MilkRepository? = null) {
    val context = LocalContext.current
    val sessionStore = remember { SessionStore(context.applicationContext) }
    val repository = remember { customRepository ?: RealMilkRepository(context.applicationContext, sessionStore.load()?.token.orEmpty()) }
    var user by remember { mutableStateOf(sessionStore.load()) }
    Surface(modifier = Modifier.fillMaxSize(), color = Page) {
        if (user == null) {
            LoginScreen(repository, sessionStore) { user = it }
        } else {
            MainShell(
                user = user!!,
                repository = repository,
                onUserUpdated = { updated ->
                    sessionStore.save(updated)
                    user = updated
                },
                onLogout = {
                    sessionStore.clear()
                    user = null
                },
            )
        }
    }
}

@Composable
private fun LoginScreen(repository: MilkRepository, sessionStore: SessionStore, onLoggedIn: (AppUser) -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var displayName by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var ipThird by remember { mutableStateOf("") }
    var ipFourth by remember { mutableStateOf("") }
    var serverError by remember { mutableStateOf<String?>(null) }
    var registerMode by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var agreed by remember { mutableStateOf(false) }
    var showForgotDialog by remember { mutableStateOf(false) }
    var showAgreementDialog by remember { mutableStateOf(false) }
    var showServerDialog by remember { mutableStateOf(false) }
    var registerSubmitted by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    Box(modifier = Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(R.drawable.app_main_bg),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop,
        )
        Box(modifier = Modifier.fillMaxSize().background(Color.White.copy(alpha = 0.58f)))
        Row(modifier = Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(48.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f).padding(end = 72.dp)) {
                Text("牧衡", color = Green, fontSize = 34.sp, fontWeight = FontWeight.Bold)
                Text("辅料称重防错系统", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(16.dp))
                Text("让每一次辅料称量都有依据、有记录、可追溯。", color = Muted, fontSize = 18.sp)
            }
            Card(modifier = Modifier.width(420.dp), colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(12.dp)) {
                Column(modifier = Modifier.padding(30.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(if (registerMode) "注册普通账号" else "登录工作台", color = Ink, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                            Text(if (registerMode) "创建现场操作员账号" else "使用现场账号进入称量任务", color = Muted, fontSize = 15.sp)
                        }
                        IconButton(onClick = {
                            val parts = parseIpParts(sessionStore.serverUrl())
                            ipThird = parts.first
                            ipFourth = parts.second
                            serverError = null
                            showServerDialog = true
                        }) {
                            Icon(Icons.Default.Settings, contentDescription = "服务器设置", tint = Muted)
                        }
                    }
                    OutlinedTextField(username, { username = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("账号") }, singleLine = true)
                    if (registerMode) {
                        OutlinedTextField(displayName, { displayName = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("姓名") }, singleLine = true)
                    }
                    OutlinedTextField(password, { password = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("密码") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                    if (registerMode) {
                        OutlinedTextField(confirmPassword, { confirmPassword = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("确认密码") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                    }
                    error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.CenterVertically) {
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
                                    .onSuccess {
                                        registerSubmitted = it.message
                                        registerMode = false
                                        username = ""
                                        displayName = ""
                                        password = ""
                                        confirmPassword = ""
                                        agreed = false
                                    }
                                    .onFailure { error = it.message }
                            }
                        } else {
                            scope.launch {
                                runCatching { repository.login(username.trim(), password) }
                                    .onSuccess { sessionStore.save(it); onLoggedIn(it) }
                                    .onFailure { error = it.message }
                            }
                        }
                    }, modifier = Modifier.fillMaxWidth()) { Text(if (registerMode) "提交注册申请" else "登录") }
                    if (!registerMode) {
                        TextButton(onClick = { registerMode = true; error = null }, modifier = Modifier.align(Alignment.End)) { Text("没有账号？注册普通账号", color = Green) }
                    }
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
    if (showServerDialog) {
        AlertDialog(
            onDismissRequest = { showServerDialog = false },
            title = { Text("系统设置") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
                    ) {
                        Text("192.168.", color = Ink, fontSize = 16.sp, fontWeight = FontWeight.Medium)
                        OutlinedTextField(
                            ipThird,
                            { ipThird = it.filter { char -> char.isDigit() }.take(3) },
                            modifier = Modifier.width(82.dp),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            placeholder = { Text("000") },
                        )
                        Text(".", color = Ink, fontSize = 20.sp, fontWeight = FontWeight.Medium)
                        OutlinedTextField(
                            ipFourth,
                            { ipFourth = it.filter { char -> char.isDigit() }.take(3) },
                            modifier = Modifier.width(82.dp),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            placeholder = { Text("000") },
                        )
                    }
                    serverError?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
                }
            },
            confirmButton = {
                Button(onClick = {
                    val third = ipThird.trim()
                    val fourth = ipFourth.trim()
                    val thirdValue = third.toIntOrNull()
                    val fourthValue = fourth.toIntOrNull()
                    serverError = when {
                        third.isEmpty() || fourth.isEmpty() -> "请输入 IP 地址的第三段和第四段"
                        thirdValue == null || thirdValue !in 0..255 -> "IP 第三段应为 0-255 的数字"
                        fourthValue == null || fourthValue !in 0..255 -> "IP 第四段应为 0-255 的数字"
                        else -> null
                    }
                    if (serverError == null) {
                        sessionStore.saveServerUrl("http://192.168.$third.$fourth:8011/api/v1/")
                        showServerDialog = false
                    }
                }) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = { showServerDialog = false }) { Text("取消") }
            },
        )
    }
    if (registerSubmitted != null) {
        AlertDialog(
            onDismissRequest = { registerSubmitted = null },
            title = { Text("注册申请已提交") },
            text = { Text(registerSubmitted.orEmpty()) },
            confirmButton = {
                TextButton(onClick = { registerSubmitted = null }) { Text("知道了") }
            },
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

@Composable
private fun AvatarImage(
    avatarFileId: String?,
    displayName: String,
    repository: MilkRepository,
    previewUri: String? = null,
    onClick: (() -> Unit)? = null,
    size: Dp = 38.dp,
) {
    val context = LocalContext.current
    var bitmap by remember(avatarFileId, previewUri) { mutableStateOf<ImageBitmap?>(null) }
    androidx.compose.runtime.LaunchedEffect(avatarFileId, previewUri) {
        bitmap = null
        if (!previewUri.isNullOrBlank()) {
            val bytes = runCatching {
                context.contentResolver.openInputStream(Uri.parse(previewUri))?.use { it.readBytes() }
            }.getOrNull()
            bitmap = bytes
                ?.takeIf { it.isNotEmpty() }
                ?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
            return@LaunchedEffect
        }
        if (avatarFileId.isNullOrBlank()) return@LaunchedEffect
        val bytes = runCatching { repository.loadFileBytes(avatarFileId) }.getOrNull()
        bitmap = bytes
            ?.takeIf { it.isNotEmpty() }
            ?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }
    val avatarModifier = if (onClick == null) {
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(if (bitmap != null) Color.Transparent else Color(0xFFEAF6F0))
    } else {
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(if (bitmap != null) Color.Transparent else Color(0xFFEAF6F0))
            .clickable { onClick.invoke() }
    }
    Box(
        modifier = avatarModifier,
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(bitmap = bitmap!!, contentDescription = null, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        } else {
            Text(
                displayName.take(1).ifBlank { "牧" },
                color = Green,
                fontWeight = FontWeight.Bold,
                fontSize = minOf(size.value * 0.4f, 64f).sp,
            )
        }
    }
}

@Composable
private fun UserMenu(
    user: AppUser,
    repository: MilkRepository,
    onProfile: () -> Unit,
    onChangePassword: () -> Unit,
    onLogout: () -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = !expanded }) {
            AvatarImage(
                avatarFileId = user.avatarFileId,
                displayName = user.displayName,
                repository = repository,
                onClick = { expanded = true },
            )
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("${user.displayName} · ${user.username}", color = Muted) },
                onClick = { expanded = false },
                enabled = false,
            )
            DropdownMenuItem(text = { Text("用户资料") }, onClick = { expanded = false; onProfile() })
            DropdownMenuItem(text = { Text("密码管理") }, onClick = { expanded = false; onChangePassword() })
            DropdownMenuItem(text = { Text("切换账号") }, onClick = { expanded = false; onLogout() })
            DropdownMenuItem(text = { Text("退出登录") }, onClick = { expanded = false; onLogout() })
        }
    }
}

@Composable
private fun UserProfileDialog(
    user: AppUser,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onUpdated: (AppUser) -> Unit,
) {
    var displayName by remember(user.displayName) { mutableStateOf(user.displayName) }
    var phone by remember(user.phone) { mutableStateOf(user.phone) }
    var selectedAvatarUri by remember { mutableStateOf<String?>(null) }
    var cameraOutputUri by remember { mutableStateOf<Uri?>(null) }
    var showAvatarPreview by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        selectedAvatarUri = uri?.toString()
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        val uri = cameraOutputUri
        if (saved && uri != null) selectedAvatarUri = uri.toString()
    }
    val launchCamera = cameraPermissionLauncher {
        val uri = createPhotoUri(context)
        cameraOutputUri = uri
        runCatching { cameraLauncher.launch(uri) }
            .onFailure { error = "无法启动相机：${it.message}" }
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text("用户资料") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    AvatarImage(
                        avatarFileId = user.avatarFileId,
                        displayName = displayName,
                        repository = repository,
                        previewUri = selectedAvatarUri,
                        onClick = { showAvatarPreview = true },
                        size = 46.dp,
                    )
                    OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.weight(1f)) { Text("相册头像") }
                    OutlinedButton(
                        onClick = launchCamera,
                        modifier = Modifier.weight(1f),
                    ) { Text("拍照头像") }
                }
                OutlinedTextField(displayName, { displayName = it }, modifier = Modifier.fillMaxWidth(), label = { Text("姓名") }, singleLine = true)
                OutlinedTextField(phone, { phone = it.filter { char -> char.isDigit() || char == '-' } }, modifier = Modifier.fillMaxWidth(), label = { Text("电话") }, singleLine = true)
                Text("身份证：${user.idCard.ifBlank { "未录入" }}", color = Muted, fontSize = 15.sp)
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(
                enabled = !working,
                onClick = {
                    working = true
                    error = null
                    scope.launch {
                        runCatching {
                            val avatarId = selectedAvatarUri?.let { repository.uploadAvatar(it) } ?: user.avatarFileId
                            repository.updateProfile(displayName.trim(), phone.trim(), avatarId)
                        }.onSuccess {
                            onUpdated(it)
                            onDismiss()
                        }.onFailure {
                            error = it.message
                        }
                        working = false
                    }
                },
            ) { Text("保存资料") }
        },
        dismissButton = {
            TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") }
        },
    )
    if (showAvatarPreview) {
        AlertDialog(
            onDismissRequest = { showAvatarPreview = false },
            title = { Text("头像预览") },
            text = {
                Box(
                    modifier = Modifier.fillMaxWidth().height(320.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    AvatarImage(
                        avatarFileId = user.avatarFileId,
                        displayName = displayName,
                        repository = repository,
                        previewUri = selectedAvatarUri,
                        size = 280.dp,
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { showAvatarPreview = false }) { Text("关闭") }
            },
        )
    }
}

@Composable
private fun ChangePasswordDialog(
    required: Boolean,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onChanged: () -> Unit,
) {
    var currentPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = { if (!required && !working) onDismiss() },
        title = { Text(if (required) "首次登录需修改密码" else "修改密码") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (required) Text("管理员已重置您的密码，请先设置一个新的个人密码。", color = Muted, fontSize = 15.sp)
                OutlinedTextField(
                    currentPassword,
                    { currentPassword = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("当前密码") },
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                OutlinedTextField(
                    newPassword,
                    { newPassword = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("新密码") },
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                OutlinedTextField(
                    confirmPassword,
                    { confirmPassword = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("确认新密码") },
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(
                enabled = !working && currentPassword.isNotBlank() && newPassword.length >= 8 && confirmPassword.isNotBlank(),
                onClick = {
                    working = true
                    error = null
                    when {
                        currentPassword.isBlank() -> error = "请输入当前密码"
                        newPassword.length < 8 -> error = "新密码至少 8 位"
                        newPassword != confirmPassword -> error = "两次输入的新密码不一致"
                        else -> scope.launch {
                            runCatching { repository.changePassword(currentPassword, newPassword) }
                                .onSuccess { onChanged() }
                                .onFailure { error = it.message }
                            working = false
                        }
                    }
                },
            ) { Text("确认修改") }
        },
        dismissButton = {
            if (!required) {
                TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") }
            }
        },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainShell(
    user: AppUser,
    repository: MilkRepository,
    onUserUpdated: (AppUser) -> Unit,
    onLogout: () -> Unit,
) {
    var selected by remember { mutableStateOf("工作台") }
    var selectedOrderNo by remember { mutableStateOf<String?>(null) }
    var orders by remember { mutableStateOf<List<WorkOrder>>(emptyList()) }
    var products by remember { mutableStateOf<List<Product>>(emptyList()) }
    var showCreateDialog by remember { mutableStateOf(false) }
    var currentUser by remember { mutableStateOf(user) }
    var showProfileDialog by remember { mutableStateOf(false) }
    var showChangePasswordDialog by remember { mutableStateOf(user.mustChangePassword) }
    val scope = rememberCoroutineScope()
    androidx.compose.runtime.LaunchedEffect(Unit) {
        orders = repository.listWorkOrders()
        products = repository.listProducts()
    }
    androidx.compose.runtime.LaunchedEffect(currentUser.mustChangePassword) {
        if (currentUser.mustChangePassword) showChangePasswordDialog = true
    }
    Scaffold(topBar = {
        TopAppBar(
            title = { Text("牧衡辅料称重", fontWeight = FontWeight.Bold) },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White),
            actions = {
                UserMenu(
                    user = currentUser,
                    repository = repository,
                    onProfile = { showProfileDialog = true },
                    onChangePassword = { showChangePasswordDialog = true },
                    onLogout = onLogout,
                )
            },
        )
    }, containerColor = Page) { padding ->
        Row(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(modifier = Modifier.width(230.dp).fillMaxSize().background(Color.White).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("现场操作", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(8.dp))
                NavItem("工作台", Icons.Default.Assignment, selected == "工作台") { selected = "工作台" }
                NavItem("工单", Icons.Default.Inventory2, selected == "工单") { selected = "工单" }
                if (currentUser.role == UserRole.ADMIN) {
                    Spacer(Modifier.height(12.dp)); Text("管理员", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(8.dp))
                    NavItem("辅料与配方", Icons.Default.Settings, selected == "辅料与配方") { selected = "辅料与配方" }
                }
                Spacer(Modifier.weight(1f)); Text("局域网模式 · 实时接口", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(8.dp))
            }
            when (selected) {
                "工单" -> OrderListScreen(orders, onCreate = { showCreateDialog = true }) { order ->
                    selectedOrderNo = order.orderNo
                    selected = "详情"
                }
                "详情" -> OrderDetailScreen(
                    order = orders.firstOrNull { it.orderNo == selectedOrderNo },
                    repository = repository,
                    canApprove = currentUser.role == UserRole.ADMIN,
                    onBack = { selected = "工单" },
                    onUpdated = { updated -> orders = orders.map { if (it.orderNo == updated.orderNo) updated else it } },
                )
                "辅料与配方" -> AdminMasterDataScreen(repository)
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
    if (showProfileDialog) {
        UserProfileDialog(
            user = currentUser,
            repository = repository,
            onDismiss = { showProfileDialog = false },
            onUpdated = { updated ->
                currentUser = updated
                onUserUpdated(updated)
            },
        )
    }
    if (showChangePasswordDialog) {
        ChangePasswordDialog(
            required = currentUser.mustChangePassword,
            repository = repository,
            onDismiss = { showChangePasswordDialog = false },
            onChanged = {
                val updated = currentUser.copy(mustChangePassword = false)
                currentUser = updated
                onUserUpdated(updated)
                showChangePasswordDialog = false
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
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) { StatCard("今日工单", orders.count { it.status != WorkOrderStatus.CANCELLED && it.status != WorkOrderStatus.DELETED }.toString(), "生产称量任务"); StatCard("执行中", orders.count { it.status == WorkOrderStatus.IN_PROGRESS }.toString(), "现场正在称重"); StatCard("待审批", orders.count { it.status == WorkOrderStatus.PENDING_APPROVAL }.toString(), "需要及时处理") }
        Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) { Column(modifier = Modifier.padding(22.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) { Row(verticalAlignment = Alignment.CenterVertically) { Text("最近工单", color = Ink, fontSize = 20.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.weight(1f)); Text("查看全部", color = Green, modifier = Modifier.clickable(onClick = openOrders)) }; orders.filter { it.status != WorkOrderStatus.CANCELLED && it.status != WorkOrderStatus.DELETED }.take(3).forEach { OrderRow(it) { openOrder(it) } } } }
}
}

@Composable private fun StatCard(title: String, value: String, detail: String) { Card(modifier = Modifier.width(220.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) { Column(Modifier.padding(18.dp)) { Text(title, color = Muted); Text(value, color = Ink, fontSize = 30.sp, fontWeight = FontWeight.Bold); Text(detail, color = Green, fontSize = 13.sp) } } }

@Composable
private fun OrderListScreen(orders: List<WorkOrder>, onCreate: () -> Unit, openDetail: (WorkOrder) -> Unit) {
    var filter by remember { mutableStateOf<String?>(null) }
    val filterOptions = listOf("全部") + WorkOrderStatus.entries.map { it.label }
    val filteredOrders = orders
        .sortedBy { it.status == WorkOrderStatus.CANCELLED || it.status == WorkOrderStatus.DELETED }
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

@Composable private fun StatusPill(status: WorkOrderStatus) { val color = when (status) { WorkOrderStatus.IN_PROGRESS -> Color(0xFFC9854C); WorkOrderStatus.COMPLETED -> Green; WorkOrderStatus.CANCELLED, WorkOrderStatus.DELETED -> Color(0xFFC7473C); else -> Color(0xFF68808E) }; Text(status.label, color = color, fontWeight = FontWeight.Bold, modifier = Modifier.background(color.copy(alpha = .1f), RoundedCornerShape(50)).padding(horizontal = 12.dp, vertical = 7.dp)) }

@Composable
private fun OrderDetailScreen(order: WorkOrder?, repository: MilkRepository, canApprove: Boolean, onBack: () -> Unit, onUpdated: (WorkOrder) -> Unit) {
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
                StepCard(step, order.status, currentStepNo, canApprove, onAction = { actionStepNo = step.stepNo })
            }
            error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            when {
                order.status == WorkOrderStatus.PENDING_APPROVAL -> Text("等待后台审批通过后开始执行", color = Muted)
                order.status == WorkOrderStatus.APPROVED -> Button(onClick = {
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
                if (order.pendingRequest == null && order.status != WorkOrderStatus.COMPLETED && order.status != WorkOrderStatus.CANCELLED && order.status != WorkOrderStatus.DELETED) {
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
                canApprove = canApprove,
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
private fun StepCard(step: WorkOrderStep, orderStatus: WorkOrderStatus, currentStepNo: Int, canApprove: Boolean, onAction: () -> Unit) {
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
                    StepStatus.TYPE_CONFIRMATION -> if (canApprove) {
                        Button(onClick = onAction) { Text("审批通过") }
                    } else {
                        Text("等待后台审批", color = Muted)
                    }
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
    canApprove: Boolean,
    onDismiss: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    var mode by remember { mutableStateOf(if (step.status == StepStatus.TYPE_CONFIRMATION) "approve" else "scan") }
    var materialId by remember { mutableStateOf(step.materialId) }
    var reason by remember { mutableStateOf("") }
    var photoName by remember { mutableStateOf("") }
    var photoUri by remember { mutableStateOf<String?>(null) }
    var cameraOutputUri by remember { mutableStateOf<Uri?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val scanLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val scanResult = IntentIntegrator.parseActivityResult(0, result.resultCode, result.data)
        scanResult?.contents?.takeIf { it.isNotBlank() }?.let { materialId = it }
    }
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        photoUri = uri?.toString()
        photoName = uri?.lastPathSegment ?: "现场包装照片"
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        if (saved) {
            val uri = cameraOutputUri
            if (uri != null) {
                photoUri = uri.toString()
                photoName = "现场拍照"
            }
        }
    }
    val launchPhotoCamera = cameraPermissionLauncher {
        val uri = createPhotoUri(context)
        cameraOutputUri = uri
        runCatching { cameraLauncher.launch(uri) }
            .onFailure { error = "无法启动相机：${it.message}" }
    }
    val launchScanCamera = cameraPermissionLauncher {
        val activity = context as? Activity
        if (activity == null) {
            error = "无法启动扫码"
        } else {
            runCatching { scanLauncher.launch(IntentIntegrator(activity).createScanIntent()) }
                .onFailure { error = "无法启动扫码：${it.message}" }
        }
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
                        OutlinedTextField(materialId, { materialId = it }, modifier = Modifier.fillMaxWidth(), label = { Text("扫码结果 / 辅料 ID") }, singleLine = true)
                        OutlinedButton(
                            onClick = launchScanCamera,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Icon(Icons.Default.QrCodeScanner, null)
                            Spacer(Modifier.width(6.dp))
                            Text("扫描自制二维码")
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                            OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.weight(1f)) {
                                Text(if (photoName.isBlank()) "相册照片" else "已选相册")
                            }
                            OutlinedButton(
                                onClick = launchPhotoCamera,
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.CameraAlt, null)
                                Spacer(Modifier.width(4.dp))
                                Text("拍照")
                            }
                        }
                    }
                    else -> {
                        OutlinedTextField(reason, { reason = it }, modifier = Modifier.fillMaxWidth(), label = { Text("放行原因") }, singleLine = true)
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                            OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.weight(1f)) {
                                Text(if (photoName.isBlank()) "相册照片" else "已选相册")
                            }
                            OutlinedButton(
                                onClick = launchPhotoCamera,
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.CameraAlt, null)
                                Spacer(Modifier.width(4.dp))
                                Text("拍照")
                            }
                        }
                        Text(photoName, color = Muted, fontSize = 13.sp, maxLines = 1)
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
                }, enabled = !working) { Text("审批通过") }
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
                            runCatching { repository.requestStepPhotoApproval(order.orderNo, step.stepNo, reason, photoUri ?: "") }
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
    var photoUri by remember { mutableStateOf<String?>(null) }
    var cameraOutputUri by remember { mutableStateOf<Uri?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var result by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        photoUri = uri?.toString()
        photoName = uri?.lastPathSegment ?: "电子秤读数照片"
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { saved ->
        if (saved) {
            val uri = cameraOutputUri
            if (uri != null) {
                photoUri = uri.toString()
                photoName = "现场拍照"
            }
        }
    }
    val launchPhotoCamera = cameraPermissionLauncher {
        val uri = createPhotoUri(context)
        cameraOutputUri = uri
        runCatching { cameraLauncher.launch(uri) }
            .onFailure { error = "无法启动相机：${it.message}" }
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text("称重记录 · 步骤 ${step.stepNo}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("${step.materialName} · ${step.materialCode}", color = Ink, fontWeight = FontWeight.Bold)
                Text("应称 ${step.requiredWeightKg} kg · 允差 ±${step.toleranceKg} kg", color = Muted)
                OutlinedTextField(weightText, { weightText = it.filter { c -> c.isDigit() || c == '.' } }, modifier = Modifier.fillMaxWidth(), label = { Text("电子秤读数 (kg)") }, singleLine = true)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(onClick = { photoPicker.launch("image/*") }, modifier = Modifier.weight(1f)) {
                        Text(if (photoName.isBlank()) "相册照片" else "已选相册")
                    }
                    OutlinedButton(
                        onClick = launchPhotoCamera,
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.Default.CameraAlt, null)
                        Spacer(Modifier.width(4.dp))
                        Text("拍照")
                    }
                }
                Text(photoName, color = Muted, fontSize = 13.sp, maxLines = 1)
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
                        runCatching { repository.submitStepWeight(order.orderNo, step.stepNo, weight, photoUri ?: "") }
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

private data class EditableRecipeItem(
    val materialId: String,
    val quantity: String,
)

@Composable
private fun AdminMasterDataScreen(repository: MilkRepository) {
    var tab by remember { mutableStateOf("辅料") }
    var materials by remember { mutableStateOf<List<Material>>(emptyList()) }
    var recipes by remember { mutableStateOf<List<ProductRecipe>>(emptyList()) }
    var showMaterialDialog by remember { mutableStateOf(false) }
    var editingMaterial by remember { mutableStateOf<Material?>(null) }
    var showRecipeDialog by remember { mutableStateOf(false) }
    var editingRecipe by remember { mutableStateOf<ProductRecipe?>(null) }
    val scope = rememberCoroutineScope()

    androidx.compose.runtime.LaunchedEffect(Unit) {
        materials = repository.listMaterials()
        recipes = repository.listRecipes()
    }

    Column(modifier = Modifier.fillMaxSize().padding(30.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text("辅料与配方", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                Text("管理员维护现场识别和配方计算需要的主数据", color = Muted, modifier = Modifier.padding(top = 6.dp))
            }
            Button(onClick = {
                if (tab == "辅料") showMaterialDialog = true else showRecipeDialog = true
            }) {
                Icon(Icons.Default.Add, null)
                Spacer(Modifier.width(6.dp))
                Text(if (tab == "辅料") "新增辅料" else "新增配方")
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("辅料", "产品配方").forEach { option ->
                val selected = tab == option
                Text(
                    option,
                    modifier = Modifier
                        .clickable { tab = option }
                        .background(if (selected) Green.copy(alpha = 0.12f) else Color.White, RoundedCornerShape(50))
                        .border(1.dp, if (selected) Green.copy(alpha = 0.45f) else Color(0xFFE3E8EA), RoundedCornerShape(50))
                        .padding(horizontal = 18.dp, vertical = 9.dp),
                    color = if (selected) Green else Muted,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                )
            }
        }

        if (tab == "辅料") {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(materials, key = { it.materialId }) { material ->
                    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("${material.nameZh} · ${material.materialCode}", color = Ink, fontWeight = FontWeight.Bold)
                                Text("${material.materialId} · 保质期 ${material.shelfLifeMonths} 个月", color = Muted, fontSize = 14.sp)
                                Text("${material.imageNames.size} 张包装图片", color = Muted, fontSize = 14.sp)
                            }
                            TextButton(onClick = { editingMaterial = material }) { Text("编辑") }
                        }
                    }
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(recipes, key = { it.id }) { recipe ->
                    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(recipe.name, color = Ink, fontWeight = FontWeight.Bold)
                                Text("${recipe.items.size} 种辅料 · ${if (recipe.enabled) "启用" else "停用"}", color = Muted, fontSize = 14.sp)
                            }
                            TextButton(onClick = { editingRecipe = recipe }) { Text("编辑") }
                        }
                    }
                }
            }
        }
    }

    if (showMaterialDialog || editingMaterial != null) {
        MaterialEditDialog(
            material = editingMaterial,
            repository = repository,
            onDismiss = { showMaterialDialog = false; editingMaterial = null },
            onSaved = {
                scope.launch { materials = repository.listMaterials() }
                showMaterialDialog = false
                editingMaterial = null
            },
        )
    }
    if (showRecipeDialog || editingRecipe != null) {
        RecipeEditDialog(
            recipe = editingRecipe,
            materials = materials,
            repository = repository,
            onDismiss = { showRecipeDialog = false; editingRecipe = null },
            onSaved = {
                scope.launch {
                    recipes = repository.listRecipes()
                    materials = repository.listMaterials()
                }
                showRecipeDialog = false
                editingRecipe = null
            },
        )
    }
}

@Composable
private fun MaterialEditDialog(
    material: Material?,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onSaved: (Material) -> Unit,
) {
    var code by remember { mutableStateOf(material?.materialCode ?: "") }
    var nameZh by remember { mutableStateOf(material?.nameZh ?: "") }
    var nameEn by remember { mutableStateOf(material?.nameEn ?: "") }
    var shelfLife by remember { mutableStateOf(material?.shelfLifeMonths?.toString() ?: "24") }
    var imageNames by remember { mutableStateOf(material?.imageNames ?: emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        imageNames = uris.map { it.toString() }
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text(if (material == null) "新增辅料" else "编辑辅料") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                OutlinedTextField(code, { code = it.uppercase() }, modifier = Modifier.fillMaxWidth(), label = { Text("内部代号") }, singleLine = true)
                OutlinedTextField(nameZh, { nameZh = it }, modifier = Modifier.fillMaxWidth(), label = { Text("中文名称") }, singleLine = true)
                OutlinedTextField(nameEn, { nameEn = it }, modifier = Modifier.fillMaxWidth(), label = { Text("英文名称（可选）") }, singleLine = true)
                OutlinedTextField(shelfLife, { shelfLife = it.filter(Char::isDigit) }, modifier = Modifier.fillMaxWidth(), label = { Text("保质期（月）") }, singleLine = true)
                OutlinedButton(onClick = { imagePicker.launch("image/*") }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.CameraAlt, null)
                    Spacer(Modifier.width(6.dp))
                    Text(if (imageNames.isEmpty()) "选择多张包装图片" else "已选择 ${imageNames.size} 张图片")
                }
                imageNames.take(5).forEach { Text("· ${it.substringAfterLast('/').take(42)}", color = Muted, fontSize = 13.sp) }
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(onClick = {
                val shelf = shelfLife.toIntOrNull()
                if (code.isBlank() || nameZh.isBlank() || shelf == null || shelf <= 0) {
                    error = "请完整填写辅料信息"
                    return@Button
                }
                if (!working) {
                    working = true
                    error = null
                    scope.launch {
                        runCatching {
                            repository.saveMaterial(
                                Material(
                                    materialId = material?.materialId ?: "",
                                    materialCode = code,
                                    nameZh = nameZh,
                                    nameEn = nameEn,
                                    shelfLifeMonths = shelf,
                                    imageNames = imageNames,
                                )
                            )
                        }
                            .onSuccess(onSaved)
                            .onFailure { error = it.message }
                            .also { working = false }
                    }
                }
            }, enabled = !working) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") } },
    )
}

@Composable
private fun RecipeEditDialog(
    recipe: ProductRecipe?,
    materials: List<Material>,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onSaved: (ProductRecipe) -> Unit,
) {
    var name by remember { mutableStateOf(recipe?.name ?: "") }
    var enabled by remember { mutableStateOf(recipe?.enabled ?: true) }
    var items by remember {
        mutableStateOf(
            recipe?.items?.map { EditableRecipeItem(it.materialId, it.quantityPerTonKg.toString()) }
                ?: listOf(EditableRecipeItem(materials.firstOrNull()?.materialId ?: "", "1"))
        )
    }
    var expandedIndex by remember { mutableStateOf(-1) }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text(if (recipe == null) "新增产品配方" else "编辑产品配方") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                OutlinedTextField(name, { name = it }, modifier = Modifier.fillMaxWidth(), label = { Text("产品名称") }, singleLine = true)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = enabled, onCheckedChange = { enabled = it })
                    Text(if (enabled) "配方启用" else "配方停用", color = Muted)
                }
                if (materials.isEmpty()) {
                    Text("请先创建辅料，再添加产品配方。", color = Muted)
                } else {
                    items.forEachIndexed { index, item ->
                        val material = materials.firstOrNull { it.materialId == item.materialId }
                        Box(modifier = Modifier.fillMaxWidth()) {
                            OutlinedButton(onClick = { expandedIndex = index }, modifier = Modifier.fillMaxWidth()) {
                                Text(material?.let { "${it.nameZh} (${it.materialCode})" } ?: "选择辅料", modifier = Modifier.weight(1f), color = Ink)
                                Icon(Icons.Default.KeyboardArrowDown, null, tint = Muted)
                            }
                            DropdownMenu(expanded = expandedIndex == index, onDismissRequest = { expandedIndex = -1 }) {
                                materials.forEach { option ->
                                    DropdownMenuItem(
                                        text = { Text("${option.nameZh} (${option.materialCode})") },
                                        onClick = {
                                            items = items.mapIndexed { itemIndex, current ->
                                                if (itemIndex == index) current.copy(materialId = option.materialId) else current
                                            }
                                            expandedIndex = -1
                                        },
                                    )
                                }
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            OutlinedTextField(
                                value = item.quantity,
                                onValueChange = { value ->
                                    items = items.mapIndexed { itemIndex, current ->
                                        if (itemIndex == index) current.copy(quantity = value.filter { c -> c.isDigit() || c == '.' }) else current
                                    }
                                },
                                modifier = Modifier.weight(1f),
                                label = { Text("每吨用量 (kg)") },
                                singleLine = true,
                            )
                            if (items.size > 1) {
                                TextButton(onClick = {
                                    items = items.filterIndexed { itemIndex, _ -> itemIndex != index }
                                    expandedIndex = -1
                                }) { Text("移除") }
                            }
                        }
                    }
                    TextButton(onClick = {
                        items = items + EditableRecipeItem(materials.first().materialId, "1")
                    }) { Text("添加辅料") }
                }
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(onClick = {
                val parsedItems = runCatching {
                    items.map { item ->
                        val quantity = item.quantity.toDoubleOrNull()
                        if (quantity == null || quantity <= 0) error("每吨用量必须大于 0")
                        RecipeItem(item.materialId, quantity)
                    }
                }.getOrNull()
                if (name.isBlank()) {
                    error = "请输入产品名称"
                    return@Button
                }
                if (parsedItems == null || parsedItems.isEmpty()) {
                    error = "请至少添加一种有效辅料"
                    return@Button
                }
                if (!working) {
                    working = true
                    error = null
                    scope.launch {
                        runCatching {
                            val saved = repository.saveProductRecipe(
                                ProductRecipe(
                                    id = recipe?.id ?: 0,
                                    name = name,
                                    enabled = enabled,
                                    items = parsedItems,
                                    imageFileId = recipe?.imageFileId,
                                )
                            )
                            if (enabled != (recipe?.enabled ?: true)) {
                                repository.setProductActive(saved.id, enabled)
                            }
                            saved
                        }
                            .onSuccess(onSaved)
                            .onFailure { error = it.message }
                            .also { working = false }
                    }
                }
            }, enabled = !working) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") } },
    )
}
