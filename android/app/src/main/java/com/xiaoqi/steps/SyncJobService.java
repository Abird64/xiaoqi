package com.xiaoqi.steps;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.os.Build;
import android.util.Log;

/**
 * 15 分钟一次的兜底同步任务。前台服务被厂商杀掉、或用户把 App 从最近任务划掉后，
 * JobScheduler 仍会按系统节奏把“今日步数”补报一次。它不会启动前台服务。
 */
public final class SyncJobService extends JobService {

    public static final int JOB_ID = 2001;
    private static final String TAG = "XiaoqiSteps";
    private volatile boolean running;

    public static void schedule(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) {
            return;
        }
        JobScheduler scheduler =
                (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler == null) {
            return;
        }
        JobInfo job = new JobInfo.Builder(JOB_ID,
                new ComponentName(context, SyncJobService.class))
                .setPeriodic(15L * 60L * 1000L)
                .setPersisted(true)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .build();
        try {
            scheduler.schedule(job);
        } catch (Exception e) {
            Log.w(TAG, "schedule job failed", e);
        }
    }

    public static void cancel(Context context) {
        JobScheduler scheduler =
                (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler != null) {
            scheduler.cancel(JOB_ID);
        }
    }

    @Override
    public boolean onStartJob(JobParameters params) {
        if (running) {
            return false;
        }
        running = true;
        new Thread(() -> {
            try {
                SyncRunner.syncNow(getApplicationContext(), false);
            } catch (Exception e) {
                Log.e(TAG, "job sync failed", e);
            } finally {
                running = false;
                jobFinished(params, false);
            }
        }, "xiaoqi-job-sync").start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return true;
    }
}
