package com.xiaoqi.steps;

import java.text.NumberFormat;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/** 展示层文案。所有“人话”集中在这里，方便 UI 与通知共用。 */
public final class Format {

    private static final DateTimeFormatter TIME =
            DateTimeFormatter.ofPattern("HH:mm", Locale.CHINA);

    private Format() {
    }

    public static String steps(long steps) {
        if (steps < 0L) {
            return "—";
        }
        NumberFormat format = NumberFormat.getIntegerInstance(Locale.CHINA);
        format.setGroupingUsed(true);
        return format.format(steps);
    }

    public static String percent(long today, int goal) {
        if (goal <= 0) {
            return "0%";
        }
        long value = Math.round(today * 100.0 / goal);
        return Math.max(0L, value) + "%";
    }

    public static int ringPercent(long today, int goal) {
        if (goal <= 0) {
            return 0;
        }
        return (int) Math.min(100L, Math.max(0L, Math.round(today * 100.0 / goal)));
    }

    public static String age(long ageMs) {
        if (ageMs < 0L) {
            ageMs = 0L;
        }
        if (ageMs < 60_000L) {
            return "刚刚";
        }
        long minutes = ageMs / 60_000L;
        if (minutes < 60L) {
            return minutes + " 分钟前";
        }
        long hours = minutes / 60L;
        if (hours < 24L) {
            return hours + " 小时前";
        }
        return (hours / 24L) + " 天前";
    }

    public static String time(long epochMs) {
        if (epochMs <= 0L) {
            return "—";
        }
        return TIME.format(Instant.ofEpochMilli(epochMs).atZone(ZoneId.systemDefault()));
    }

    /** 同步状态一行文案（不含“失败”以外的技术细节）。 */
    public static String syncLine(AppConfig cfg) {
        if (!cfg.isConfigured()) {
            return "尚未配置电脑地址与令牌";
        }
        if (!cfg.lastSyncOk() && cfg.lastAttemptAt() > 0L) {
            return cfg.lastSyncMessage() + " · "
                    + age(System.currentTimeMillis() - cfg.lastAttemptAt());
        }
        long last = cfg.lastSyncAt();
        if (last <= 0L) {
            return "尚未同步";
        }
        long age = System.currentTimeMillis() - last;
        return (age <= 15L * 60_000L ? "已同步 · " : "待同步 · ") + age(age);
    }

    public static String syncState(AppConfig cfg) {
        if (!cfg.isConfigured()) {
            return "待配置";
        }
        long last = cfg.lastSyncAt();
        if (last <= 0L) {
            return cfg.lastAttemptAt() > 0L && !cfg.lastSyncOk() ? "同步失败" : "待同步";
        }
        long age = System.currentTimeMillis() - last;
        if (!cfg.lastSyncOk()) {
            return "同步失败";
        }
        return age <= 15L * 60_000L ? "已同步" : "待同步";
    }
}
