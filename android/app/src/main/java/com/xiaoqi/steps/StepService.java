package com.xiaoqi.steps;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import com.xiaoqi.steps.core.StepTracker;
import com.xiaoqi.steps.core.SyncClient;
import com.xiaoqi.steps.core.SyncConfig;
import com.xiaoqi.steps.core.SyncResult;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 前台计步服务。
 *
 * <p>为什么必须前台：手机锁屏后普通后台进程会被冻结，计步传感器虽然有硬件累计值，
 * 但 App 拿不到事件就无法在零点/重启时把增量算对。前台服务 + 常驻通知是 Android
 * 上持续计步的标准做法（不申请 WakeLock，靠硬件计步器低功耗上报）。</p>
 *
 * <p>同步节奏：默认每 5 分钟一次；步数每增加 300 步且距上次尝试 ≥75 秒时提前同步。
 * 协议规定同设备 60 秒内重复上报会被幂等丢弃，所以 75 秒是安全下限。</p>
 */
public final class StepService extends Service implements SensorEventListener {

    public static final String ACTION_SYNC_NOW = "com.xiaoqi.steps.action.SYNC_NOW";
    public static final String ACTION_STOP = "com.xiaoqi.steps.action.STOP";
    public static final String ACTION_STATE_CHANGED = "com.xiaoqi.steps.action.STATE_CHANGED";

    private static final String TAG = "XiaoqiSteps";
    private static final long NOTIFY_THROTTLE_MS = 2500L;
    private static final long EARLY_SYNC_MIN_GAP_MS = 75_000L;
    private static final long EARLY_SYNC_STEP_DELTA = 300L;
    private static final AtomicBoolean RUNNING = new AtomicBoolean(false);

    private final AtomicBoolean syncing = new AtomicBoolean(false);
    private final Object sensorLock = new Object();

    private SensorManager sensorManager;
    private Sensor sensor;
    private int sensorKind = AppConfig.SENSOR_UNKNOWN;
    private boolean sensorRegistered;
    private ScheduledExecutorService executor;
    private StepRepository repository;
    private boolean foregroundStarted;

    private long lastSyncAttemptAt;
    private long lastSyncedStepValue;
    private long lastNotificationAt;
    private long lastBroadcastAt;

    public static void start(Context context) {
        Intent intent = new Intent(context, StepService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    public static void requestSync(Context context) {
        Intent intent = new Intent(context, StepService.class);
        intent.setAction(ACTION_SYNC_NOW);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    public static void stop(Context context) {
        context.stopService(new Intent(context, StepService.class));
    }

    public static boolean isRunning() {
        return RUNNING.get();
    }

    @Override
    public void onCreate() {
        super.onCreate();
        RUNNING.set(true);
        repository = StepRepository.get(this);
        AppConfig cfg = new AppConfig(this);
        lastSyncAttemptAt = cfg.lastAttemptAt();
        lastSyncedStepValue = Math.max(0L, cfg.lastSyncedSteps());

        Notifications.ensureChannel(this);
        try {
            startForeground(Notifications.NOTIFICATION_ID,
                    Notifications.build(this, cfg, repository.todaySteps()));
            foregroundStarted = true;
        } catch (Exception e) {
            Log.e(TAG, "startForeground 失败", e);
        }

        registerSensor();
        executor = Executors.newSingleThreadScheduledExecutor(runnable -> {
            Thread thread = new Thread(runnable, "xiaoqi-step-sync");
            thread.setDaemon(true);
            return thread;
        });
        executor.scheduleWithFixedDelay(this::tick, 5L, 15L, TimeUnit.SECONDS);
        broadcast();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? null : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (ACTION_SYNC_NOW.equals(action) && executor != null && !executor.isShutdown()) {
            executor.execute(() -> doSync(true));
        }
        // 权限可能在服务启动后由系统设置授予；再次 start 时补注册传感器。
        if (!sensorRegistered && Permissions.hasActivityRecognition(this)) {
            registerSensor();
            broadcast();
        }
        return START_STICKY;
    }

    private void registerSensor() {
        if (sensorRegistered) {
            return;
        }
        AppConfig cfg = new AppConfig(this);
        try {
            sensorManager = (SensorManager) getSystemService(Context.SENSOR_SERVICE);
            if (sensorManager == null) {
                cfg.recordSensor(false, "本机没有传感器服务", AppConfig.SENSOR_NONE);
                return;
            }
            Sensor counter = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER);
            Sensor detector = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR);

            if (counter != null) {
                sensor = counter;
                sensorKind = AppConfig.SENSOR_COUNTER;
            } else if (detector != null) {
                sensor = detector;
                sensorKind = AppConfig.SENSOR_DETECTOR;
            } else {
                sensor = null;
                sensorKind = AppConfig.SENSOR_NONE;
            }

            if (sensor == null) {
                cfg.recordSensor(false, "本机无计步传感器（或未授权）",
                        AppConfig.SENSOR_NONE);
                Log.w(TAG, "no step sensor");
                return;
            }

            boolean ok = sensorManager.registerListener(
                    this, sensor, SensorManager.SENSOR_DELAY_NORMAL, 0);
            if (ok) {
                sensorRegistered = true;
                cfg.recordSensor(true, sensor.getName(), sensorKind);
                Log.i(TAG, "sensor registered: " + sensor.getName() + " kind=" + sensorKind);
            } else {
                sensorRegistered = false;
                cfg.recordSensor(false, "传感器注册失败：" + sensor.getName(),
                        AppConfig.SENSOR_NONE);
            }
        } catch (SecurityException e) {
            sensorRegistered = false;
            cfg.recordSensor(false, "缺少“身体活动”权限", AppConfig.SENSOR_NONE);
            Log.e(TAG, "sensor permission denied", e);
        } catch (Exception e) {
            sensorRegistered = false;
            cfg.recordSensor(false, "传感器异常：" + e.getClass().getSimpleName(),
                    AppConfig.SENSOR_NONE);
            Log.e(TAG, "sensor register failed", e);
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event == null || event.values == null || event.values.length == 0) {
            return;
        }
        try {
            StepTracker.Update update;
            if (event.sensor.getType() == Sensor.TYPE_STEP_COUNTER) {
                long total = (long) event.values[0];
                if (total < 0L) {
                    return;
                }
                update = repository.onCounter(total);
            } else if (event.sensor.getType() == Sensor.TYPE_STEP_DETECTOR) {
                update = repository.onDetector();
            } else {
                return;
            }
            if (update.changed) {
                maybeSyncOnProgress();
                updateNotification(false);
                broadcast();
            }
        } catch (Exception e) {
            Log.e(TAG, "onSensorChanged failed", e);
        }
    }

    @Override
    public void onAccuracyChanged(Sensor changed, int accuracy) {
        // 计步器精度变化不需要处理。
    }

    private void maybeSyncOnProgress() {
        AppConfig cfg = new AppConfig(this);
        if (!cfg.autoSync() || !cfg.isConfigured()) {
            return;
        }
        long now = System.currentTimeMillis();
        long steps = repository.todaySteps();
        long delta = steps - lastSyncedStepValue;
        if (delta >= EARLY_SYNC_STEP_DELTA && now - lastSyncAttemptAt >= EARLY_SYNC_MIN_GAP_MS) {
            if (executor != null && !executor.isShutdown()) {
                executor.execute(() -> doSync(false));
            }
        }
    }

    private void tick() {
        try {
            long steps = repository.todaySteps();
            AppConfig cfg = new AppConfig(this);
            long now = System.currentTimeMillis();
            long intervalMs = cfg.syncIntervalSec() * 1000L;
            if (cfg.autoSync() && cfg.isConfigured()
                    && (lastSyncAttemptAt <= 0L || now - lastSyncAttemptAt >= intervalMs)) {
                doSync(false);
            } else {
                updateNotification(false);
                if (now - lastBroadcastAt > 30_000L) {
                    broadcast();
                }
            }
        } catch (Throwable t) {
            Log.e(TAG, "tick failed", t);
        }
    }

    private void doSync(boolean manual) {
        if (!syncing.compareAndSet(false, true)) {
            return;
        }
        long steps = 0L;
        try {
            steps = repository.todaySteps();
            AppConfig cfg = new AppConfig(this);
            long now = System.currentTimeMillis();
            SyncResult result;
            if (!cfg.isConfigured()) {
                result = SyncResult.configError("未配置电脑地址或令牌");
            } else {
                SyncConfig syncConfig = new SyncConfig(
                        cfg.baseUrl(), cfg.token(), cfg.deviceId());
                result = SyncClient.push(syncConfig, steps, now);
            }
            cfg.recordSync(result, steps, now);
            lastSyncAttemptAt = now;
            if (result.ok) {
                lastSyncedStepValue = steps;
            }
            Log.i(TAG, "sync manual=" + manual + " steps=" + steps + " -> "
                    + result.httpCode + " " + result.message);
            updateNotification(true);
            broadcast();
        } catch (Exception e) {
            Log.e(TAG, "sync failed", e);
            AppConfig cfg = new AppConfig(this);
            long now = System.currentTimeMillis();
            cfg.recordSync(SyncResult.networkError(e.getMessage(), ""), steps, now);
            lastSyncAttemptAt = now;
            updateNotification(true);
            broadcast();
        } finally {
            syncing.set(false);
        }
    }

    private void updateNotification(boolean force) {
        if (!foregroundStarted) {
            return;
        }
        long now = System.currentTimeMillis();
        if (!force && now - lastNotificationAt < NOTIFY_THROTTLE_MS) {
            return;
        }
        lastNotificationAt = now;
        Notifications.update(this, new AppConfig(this), repository.todaySteps());
    }

    private void broadcast() {
        lastBroadcastAt = System.currentTimeMillis();
        Intent intent = new Intent(ACTION_STATE_CHANGED);
        intent.setPackage(getPackageName());
        sendBroadcast(intent);
    }

    @Override
    public void onDestroy() {
        RUNNING.set(false);
        sensorRegistered = false;
        if (sensorManager != null) {
            synchronized (sensorLock) {
                try {
                    sensorManager.unregisterListener(this);
                } catch (Exception ignored) {
                    // 服务销毁阶段忽略。
                }
            }
        }
        if (executor != null) {
            executor.shutdownNow();
        }
        if (repository != null) {
            repository.flush();
        }
        if (foregroundStarted) {
            stopForeground(true);
            foregroundStarted = false;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
