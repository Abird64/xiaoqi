package com.xiaoqi.steps;

import android.content.Context;
import android.content.SharedPreferences;
import android.provider.Settings;

import com.xiaoqi.steps.core.SyncClient;
import com.xiaoqi.steps.core.SyncResult;

import java.util.Locale;
import java.util.UUID;

/**
 * App 的本地配置与同步状态。只存应用私有 SharedPreferences，不申请存储权限。
 *
 * <p>令牌以明文存放在应用私有目录：这是局域网课程项目可接受的取舍，
 * 文档里已标注；不要把它当成生产级密钥管理。</p>
 */
public final class AppConfig {

    public static final String PREFS = "xiaoqi_steps_config";

    private static final String K_BASE_URL = "base_url";
    private static final String K_TOKEN = "token";
    private static final String K_DEVICE_ID = "device_id";
    private static final String K_GOAL = "goal_steps";
    private static final String K_INTERVAL = "sync_interval_sec";
    private static final String K_AUTO_SYNC = "auto_sync";
    private static final String K_AUTO_START = "auto_start";
    private static final String K_SERVICE_REQUESTED = "service_requested";

    private static final String K_LAST_SYNC_AT = "last_sync_at";
    private static final String K_LAST_ATTEMPT_AT = "last_attempt_at";
    private static final String K_LAST_SYNC_OK = "last_sync_ok";
    private static final String K_LAST_SYNC_MSG = "last_sync_msg";
    private static final String K_LAST_SYNC_CODE = "last_sync_code";
    private static final String K_LAST_SYNC_STEPS = "last_sync_steps";
    private static final String K_LAST_SYNC_DEDUPED = "last_sync_deduped";

    private static final String K_SENSOR_AVAILABLE = "sensor_available";
    private static final String K_SENSOR_NAME = "sensor_name";
    private static final String K_SENSOR_KIND = "sensor_kind";

    public static final int SENSOR_UNKNOWN = 0;
    public static final int SENSOR_COUNTER = 1;
    public static final int SENSOR_DETECTOR = 2;
    public static final int SENSOR_NONE = 3;

    public static final int DEFAULT_GOAL = 8000;
    public static final int DEFAULT_INTERVAL_SEC = 300;

    private final SharedPreferences prefs;
    private final Context context;

    public AppConfig(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        ensureDeviceId();
    }

    public static AppConfig get(Context context) {
        return new AppConfig(context);
    }

    private void ensureDeviceId() {
        if (prefs.getString(K_DEVICE_ID, "").isEmpty()) {
            String androidId = null;
            try {
                androidId = Settings.Secure.getString(
                        context.getContentResolver(), Settings.Secure.ANDROID_ID);
            } catch (Exception ignored) {
                // 少数定制系统会抛异常，降级为随机 ID。
            }
            if (androidId == null || androidId.trim().isEmpty()) {
                androidId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
            }
            prefs.edit().putString(K_DEVICE_ID,
                    "android-" + androidId.toLowerCase(Locale.US)).apply();
        }
    }

    public String baseUrl() {
        return prefs.getString(K_BASE_URL, "");
    }

    public String normalizedBaseUrl() {
        return SyncClient.normalizeBaseUrl(baseUrl());
    }

    public String token() {
        return prefs.getString(K_TOKEN, "");
    }

    public String deviceId() {
        return prefs.getString(K_DEVICE_ID, "android-unknown");
    }

    public boolean isConfigured() {
        return !normalizedBaseUrl().isEmpty() && !token().isEmpty();
    }

    public int goalSteps() {
        int value = prefs.getInt(K_GOAL, DEFAULT_GOAL);
        return Math.max(1000, Math.min(100_000, value));
    }

    public int syncIntervalSec() {
        int value = prefs.getInt(K_INTERVAL, DEFAULT_INTERVAL_SEC);
        // 上限 10 分钟：协议 15 分钟未更新即 stale，超过 10 分钟会让前端长期显示「待同步」。
        return Math.max(60, Math.min(600, value));
    }

    public boolean autoSync() {
        return prefs.getBoolean(K_AUTO_SYNC, true);
    }

    public boolean autoStart() {
        return prefs.getBoolean(K_AUTO_START, true);
    }

    public boolean serviceRequested() {
        return prefs.getBoolean(K_SERVICE_REQUESTED, false);
    }

    public long lastSyncAt() {
        return prefs.getLong(K_LAST_SYNC_AT, 0L);
    }

    public long lastAttemptAt() {
        return prefs.getLong(K_LAST_ATTEMPT_AT, 0L);
    }

    public boolean lastSyncOk() {
        return prefs.getBoolean(K_LAST_SYNC_OK, false);
    }

    public String lastSyncMessage() {
        return prefs.getString(K_LAST_SYNC_MSG, "尚未同步");
    }

    public int lastSyncCode() {
        return prefs.getInt(K_LAST_SYNC_CODE, 0);
    }

    public long lastSyncedSteps() {
        return prefs.getLong(K_LAST_SYNC_STEPS, -1L);
    }

    public boolean lastSyncDeduped() {
        return prefs.getBoolean(K_LAST_SYNC_DEDUPED, false);
    }

    public boolean sensorAvailable() {
        return prefs.getBoolean(K_SENSOR_AVAILABLE, false);
    }

    public String sensorName() {
        return prefs.getString(K_SENSOR_NAME, "未检测");
    }

    public int sensorKind() {
        return prefs.getInt(K_SENSOR_KIND, SENSOR_UNKNOWN);
    }

    public void saveConnection(String baseUrl, String token) {
        prefs.edit()
                .putString(K_BASE_URL, baseUrl == null ? "" : baseUrl.trim())
                .putString(K_TOKEN, token == null ? "" : token.trim())
                .apply();
    }

    public void saveGoal(int goal) {
        prefs.edit().putInt(K_GOAL, Math.max(1000, Math.min(100_000, goal))).apply();
    }

    public void saveSyncInterval(int seconds) {
        prefs.edit().putInt(K_INTERVAL, Math.max(60, Math.min(600, seconds))).apply();
    }

    public void setAutoSync(boolean value) {
        prefs.edit().putBoolean(K_AUTO_SYNC, value).apply();
    }

    public void setAutoStart(boolean value) {
        prefs.edit().putBoolean(K_AUTO_START, value).apply();
    }

    public void setServiceRequested(boolean value) {
        prefs.edit().putBoolean(K_SERVICE_REQUESTED, value).apply();
    }

    public void recordSensor(boolean available, String name, int kind) {
        prefs.edit()
                .putBoolean(K_SENSOR_AVAILABLE, available)
                .putString(K_SENSOR_NAME, name == null ? "未检测" : name)
                .putInt(K_SENSOR_KIND, kind)
                .apply();
    }

    /** 记录一次同步（成功或失败）。成功才推进 lastSyncAt。 */
    public void recordSync(SyncResult result, long steps, long nowMs) {
        SharedPreferences.Editor editor = prefs.edit()
                .putLong(K_LAST_ATTEMPT_AT, nowMs)
                .putBoolean(K_LAST_SYNC_OK, result != null && result.ok)
                .putString(K_LAST_SYNC_MSG, result == null ? "未知错误" : result.shortText())
                .putInt(K_LAST_SYNC_CODE, result == null ? 0 : result.httpCode)
                .putLong(K_LAST_SYNC_STEPS, steps)
                .putBoolean(K_LAST_SYNC_DEDUPED, result != null && result.deduped);
        if (result != null && result.ok) {
            editor.putLong(K_LAST_SYNC_AT, nowMs);
        }
        editor.apply();
    }
}
