package com.xiaoqi.steps.core;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

/**
 * 当日步数计算器 —— 纯 Java，不依赖 Android，可直接在 JVM 上跑测试。
 *
 * <h3>为什么要自己算“今日”</h3>
 * Android 的 {@code TYPE_STEP_COUNTER} 给的是“开机以来的累计步数”，既不按自然日
 * 清零，也会在重启后归零；而协议要求上报的是“当日累计步数”。所以必须在手机端
 * 维护一个“当天零点以来的增量”。
 *
 * <h3>三条规则</h3>
 * <ol>
 *   <li><b>日切</b>：设备本地日期变化时 {@code todaySteps=0}，但保留上次累计值，
 *       让跨越零点的一小段步数仍能计入新的一天。</li>
 *   <li><b>重启/传感器重置</b>：新读数小于旧读数时，把新读数本身当作“重启后的步数”
 *       累加，而不是当成负数丢掉。</li>
 *   <li><b>防跳变</b>：如果日切时距上次采样超过 {@link #MAX_CARRY_GAP_MS}，
 *       说明跨了很多天/长时间关机，无法拆分归属，宁可这一段不计数，也不把
 *       几天的步数全算到今天。同一自然日内的大增量则按“每秒最多 5 步”做上限校验。</li>
 * </ol>
 *
 * <p>线程安全：所有公开读写方法都 {@code synchronized}。UI 与前台服务可能同时访问。</p>
 */
public final class StepTracker {

    /** 日切时最多把多长的“上次采样 → 现在”间隔带入新一天（2 小时）。 */
    public static final long MAX_CARRY_GAP_MS = 2L * 60L * 60L * 1000L;

    /** 人跑步的极限大约 4~5 步/秒；用它给同一自然日内的大跳变做上限。 */
    public static final long MAX_STEPS_PER_SEC = 5L;

    /** 采样间隔内允许的固定余量（停顿、传感器批量上报、时钟抖动）。 */
    public static final long PLAUSIBLE_SLACK = 2000L;

    private String dayKey = "";
    private long todaySteps;
    private long lastTotal = -1L;
    private long lastSensorTs;

    public StepTracker() {
    }

    public StepTracker(String dayKey, long todaySteps, long lastTotal, long lastSensorTs) {
        this.dayKey = dayKey == null ? "" : dayKey;
        this.todaySteps = Math.max(0L, todaySteps);
        this.lastTotal = lastTotal;
        this.lastSensorTs = Math.max(0L, lastSensorTs);
    }

    /**
     * 处理一次 {@code TYPE_STEP_COUNTER} 读数。
     *
     * @param total    传感器给出的“开机以来累计步数”
     * @param nowMs    本次采样时刻（Unix 毫秒）
     * @param todayKey 设备本地日期，格式 yyyy-MM-dd
     */
    public synchronized Update onCounter(long total, long nowMs, String todayKey) {
        if (total < 0L) {
            total = 0L;
        }
        if (nowMs <= 0L) {
            nowMs = System.currentTimeMillis();
        }
        if (todayKey == null || todayKey.isEmpty()) {
            todayKey = dayKey(nowMs, ZoneId.systemDefault());
        }

        // 第一次运行：只建立基线，不把“开机以来”的步数算进今天。
        if (dayKey.isEmpty() || lastTotal < 0L) {
            dayKey = todayKey;
            lastTotal = total;
            lastSensorTs = nowMs;
            return new Update(true, false, 0L, todaySteps, dayKey, lastTotal);
        }

        long gapMs = nowMs - lastSensorTs;
        boolean rolled = false;
        if (!dayKey.equals(todayKey)) {
            dayKey = todayKey;
            todaySteps = 0L;
            rolled = true;
        }

        long delta;
        if (total >= lastTotal) {
            delta = total - lastTotal;
        } else {
            // 重启或传感器重置：读数从 0 重新开始。
            delta = total;
        }

        // 跨天且间隔太久：无法判断哪些步数属于今天，整段丢弃。
        if (rolled && gapMs > MAX_CARRY_GAP_MS) {
            delta = 0L;
        }

        // 同一自然日内的大跳变：按时间间隔做物理上限校验。
        if (gapMs > 0L) {
            long plausible = (gapMs / 1000L) * MAX_STEPS_PER_SEC + PLAUSIBLE_SLACK;
            if (delta > plausible) {
                delta = 0L;
            }
        } else if (delta > PLAUSIBLE_SLACK) {
            delta = 0L;
        }

        if (delta > 0L) {
            todaySteps += delta;
        }
        lastTotal = total;
        lastSensorTs = nowMs;

        return new Update(true, rolled, delta, todaySteps, dayKey, lastTotal);
    }

    /**
     * 处理一次 {@code TYPE_STEP_DETECTOR} 事件（没有计步器硬件时的降级方案）。
     * 每来一个事件就是一步，没有累计值可用。
     */
    public synchronized Update onDetector(long nowMs, String todayKey) {
        if (nowMs <= 0L) {
            nowMs = System.currentTimeMillis();
        }
        if (todayKey == null || todayKey.isEmpty()) {
            todayKey = dayKey(nowMs, ZoneId.systemDefault());
        }
        if (dayKey.isEmpty()) {
            dayKey = todayKey;
            lastSensorTs = nowMs;
            return new Update(true, false, 0L, todaySteps, dayKey, lastTotal);
        }
        boolean rolled = false;
        if (!dayKey.equals(todayKey)) {
            dayKey = todayKey;
            todaySteps = 0L;
            rolled = true;
        }
        todaySteps += 1L;
        lastSensorTs = nowMs;
        return new Update(true, rolled, 1L, todaySteps, dayKey, lastTotal);
    }

    /**
     * UI 在零点后打开、但还没有新传感器事件时调用：让“今日”立即变 0。
     * 不改变 {@code lastTotal}，下一次传感器事件仍能算出跨零点的增量。
     */
    public synchronized boolean rollDay(String todayKey) {
        if (todayKey == null || todayKey.isEmpty()) {
            return false;
        }
        if (dayKey.isEmpty()) {
            dayKey = todayKey;
            return true;
        }
        if (!dayKey.equals(todayKey)) {
            dayKey = todayKey;
            todaySteps = 0L;
            return true;
        }
        return false;
    }

    /**
     * 仅用于调试/演示：手动加步数。不推进 {@code lastTotal}，因此下一次真实
     * 传感器事件不会把演示步数重复计算。
     */
    public synchronized Update addManual(long steps, long nowMs, String todayKey) {
        if (steps <= 0L) {
            return new Update(false, false, 0L, todaySteps, dayKey, lastTotal);
        }
        if (nowMs <= 0L) {
            nowMs = System.currentTimeMillis();
        }
        if (todayKey == null || todayKey.isEmpty()) {
            todayKey = dayKey(nowMs, ZoneId.systemDefault());
        }
        boolean rolled = false;
        if (dayKey.isEmpty()) {
            dayKey = todayKey;
        } else if (!dayKey.equals(todayKey)) {
            dayKey = todayKey;
            todaySteps = 0L;
            rolled = true;
        }
        todaySteps += steps;
        lastSensorTs = nowMs;
        return new Update(true, rolled, steps, todaySteps, dayKey, lastTotal);
    }

    /** 仅用于调试/演示：把今日清零（保留传感器基线）。 */
    public synchronized Update resetToday(long nowMs, String todayKey) {
        if (nowMs <= 0L) {
            nowMs = System.currentTimeMillis();
        }
        if (todayKey == null || todayKey.isEmpty()) {
            todayKey = dayKey(nowMs, ZoneId.systemDefault());
        }
        if (dayKey.isEmpty()) {
            dayKey = todayKey;
        } else if (!dayKey.equals(todayKey)) {
            dayKey = todayKey;
        }
        todaySteps = 0L;
        lastSensorTs = nowMs;
        return new Update(true, false, 0L, todaySteps, dayKey, lastTotal);
    }

    public synchronized long todaySteps() {
        return todaySteps;
    }

    public synchronized String dayKey() {
        return dayKey;
    }

    public synchronized long lastTotal() {
        return lastTotal;
    }

    public synchronized long lastSensorTs() {
        return lastSensorTs;
    }

    public synchronized State snapshot() {
        return new State(dayKey, todaySteps, lastTotal, lastSensorTs);
    }

    /** 设备本地日期键（yyyy-MM-dd）。测试可传入固定时区。 */
    public static String dayKey(long epochMs, ZoneId zone) {
        ZoneId z = zone == null ? ZoneId.systemDefault() : zone;
        return LocalDate.ofInstant(Instant.ofEpochMilli(epochMs), z).toString();
    }

    /** 当天 00:00 的 Unix 毫秒（用于 UI 显示与测试）。 */
    public static long startOfDayMs(long epochMs, ZoneId zone) {
        ZoneId z = zone == null ? ZoneId.systemDefault() : zone;
        return LocalDate.ofInstant(Instant.ofEpochMilli(epochMs), z)
                .atStartOfDay(z).toInstant().toEpochMilli();
    }

    /** 一次传感器事件的计算结果。 */
    public static final class Update {
        public final boolean changed;
        public final boolean dayRolled;
        public final long delta;
        public final long todaySteps;
        public final String dayKey;
        public final long lastTotal;

        Update(boolean changed, boolean dayRolled, long delta, long todaySteps,
               String dayKey, long lastTotal) {
            this.changed = changed;
            this.dayRolled = dayRolled;
            this.delta = delta;
            this.todaySteps = todaySteps;
            this.dayKey = dayKey;
            this.lastTotal = lastTotal;
        }
    }

    /** 可持久化的快照。 */
    public static final class State {
        public final String dayKey;
        public final long todaySteps;
        public final long lastTotal;
        public final long lastSensorTs;

        State(String dayKey, long todaySteps, long lastTotal, long lastSensorTs) {
            this.dayKey = dayKey;
            this.todaySteps = todaySteps;
            this.lastTotal = lastTotal;
            this.lastSensorTs = lastSensorTs;
        }
    }
}
