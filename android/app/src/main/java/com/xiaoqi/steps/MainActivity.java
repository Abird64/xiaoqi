package com.xiaoqi.steps;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageInfo;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.xiaoqi.steps.core.SyncResult;

import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 主页：今日步数、同步状态、权限与后台运行入口。
 */
public final class MainActivity extends Activity {

    private static final int BANNER_NONE = 0;
    private static final int BANNER_PERMISSION = 1;
    private static final int BANNER_CONFIG = 2;
    private static final int BANNER_START = 3;
    private static final int BANNER_NOTIFICATION = 4;

    private AppConfig cfg;
    private StepRepository repository;
    private ExecutorService worker;
    private Handler handler;
    private BroadcastReceiver receiver;
    private boolean receiverRegistered;
    private boolean firstRefresh = true;
    private int bannerType = BANNER_NONE;

    private RingView ring;
    private TextView stepNumber;
    private TextView goalLine;
    private TextView servicePill;
    private TextView syncPill;
    private TextView syncLine;
    private TextView statGoal;
    private TextView statProgress;
    private TextView statSensor;
    private TextView statService;
    private TextView statBase;
    private TextView statLast;
    private TextView statResult;
    private TextView statDevice;
    private TextView statPermission;
    private TextView statNotification;
    private TextView statBattery;

    private LinearLayout banner;
    private TextView bannerTitle;
    private TextView bannerText;
    private Button bannerAction;
    private Button syncButton;
    private Button permissionButton;
    private Button batteryButton;

    private final Runnable ticker = new Runnable() {
        @Override
        public void run() {
            refresh(false);
            handler.postDelayed(this, 30_000L);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ui.systemBars(this);
        cfg = new AppConfig(this);
        repository = StepRepository.get(this);
        worker = Executors.newSingleThreadExecutor();
        handler = new Handler(Looper.getMainLooper());
        handleDeepLink(getIntent());
        setContentView(buildUi());
        refresh(true);
    }

    @Override
    protected void onResume() {
        super.onResume();
        registerReceiver();
        refresh(firstRefresh);
        firstRefresh = false;
        startIfNeeded();
        requestSyncIfStale();
        handler.removeCallbacks(ticker);
        handler.postDelayed(ticker, 30_000L);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(ticker);
        unregisterReceiver();
        super.onPause();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleDeepLink(intent);
        refresh(false);
        startIfNeeded();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        worker.shutdownNow();
        super.onDestroy();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == Permissions.REQUEST_STEP
                || requestCode == Permissions.REQUEST_NOTIFICATIONS) {
            if (Permissions.hasActivityRecognition(this)) {
                startStepService();
            }
            refresh(false);
        }
    }

    // ------------------------------------------------------------------
    // UI
    // ------------------------------------------------------------------

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Ui.BG);
        scroll.setClipToPadding(false);
        scroll.addView(buildContent(),
                new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT));
        return scroll;
    }

    private View buildContent() {
        LinearLayout root = Ui.column(this);
        int side = Ui.dp(this, 20);
        root.setPadding(side, Ui.dp(this, 18), side, Ui.dp(this, 30));

        root.addView(buildHeader(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 18));
        root.addView(buildHero(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 14));
        root.addView(buildActions(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 16));
        root.addView(buildBanner(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 16));
        root.addView(buildOverview(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 14));
        root.addView(buildSyncCard(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 14));
        root.addView(buildRuntimeCard(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 0));
        root.addView(buildFooter(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 8, 0, 0));
        return root;
    }

    private View buildHeader() {
        LinearLayout header = Ui.row(this);
        LinearLayout titles = Ui.column(this);

        TextView title = Ui.text(this, "小栖 · 步数", 26, Ui.TEXT,
                Typeface.BOLD, "sans-serif-medium");
        title.setLetterSpacing(0.01f);
        titles.addView(title);

        TextView sub = Ui.text(this, "把今天的脚步，带进房间", 13, Ui.DIM);
        titles.addView(sub, lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 5, 0, 0));

        header.addView(titles, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        servicePill = Ui.pill(this, "检查中", Ui.DIM, 0xFF232B35);
        header.addView(servicePill);
        return header;
    }

    private View buildHero() {
        LinearLayout hero = Ui.column(this);
        hero.setGravity(Gravity.CENTER_HORIZONTAL);
        hero.setPadding(Ui.dp(this, 12), Ui.dp(this, 16),
                Ui.dp(this, 12), Ui.dp(this, 18));
        android.graphics.drawable.GradientDrawable background =
                Ui.gradient(0xFF1E2A34, 0xFF141A21, 30, this);
        background.setStroke(Ui.dp(this, 1), 0xFF2B3946);
        hero.setBackground(background);

        FrameLayout ringBox = new FrameLayout(this);
        ringBox.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 292)));

        ring = new RingView(this);
        FrameLayout.LayoutParams ringParams = new FrameLayout.LayoutParams(
                Ui.dp(this, 260), Ui.dp(this, 260), Gravity.CENTER);
        ringBox.addView(ring, ringParams);

        LinearLayout center = Ui.column(this);
        center.setGravity(Gravity.CENTER_HORIZONTAL);

        TextView label = Ui.text(this, "今日步数", 12, Ui.DIM,
                Typeface.BOLD, "sans-serif-medium");
        label.setLetterSpacing(0.18f);
        center.addView(label);

        LinearLayout numberRow = Ui.row(this);
        numberRow.setGravity(Gravity.CENTER);
        stepNumber = Ui.bigNumber(this, "0");
        numberRow.addView(stepNumber);
        TextView unit = Ui.text(this, "步", 14, Ui.DIM);
        unit.setPadding(Ui.dp(this, 6), 0, 0, Ui.dp(this, 8));
        unit.setGravity(Gravity.BOTTOM);
        numberRow.addView(unit);
        center.addView(numberRow);

        goalLine = Ui.text(this, "目标 8,000 步 · 0%", 12, Ui.DIM);
        center.addView(goalLine, lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 4, 0, 0));

        ringBox.addView(center, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER));
        hero.addView(ringBox);

        syncPill = Ui.pill(this, "● 待配置", Ui.AMBER, 0xFF2A2318);
        hero.addView(syncPill, lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 0));

        syncLine = Ui.text(this, "尚未配置电脑地址与令牌", 12, Ui.DIM);
        syncLine.setGravity(Gravity.CENTER);
        hero.addView(syncLine, lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 6, 0, 0));
        return hero;
    }

    private View buildActions() {
        LinearLayout actions = Ui.row(this);
        syncButton = Ui.primaryButton(this, "立即同步");
        Button settingsButton = Ui.secondaryButton(this, "设置");
        actions.addView(syncButton, new LinearLayout.LayoutParams(
                0, Ui.dp(this, 52), 1f));
        LinearLayout.LayoutParams settingsParams = new LinearLayout.LayoutParams(
                0, Ui.dp(this, 52), 1f);
        settingsParams.leftMargin = Ui.dp(this, 10);
        actions.addView(settingsButton, settingsParams);

        syncButton.setOnClickListener(v -> onSyncClicked());
        settingsButton.setOnClickListener(v ->
                startActivity(new Intent(this, SettingsActivity.class)));
        return actions;
    }

    private View buildBanner() {
        banner = Ui.column(this);
        banner.setPadding(Ui.dp(this, 16), Ui.dp(this, 14),
                Ui.dp(this, 16), Ui.dp(this, 14));
        banner.setBackground(Ui.stroked(0xFF211C15, 0xFF4A3A22, 20, this));
        banner.setVisibility(View.GONE);

        bannerTitle = Ui.text(this, "", 14, Ui.AMBER,
                Typeface.BOLD, "sans-serif-medium");
        banner.addView(bannerTitle);
        bannerText = Ui.text(this, "", 12, Ui.DIM);
        banner.addView(bannerText, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 5, 0, 0));

        bannerAction = Ui.secondaryButton(this, "去处理");
        bannerAction.setTextColor(Ui.AMBER);
        bannerAction.setOnClickListener(v -> onBannerAction());
        LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 46));
        actionParams.topMargin = Ui.dp(this, 10);
        banner.addView(bannerAction, actionParams);
        return banner;
    }

    private View buildOverview() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "今日概览"));
        statGoal = addRow(card, "今日目标");
        statProgress = addRow(card, "完成度");
        statSensor = addRow(card, "计步方式");
        statService = addRow(card, "后台服务");
        return card;
    }

    private View buildSyncCard() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "同步到小栖"));
        statBase = addRow(card, "电脑地址");
        statBase.setTextSize(11);
        statLast = addRow(card, "上次同步");
        statResult = addRow(card, "同步结果");
        statDevice = addRow(card, "设备标识");
        statDevice.setTextSize(11);
        return card;
    }

    private View buildRuntimeCard() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "运行状态"));
        statPermission = addRow(card, "身体活动权限");
        statNotification = addRow(card, "通知权限");
        statBattery = addRow(card, "电池优化");

        LinearLayout buttons = Ui.row(this);
        permissionButton = Ui.secondaryButton(this, "权限设置");
        batteryButton = Ui.secondaryButton(this, "电池优化");
        buttons.addView(permissionButton, new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f));
        LinearLayout.LayoutParams batteryParams = new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f);
        batteryParams.leftMargin = Ui.dp(this, 10);
        buttons.addView(batteryButton, batteryParams);
        card.addView(buttons, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 10, 0, 0));

        TextView tip = Ui.text(this,
                "部分国产系统还需要在系统设置里允许“自启动 / 后台运行”，否则锁屏后可能被清理。",
                11, Ui.DIM_2);
        card.addView(tip, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 10, 0, 0));

        permissionButton.setOnClickListener(v -> {
            if (!Permissions.hasActivityRecognition(this)) {
                Permissions.requestStepPermissions(this);
            } else if (!Permissions.hasNotifications(this)) {
                Permissions.requestNotifications(this);
            } else {
                Toast.makeText(this, "计步与通知权限已齐全", Toast.LENGTH_SHORT).show();
            }
        });
        batteryButton.setOnClickListener(v -> {
            if (Permissions.isIgnoringBatteryOptimizations(this)) {
                Toast.makeText(this, "已忽略电池优化", Toast.LENGTH_SHORT).show();
            } else {
                Permissions.requestIgnoreBatteryOptimizations(this);
            }
        });
        return card;
    }

    private View buildFooter() {
        String version = versionName();
        TextView footer = Ui.text(this,
                "小栖 · 步数同步 " + version
                        + "\nPOST /api/ingest/health · source=android-app"
                        + "\n数据只在局域网内传输",
                11, Ui.DIM_2);
        footer.setGravity(Gravity.CENTER);
        footer.setLineSpacing(Ui.dp(this, 3), 1f);
        return footer;
    }

    private TextView addRow(LinearLayout card, String label) {
        LinearLayout row = Ui.rowItem(this, label, "—");
        card.addView(row);
        return (TextView) row.getChildAt(1);
    }

    private LinearLayout.LayoutParams lp(int width, int height,
                                         int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        params.setMargins(Ui.dp(this, left), Ui.dp(this, top),
                Ui.dp(this, right), Ui.dp(this, bottom));
        return params;
    }

    // ------------------------------------------------------------------
    // 状态刷新
    // ------------------------------------------------------------------

    private void refresh(boolean animate) {
        cfg = new AppConfig(this);
        long steps = repository.todaySteps();
        int goal = cfg.goalSteps();
        int percent = Format.ringPercent(steps, goal);

        ring.setProgress(percent / 100f, animate);
        ring.setContentDescription("今日 " + steps + " 步，目标 " + goal + " 步");
        stepNumber.setText(Format.steps(steps));
        goalLine.setText("目标 " + Format.steps(goal) + " 步 · " + Format.percent(steps, goal));

        boolean permission = Permissions.hasActivityRecognition(this);
        boolean notifications = Permissions.hasNotifications(this);
        boolean configured = cfg.isConfigured();
        boolean running = StepService.isRunning();
        boolean battery = Permissions.isIgnoringBatteryOptimizations(this);

        if (!permission) {
            setPill(servicePill, "未授权", Ui.AMBER, 0xFF2A2318);
        } else if (!running) {
            setPill(servicePill, "未启动", Ui.DIM, 0xFF232B35);
        } else if (cfg.sensorKind() == AppConfig.SENSOR_NONE) {
            setPill(servicePill, "无传感器", Ui.RED, 0xFF2A1B1A);
        } else {
            setPill(servicePill, "计步中", Ui.GREEN, 0xFF1C2A1C);
        }

        String syncState = Format.syncState(cfg);
        if ("已同步".equals(syncState)) {
            setPill(syncPill, "● 已同步", Ui.GREEN, 0xFF1C2A1C);
        } else if ("同步失败".equals(syncState)) {
            setPill(syncPill, "● 同步失败", Ui.RED, 0xFF2A1B1A);
        } else if ("待配置".equals(syncState)) {
            setPill(syncPill, "● 待配置", Ui.AMBER, 0xFF2A2318);
        } else {
            setPill(syncPill, "● 待同步", Ui.AMBER, 0xFF2A2318);
        }
        syncLine.setText(Format.syncLine(cfg));

        statGoal.setText(Format.steps(goal) + " 步");
        long remain = Math.max(0L, goal - steps);
        statProgress.setText(Format.percent(steps, goal)
                + (remain > 0 ? " · 还差 " + Format.steps(remain) + " 步" : " · 已达成"));
        statProgress.setTextColor(remain > 0 ? Ui.TEXT : Ui.GREEN);

        if (!running) {
            statSensor.setText("服务未启动");
        } else if (cfg.sensorAvailable()) {
            statSensor.setText(cfg.sensorKind() == AppConfig.SENSOR_DETECTOR
                    ? "步数检测器（降级）" : "硬件计步器");
        } else {
            statSensor.setText("未检测到");
        }
        statService.setText(running
                ? "运行中 · 每 " + intervalLabel(cfg.syncIntervalSec()) + "同步"
                : "未启动");

        statBase.setText(configured ? cfg.normalizedBaseUrl() : "未配置");
        statBase.setTextColor(configured ? Ui.TEXT : Ui.AMBER);
        if (cfg.lastSyncAt() > 0L) {
            statLast.setText(Format.time(cfg.lastSyncAt()) + " · "
                    + Format.age(System.currentTimeMillis() - cfg.lastSyncAt()));
        } else {
            statLast.setText("—");
        }
        if (cfg.lastAttemptAt() <= 0L) {
            statResult.setText("尚未同步");
            statResult.setTextColor(Ui.DIM);
        } else {
            statResult.setText(cfg.lastSyncMessage());
            statResult.setTextColor(cfg.lastSyncOk() ? Ui.GREEN : Ui.RED);
        }
        statDevice.setText(cfg.deviceId());

        statPermission.setText(permission ? "已授权" : "未授权");
        statPermission.setTextColor(permission ? Ui.GREEN : Ui.AMBER);
        statNotification.setText(notifications ? "已授权" : "未授权");
        statNotification.setTextColor(notifications ? Ui.GREEN : Ui.AMBER);
        statBattery.setText(battery ? "已忽略（推荐）" : "受系统限制");
        statBattery.setTextColor(battery ? Ui.GREEN : Ui.AMBER);

        updateBanner(permission, configured, running, notifications);
    }

    private void updateBanner(boolean permission, boolean configured,
                             boolean running, boolean notifications) {
        if (!permission) {
            showBanner(BANNER_PERMISSION, "还差一步：允许“身体活动”",
                    "Android 10 起，读取计步传感器需要该权限；授予后后台计步才能开始。",
                    "授予权限");
        } else if (!configured) {
            showBanner(BANNER_CONFIG, "连接你的电脑",
                    "在电脑上启动小栖后端，把控制台里的地址与配对令牌填进来（手机与电脑需同一 Wi-Fi）。",
                    "去配置");
        } else if (!running) {
            showBanner(BANNER_START, "后台计步还没有启动",
                    "启动后锁屏也会继续记录，零点自动开新的一天。建议同时允许忽略电池优化。",
                    "启动计步");
        } else if (!notifications) {
            showBanner(BANNER_NOTIFICATION, "通知权限被关闭",
                    "前台服务仍在计步，但常驻通知与同步状态会被系统隐藏。",
                    "去开启");
        } else {
            bannerType = BANNER_NONE;
            banner.setVisibility(View.GONE);
        }
    }

    private void showBanner(int type, String title, String text, String action) {
        bannerType = type;
        bannerTitle.setText(title);
        bannerText.setText(text);
        bannerAction.setText(action);
        banner.setVisibility(View.VISIBLE);
    }

    private void onBannerAction() {
        switch (bannerType) {
            case BANNER_PERMISSION:
                Permissions.requestStepPermissions(this);
                break;
            case BANNER_CONFIG:
                startActivity(new Intent(this, SettingsActivity.class));
                break;
            case BANNER_START:
                startStepService();
                break;
            case BANNER_NOTIFICATION:
                Permissions.requestNotifications(this);
                break;
            default:
                break;
        }
    }

    private void setPill(TextView view, String text, int foreground, int background) {
        view.setText(text);
        view.setTextColor(foreground);
        view.setBackground(Ui.rounded(background, 99, this));
    }

    private String intervalLabel(int seconds) {
        if (seconds < 3600) {
            return (seconds / 60) + " 分钟";
        }
        return String.format(Locale.CHINA, "%.1f 小时", seconds / 3600f);
    }

    // ------------------------------------------------------------------
    // 动作
    // ------------------------------------------------------------------

    private void onSyncClicked() {
        if (!Permissions.hasActivityRecognition(this)) {
            Permissions.requestStepPermissions(this);
            return;
        }
        cfg = new AppConfig(this);
        if (!cfg.isConfigured()) {
            startActivity(new Intent(this, SettingsActivity.class));
            return;
        }
        syncButton.setEnabled(false);
        syncButton.setText("同步中…");
        worker.execute(() -> {
            SyncResult result = SyncRunner.syncNow(this, true);
            runOnUiThread(() -> {
                syncButton.setEnabled(true);
                syncButton.setText("立即同步");
                refresh(false);
                Toast.makeText(this, result.message, Toast.LENGTH_SHORT).show();
            });
        });
    }

    private void startIfNeeded() {
        if (!cfg.serviceRequested() || !Permissions.hasActivityRecognition(this)) {
            return;
        }
        if (!StepService.isRunning()) {
            startStepService();
        } else if (!cfg.sensorAvailable() || cfg.sensorKind() == AppConfig.SENSOR_NONE) {
            // 服务在跑但传感器还没注册成功（例如权限是刚去系统设置里开的）：
            // 再发一次 start 让 StepService 补注册，不重置任何步数。
            try {
                StepService.start(this);
            } catch (Exception ignored) {
                // 前台服务启动限制/厂商拦截时忽略，下次 onResume 再试。
            }
        }
    }

    private void startStepService() {
        if (!Permissions.hasActivityRecognition(this)) {
            Permissions.requestStepPermissions(this);
            return;
        }
        cfg.setServiceRequested(true);
        try {
            StepService.start(this);
            SyncJobService.schedule(this);
        } catch (Exception e) {
            Toast.makeText(this, "启动失败：" + e.getClass().getSimpleName(),
                    Toast.LENGTH_LONG).show();
        }
        refresh(false);
    }

    /** 打开 App 时如果距上次尝试超过 75 秒，顺手补一次同步（避开后端 60s 幂等窗口）。 */
    private void requestSyncIfStale() {
        cfg = new AppConfig(this);
        if (!cfg.serviceRequested() || !cfg.isConfigured() || !cfg.autoSync()
                || !StepService.isRunning()) {
            return;
        }
        long age = System.currentTimeMillis() - cfg.lastAttemptAt();
        if (age > 75_000L) {
            try {
                StepService.requestSync(this);
            } catch (Exception ignored) {
                // 前台服务启动受限时等周期同步。
            }
        }
    }

    private void registerReceiver() {
        if (receiverRegistered) {
            return;
        }
        receiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                refresh(false);
            }
        };
        IntentFilter filter = new IntentFilter(StepService.ACTION_STATE_CHANGED);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(receiver, filter);
        }
        receiverRegistered = true;
    }

    private void unregisterReceiver() {
        if (!receiverRegistered) {
            return;
        }
        try {
            unregisterReceiver(receiver);
        } catch (Exception ignored) {
            // 已注销。
        }
        receiverRegistered = false;
        receiver = null;
    }

    private void handleDeepLink(Intent intent) {
        if (intent == null) {
            return;
        }
        Uri data = intent.getData();
        if (data == null || !"xiaoqi".equals(data.getScheme())
                || !"pair".equals(data.getHost())) {
            return;
        }
        String base = data.getQueryParameter("base");
        String token = data.getQueryParameter("token");
        if (base == null && token == null) {
            return;
        }
        AppConfig fresh = new AppConfig(this);
        fresh.saveConnection(base != null ? base : fresh.baseUrl(),
                token != null ? token : fresh.token());
        if (fresh.isConfigured()) {
            fresh.setServiceRequested(true);
        }
        Toast.makeText(this, "已导入小栖配对信息", Toast.LENGTH_SHORT).show();
    }

    private String versionName() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            return "v" + info.versionName;
        } catch (Exception e) {
            return "v1.0.0";
        }
    }
}
