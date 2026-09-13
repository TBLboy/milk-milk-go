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
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContract
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandHorizontally
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkHorizontally
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
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
import androidx.compose.material.icons.filled.BugReport
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
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.material3.ripple
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
import androidx.compose.ui.draw.clipToBounds
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
import androidx.exifinterface.media.ExifInterface
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
private const val UserAgreementVersion = "1.1"
private val UserAgreementText = """
    牧衡辅料称重防错系统用户协议

    版本：V$UserAgreementVersion
    生效日期：2026年9月13日

    特别提示
    1. 本系统是部署在系统使用单位内部网络中的生产辅助管理系统，用于辅料主数据、产品配方、工单、辅料类型确认、称重记录、审批、标签打印和追溯查询。本系统不连接金蝶系统，不以面向社会公众的互联网平台形式提供服务。
    2. 用户在注册、登录或使用本系统前，应完整阅读并理解本协议。用户勾选“我已阅读并同意《用户协议》”，或实际注册、登录、使用本系统，即表示已阅读、理解并同意接受本协议约束。
    3. 本系统用于辅助生产管理和留痕，不能替代使用单位的岗位标准操作流程、食品安全管理、计量管理、质量控制、安全生产制度以及国家法律法规。用户仍应对实际领料、称量、投料和审批行为承担相应责任。

    一、定义
    1. “运营方”指部署、管理和使用本系统并负责账号、业务数据及现场管理的单位。
    2. “用户”指经运营方批准并取得账号，依法依规使用本系统的管理员或普通操作员。
    3. “业务数据”指产品、配方、辅料、工单、生产步骤、称量结果、审批结论、标签及设置等数据。
    4. “操作证据”指用户通过本系统形成或提交的现场照片、二维码识别结果、称重数据、水印信息、操作日志及其他可追溯记录。
    5. “管理员”指经运营方授权，能够维护主数据、账号、审批事项、标签和系统设置的用户。

    二、账号申请、审批与权限
    1. 平板端注册的账号默认为普通操作员账号。注册申请须经管理员审批，审批通过后方可登录和使用相应功能。
    2. 管理员账号应由运营方预先配置或授权，不通过公开注册方式产生。系统按照账号角色分配功能权限，用户不得越权访问、修改或导出数据。
    3. 用户应提供真实、准确、完整的账号资料，并在资料发生变化时及时更新。不得冒用他人身份，不得使用虚假身份或虚假资料注册账号。
    4. 账号原则上仅供本人使用。用户不得出借、转让、共享账号，不得允许他人以本人账号实施操作。
    5. 用户应妥善保管账号和密码，避免在公共设备或无人值守状态下保持登录。发现账号被盗用、密码泄露或存在其他安全风险时，应立即联系管理员处理。
    6. 管理员可以依照运营方管理制度创建、审批、停用账号或重置密码。因离职、调岗、权限变化或安全风险，运营方有权及时调整或终止账号权限。

    三、系统使用规则
    1. 用户应当按照运营方批准的工单、配方、操作顺序和权限执行任务，不得擅自跳过步骤、变更配方、替换辅料或绕过审批。
    2. 辅料类型确认应使用系统提供的现场“拍照扫码”功能。系统从本次现场拍摄的照片中解析二维码，并使用该照片作为操作证据。用户不得使用历史照片、相册图片、截图或伪造图片代替现场拍摄。
    3. 重量确认应以实际称量结果为准。第一版系统不直接连接电子秤，用户须人工输入称量读数，并拍摄能够辨认电子秤读数的现场照片。用户应对输入数据和照片真实性负责。
    4. 用户不得篡改、遮挡、删除或伪造系统水印、时间、操作人员、工单、步骤、辅料、二维码、重量和审批记录，不得通过技术手段规避类型校验、重量允差或审批流程。
    5. 管理员应准确维护辅料、产品配方、标签和账号资料。主数据发生变化时，应以书面制度、审批记录或其他可靠依据为基础，确保后续生产使用最新有效数据。
    6. 工单应按顺序完成全部辅料步骤，并在类型确认、称重证据等必要信息完整后方可提交完成。撤销或终止工单不删除历史记录，相关操作继续保留用于追溯。
    7. 用户发现二维码异常、辅料包装不一致、称量超差、设备故障、网络中断、数据冲突或其他可能影响生产安全的情况时，应停止相关操作并按运营方制度报告，不得隐瞒或强行绕过。

    四、个人信息与数据处理
    1. 为实现账号管理、身份核验、生产追溯、质量审计、安全管理和系统运维，系统可能处理用户提供的姓名或显示名、账号、电话、工号、头像，以及用户在使用过程中形成的登录记录、设备或网络信息、操作日志、工单记录、审批记录、称重数据和现场照片。
    2. 运营方按照合法、正当、必要和诚信原则处理个人信息，处理目的包括履行内部管理职责、保障食品安全和生产追溯、维护系统安全、处理争议及履行法律法规要求的义务。
    3. 系统不采集、不保存身份证件号码。工号用于内部账号识别和生产追溯，普通用户仅可查看本人工号，管理员可按内部制度维护工号。
    4. 现场照片可能包含人员、辅料、电子秤读数或生产环境信息。用户应避免拍摄与业务无关的人员面部、私密信息或其他不必要内容。相关照片仅用于生产管理、追溯、审计和异常核查，未经授权不得对外提供。
    5. 本系统原则上在运营方内部网络运行，不主动将业务数据上传至互联网。用户主动提交 BUG 反馈时，系统会将问题描述、所选图片、提交账号及必要的技术信息发送至运营方配置的指定维护邮箱，用于问题排查和系统维护。
    6. 生产工单、称重记录、审批记录、操作证据和审计日志按照运营方的追溯要求长期保存。第一版不提供物理删除功能。因法律法规、食品安全追溯、审计或争议处理需要，运营方可以在必要期限内继续保存相关记录。
    7. 用户可以通过管理员或运营方提供的内部渠道，依法申请查询、更正本人资料或提出个人信息相关请求。对于依法必须保存的业务记录和操作证据，运营方可以不予删除，但应说明处理依据。
    8. 运营方应采取访问控制、权限校验、密码哈希、备份、日志审计等合理措施保护数据安全。任何用户不得未经授权收集、复制、导出、传播、出售或用于与本职工作无关的目的。

    五、操作记录、证据与审计
    1. 系统以服务器记录的时间作为主要审计时间。现场照片按照系统规则添加操作人员、拍摄时间、工单、步骤或辅料等水印信息。
    2. 登录、主数据修改、工单执行、类型确认、称重、审批、标签打印、备份和异常处理等关键活动可能被记录并接受审计。
    3. 操作记录和证据可用于生产追溯、质量检查、内部审计、事故调查、争议处理以及配合监管或司法机关依法开展的调查。
    4. 用户不得以任何理由要求管理员删除、修改或伪造已经形成的真实操作记录。发现记录确有错误的，应通过系统允许的更正、撤销、补充说明或异常审批流程处理，并保留原始痕迹。

    六、禁止行为
    1. 禁止利用本系统实施违反法律法规、食品安全、计量、劳动、网络与数据安全等规定的行为。
    2. 禁止未经授权访问、探测、攻击、干扰、破坏系统，或传播病毒、恶意程序及其他危害系统安全的代码。
    3. 禁止绕过权限控制，擅自修改数据库、接口数据、系统时间、审计日志、图片水印或业务状态。
    4. 禁止伪造、变造、买卖或冒用账号、二维码、标签、照片、审批意见和生产记录。
    5. 禁止擅自对系统进行反向工程、破解、批量抓取、搭建未经授权的镜像或接口，或删除、隐藏系统的权利标识。
    6. 禁止将运营方的业务数据、配方、工艺、客户信息、账号资料和现场照片用于未经授权的商业活动或对外披露。
    7. 用户违反本协议或运营方管理制度，运营方有权根据情节采取提醒、限制功能、暂停账号、终止权限、追究责任等措施；涉嫌违法的，依法移送有关机关处理。

    七、知识产权
    1. 本系统软件、界面设计、文档、标识及相关技术成果的知识产权归其合法权利人所有。未经权利人书面许可，用户不得复制、修改、发布、出租、出售、转让或用于本协议约定之外的用途。
    2. 用户录入的产品、配方、辅料、工单、生产记录和操作证据等业务数据，其权利归属及使用规则按照运营方制度、相关合同和法律规定确定。本协议不改变业务数据原有的权利归属。
    3. 用户不得因使用本系统而取得系统软件或运营方知识产权的所有权。系统在授权范围内提供的是有限、非独占、不可转让的使用权。

    八、服务提供、变更、中断与终止
    1. 本系统依赖运营方内部电脑、局域网、Android 平板、存储设备、备份和电源等环境。网络中断、设备故障、系统维护、升级、断电、容量不足或不可抗力可能导致服务暂时中断。
    2. 系统进行维护、升级或数据迁移时，运营方应尽可能提前通知用户并采取合理措施保护数据。因现场生产需要，用户可以按照运营方制度采用经批准的应急流程，但应及时补录并保留原始依据。
    3. 运营方有权根据业务、法律或安全需要调整系统功能、接口、版本和权限。影响用户重要权益的重大变更，应以合理方式通知用户；依法需要重新取得同意的，运营方应重新征得同意。
    4. 用户离职、调岗、账号停用或授权终止后，应停止使用系统，并按照运营方要求交还设备、资料和账号权限。账号终止不影响终止前已形成的操作记录和证据的依法保存。

    九、责任边界
    1. 用户应按照岗位要求核对屏幕提示、实物、电子秤读数和现场情况后再提交操作。系统校验通过不代表用户已经免除人工核对、岗位复核或质量放行义务。
    2. 因用户未按规定扫码、拍照、输入、核对、审批或保管账号，导致数据错误、生产异常或损失的，由用户及运营方按照内部制度和法律规定处理。
    3. 因不可抗力、第三方设备或网络故障、电力中断、操作系统或数据库异常等非系统运营方可合理控制的原因造成服务中断或数据延迟的，运营方应尽合理努力恢复，但依法可以免除或减轻相应责任。
    4. 运营方不对用户擅自修改系统、使用未经授权的软件或设备、泄露账号密码、传播虚假信息等行为造成的后果承担责任。
    5. 本协议中的责任限制不适用于法律禁止免除或限制的责任，也不免除因故意或重大过失依法应承担的责任。

    十、通知与联系
    1. 系统公告、后台通知、管理员通知、弹窗提示和协议更新页面均可作为有效通知方式。
    2. 用户对账号、数据、权限、个人信息或系统使用有疑问的，应通过运营方指定的内部管理员或服务渠道联系处理。

    十一、协议更新
    1. 运营方可以依据法律法规变化、监管要求、系统功能调整或内部管理制度更新本协议，并在系统中标注新版本和生效日期。
    2. 协议更新后，用户继续使用系统即表示接受更新后的协议。用户不同意更新内容的，应停止使用并联系管理员处理账号和权限。
    3. 对用户权益可能产生重大影响的变更，运营方应通过合理方式提示，必要时要求用户重新阅读并确认。

    十二、法律适用与争议解决
    1. 本协议的订立、效力、解释、履行和争议解决适用中华人民共和国大陆地区法律。
    2. 因本协议或系统使用发生争议，双方应先友好协商；协商不成的，除法律另有强制性规定外，可向运营方所在地有管辖权的人民法院提起诉讼。
    3. 本协议部分条款被认定无效、被撤销或不可执行的，不影响其他条款的效力。双方应以合法有效且最接近原条款目的的方式处理。

    十三、其他
    1. 本协议标题仅为方便阅读，不影响条款含义。
    2. 本协议与运营方依法发布的专项规则、岗位制度或单独签署的协议不一致时，以更符合法律法规且更具体的约定为准。
    3. 用户在系统中点击同意、登录或实际使用系统，即确认已获得必要的岗位授权，并愿意按照本协议及运营方制度使用本系统。
""".trimIndent()

private fun parseIpParts(url: String): Pair<String, String> {
    val match = Regex("""^http://192\.168\.(\d{1,3})\.(\d{1,3}):\d+/api/v1/?$""", RegexOption.IGNORE_CASE)
        .find(url.trim())
    return if (match == null) {
        "" to ""
    } else {
        match.groupValues[1] to match.groupValues[2]
    }
}

private data class ScannedQrPayload(
    val labelId: String,
    val materialId: String,
)

private fun extractScannedQrPayload(raw: String): ScannedQrPayload? {
    val trimmed = raw.trim()
    if (trimmed.isEmpty()) return null
    return runCatching {
        val json = JSONObject(trimmed)
        val materialId = json.optString("materialId").ifBlank { json.optString("material_id") }
        val labelId = json.optString("labelId").ifBlank { json.optString("label_id") }
        if (materialId.isBlank() || labelId.isBlank()) null else ScannedQrPayload(labelId = labelId, materialId = materialId)
    }.getOrNull()
}

private data class ProcessedEvidence(
    val photoUri: String,
    val scannedQr: ScannedQrPayload?,
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
    val scannedQr = if (scanQr) scanQrFromBitmap(bitmap)?.let(::extractScannedQrPayload) else null
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
        scannedQr = scannedQr,
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
        UserAgreementDialog(onDismiss = { showAgreementDialog = false })
    }
}

@Composable
private fun UserAgreementDialog(onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("用户协议")
                Text(
                    "版本 V$UserAgreementVersion · 生效日期 2026年9月13日",
                    color = Muted,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Normal,
                )
            }
        },
        text = {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 520.dp)
                    .verticalScroll(rememberScrollState()),
            ) {
                Text(
                    UserAgreementText,
                    color = Ink,
                    fontSize = 14.sp,
                    lineHeight = 22.sp,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭")
            }
        },
    )
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
                Text("工号：${user.employeeNo.ifBlank { "未录入" }}", color = Muted, fontSize = 15.sp)
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
    var sidebarExpanded by rememberSaveable { mutableStateOf(true) }
    var selectedOrderNo by remember { mutableStateOf<String?>(null) }
    var orders by remember { mutableStateOf<List<WorkOrder>>(emptyList()) }
    var products by remember { mutableStateOf<List<Product>>(emptyList()) }
    var showCreateDialog by remember { mutableStateOf(false) }
    var currentUser by remember { mutableStateOf(user) }
    var showProfileDialog by remember { mutableStateOf(false) }
    var showChangePasswordDialog by remember { mutableStateOf(user.mustChangePassword) }
    var showBugReportDialog by remember { mutableStateOf(false) }
    var isRefreshing by remember { mutableStateOf(false) }
    val sidebarToggleInteraction = remember { MutableInteractionSource() }
    val sidebarTogglePressed by sidebarToggleInteraction.collectIsPressedAsState()
    val sidebarToggleBackground by animateColorAsState(
        targetValue = if (sidebarTogglePressed) Color(0xFFEAF6F0) else Color(0xFFF4F7F6),
        label = "sidebarToggleBackground",
    )
    val sidebarExpandedWidth = 230.dp
    val sidebarCollapsedWidth = 76.dp
    val expandedSidebarPadding = 14.dp
    val collapsedSidebarPadding = 8.dp
    val sidebarAnimationSpec = tween<Dp>(durationMillis = 220)
    val sidebarWidth by animateDpAsState(
        targetValue = if (sidebarExpanded) sidebarExpandedWidth else sidebarCollapsedWidth,
        animationSpec = sidebarAnimationSpec,
        label = "sidebarWidth",
    )
    val sidebarHorizontalPadding by animateDpAsState(
        targetValue = if (sidebarExpanded) expandedSidebarPadding else collapsedSidebarPadding,
        animationSpec = sidebarAnimationSpec,
        label = "sidebarHorizontalPadding",
    )
    val sidebarToggleWidth by animateDpAsState(
        targetValue = if (sidebarExpanded) 36.dp else sidebarCollapsedWidth - collapsedSidebarPadding * 2,
        animationSpec = sidebarAnimationSpec,
        label = "sidebarToggleWidth",
    )
    val sidebarToggleHeight by animateDpAsState(
        targetValue = if (sidebarExpanded) 36.dp else 48.dp,
        animationSpec = sidebarAnimationSpec,
        label = "sidebarToggleHeight",
    )
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
        Column(modifier = Modifier.fillMaxWidth().background(Color.White)) {
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
            HorizontalDivider(thickness = 1.dp, color = Color(0xFFDDE4E8))
        }
    }, containerColor = Page, floatingActionButton = {
        FloatingActionButton(
            onClick = { showBugReportDialog = true },
            containerColor = Green,
            contentColor = Color.White,
        ) {
            Icon(Icons.Default.BugReport, contentDescription = "提交 BUG 反馈")
        }
    }) { padding ->
        Row(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(
                modifier = Modifier
                    .width(sidebarWidth)
                    .fillMaxSize()
                    .background(Color.White)
                    .clipToBounds()
                    .padding(horizontal = sidebarHorizontalPadding, vertical = 14.dp)
                    .animateContentSize(),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Box(
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                ) {
                    SidebarSectionTitle(
                        visible = sidebarExpanded,
                        modifier = Modifier.align(Alignment.CenterStart),
                    )
                    Box(
                        modifier = Modifier
                            .align(Alignment.CenterEnd)
                            .width(sidebarToggleWidth)
                            .height(sidebarToggleHeight)
                            .clip(RoundedCornerShape(8.dp))
                            .background(sidebarToggleBackground)
                            .border(
                                width = 1.dp,
                                color = if (sidebarTogglePressed) Color(0xFFB9DCCB) else Color(0xFFE5EBEE),
                                shape = RoundedCornerShape(8.dp),
                            )
                            .clickable(
                                interactionSource = sidebarToggleInteraction,
                                indication = ripple(bounded = true, color = Green.copy(alpha = 0.16f)),
                                onClick = { sidebarExpanded = !sidebarExpanded },
                            ),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            if (sidebarExpanded) Icons.Default.ChevronLeft else Icons.Default.ChevronRight,
                            contentDescription = if (sidebarExpanded) "收起侧边栏" else "展开侧边栏",
                            tint = Muted,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                }
                NavItem("工作台", Icons.Default.Assignment, selected == "工作台", collapsed = !sidebarExpanded) { selected = "工作台" }
                NavItem("工单", Icons.Default.Inventory2, selected == "工单", collapsed = !sidebarExpanded) { selected = "工单" }
                if (currentUser.role == UserRole.ADMIN) {
                    if (sidebarExpanded) {
                        Spacer(Modifier.height(10.dp))
                        Text("管理员", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp))
                    }
                    NavItem("辅料与配方", Icons.Default.Settings, selected == "辅料与配方", collapsed = !sidebarExpanded) { selected = "辅料与配方" }
                }
                Spacer(Modifier.weight(1f))
                SidebarNetworkStatus(
                    visible = sidebarExpanded,
                    modifier = Modifier.fillMaxWidth(),
                )
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
    if (showBugReportDialog) {
        BugReportDialog(
            repository = repository,
            onDismiss = { showBugReportDialog = false },
        )
    }
}

@Composable
private fun SidebarSectionTitle(
    visible: Boolean,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        modifier = modifier,
        enter = fadeIn(
            animationSpec = tween(durationMillis = 150, delayMillis = 70),
        ) + slideInHorizontally(
            animationSpec = tween(durationMillis = 180, delayMillis = 50),
            initialOffsetX = { width -> -width / 4 },
        ),
        exit = fadeOut(
            animationSpec = tween(durationMillis = 80),
        ) + slideOutHorizontally(
            animationSpec = tween(durationMillis = 150),
            targetOffsetX = { width -> -width / 4 },
        ),
    ) {
        Text(
            "现场制作",
            color = Ink,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(start = 10.dp),
        )
    }
}

@Composable
private fun SidebarNetworkStatus(
    visible: Boolean,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        modifier = modifier,
        enter = fadeIn(
            animationSpec = tween(durationMillis = 150, delayMillis = 80),
        ) + expandVertically(
            animationSpec = tween(durationMillis = 180, delayMillis = 60),
            expandFrom = Alignment.Bottom,
        ),
        exit = fadeOut(
            animationSpec = tween(durationMillis = 70),
        ) + shrinkVertically(
            animationSpec = tween(durationMillis = 140),
            shrinkTowards = Alignment.Bottom,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Color(0xFFF5F9F7))
                .padding(horizontal = 10.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(7.dp)
                    .clip(CircleShape)
                    .background(Green),
            )
            Spacer(Modifier.width(8.dp))
            Text(
                "局域网模式",
                color = Ink,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.weight(1f))
            Text(
                "实时接口",
                color = Green,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}

@Composable
private fun NavItem(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    active: Boolean,
    collapsed: Boolean,
    onClick: () -> Unit,
) {
    val horizontalPadding by animateDpAsState(
        targetValue = if (collapsed) 19.5.dp else 13.dp,
        animationSpec = tween(durationMillis = 220),
        label = "navItemHorizontalPadding",
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(if (active) Color(0xFFEAF6F0) else Color.Transparent)
            .clickable(onClick = onClick)
            .padding(start = horizontalPadding, end = 13.dp)
            .animateContentSize(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Start,
    ) {
        Icon(
            icon,
            contentDescription = label,
            tint = if (active) Green else Muted,
            modifier = Modifier.size(21.dp),
        )
        AnimatedVisibility(
            visible = !collapsed,
            enter = fadeIn(
                animationSpec = tween(durationMillis = 140, delayMillis = 100),
            ) + expandHorizontally(
                animationSpec = tween(durationMillis = 180, delayMillis = 70),
                expandFrom = Alignment.Start,
            ),
            exit = fadeOut(
                animationSpec = tween(durationMillis = 70),
            ) + shrinkHorizontally(
                animationSpec = tween(durationMillis = 140),
                shrinkTowards = Alignment.Start,
            ),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Spacer(Modifier.width(12.dp))
                Text(
                    label,
                    color = if (active) Green else Ink,
                    fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                    maxLines = 1,
                )
            }
        }
    }
}

@Composable
private fun BugReportDialog(
    repository: MilkRepository,
    onDismiss: () -> Unit,
) {
    var description by remember { mutableStateOf("") }
    var imageUris by remember { mutableStateOf<List<String>>(emptyList()) }
    var submitting by remember { mutableStateOf(false) }
    var sent by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        val additions = uris.map(Uri::toString)
        val combined = (imageUris + additions).distinct()
        imageUris = combined.take(8)
        if (combined.size > 8) {
            error = "最多上传 8 张图片"
        }
    }

    if (sent) {
        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text("BUG 反馈已提交") },
            text = { Text("反馈已发送，我们会根据描述和图片定位问题。") },
            confirmButton = { Button(onClick = onDismiss) { Text("完成") } },
        )
        return
    }

    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        title = { Text("提交 BUG 反馈") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 540.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it.take(5000) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("问题描述") },
                    placeholder = { Text("请描述在哪个页面、执行了什么操作、出现了什么问题") },
                    minLines = 4,
                    maxLines = 8,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text("问题截图", color = Ink, fontWeight = FontWeight.SemiBold)
                        Text("可选，最多 8 张", color = Muted, fontSize = 13.sp)
                    }
                    OutlinedButton(
                        onClick = { imagePicker.launch("image/*") },
                        enabled = !submitting && imageUris.size < 8,
                    ) {
                        Icon(Icons.Default.PhotoLibrary, null)
                        Spacer(Modifier.width(6.dp))
                        Text("添加图片")
                    }
                }
                if (imageUris.isNotEmpty()) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                        items(imageUris, key = { it }) { uri ->
                            Box(modifier = Modifier.size(86.dp)) {
                                StoredImage(
                                    fileId = null,
                                    previewUri = uri,
                                    repository = repository,
                                    modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(7.dp)),
                                )
                                IconButton(
                                    onClick = { imageUris = imageUris - uri },
                                    modifier = Modifier
                                        .align(Alignment.TopEnd)
                                        .size(30.dp)
                                        .background(Color(0xCCB63D3D), CircleShape),
                                    enabled = !submitting,
                                ) {
                                    Icon(Icons.Default.Delete, contentDescription = "删除图片", tint = Color.White, modifier = Modifier.size(17.dp))
                                }
                            }
                        }
                    }
                }
                error?.let { Text(it, color = Color(0xFFC7473C), fontSize = 14.sp) }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (description.isBlank()) {
                        error = "请填写问题描述"
                        return@Button
                    }
                    if (!submitting) {
                        submitting = true
                        error = null
                        scope.launch {
                            runCatching { repository.submitBugReport(description, imageUris) }
                                .onSuccess { sent = true }
                                .onFailure { error = it.message ?: "BUG 反馈提交失败" }
                                .also { submitting = false }
                        }
                    }
                },
                enabled = !submitting,
            ) {
                Text(if (submitting) "提交中..." else "提交反馈")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text("取消") }
        },
    )
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
    var labelId by remember { mutableStateOf("") }
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
            labelId = ""
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
                    labelId = processed.scannedQr?.labelId.orEmpty()
                    materialId = processed.scannedQr?.materialId.orEmpty()
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
                        if (labelId.isNotBlank() && materialId.isNotBlank()) {
                            Text("二维码识别结果：$materialId · $labelId", color = Ink, fontWeight = FontWeight.Bold)
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
                labelId.isNotBlank() && materialId.isNotBlank() -> Button(onClick = {
                    if (!working) {
                        working = true
                        error = null
                        scope.launch {
                            runCatching { repository.confirmStepQr(order.orderNo, step.stepNo, labelId, materialId, photoUri.orEmpty()) }
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

@OptIn(ExperimentalMaterial3Api::class)
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
    var historyRecipe by remember { mutableStateOf<ProductRecipe?>(null) }
    var previewImage by remember { mutableStateOf<ImagePreviewTarget?>(null) }
    var isRefreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    suspend fun loadMasterData() {
        materials = repository.listMaterials()
        recipes = repository.listRecipes()
    }

    androidx.compose.runtime.LaunchedEffect(Unit) {
        runCatching { loadMasterData() }
    }

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = {
            if (!isRefreshing) {
                isRefreshing = true
                scope.launch {
                    runCatching { loadMasterData() }
                        .onFailure {
                            Toast.makeText(context, "刷新失败，请检查网络后重试", Toast.LENGTH_SHORT).show()
                        }
                    isRefreshing = false
                }
            }
        },
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
            }

            item {
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
            }

            if (tab == "辅料") {
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
            } else {
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
                                Text("V${recipe.version} · ${recipe.items.size} 种辅料 · ${if (recipe.enabled) "启用" else "停用"}", color = Muted, fontSize = 14.sp)
                            }
                            Column(horizontalAlignment = Alignment.End) {
                                TextButton(onClick = { historyRecipe = recipe }) { Text("历史") }
                                TextButton(onClick = { editingRecipe = recipe }) { Text("编辑") }
                            }
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
    historyRecipe?.let { recipe ->
        RecipeHistoryDialog(
            recipe = recipe,
            repository = repository,
            onDismiss = { historyRecipe = null },
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

@Composable
private fun RecipeHistoryDialog(
    recipe: ProductRecipe,
    repository: MilkRepository,
    onDismiss: () -> Unit,
) {
    var versions by remember(recipe.id) { mutableStateOf<List<RecipeVersion>?>(null) }
    var error by remember(recipe.id) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    androidx.compose.runtime.LaunchedEffect(recipe.id) {
        runCatching { repository.listRecipeVersions(recipe.id) }
            .onSuccess { versions = it }
            .onFailure { error = it.message ?: "配方历史版本加载失败" }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("配方历史 · ${recipe.name}") },
        text = {
            when {
                error != null -> Text(error ?: "", color = Color(0xFFC7473C))
                versions == null -> Text("正在加载历史版本...", color = Muted)
                versions?.isEmpty() == true -> Text("当前配方尚无历史版本记录。", color = Muted)
                else -> LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 500.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(versions.orEmpty(), key = { it.version }) { version ->
                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = if (version.isCurrent) Green.copy(alpha = 0.08f) else Color(0xFFF7F9F8),
                            ),
                        ) {
                            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text(
                                        "V${version.version}${if (version.isCurrent) " · 当前版本" else ""}",
                                        color = Ink,
                                        fontWeight = FontWeight.Bold,
                                    )
                                    Text(version.createdByName, color = Muted, fontSize = 13.sp)
                                }
                                Text(
                                    version.createdAt.replace("T", " ").take(16).ifBlank { "时间未记录" },
                                    color = Muted,
                                    fontSize = 12.sp,
                                )
                                HorizontalDivider(color = Color(0xFFE2EAE7))
                                version.items.forEach { item ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                    ) {
                                        Text(
                                            "${item.nameZh} · ${item.materialCode}",
                                            color = Ink,
                                            modifier = Modifier.weight(1f),
                                        )
                                        Text("${item.quantityPerTonKg} kg/吨", color = Green, fontWeight = FontWeight.Bold)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    error = null
                    versions = null
                    scope.launch {
                        runCatching { repository.listRecipeVersions(recipe.id) }
                            .onSuccess { versions = it }
                            .onFailure { error = it.message ?: "配方历史版本加载失败" }
                    }
                },
            ) { Text("刷新") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
    )
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
