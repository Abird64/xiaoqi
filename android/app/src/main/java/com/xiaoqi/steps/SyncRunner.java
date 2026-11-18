package com.xiaoqi.steps;

import android.content.Context;
import android.content.Intent;
import android.util.Log;

import com.xiaoqi.steps.core.SyncClient;
import com.xiaoqi.steps.core.SyncConfig;
import com.xiaoqi.steps.core.SyncResult;

/**
 * 同步执行器：Activity 手动同步、JobScheduler 兜底同步共用。
 * 同一进程内用一把锁串行化，避免两次请求同时打后端。
 */
public final class SyncRunner {

    private static final String TAG = "XiaoqiSteps";
    private static final Object LOCK = new Object();

    private SyncRunner() {
    }

    public static SyncResult syncNow(Context context, boolean manual) {
        Context app = context.getApplicationContext();
        synchronized (LOCK) {
            AppConfig cfg = new AppConfig(app);
            long steps = StepRepository.get(app).todaySteps();
            long now = System.currentTimeMillis();
            SyncResult result;
            if (!cfg.isConfigured()) {
                result = SyncResult.configError("未配置电脑地址或令牌");
            } else {
                result = SyncClient.push(new SyncConfig(
                        cfg.baseUrl(), cfg.token(), cfg.deviceId()), steps, now);
            }
            cfg.recordSync(result, steps, now);
            Log.i(TAG, "sync(" + (manual ? "manual" : "auto") + ") steps=" + steps
                    + " -> " + result.httpCode + " " + result.message);
            if (StepService.isRunning()) {
                Notifications.update(app, cfg, steps);
            }
            broadcast(app);
            return result;
        }
    }

    static void broadcast(Context context) {
        Intent intent = new Intent(StepService.ACTION_STATE_CHANGED);
        intent.setPackage(context.getPackageName());
        context.sendBroadcast(intent);
    }
}
