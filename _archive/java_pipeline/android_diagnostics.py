"""Concise diagnostics for Android build/install output."""
from __future__ import annotations


def android_pipeline_failure_hint(output: str, stage: str) -> str:
    text = str(output or "").lower()
    stage = str(stage or "").lower()
    if "androidx.core:core:1.17.0" in text and ("compile against version 36" in text or "plugin 8.9.1" in text):
        return "AndroidX Core 1.17 không tương thích compileSdk 35/AGP 8.8; hãy đồng bộ lại module Android bằng Engine."
    if "sdk location not found" in text:
        return "Không tìm thấy Android SDK; đặt ANDROID_SDK_ROOT/ANDROID_HOME hoặc sdk.dir trong local.properties."
    if "license for package" in text and "not accepted" in text:
        return "Android SDK license chưa được chấp nhận; chạy sdkmanager --licenses."
    if "processing instruction target matching" in text and "xml" in text:
        return "XML Android có khoảng trắng trước khai báo <?xml?>; hãy đồng bộ lại module Android bằng Engine."
    if "device offline" in text or "state 'offline'" in text:
        return "Thiết bị đang offline; rút/cắm lại USB, mở khóa máy rồi Restart ADB Server."
    if "device unauthorized" in text or "unauthorized" in text:
        return "Thiết bị chưa cấp quyền USB debugging; mở khóa máy và chấp nhận hộp thoại RSA."
    if "install_failed_insufficient_storage" in text:
        return "Thiết bị không đủ dung lượng để cài APK debug."
    if "install_failed_version_downgrade" in text:
        return "APK trên thiết bị có versionCode cao hơn; gỡ bản cũ hoặc tăng versionCode."
    if "no connected devices" in text or "device not found" in text:
        return "ADB không còn thấy thiết bị đã chọn; quét lại danh sách thiết bị."
    if stage == "launch" and ("error type 3" in text or "does not exist" in text):
        return "Không tìm thấy Android Activity để chạy; kiểm tra package name và AndroidLauncher."
    return ""
