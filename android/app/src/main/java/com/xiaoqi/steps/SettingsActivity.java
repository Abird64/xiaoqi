package com.xiaoqi.steps;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import com.xiaoqi.steps.core.SyncClient;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 设置页：配对、同步节奏、权限、演示工具。 */
public final class SettingsActivity extends Activity {

    private static final int[] INTERVAL_VALUES = {60, 300, 600};
    private static final String[] INTERVAL_LABELS = {"1 分钟", "5 分钟", "10 分钟"};

    private AppConfig cfg;
    private StepRepository repository;
    private ExecutorService worker;
    private Handler handler;

    private EditText baseInput;
    private EditText tokenInput;
    private EditText goalInput;
    private Spinner intervalSpinner;
    private Switch autoSyncSwitch;
    private Switch autoStartSwitch;
    private TextView testResult;
    private TextView currentSteps;
    private TextView permissionStatus;
    private TextView notificationStatus;
    private TextView batteryStatus;
    private Button fetchTokenButton;
    private Button testButton;
    private boolean pendingStart;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ui.systemBars(this);
        cfg = new AppConfig(this);
        repository = StepRepository.get(this);
        worker = Executors.newSingleThreadExecutor();
        handler = new Handler(Looper.getMainLooper());
        setContentView(buildUi());
        fillForm();
        refreshStatus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    @Override
    protected void onDestroy() {
        worker.shutdownNow();
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == Permissions.REQUEST_STEP) {
            refreshStatus();
            if (pendingStart && Permissions.hasActivityRecognition(this)) {
                pendingStart = false;
                startServiceNow();
                Toast.makeText(this, "权限已授予，后台计步已启动", Toast.LENGTH_SHORT).show();
                finish();
            }
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
        LinearLayout root = Ui.column(this);
        int side = Ui.dp(this, 20);
        root.setPadding(side, Ui.dp(this, 16), side, Ui.dp(this, 30));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        root.addView(buildHeader(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 0, 0, 18));
        root.addView(buildConnectionCard());
        root.addView(buildSyncCard());
        root.addView(buildPermissionCard());
        root.addView(buildDebugCard());
        root.addView(buildSaveArea());
        root.addView(buildFooter(), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 16, 0, 0));
        return scroll;
    }

    private View buildHeader() {
        LinearLayout header = Ui.row(this);
        TextView back = Ui.text(this, "‹", 34, Ui.TEXT,
                Typeface.NORMAL, "sans-serif-light");
        back.setGravity(Gravity.CENTER);
        back.setPadding(Ui.dp(this, 0), 0, Ui.dp(this, 14), Ui.dp(this, 2));
        back.setOnClickListener(v -> finish());
        back.setContentDescription("返回");
        header.addView(back);

        LinearLayout titles = Ui.column(this);
        TextView title = Ui.text(this, "设置", 24, Ui.TEXT,
                Typeface.BOLD, "sans-serif-medium");
        titles.addView(title);
        titles.addView(Ui.text(this, "手机 → 小栖后端", 12, Ui.DIM),
                lp(ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT, 0, 4, 0, 0));
        header.addView(titles, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return header;
    }

    private View buildConnectionCard() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "连接小栖"));

        card.addView(fieldLabel("电脑地址"));
        baseInput = input("http://192.168.1.5:8000", InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_URI);
        card.addView(baseInput);
        TextView hint = Ui.text(this,
                "后端默认监听 8000 端口；手机与电脑需在同一 Wi-Fi。", 11, Ui.DIM_2);
        card.addView(hint, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 6, 0, 12));

        card.addView(fieldLabel("配对令牌"));
        tokenInput = input("后端控制台打印的 X-Xiaoqi-Token", InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        card.addView(tokenInput);

        LinearLayout buttons = Ui.row(this);
        fetchTokenButton = Ui.secondaryButton(this, "自动获取令牌");
        testButton = Ui.secondaryButton(this, "测试连接");
        buttons.addView(fetchTokenButton, new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f));
        LinearLayout.LayoutParams testParams = new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f);
        testParams.leftMargin = Ui.dp(this, 10);
        buttons.addView(testButton, testParams);
        card.addView(buttons, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 12, 0, 0));

        testResult = Ui.text(this, "填好地址后点“测试连接”，只读取状态、不会写入步数。",
                12, Ui.DIM_2);
        card.addView(testResult, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 10, 0, 0));

        fetchTokenButton.setOnClickListener(v -> fetchToken());
        testButton.setOnClickListener(v -> testConnection());
        return card;
    }

    private View buildSyncCard() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "同步节奏"));

        card.addView(fieldLabel("每日目标"));
        LinearLayout goalRow = Ui.row(this);
        goalInput = input("8000", InputType.TYPE_CLASS_NUMBER);
        goalRow.addView(goalInput, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView unit = Ui.text(this, "步", 14, Ui.DIM);
        unit.setPadding(Ui.dp(this, 10), 0, 0, 0);
        goalRow.addView(unit);
        card.addView(goalRow);

        card.addView(fieldLabel("自动同步间隔"), lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 14, 0, 6));
        intervalSpinner = new Spinner(this);
        ArrayAdapter<String> adapter = new ArrayAdapter<String>(this,
                android.R.layout.simple_spinner_item, INTERVAL_LABELS) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getView(position, convertView, parent);
                styleSpinnerText(view);
                return view;
            }

            @Override
            public View getDropDownView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getDropDownView(position, convertView, parent);
                styleSpinnerText(view);
                return view;
            }
        };
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        intervalSpinner.setAdapter(adapter);
        intervalSpinner.setBackground(null);
        intervalSpinner.setPadding(Ui.dp(this, 8), 0, 0, 0);
        intervalSpinner.setPopupBackgroundDrawable(Ui.rounded(0xFF1A212A, 14, this));

        LinearLayout spinnerRow = Ui.row(this);
        spinnerRow.setBackground(Ui.stroked(0xFF141A21, Ui.STROKE, 14, this));
        spinnerRow.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 12), 0);
        spinnerRow.addView(intervalSpinner, new LinearLayout.LayoutParams(
                0, Ui.dp(this, 50), 1f));
        TextView arrow = Ui.text(this, "▾", 16, Ui.DIM);
        spinnerRow.addView(arrow);
        card.addView(spinnerRow, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                Ui.dp(this, 50), 0, 0, 0, 0));
        TextView hint = Ui.text(this,
                "协议规定同设备 60 秒内重复上报会被后端幂等丢弃；建议 5 分钟。"
                        + "最长 10 分钟（超过 15 分钟未更新前端会显示「待同步」）。"
                        + "步数每增加 300 步会提前同步一次（≥75 秒）。", 11, Ui.DIM_2);
        card.addView(hint, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 8, 0, 10));

        autoSyncSwitch = switchRow("自动同步", "按上面的间隔把今日步数推给电脑", true);
        autoStartSwitch = switchRow("开机自启", "重启手机后自动恢复后台计步", true);
        card.addView(autoSyncSwitch);
        card.addView(autoStartSwitch);
        return card;
    }

    private Switch switchRow(String title, String subtitle, boolean value) {
        Switch sw = new Switch(this);
        sw.setText(title);
        sw.setTextColor(Ui.TEXT);
        sw.setTextSize(14);
        sw.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        sw.setChecked(value);
        sw.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        sw.setThumbTintList(ColorStateList.valueOf(Ui.GREEN));
        sw.setTrackTintList(ColorStateList.valueOf(0xFF3A4856));
        sw.setContentDescription(title + "：" + subtitle);
        return sw;
    }

    private View buildPermissionCard() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "权限与后台"));

        permissionStatus = addRow(card, "身体活动权限");
        notificationStatus = addRow(card, "通知权限");
        batteryStatus = addRow(card, "电池优化");

        LinearLayout buttons = Ui.row(this);
        Button permissionButton = Ui.secondaryButton(this, "授予权限");
        Button batteryButton = Ui.secondaryButton(this, "电池优化");
        buttons.addView(permissionButton, new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f));
        LinearLayout.LayoutParams batteryParams = new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f);
        batteryParams.leftMargin = Ui.dp(this, 10);
        buttons.addView(batteryButton, batteryParams);
        card.addView(buttons, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 10, 0, 0));

        permissionButton.setOnClickListener(v -> {
            if (!Permissions.hasActivityRecognition(this)) {
                Permissions.requestStepPermissions(this);
            } else if (!Permissions.hasNotifications(this)) {
                Permissions.requestNotifications(this);
            } else {
                Permissions.openAppNotificationSettings(this);
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

    private View buildDebugCard() {
        LinearLayout card = Ui.card(this);
        card.addView(Ui.sectionTitle(this, "演示与排障"));
        currentSteps = Ui.text(this, "今日 0 步", 13, Ui.DIM);
        card.addView(currentSteps);

        LinearLayout buttons = Ui.row(this);
        Button addButton = Ui.secondaryButton(this, "+1000 步");
        Button resetButton = Ui.secondaryButton(this, "今日清零");
        buttons.addView(addButton, new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f));
        LinearLayout.LayoutParams resetParams = new LinearLayout.LayoutParams(
                0, Ui.dp(this, 44), 1f);
        resetParams.leftMargin = Ui.dp(this, 10);
        buttons.addView(resetButton, resetParams);
        card.addView(buttons, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 10, 0, 0));

        TextView tip = Ui.text(this,
                "仅用于没有真机传感器时的联调：演示步数会像真实步数一样参与上报，"
                        + "但不会改变传感器基线。清零只清“今日”，不影响同步配置。",
                11, Ui.DIM_2);
        card.addView(tip, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, 0, 8, 0, 0));

        addButton.setOnClickListener(v -> {
            repository.addDemoSteps(1000);
            refreshStatus();
            Toast.makeText(this, "已加 1000 步", Toast.LENGTH_SHORT).show();
            SyncRunner.broadcast(this);
        });
        resetButton.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("今日清零？")
                .setMessage("只把本机“今日步数”归零，用于演示；已同步到电脑的历史记录不会删除。")
                .setNegativeButton("取消", null)
                .setPositiveButton("清零", (dialog, which) -> {
                    repository.resetToday();
                    refreshStatus();
                    SyncRunner.broadcast(this);
                })
                .show());
        return card;
    }

    private View buildSaveArea() {
        LinearLayout area = Ui.column(this);
        Button save = Ui.primaryButton(this, "保存并启动");
        area.addView(save, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                Ui.dp(this, 52), 0, 0, 0, 0));
        Button stop = Ui.secondaryButton(this, "停止后台计步");
        stop.setTextColor(Ui.RED);
        area.addView(stop, lp(ViewGroup.LayoutParams.MATCH_PARENT,
                Ui.dp(this, 48), 0, 10, 0, 0));
        save.setOnClickListener(v -> saveAndStart());
        stop.setOnClickListener(v -> confirmStop());
        return area;
    }

    private View buildFooter() {
        TextView footer = Ui.text(this,
                "设备标识 " + cfg.deviceId()
                        + "\nPOST /api/ingest/health · X-Xiaoqi-Token",
                11, Ui.DIM_2);
        footer.setGravity(Gravity.CENTER);
        footer.setLineSpacing(Ui.dp(this, 3), 1f);
        return footer;
    }

    private TextView fieldLabel(String text) {
        TextView label = Ui.text(this, text, 12, Ui.DIM,
                Typeface.BOLD, "sans-serif-medium");
        label.setPadding(0, Ui.dp(this, 12), 0, Ui.dp(this, 6));
        return label;
    }

    private EditText input(String hint, int inputType) {
        EditText edit = new EditText(this);
        edit.setHint(hint);
        edit.setHintTextColor(Ui.DIM_2);
        edit.setTextColor(Ui.TEXT);
        edit.setTextSize(15);
        edit.setSingleLine(true);
        edit.setInputType(inputType);
        edit.setBackground(Ui.stroked(0xFF141A21, Ui.STROKE, 14, this));
        edit.setPadding(Ui.dp(this, 14), Ui.dp(this, 12),
                Ui.dp(this, 14), Ui.dp(this, 12));
        return edit;
    }

    private void styleSpinnerText(TextView view) {
        view.setTextColor(Ui.TEXT);
        view.setTextSize(15);
        view.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        view.setPadding(Ui.dp(this, 6), 0, Ui.dp(this, 6), 0);
    }

    private LinearLayout.LayoutParams lp(int width, int height,
                                         int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        params.setMargins(Ui.dp(this, left), Ui.dp(this, top),
                Ui.dp(this, right), Ui.dp(this, bottom));
        return params;
    }

    private TextView addRow(LinearLayout card, String label) {
        LinearLayout row = Ui.rowItem(this, label, "—");
        card.addView(row);
        return (TextView) row.getChildAt(1);
    }

    // ------------------------------------------------------------------
    // 数据与动作
    // ------------------------------------------------------------------

    private void fillForm() {
        baseInput.setText(cfg.baseUrl());
        tokenInput.setText(cfg.token());
        goalInput.setText(String.valueOf(cfg.goalSteps()));
        int selected = 1;
        for (int i = 0; i < INTERVAL_VALUES.length; i++) {
            if (INTERVAL_VALUES[i] == cfg.syncIntervalSec()) {
                selected = i;
                break;
            }
        }
        intervalSpinner.setSelection(selected);
        autoSyncSwitch.setChecked(cfg.autoSync());
        autoStartSwitch.setChecked(cfg.autoStart());
    }

    private void refreshStatus() {
        cfg = new AppConfig(this);
        long steps = repository.todaySteps();
        currentSteps.setText("今日 " + Format.steps(steps) + " 步（"
                + Format.percent(steps, cfg.goalSteps()) + "）");

        boolean permission = Permissions.hasActivityRecognition(this);
        boolean notifications = Permissions.hasNotifications(this);
        boolean battery = Permissions.isIgnoringBatteryOptimizations(this);
        setStatus(permissionStatus, permission ? "已授权" : "未授权", permission);
        setStatus(notificationStatus, notifications ? "已授权" : "未授权", notifications);
        setStatus(batteryStatus, battery ? "已忽略（推荐）" : "受系统限制", battery);
    }

    private void setStatus(TextView view, String text, boolean ok) {
        view.setText(text);
        view.setTextColor(ok ? Ui.GREEN : Ui.AMBER);
    }

    private void fetchToken() {
        String base = SyncClient.normalizeBaseUrl(baseInput.getText().toString());
        if (base.isEmpty()) {
            testResult.setTextColor(Ui.RED);
            testResult.setText("先填一个合法的电脑地址，例如 http://192.168.1.5:8000");
            return;
        }
        fetchTokenButton.setEnabled(false);
        testResult.setTextColor(Ui.DIM);
        testResult.setText("正在向 " + base + "/api/token 取令牌…");
        worker.execute(() -> {
            SyncClient.TokenResult result = SyncClient.fetchToken(base);
            runOnUiThread(() -> {
                fetchTokenButton.setEnabled(true);
                if (result.ok) {
                    tokenInput.setText(result.token);
                    testResult.setTextColor(Ui.GREEN);
                    testResult.setText("已取到令牌，点“保存并启动”即可。");
                } else {
                    testResult.setTextColor(Ui.RED);
                    testResult.setText("取令牌失败：" + result.error
                            + "\n可从后端控制台复制令牌后手动填入。");
                }
            });
        });
    }

    private void testConnection() {
        String base = SyncClient.normalizeBaseUrl(baseInput.getText().toString());
        if (base.isEmpty()) {
            testResult.setTextColor(Ui.RED);
            testResult.setText("先填一个合法的电脑地址，例如 http://192.168.1.5:8000");
            return;
        }
        testButton.setEnabled(false);
        testResult.setTextColor(Ui.DIM);
        testResult.setText("正在连接 " + base + " …");
        worker.execute(() -> {
            SyncClient.HealthResult health = SyncClient.health(base);
            SyncClient.RemoteState state = SyncClient.fetchState(base);
            runOnUiThread(() -> {
                testButton.setEnabled(true);
                if (!health.ok) {
                    testResult.setTextColor(Ui.RED);
                    testResult.setText("连不上：" + health.error
                            + "\n检查手机与电脑是否同一 Wi-Fi、地址/端口、电脑防火墙。");
                    return;
                }
                StringBuilder text = new StringBuilder();
                text.append("已连接 · 小栖后端 ").append(health.version)
                        .append(" · 在线前端 ").append(health.clients).append(" 个");
                if (state.ok && state.steps != null) {
                    text.append("\n服务端已有 ").append(Format.steps(state.steps)).append(" 步");
                    text.append(state.stale ? "（超过 15 分钟未更新）" : "（数据是新的）");
                } else if (state.ok) {
                    text.append("\n服务端还没有手机步数，保存后点“立即同步”。");
                }
                testResult.setTextColor(Ui.GREEN);
                testResult.setText(text.toString());
            });
        });
    }

    private void saveAndStart() {
        String rawBase = baseInput.getText().toString().trim();
        String normalized = SyncClient.normalizeBaseUrl(rawBase);
        if (!rawBase.isEmpty() && normalized.isEmpty()) {
            testResult.setTextColor(Ui.RED);
            testResult.setText("电脑地址不合法：必须以 http:// 或 https:// 开头，并包含主机名。");
            baseInput.requestFocus();
            return;
        }
        String token = tokenInput.getText().toString().trim();
        int goal;
        try {
            goal = Integer.parseInt(goalInput.getText().toString().trim());
        } catch (NumberFormatException e) {
            goal = AppConfig.DEFAULT_GOAL;
        }
        goal = Math.max(1000, Math.min(100_000, goal));
        int interval = INTERVAL_VALUES[Math.max(0,
                Math.min(INTERVAL_VALUES.length - 1, intervalSpinner.getSelectedItemPosition()))];

        cfg.saveConnection(normalized, token);
        cfg.saveGoal(goal);
        cfg.saveSyncInterval(interval);
        cfg.setAutoSync(autoSyncSwitch.isChecked());
        cfg.setAutoStart(autoStartSwitch.isChecked());
        cfg.setServiceRequested(true);
        SyncJobService.schedule(this);

        if (!Permissions.hasActivityRecognition(this)) {
            pendingStart = true;
            Permissions.requestStepPermissions(this);
            Toast.makeText(this, "已保存；请授予“身体活动”权限以开始计步",
                    Toast.LENGTH_LONG).show();
            return;
        }
        startServiceNow();
        String message = token.isEmpty()
                ? "已保存；令牌为空时不会自动同步" : "已保存，后台计步已启动";
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
        finish();
    }

    private void startServiceNow() {
        try {
            StepService.start(this);
            SyncJobService.schedule(this);
        } catch (Exception e) {
            Toast.makeText(this, "启动失败：" + e.getClass().getSimpleName(),
                    Toast.LENGTH_LONG).show();
        }
    }

    private void confirmStop() {
        new AlertDialog.Builder(this)
                .setTitle("停止后台计步？")
                .setMessage("停止后锁屏不再记录新步数；已记录的今日步数与配置都会保留。")
                .setNegativeButton("取消", null)
                .setPositiveButton("停止", (dialog, which) -> {
                    cfg.setServiceRequested(false);
                    StepService.stop(this);
                    SyncJobService.cancel(this);
                    refreshStatus();
                    Toast.makeText(this, "已停止后台计步", Toast.LENGTH_SHORT).show();
                })
                .show();
    }
}
