package com.xiaoqi.steps;

import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

/** 开机/升级后恢复计步服务。没有权限或用户没请求过就什么都不做。 */
public final class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || intent.getAction() == null) {
            return;
        }
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) {
            return;
        }
        AppConfig cfg = new AppConfig(context);
        if (!cfg.serviceRequested() || !cfg.autoStart()) {
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
                && context.checkSelfPermission(Manifest.permission.ACTIVITY_RECOGNITION)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        try {
            StepService.start(context);
            SyncJobService.schedule(context);
        } catch (Exception ignored) {
            // 个别系统在开机阶段禁止启动前台服务；用户下次打开 App 会恢复。
        }
    }
}
