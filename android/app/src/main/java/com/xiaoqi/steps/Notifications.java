package com.xiaoqi.steps;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/** 常驻通知：既是前台服务凭证，也是“今天走了多少 / 同步是否正常”的随手入口。 */
final class Notifications {

    static final String CHANNEL_ID = "xiaoqi_steps";
    static final int NOTIFICATION_ID = 1001;

    private Notifications() {
    }

    static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "步数同步", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("小栖步数的后台计步与同步状态");
        channel.setShowBadge(false);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        manager.createNotificationChannel(channel);
    }

    static Notification build(Context context, AppConfig cfg, long steps) {
        ensureChannel(context);
        Intent openIntent = new Intent(context, MainActivity.class);
        openIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent open = PendingIntent.getActivity(context, 1, openIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent syncIntent = new Intent(context, StepService.class);
        syncIntent.setAction(StepService.ACTION_SYNC_NOW);
        PendingIntent sync = PendingIntent.getService(context, 2, syncIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent settingsIntent = new Intent(context, SettingsActivity.class);
        PendingIntent settings = PendingIntent.getActivity(context, 3, settingsIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        String title = "小栖 · 今日 " + Format.steps(steps) + " 步";
        String text;
        if (!cfg.isConfigured()) {
            text = "待配置电脑地址与令牌";
        } else if (cfg.lastSyncAt() > 0L && cfg.lastSyncOk()) {
            long age = System.currentTimeMillis() - cfg.lastSyncAt();
            text = (age <= 15L * 60_000L ? "已同步 · " : "待同步 · ") + Format.age(age);
        } else if (cfg.lastAttemptAt() > 0L && !cfg.lastSyncOk()) {
            text = cfg.lastSyncMessage();
        } else {
            text = "等待首次同步";
        }

        Notification.Builder builder = new Notification.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_steps)
                .setContentTitle(title)
                .setContentText(text)
                .setContentIntent(open)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setShowWhen(false)
                .setCategory(Notification.CATEGORY_SERVICE)
                .setPriority(Notification.PRIORITY_LOW)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setColor(Ui.GREEN)
                .addAction(new Notification.Action.Builder(
                        R.drawable.ic_stat_sync, "立即同步", sync).build())
                .addAction(new Notification.Action.Builder(
                        R.drawable.ic_stat_settings, "设置", settings).build());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            builder.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE);
        }
        return builder.build();
    }

    static void update(Context context, AppConfig cfg, long steps) {
        NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        try {
            manager.notify(NOTIFICATION_ID, build(context, cfg, steps));
        } catch (Exception ignored) {
            // 通知权限被拒 / 厂商拦截时不影响计步与同步。
        }
    }
}
