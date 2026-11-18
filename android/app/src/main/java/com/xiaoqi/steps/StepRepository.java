package com.xiaoqi.steps;

import android.content.Context;
import android.content.SharedPreferences;

import com.xiaoqi.steps.core.StepTracker;

import java.time.ZoneId;

/**
 * 步数仓库：把纯 Java 的 {@link StepTracker} 与 SharedPreferences 粘起来。
 *
 * <p>Activity 与前台 Service 在同一个进程，共享这个单例；进程被杀后从
 * SharedPreferences 恢复。所有读写都串行化，避免传感器线程与 UI 线程打架。</p>
 */
public final class StepRepository {

    private static final String K_DAY = "step_day";
    private static final String K_TODAY = "step_today";
    private static final String K_LAST_TOTAL = "step_last_total";
    private static final String K_LAST_TS = "step_last_ts";

    private static volatile StepRepository instance;

    private final SharedPreferences prefs;
    private final StepTracker tracker;

    private StepRepository(Context context) {
        this.prefs = context.getApplicationContext()
                .getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE);
        this.tracker = new StepTracker(
                prefs.getString(K_DAY, ""),
                prefs.getLong(K_TODAY, 0L),
                prefs.getLong(K_LAST_TOTAL, -1L),
                prefs.getLong(K_LAST_TS, 0L));
        if (tracker.rollDay(nowKey())) {
            persist(false);
        }
    }

    public static StepRepository get(Context context) {
        StepRepository local = instance;
        if (local == null) {
            synchronized (StepRepository.class) {
                local = instance;
                if (local == null) {
                    local = new StepRepository(context);
                    instance = local;
                }
            }
        }
        return local;
    }

    public synchronized StepTracker.Update onCounter(long total) {
        long now = System.currentTimeMillis();
        StepTracker.Update update = tracker.onCounter(total, now, key(now));
        persist(false);
        return update;
    }

    public synchronized StepTracker.Update onDetector() {
        long now = System.currentTimeMillis();
        StepTracker.Update update = tracker.onDetector(now, key(now));
        persist(false);
        return update;
    }

    public synchronized long todaySteps() {
        long now = System.currentTimeMillis();
        if (tracker.rollDay(key(now))) {
            persist(false);
        }
        return tracker.todaySteps();
    }

    public synchronized StepTracker.State snapshot() {
        long now = System.currentTimeMillis();
        if (tracker.rollDay(key(now))) {
            persist(false);
        }
        return tracker.snapshot();
    }

    /** 调试/演示：手动加步数。 */
    public synchronized StepTracker.Update addDemoSteps(long steps) {
        long now = System.currentTimeMillis();
        StepTracker.Update update = tracker.addManual(steps, now, key(now));
        persist(false);
        return update;
    }

    /** 调试/演示：今日清零。 */
    public synchronized StepTracker.Update resetToday() {
        long now = System.currentTimeMillis();
        StepTracker.Update update = tracker.resetToday(now, key(now));
        persist(false);
        return update;
    }

    /** 进程即将结束前同步落盘，避免 apply() 还没写完。 */
    public synchronized void flush() {
        persist(true);
    }

    private void persist(boolean commit) {
        StepTracker.State state = tracker.snapshot();
        SharedPreferences.Editor editor = prefs.edit()
                .putString(K_DAY, state.dayKey)
                .putLong(K_TODAY, state.todaySteps)
                .putLong(K_LAST_TOTAL, state.lastTotal)
                .putLong(K_LAST_TS, state.lastSensorTs);
        if (commit) {
            editor.commit();
        } else {
            editor.apply();
        }
    }

    private static String nowKey() {
        long now = System.currentTimeMillis();
        return key(now);
    }

    private static String key(long epochMs) {
        return StepTracker.dayKey(epochMs, ZoneId.systemDefault());
    }
}
