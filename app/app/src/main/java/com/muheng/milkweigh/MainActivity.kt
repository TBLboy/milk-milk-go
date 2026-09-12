package com.muheng.milkweigh

import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.Paint
import android.media.ExifInterface
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContract
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
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.PhotoLibrary
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
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
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
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.max
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

private data class CameraOutput(
    val uri: Uri,
    val file: File,
)

private fun createCameraOutput(context: Context): CameraOutput {
    val directory = File(context.cacheDir, "evidence").apply { mkdirs() }
    val file = File.createTempFile("photo_", ".jpg", directory)
    return CameraOutput(
        uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file),
        file = file,
    )
}

private class EvidenceTakePicture : ActivityResultContract<Uri, Boolean>() {
    override fun createIntent(context: Context, input: Uri): Intent {
        val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            .putExtra(MediaStore.EXTRA_OUTPUT, input)
        intent.clipData = ClipData.newRawUri("evidence", input)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        return intent
    }

    override fun getSynchronousResult(context: Context, input: Uri): SynchronousResult<Boolean>? = null

    override fun parseResult(resultCode: Int, intent: Intent?): Boolean =
        resultCode == Activity.RESULT_OK
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

private fun extractScannedMaterialId(raw: String): String {
    val trimmed = raw.trim()
    if (trimmed.isEmpty()) return ""
    return runCatching {
        val json = JSONObject(trimmed)
        json.optString("materialId").ifBlank { json.optString("material_id") }
    }.getOrElse { trimmed }
}

private data class ProcessedEvidence(
    val photoUri: String,
    val scannedMaterialId: String?,
)

private fun decodeEvidenceBitmap(file: File, maxDimension: Int = 2400): Bitmap {
    if (!file.exists() || file.length() <= 0L) error("相机未返回有效照片")
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    file.inputStream().use {
        BitmapFactory.decodeStream(it, null, bounds)
    }
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0) error("拍摄照片格式不受支持")
    var sampleSize = 1
    while (max(bounds.outWidth, bounds.outHeight) / sampleSize > maxDimension) {
        sampleSize *= 2
    }
    val options = BitmapFactory.Options().apply { inSampleSize = sampleSize }
    return file.inputStream().use {
        BitmapFactory.decodeStream(it, null, options)
    } ?: error("无法解析拍摄照片")
}

private fun normalizeEvidenceOrientation(file: File, bitmap: Bitmap): Bitmap {
    val orientation = runCatching {
        file.inputStream().use { stream ->
            ExifInterface(stream).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        }
    }.getOrDefault(ExifInterface.ORIENTATION_NORMAL)

    val matrix = Matrix()
    when (orientation) {
        ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.setScale(-1f, 1f)
        ExifInterface.ORIENTATION_ROTATE_180 -> matrix.setRotate(180f)
        ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.setScale(1f, -1f)
        ExifInterface.ORIENTATION_TRANSPOSE -> {
            matrix.setRotate(90f)
            matrix.postScale(-1f, 1f)
        }
        ExifInterface.ORIENTATION_ROTATE_90 -> matrix.setRotate(90f)
        ExifInterface.ORIENTATION_TRANSVERSE -> {
            matrix.setRotate(-90f)
            matrix.postScale(-1f, 1f)
        }
        ExifInterface.ORIENTATION_ROTATE_270 -> matrix.setRotate(-90f)
    }
    if (matrix.isIdentity) return bitmap

    val normalized = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    if (normalized !== bitmap) bitmap.recycle()
    return normalized
}

private fun scanQrFromBitmap(bitmap: Bitmap): String? {
    val pixels = IntArray(bitmap.width * bitmap.height)
    bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
    val source = RGBLuminanceSource(bitmap.width, bitmap.height, pixels)
    val binaryBitmap = BinaryBitmap(HybridBinarizer(source))
    val hints = mapOf(DecodeHintType.TRY_HARDER to true)
    return runCatching { MultiFormatReader().decode(binaryBitmap, hints).text }.getOrNull()
}

private suspend fun processCapturedEvidence(
    context: Context,
    sourceFile: File,
    watermarkLines: List<String>,
    scanQr: Boolean,
): ProcessedEvidence = withContext(Dispatchers.Default) {
    val bitmap = normalizeEvidenceOrientation(sourceFile, decodeEvidenceBitmap(sourceFile))
    val scannedMaterialId = if (scanQr) scanQrFromBitmap(bitmap)?.let(::extractScannedMaterialId) else null
    val output = bitmap.copy(Bitmap.Config.ARGB_8888, true) ?: error("无法处理拍摄照片")
    bitmap.recycle()

    val canvas = Canvas(output)
    val textSize = (output.width * 0.022f).coerceIn(22f, 54f)
    val margin = (output.width * 0.022f).coerceIn(20f, 56f)
    val lineHeight = textSize * 1.35f
    val boxHeight = margin * 2 + lineHeight * watermarkLines.size
    val shade = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = android.graphics.Color.argb(150, 0, 0, 0)
    }
    canvas.drawRect(0f, output.height - boxHeight, output.width.toFloat(), output.height.toFloat(), shade)

    val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = android.graphics.Color.WHITE
        this.textSize = textSize
        typeface = android.graphics.Typeface.DEFAULT_BOLD
        setShadowLayer(3f, 1f, 1f, android.graphics.Color.BLACK)
    }
    watermarkLines.forEachIndexed { index, line ->
        val baseline = output.height - boxHeight + margin + textSize + index * lineHeight
        canvas.drawText(line, margin, baseline, textPaint)
    }

    val directory = File(context.cacheDir, "evidence").apply { mkdirs() }
    val outputFile = File.createTempFile("evidence_", ".jpg", directory)
    FileOutputStream(outputFile).use { stream ->
        if (!output.compress(Bitmap.CompressFormat.JPEG, 92, stream)) error("照片保存失败")
    }
    output.recycle()
    ProcessedEvidence(
        photoUri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", outputFile).toString(),
        scannedMaterialId = scannedMaterialId,
    )
}

private fun evidenceWatermarkLines(
    order: WorkOrder,
    step: WorkOrderStep,
    operatorName: String,
    kind: String,
): List<String> {
    val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(Date())
    return listOf(
        "操作员：${operatorName.ifBlank { "未知" }}",
        "时间：$timestamp",
        "工单：${order.orderNo}",
        "$kind：步骤 ${step.stepNo} · ${step.materialCode} ${step.materialName}",
    )
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
    androidx.compose.runtime.LaunchedEffect(user?.token) {
        if (user != null && user?.id == 0) {
            runCatching { repository.refreshUser() }
                .onSuccess {
                    sessionStore.save(it)
                    user = it
                }
        }
    }
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
    val initialRemembered = remember { sessionStore.rememberedLogins().firstOrNull() }
    var username by remember { mutableStateOf(initialRemembered?.username.orEmpty()) }
    var password by remember { mutableStateOf(initialRemembered?.password.orEmpty()) }
    var displayName by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var ipThird by remember { mutableStateOf("") }
    var ipFourth by remember { mutableStateOf("") }
    var serverError by remember { mutableStateOf<String?>(null) }
    var registerMode by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var agreed by remember { mutableStateOf(false) }
    var rememberPassword by remember { mutableStateOf(!initialRemembered?.password.isNullOrBlank()) }
    var rememberedAccounts by remember { mutableStateOf(sessionStore.rememberedLogins()) }
    var accountMenuExpanded by remember { mutableStateOf(false) }
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
                    Box {
                        OutlinedTextField(
                            username,
                            { username = it; accountMenuExpanded = false },
                            modifier = Modifier.fillMaxWidth(),
                            placeholder = { Text("账号") },
                            singleLine = true,
                            trailingIcon = {
                                if (rememberedAccounts.isNotEmpty()) {
                                    IconButton(onClick = { accountMenuExpanded = true }) {
                                        Icon(
                                            Icons.Default.KeyboardArrowDown,
                                            contentDescription = "选择已记住账号",
                                            tint = Muted,
                                        )
                                    }
                                }
                            },
                        )
                        DropdownMenu(
                            expanded = accountMenuExpanded,
                            onDismissRequest = { accountMenuExpanded = false },
                        ) {
                            rememberedAccounts.forEach { account ->
                                DropdownMenuItem(
                                    text = { Text(account.username, fontSize = 16.sp) },
                                    onClick = {
                                        username = account.username
                                        password = account.password.orEmpty()
                                        rememberPassword = !account.password.isNullOrBlank()
                                        accountMenuExpanded = false
                                    },
                                )
                            }
                            DropdownMenuItem(
                                text = { Text("清除已记账号", color = Muted) },
                                onClick = {
                                    sessionStore.clearRememberedLogins()
                                    rememberedAccounts = emptyList()
                                    accountMenuExpanded = false
                                    username = ""
                                    password = ""
                                    rememberPassword = false
                                },
                            )
                        }
                    }
                    if (registerMode) {
                        OutlinedTextField(displayName, { displayName = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("姓名") }, singleLine = true)
                    }
                    OutlinedTextField(password, { password = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("密码") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                    if (registerMode) {
                        OutlinedTextField(confirmPassword, { confirmPassword = it }, modifier = Modifier.fillMaxWidth(), placeholder = { Text("确认密码") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = agreed, onCheckedChange = { agreed = it })
                            Text("我已阅读并同意《用户协议》", color = Muted, fontSize = 14.sp, modifier = Modifier.clickable { agreed = !agreed })
                        }
                    } else {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(checked = rememberPassword, onCheckedChange = { rememberPassword = it })
                                Text(
                                    "记住密码",
                                    color = Ink,
                                    fontSize = 15.sp,
                                    modifier = Modifier.clickable { rememberPassword = !rememberPassword },
                                )
                            }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(checked = agreed, onCheckedChange = { agreed = it })
                                Text("我已阅读并同意《用户协议》", color = Muted, fontSize = 14.sp, modifier = Modifier.clickable { agreed = !agreed })
                            }
                        }
                    }
                    error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
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
                                    .onSuccess {
                                        sessionStore.saveRememberedLogin(
                                            username.trim(),
                                            password,
                                            rememberPassword,
                                        )
                                        sessionStore.save(it)
                                        onLoggedIn(it)
                                    }
                                    .onFailure { error = it.message }
                            }
                        }
                    }, modifier = Modifier.fillMaxWidth()) { Text(if (registerMode) "提交注册申请" else "登录") }
                    if (!registerMode) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            TextButton(
                                onClick = { showForgotDialog = true },
                                modifier = Modifier.padding(start = 0.dp),
                            ) { Text("忘记密码", color = Green) }
                            TextButton(onClick = { registerMode = true; error = null }) { Text("帐号注册", color = Green) }
                            TextButton(onClick = { showAgreementDialog = true }) { Text("用户协议", color = Green) }
                        }
                    } else {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            TextButton(
                                onClick = { registerMode = false; error = null },
                                modifier = Modifier.padding(start = 0.dp),
                            ) { Text("返回登录", color = Green) }
                            TextButton(onClick = { showAgreementDialog = true }) { Text("用户协议", color = Green) }
                        }
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
private fun StoredImage(
    fileId: String?,
    previewUri: String? = null,
    repository: MilkRepository,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    onClick: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    var bitmap by remember(fileId, previewUri) { mutableStateOf<ImageBitmap?>(null) }

    androidx.compose.runtime.LaunchedEffect(fileId, previewUri) {
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
        if (fileId.isNullOrBlank()) return@LaunchedEffect
        val bytes = runCatching { repository.loadFileBytes(fileId) }.getOrNull()
        bitmap = bytes
            ?.takeIf { it.isNotEmpty() }
            ?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }

    Box(
        modifier = if (onClick == null) {
            modifier.background(Color(0xFFF1F5F4))
        } else {
            modifier.background(Color(0xFFF1F5F4)).clickable(onClick = onClick)
        },
        contentAlignment = Alignment.Center,
    ) {
        val image = bitmap
        if (image != null) {
            Image(
                bitmap = image,
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = contentScale,
            )
        } else {
            Icon(Icons.Default.Inventory2, contentDescription = null, tint = Muted)
        }
    }
}

@Composable
private fun ImagePreviewDialog(
    target: ImagePreviewTarget,
    repository: MilkRepository,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("图片预览") },
        text = {
            StoredImage(
                fileId = target.fileId,
                previewUri = target.previewUri,
                repository = repository,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(460.dp)
                    .clip(RoundedCornerShape(10.dp)),
                contentScale = ContentScale.Fit,
            )
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("关闭") }
        },
    )
}

@Composable
private fun ImageThumbnail(
    fileId: String? = null,
    previewUri: String? = null,
    repository: MilkRepository,
    onClick: () -> Unit,
    onDelete: (() -> Unit)? = null,
    size: Dp = 104.dp,
) {
    Box(modifier = Modifier.size(size)) {
        StoredImage(
            fileId = fileId,
            previewUri = previewUri,
            repository = repository,
            modifier = Modifier
                .fillMaxSize()
                .clip(RoundedCornerShape(10.dp))
                .border(1.dp, Color(0xFFDDE5E3), RoundedCornerShape(10.dp)),
            onClick = onClick,
        )
        if (onDelete != null) {
            IconButton(
                onClick = onDelete,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(5.dp)
                    .size(28.dp)
                    .background(Color(0xCC17202B), CircleShape),
            ) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "删除图片",
                    tint = Color.White,
                    modifier = Modifier.size(16.dp),
                )
            }
        }
    }
}

@Composable
private fun EditableImageStrip(
    existingFileIds: List<String>,
    localUris: List<String>,
    repository: MilkRepository,
    onPreview: (ImagePreviewTarget) -> Unit,
    onDeleteExisting: (String) -> Unit,
    onDeleteLocal: (String) -> Unit,
) {
    if (existingFileIds.isEmpty() && localUris.isEmpty()) {
        Text("暂无图片", color = Muted, fontSize = 14.sp)
        return
    }
    LazyRow(
        modifier = Modifier.fillMaxWidth().height(112.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(existingFileIds, key = { "existing-$it" }) { fileId ->
            ImageThumbnail(
                fileId = fileId,
                repository = repository,
                onClick = { onPreview(ImagePreviewTarget(fileId = fileId)) },
                onDelete = { onDeleteExisting(fileId) },
            )
        }
        items(localUris, key = { "local-$it" }) { uri ->
            ImageThumbnail(
                previewUri = uri,
                repository = repository,
                onClick = { onPreview(ImagePreviewTarget(previewUri = uri)) },
                onDelete = { onDeleteLocal(uri) },
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
    val cameraLauncher = rememberLauncherForActivityResult(EvidenceTakePicture()) { saved ->
        val uri = cameraOutputUri
        if (saved && uri != null) selectedAvatarUri = uri.toString()
    }
    val launchCamera = cameraPermissionLauncher {
        val output = createCameraOutput(context)
        cameraOutputUri = output.uri
        runCatching { cameraLauncher.launch(output.uri) }
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
    var isRefreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    suspend fun refreshData() {
        orders = repository.listWorkOrders()
        products = repository.listProducts()
    }
    val refreshDataWithFeedback: () -> Unit = {
        if (!isRefreshing) {
            isRefreshing = true
            scope.launch {
                runCatching { refreshData() }
                    .onFailure {
                        Toast.makeText(context, "刷新失败，请检查网络后重试", Toast.LENGTH_SHORT).show()
                    }
                isRefreshing = false
            }
        }
    }
    androidx.compose.runtime.LaunchedEffect(Unit) {
        runCatching { refreshData() }
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
                "工单" -> OrderListScreen(
                    orders = orders,
                    isRefreshing = isRefreshing,
                    onRefresh = refreshDataWithFeedback,
                    onCreate = { showCreateDialog = true },
                ) { order ->
                    selectedOrderNo = order.orderNo
                    selected = "详情"
                }
                "详情" -> OrderDetailScreen(
                    order = orders.firstOrNull { it.orderNo == selectedOrderNo },
                    repository = repository,
                    currentUserId = currentUser.id,
                    operatorName = currentUser.displayName,
                    canApprove = currentUser.role == UserRole.ADMIN,
                    onBack = { selected = "工单" },
                    onUpdated = { updated -> orders = orders.map { if (it.orderNo == updated.orderNo) updated else it } },
                )
                "辅料与配方" -> AdminMasterDataScreen(repository)
                else -> DashboardScreen(
                    orders = orders,
                    isRefreshing = isRefreshing,
                    onRefresh = refreshDataWithFeedback,
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DashboardScreen(
    orders: List<WorkOrder>,
    isRefreshing: Boolean,
    onRefresh: () -> Unit,
    onCreate: () -> Unit,
    openOrders: () -> Unit,
    openOrder: (WorkOrder) -> Unit,
) {
    val recentOrders = orders.filter { it.status != WorkOrderStatus.CANCELLED && it.status != WorkOrderStatus.DELETED }
    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = onRefresh,
        modifier = Modifier.fillMaxSize(),
    ) {
        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(30.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Column { Text("工作台", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold); Text("今天的称量任务概览", color = Muted, fontSize = 15.sp) }; Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { Button(onClick = onCreate) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("新建工单") }; OutlinedButton(onClick = onRefresh, enabled = !isRefreshing) { Text(if (isRefreshing) "刷新中" else "刷新") } } }
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) { StatCard("今日工单", orders.count { it.status != WorkOrderStatus.CANCELLED && it.status != WorkOrderStatus.DELETED }.toString(), "生产称量任务"); StatCard("执行中", orders.count { it.status == WorkOrderStatus.IN_PROGRESS }.toString(), "现场正在称重"); StatCard("待审批", orders.count { it.status == WorkOrderStatus.PENDING_APPROVAL }.toString(), "需要及时处理") }
            Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(modifier = Modifier.fillMaxWidth().padding(22.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("最近工单", color = Ink, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.weight(1f))
                        Text("查看全部", color = Green, modifier = Modifier.clickable(onClick = openOrders))
                    }
                    LazyColumn(
                        modifier = Modifier.fillMaxWidth().height(264.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        if (recentOrders.isEmpty()) {
                            item { Text("暂无工单", color = Muted, fontSize = 14.sp) }
                        } else {
                            items(recentOrders, key = { it.orderNo }) { order ->
                                RecentOrderRow(order) { openOrder(order) }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable private fun StatCard(title: String, value: String, detail: String) { Card(modifier = Modifier.width(220.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) { Column(Modifier.padding(18.dp)) { Text(title, color = Muted); Text(value, color = Ink, fontSize = 30.sp, fontWeight = FontWeight.Bold); Text(detail, color = Green, fontSize = 13.sp) } } }

@Composable
private fun RecentOrderRow(order: WorkOrder, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().height(48.dp).clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF8FAF9)),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier.size(32.dp).background(Color(0xFFEAF6F0), RoundedCornerShape(8.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Default.Assignment, null, tint = Green, modifier = Modifier.size(18.dp))
            }
            Column(modifier = Modifier.padding(start = 12.dp).weight(1f)) {
                Text(
                    "${order.productName} · ${order.operatorName}",
                    color = Ink,
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    maxLines = 1,
                )
                Text(
                    "${order.orderNo} · 进度 ${order.completedSteps}/${order.totalSteps} · ${order.updatedAt}",
                    color = Muted,
                    fontSize = 12.sp,
                    maxLines = 1,
                )
            }
            StatusPill(order.status)
            Icon(
                Icons.Default.ArrowForward,
                null,
                tint = Muted,
                modifier = Modifier.padding(start = 10.dp).size(18.dp),
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OrderListScreen(
    orders: List<WorkOrder>,
    isRefreshing: Boolean,
    onRefresh: () -> Unit,
    onCreate: () -> Unit,
    openDetail: (WorkOrder) -> Unit,
) {
    var filter by remember { mutableStateOf<String?>(null) }
    var page by remember { mutableStateOf(1) }
    val pageSize = 8
    val filterOptions = listOf("全部") + WorkOrderStatus.entries
        .filter { it != WorkOrderStatus.DELETED }
        .map { it.label }
    val filteredOrders = orders
        .sortedBy { it.status == WorkOrderStatus.CANCELLED || it.status == WorkOrderStatus.DELETED }
        .filter { filter == null || filter == "全部" || it.status.label == filter }
    val totalPages = maxOf(1, (filteredOrders.size + pageSize - 1) / pageSize)
    val safePage = page.coerceIn(1, totalPages)
    val pagedOrders = filteredOrders.drop((safePage - 1) * pageSize).take(pageSize)
    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = onRefresh,
        modifier = Modifier.fillMaxSize(),
    ) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(30.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Column {
                        Text("工单管理", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                        Text("查看和继续现场称量任务", color = Muted, modifier = Modifier.padding(top = 6.dp))
                    }
                    Button(onClick = onCreate) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("新建工单") }
                }
            }
            item {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(top = 6.dp, bottom = 6.dp),
                ) {
                    filterOptions.forEach { option ->
                        val selected = (filter ?: "全部") == option
                        Text(
                            option,
                            modifier = Modifier
                                .clickable {
                                    filter = if (option == "全部") null else option
                                    page = 1
                                }
                                .background(if (selected) Green.copy(alpha = 0.12f) else Color.White, RoundedCornerShape(50))
                                .border(1.dp, if (selected) Green.copy(alpha = 0.45f) else Color(0xFFE3E8EA), RoundedCornerShape(50))
                                .padding(horizontal = 16.dp, vertical = 8.dp),
                            color = if (selected) Green else Muted,
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        )
                    }
                }
            }
            if (pagedOrders.isEmpty()) {
                item { Text("暂无工单", color = Muted, fontSize = 14.sp) }
            } else {
                items(pagedOrders, key = { it.orderNo }) { order ->
                    OrderRow(order) { openDetail(order) }
                }
            }
            item {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedButton(
                        onClick = { page = safePage - 1 },
                        enabled = safePage > 1,
                    ) {
                        Icon(Icons.Default.ChevronLeft, null)
                        Spacer(Modifier.width(4.dp))
                        Text("上一页")
                    }
                    Text(
                        "第 $safePage / $totalPages 页 · 共 ${filteredOrders.size} 条",
                        color = Muted,
                        fontSize = 13.sp,
                        modifier = Modifier.padding(horizontal = 16.dp),
                    )
                    OutlinedButton(
                        onClick = { page = safePage + 1 },
                        enabled = safePage < totalPages,
                    ) {
                        Text("下一页")
                        Spacer(Modifier.width(4.dp))
                        Icon(Icons.Default.ChevronRight, null)
                    }
                }
            }
        }
    }
}

@Composable
private fun OrderRow(order: WorkOrder, onClick: () -> Unit = {}) { Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick), colors = CardDefaults.cardColors(containerColor = Color.White)) { Row(modifier = Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(42.dp).background(Color(0xFFEAF6F0), RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Default.Assignment, null, tint = Green) }; Column(Modifier.padding(start = 14.dp).weight(1f)) { Text(order.productName, color = Ink, fontWeight = FontWeight.Bold, fontSize = 16.sp); Text("${order.orderNo} · ${order.targetWeightKg.toInt()} kg · ${order.operatorName}", color = Muted, fontSize = 13.sp); Text("进度 ${order.completedSteps}/${order.totalSteps} · ${order.updatedAt}", color = Muted, fontSize = 13.sp) }; StatusPill(order.status); Icon(Icons.Default.ArrowForward, null, tint = Muted, modifier = Modifier.padding(start = 12.dp)) } } }

@Composable private fun StatusPill(status: WorkOrderStatus) { val color = when (status) { WorkOrderStatus.IN_PROGRESS -> Color(0xFFC9854C); WorkOrderStatus.COMPLETED -> Green; WorkOrderStatus.CANCELLED, WorkOrderStatus.DELETED -> Color(0xFFC7473C); else -> Color(0xFF68808E) }; Text(status.label, color = color, fontWeight = FontWeight.Bold, modifier = Modifier.background(color.copy(alpha = .1f), RoundedCornerShape(50)).padding(horizontal = 12.dp, vertical = 7.dp)) }

@Composable
private fun OrderDetailScreen(
    order: WorkOrder?,
    repository: MilkRepository,
    currentUserId: Int,
    operatorName: String,
    canApprove: Boolean,
    onBack: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    var actionStepNo by remember { mutableStateOf<Int?>(null) }
    var requestAction by remember { mutableStateOf<String?>(null) }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(30.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
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
            val canRequest = order.pendingRequest == null &&
                order.status != WorkOrderStatus.COMPLETED &&
                order.status != WorkOrderStatus.CANCELLED &&
                order.status != WorkOrderStatus.DELETED
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
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
                if (canRequest) {
                    if (order.operatorId != currentUserId && order.createdBy != currentUserId) {
                        OutlinedButton(onClick = { requestAction = "接管" }) { Text("申请接管") }
                    }
                    OutlinedButton(onClick = { requestAction = "撤销" }) { Text("申请撤销") }
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
                operatorName = operatorName,
                repository = repository,
                canApprove = canApprove,
                onDismiss = { actionStepNo = null },
                onUpdated = { updated -> onUpdated(updated); actionStepNo = null },
            )
            StepStatus.WEIGHING -> WeightDialog(
                order = order,
                step = actionStep,
                operatorName = operatorName,
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
    operatorName: String,
    repository: MilkRepository,
    canApprove: Boolean,
    onDismiss: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    val approvalMode = step.status == StepStatus.TYPE_CONFIRMATION
    var materialId by remember { mutableStateOf("") }
    var reason by remember { mutableStateOf("") }
    var photoUri by remember { mutableStateOf<String?>(null) }
    var cameraOutputPath by rememberSaveable { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val cameraLauncher = rememberLauncherForActivityResult(EvidenceTakePicture()) { saved ->
        val outputFile = cameraOutputPath?.let(::File)
        val captured = outputFile != null && (saved || outputFile.length() > 0L)
        if (captured) {
            working = true
            error = null
            materialId = ""
            reason = ""
            photoUri = null
            scope.launch {
                runCatching {
                    processCapturedEvidence(
                        context = context,
                        sourceFile = outputFile,
                        watermarkLines = evidenceWatermarkLines(order, step, operatorName, "类型确认"),
                        scanQr = true,
                    )
                }.onSuccess { processed ->
                    photoUri = processed.photoUri
                    materialId = processed.scannedMaterialId.orEmpty()
                }.onFailure {
                    error = "照片处理失败：${it.message}"
                }
                working = false
            }
        } else if (saved) {
            error = "相机未返回有效照片，请重新拍摄"
        }
    }
    val launchEvidenceCamera = cameraPermissionLauncher {
        val output = createCameraOutput(context)
        cameraOutputPath = output.file.absolutePath
        runCatching { cameraLauncher.launch(output.uri) }
            .onFailure { error = "无法启动相机：${it.message}" }
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text("类型确认 · 步骤 ${step.stepNo}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("当前步骤要求：${step.materialName} · ${step.materialCode}", color = Ink, fontWeight = FontWeight.Bold)
                Text("应称 ${step.requiredWeightKg} kg · 允差 ±${step.toleranceKg} kg", color = Muted)
                if (approvalMode) {
                    Text("已提交无码拍照申请，等待后台审批。", color = Muted)
                } else {
                    OutlinedButton(
                        onClick = launchEvidenceCamera,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !working,
                    ) {
                        Icon(Icons.Default.CameraAlt, null)
                        Spacer(Modifier.width(6.dp))
                        Text(if (photoUri == null) "拍照扫码" else "重新拍照扫码")
                    }
                    if (working) {
                        Text("正在处理照片并识别二维码...", color = Muted)
                    }
                    if (photoUri != null && !working) {
                        if (materialId.isNotBlank()) {
                            Text("二维码识别结果：$materialId", color = Ink, fontWeight = FontWeight.Bold)
                        } else {
                            Text("未识别到二维码，可填写原因后提交后台拍照审批。", color = Color(0xFFC9854C), fontSize = 14.sp)
                            OutlinedTextField(
                                reason,
                                { reason = it; error = null },
                                modifier = Modifier.fillMaxWidth(),
                                label = { Text("放行原因") },
                                singleLine = true,
                            )
                        }
                    }
                }
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            when {
                approvalMode -> Button(onClick = {
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
                materialId.isNotBlank() -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.confirmStepQr(order.orderNo, step.stepNo, materialId, photoUri.orEmpty()) }
                                .onSuccess { onUpdated(it) }
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working && photoUri != null) { Text("确认类型") }
                photoUri != null -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.requestStepPhotoApproval(order.orderNo, step.stepNo, reason, photoUri.orEmpty()) }
                                .onSuccess { onUpdated(it) }
                                .onFailure { error = it.message }
                                .also { working = false }
                        }
                    }
                }, enabled = !working && reason.isNotBlank()) { Text("提交拍照申请") }
                else -> Button(onClick = {}, enabled = false) { Text("请先拍照扫码") }
            }
        },
        dismissButton = { TextButton(onClick = { if (!working) onDismiss() }) { Text("取消") } },
    )
}

@Composable
private fun WeightDialog(
    order: WorkOrder,
    step: WorkOrderStep,
    operatorName: String,
    repository: MilkRepository,
    onDismiss: () -> Unit,
    onUpdated: (WorkOrder) -> Unit,
) {
    var weightText by remember { mutableStateOf("") }
    var photoName by remember { mutableStateOf("") }
    var photoUri by remember { mutableStateOf<String?>(null) }
    var cameraOutputPath by rememberSaveable { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var result by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val cameraLauncher = rememberLauncherForActivityResult(EvidenceTakePicture()) { saved ->
        val outputFile = cameraOutputPath?.let(::File)
        val captured = outputFile != null && (saved || outputFile.length() > 0L)
        if (captured) {
            working = true
            error = null
            photoUri = null
            photoName = ""
            scope.launch {
                runCatching {
                    processCapturedEvidence(
                        context = context,
                        sourceFile = outputFile,
                        watermarkLines = evidenceWatermarkLines(order, step, operatorName, "电子秤读数"),
                        scanQr = false,
                    )
                }.onSuccess { processed ->
                    photoUri = processed.photoUri
                    photoName = "现场拍摄"
                }.onFailure {
                    error = "照片处理失败：${it.message}"
                }
                working = false
            }
        } else if (saved) {
            error = "相机未返回有效照片，请重新拍摄"
        }
    }
    val launchEvidenceCamera = cameraPermissionLauncher {
        val output = createCameraOutput(context)
        cameraOutputPath = output.file.absolutePath
        runCatching { cameraLauncher.launch(output.uri) }
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
                OutlinedButton(
                    onClick = launchEvidenceCamera,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !working,
                ) {
                    Icon(Icons.Default.CameraAlt, null)
                    Spacer(Modifier.width(6.dp))
                    Text(if (photoUri == null) "拍摄电子秤读数" else "重新拍摄")
                }
                if (working) Text("正在处理照片...", color = Muted)
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
            }, enabled = !working && photoUri != null && weightText.isNotBlank()) { Text("提交称重") }
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
        else -> "申请撤销工单"
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
                                else -> repository.requestCancel(order.orderNo, reason)
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

private data class ImagePreviewTarget(
    val fileId: String? = null,
    val previewUri: String? = null,
)

@Composable
private fun AdminMasterDataScreen(repository: MilkRepository) {
    var tab by remember { mutableStateOf("辅料") }
    var materials by remember { mutableStateOf<List<Material>>(emptyList()) }
    var recipes by remember { mutableStateOf<List<ProductRecipe>>(emptyList()) }
    var showMaterialDialog by remember { mutableStateOf(false) }
    var editingMaterial by remember { mutableStateOf<Material?>(null) }
    var viewingMaterial by remember { mutableStateOf<Material?>(null) }
    var showRecipeDialog by remember { mutableStateOf(false) }
    var editingRecipe by remember { mutableStateOf<ProductRecipe?>(null) }
    var previewImage by remember { mutableStateOf<ImagePreviewTarget?>(null) }
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
                            StoredImage(
                                fileId = material.existingImageFileIds.firstOrNull(),
                                repository = repository,
                                modifier = Modifier
                                    .size(58.dp)
                                    .clip(RoundedCornerShape(9.dp))
                                    .border(1.dp, Color(0xFFDDE5E3), RoundedCornerShape(9.dp)),
                            )
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("${material.nameZh} · ${material.materialCode}", color = Ink, fontWeight = FontWeight.Bold)
                                Text("${material.materialId} · 保质期 ${material.shelfLifeMonths} 个月", color = Muted, fontSize = 14.sp)
                                Text("${materialImageCount(material)} 张包装图片", color = Muted, fontSize = 14.sp)
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                TextButton(
                                    onClick = { viewingMaterial = material },
                                    enabled = materialImageCount(material) > 0,
                                ) {
                                    Icon(Icons.Default.PhotoLibrary, null, modifier = Modifier.size(17.dp))
                                    Spacer(Modifier.width(5.dp))
                                    Text("查看图片")
                                }
                                TextButton(onClick = { editingMaterial = material }) { Text("编辑") }
                            }
                        }
                    }
                }
            }
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(recipes, key = { it.id }) { recipe ->
                    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                            StoredImage(
                                fileId = recipe.imageFileId,
                                repository = repository,
                                modifier = Modifier
                                    .size(58.dp)
                                    .clip(RoundedCornerShape(9.dp))
                                    .border(1.dp, Color(0xFFDDE5E3), RoundedCornerShape(9.dp)),
                                onClick = recipe.imageFileId?.let { fileId ->
                                    { previewImage = ImagePreviewTarget(fileId = fileId) }
                                },
                            )
                            Spacer(Modifier.width(14.dp))
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
    viewingMaterial?.let { material ->
        MaterialImagesDialog(
            material = material,
            repository = repository,
            onDismiss = { viewingMaterial = null },
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
    previewImage?.let { target ->
        ImagePreviewDialog(
            target = target,
            repository = repository,
            onDismiss = { previewImage = null },
        )
    }
}

private fun materialImageCount(material: Material): Int {
    val localCount = material.imageNames.count(::isLocalImageUri)
    val imageCount = material.existingImageFileIds.size + localCount
    return if (imageCount > 0) imageCount else material.imageNames.size
}

private fun isLocalImageUri(value: String): Boolean =
    value.startsWith("content://") || value.startsWith("file://")

@Composable
private fun MaterialImagesDialog(
    material: Material,
    repository: MilkRepository,
    onDismiss: () -> Unit,
) {
    var previewTarget by remember { mutableStateOf<ImagePreviewTarget?>(null) }
    val localUris = material.imageNames.filter(::isLocalImageUri)

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("${material.nameZh} 包装图片") },
        text = {
            if (material.existingImageFileIds.isEmpty() && localUris.isEmpty()) {
                Text("暂无包装图片", color = Muted)
            } else {
                LazyRow(
                    modifier = Modifier.fillMaxWidth().height(128.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(material.existingImageFileIds, key = { "view-$it" }) { fileId ->
                        ImageThumbnail(
                            fileId = fileId,
                            repository = repository,
                            onClick = { previewTarget = ImagePreviewTarget(fileId = fileId) },
                            size = 120.dp,
                        )
                    }
                    items(localUris, key = { "view-local-$it" }) { uri ->
                        ImageThumbnail(
                            previewUri = uri,
                            repository = repository,
                            onClick = { previewTarget = ImagePreviewTarget(previewUri = uri) },
                            size = 120.dp,
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("关闭") }
        },
    )
    previewTarget?.let { target ->
        ImagePreviewDialog(
            target = target,
            repository = repository,
            onDismiss = { previewTarget = null },
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
    var existingImageIds by remember(material?.materialId) {
        mutableStateOf(material?.existingImageFileIds ?: emptyList())
    }
    var newImageUris by remember(material?.materialId) { mutableStateOf(emptyList<String>()) }
    var previewTarget by remember { mutableStateOf<ImagePreviewTarget?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        newImageUris = (newImageUris + uris.map(Uri::toString)).distinct()
    }
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text(if (material == null) "新增辅料" else "编辑辅料") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 540.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                OutlinedTextField(code, { code = it.uppercase() }, modifier = Modifier.fillMaxWidth(), label = { Text("内部代号") }, singleLine = true)
                OutlinedTextField(nameZh, { nameZh = it }, modifier = Modifier.fillMaxWidth(), label = { Text("中文名称") }, singleLine = true)
                OutlinedTextField(nameEn, { nameEn = it }, modifier = Modifier.fillMaxWidth(), label = { Text("英文名称（可选）") }, singleLine = true)
                OutlinedTextField(shelfLife, { shelfLife = it.filter(Char::isDigit) }, modifier = Modifier.fillMaxWidth(), label = { Text("保质期（月）") }, singleLine = true)
                OutlinedButton(onClick = { imagePicker.launch("image/*") }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.CameraAlt, null)
                    Spacer(Modifier.width(6.dp))
                    Text("添加包装图片")
                }
                EditableImageStrip(
                    existingFileIds = existingImageIds,
                    localUris = newImageUris,
                    repository = repository,
                    onPreview = { previewTarget = it },
                    onDeleteExisting = { fileId -> existingImageIds = existingImageIds - fileId },
                    onDeleteLocal = { uri -> newImageUris = newImageUris - uri },
                )
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
                                    imageNames = newImageUris,
                                    existingImageFileIds = existingImageIds,
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
    previewTarget?.let { target ->
        ImagePreviewDialog(
            target = target,
            repository = repository,
            onDismiss = { previewTarget = null },
        )
    }
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
    var existingImageFileId by remember(recipe?.id) { mutableStateOf(recipe?.imageFileId) }
    var selectedImageUri by remember(recipe?.id) { mutableStateOf<String?>(null) }
    var previewTarget by remember { mutableStateOf<ImagePreviewTarget?>(null) }
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
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        selectedImageUri = uri?.toString()
    }
    val hasImage = !selectedImageUri.isNullOrBlank() || !existingImageFileId.isNullOrBlank()
    AlertDialog(
        onDismissRequest = { if (!working) onDismiss() },
        title = { Text(if (recipe == null) "新增产品配方" else "编辑产品配方") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 540.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                OutlinedTextField(name, { name = it }, modifier = Modifier.fillMaxWidth(), label = { Text("产品名称") }, singleLine = true)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = enabled, onCheckedChange = { enabled = it })
                    Text(if (enabled) "配方启用" else "配方停用", color = Muted)
                }
                Text("产品图片（选填）", color = Ink, fontWeight = FontWeight.Bold)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    StoredImage(
                        fileId = existingImageFileId,
                        previewUri = selectedImageUri,
                        repository = repository,
                        modifier = Modifier
                            .size(96.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .border(1.dp, Color(0xFFDDE5E3), RoundedCornerShape(10.dp)),
                        onClick = if (hasImage) {
                            { previewTarget = ImagePreviewTarget(existingImageFileId, selectedImageUri) }
                        } else {
                            null
                        },
                    )
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        OutlinedButton(onClick = { imagePicker.launch("image/*") }) {
                            Icon(Icons.Default.PhotoLibrary, null, modifier = Modifier.size(17.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(if (hasImage) "更换图片" else "选择图片")
                        }
                        if (hasImage) {
                            TextButton(onClick = {
                                existingImageFileId = null
                                selectedImageUri = null
                            }) { Text("删除图片") }
                        }
                    }
                }
                if (materials.isEmpty()) {
                    Text("请先创建辅料，再添加产品配方。", color = Muted)
                } else {
                    items.forEachIndexed { index, item ->
                        val material = materials.firstOrNull { it.materialId == item.materialId }
                        Box(modifier = Modifier.fillMaxWidth()) {
                            OutlinedButton(onClick = { expandedIndex = index }, modifier = Modifier.fillMaxWidth()) {
                                Text(material?.let { "${it.nameZh} (${it.materialCode})" } ?: "请选择辅料", modifier = Modifier.weight(1f), color = Ink)
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
                            val imageFileId = selectedImageUri?.let { repository.uploadImage(it) } ?: existingImageFileId
                            val saved = repository.saveProductRecipe(
                                ProductRecipe(
                                    id = recipe?.id ?: 0,
                                    name = name,
                                    enabled = enabled,
                                    items = parsedItems,
                                    imageFileId = imageFileId,
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
    previewTarget?.let { target ->
        ImagePreviewDialog(
            target = target,
            repository = repository,
            onDismiss = { previewTarget = null },
        )
    }
}
