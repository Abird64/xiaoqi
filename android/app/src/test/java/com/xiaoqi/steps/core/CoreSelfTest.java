package com.xiaoqi.steps.core;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 纯 JVM 自测：不依赖 Android、不依赖 JUnit、不依赖网络外网。
 *
 * <p>运行方式见 {@code tools/test-core.ps1}。覆盖三块：</p>
 * <ul>
 *   <li>StepTracker：首次基线、日切、重启、长时间断流、防跳变、降级计步器；</li>
 *   <li>SyncClient：地址归一化、请求体、令牌头、200/400/401、去重标记、探测接口；</li>
 *   <li>MiniJson：转义与字段解析。</li>
 * </ul>
 */
public final class CoreSelfTest {

    private static int passed;
    private static int failed;

    public static void main(String[] args) throws Exception {
        testDayKey();
        testTrackerBasics();
        testMidnightCarry();
        testLongGapAcrossMidnight();
        testReboot();
        testImplausibleJump();
        testDetectorFallback();
        testRollDay();
        testNormalizeBaseUrl();
        testPayload();
        testMiniJson();
        testHttpClient();
        testHttpErrors();

        System.out.println();
        System.out.println("========================================");
        System.out.println("CoreSelfTest: " + passed + " passed, " + failed + " failed");
        System.out.println("========================================");
        if (failed > 0) {
            System.exit(1);
        }
    }

    private static void testDayKey() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long ms = LocalDateTime.of(2026, 11, 8, 0, 0, 0)
                .atZone(sh).toInstant().toEpochMilli();
        eq("2026-11-08", StepTracker.dayKey(ms, sh), "dayKey 零点");
        eq("2026-11-08", StepTracker.dayKey(ms + 86_399_999L, sh), "dayKey 当天最后一毫秒");
        eq("2026-11-09", StepTracker.dayKey(ms + 86_400_000L, sh), "dayKey 次日零点");
        eq(ms, StepTracker.startOfDayMs(ms + 12 * 3600_000L, sh), "startOfDayMs");
    }

    private static void testTrackerBasics() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long t = at(sh, 2026, 11, 8, 8, 0);
        StepTracker tracker = new StepTracker();
        tracker.onCounter(5000, t, "2026-11-08");
        eq(0L, tracker.todaySteps(), "首次只建基线，不把开机以来步数算进今天");
        tracker.onCounter(5100, t + 60_000, "2026-11-08");
        eq(100L, tracker.todaySteps(), "第二次增量 +100");
        tracker.onCounter(5200, t + 120_000, "2026-11-08");
        eq(200L, tracker.todaySteps(), "第三次增量 +100");
        tracker.onCounter(5200, t + 180_000, "2026-11-08");
        eq(200L, tracker.todaySteps(), "读数不变不加步");
    }

    private static void testMidnightCarry() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long t = at(sh, 2026, 11, 8, 23, 59);
        StepTracker tracker = new StepTracker("2026-11-08", 200, 5200, t);
        StepTracker.Update update = tracker.onCounter(5250, t + 6 * 60_000, "2026-11-09");
        yes(update.dayRolled, "日切标记");
        eq(50L, tracker.todaySteps(), "跨零点 6 分钟内的 50 步计入新一天");
        eq(0L, update.delta - 50L, "delta=50");
    }

    private static void testLongGapAcrossMidnight() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long tPrev = at(sh, 2026, 11, 7, 20, 0);
        long tNow = at(sh, 2026, 11, 8, 10, 0);
        StepTracker tracker = new StepTracker("2026-11-07", 1200, 1000, tPrev);
        StepTracker.Update update = tracker.onCounter(5000, tNow, "2026-11-08");
        yes(update.dayRolled, "跨天标记");
        eq(0L, tracker.todaySteps(), "跨天且断流 14 小时：整段丢弃，不能把昨天的步数算进今天");
        eq(5000L, tracker.lastTotal(), "基线仍推进到最新读数");
    }

    private static void testReboot() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long t = at(sh, 2026, 11, 8, 10, 0);
        StepTracker tracker = new StepTracker("2026-11-08", 3000, 8000, t);
        StepTracker.Update update = tracker.onCounter(20, t + 5 * 60_000, "2026-11-08");
        eq(3020L, tracker.todaySteps(), "重启后读数归零：把新读数 20 当作增量");
        eq(20L, update.delta, "重启 delta");
    }

    private static void testImplausibleJump() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long t = at(sh, 2026, 11, 8, 10, 0);
        StepTracker tracker = new StepTracker("2026-11-08", 100, 1000, t);
        tracker.onCounter(100_000, t + 10_000, "2026-11-08");
        eq(100L, tracker.todaySteps(), "10 秒跳 99000 步：判定异常，不计数");
    }

    private static void testDetectorFallback() {
        ZoneId sh = ZoneId.of("Asia/Shanghai");
        long t = at(sh, 2026, 11, 8, 23, 59);
        StepTracker tracker = new StepTracker();
        tracker.onDetector(t, "2026-11-08");
        tracker.onDetector(t + 1000, "2026-11-08");
        tracker.onDetector(t + 2000, "2026-11-08");
        eq(2L, tracker.todaySteps(), "降级计步器：每个事件 +1（首个只建基线）");
        tracker.onDetector(t + 2 * 60_000, "2026-11-09");
        eq(1L, tracker.todaySteps(), "降级计步器跨天清零");
    }

    private static void testRollDay() {
        StepTracker tracker = new StepTracker("2026-11-08", 500, 5000, 1L);
        yes(tracker.rollDay("2026-11-09"), "rollDay 返回 true");
        eq(0L, tracker.todaySteps(), "UI 零点刷新后显示 0");
        yes(!tracker.rollDay("2026-11-09"), "同一天再调用返回 false");
    }

    private static void testNormalizeBaseUrl() {
        eq("http://192.168.1.5:8000", SyncClient.normalizeBaseUrl("192.168.1.5:8000"), "补 http://");
        eq("http://192.168.1.5:8000", SyncClient.normalizeBaseUrl(" http://192.168.1.5:8000/ "), "去尾斜杠");
        eq("http://192.168.1.5:8000",
                SyncClient.normalizeBaseUrl("http://192.168.1.5:8000/api/ingest/health"),
                "粘贴完整上报地址");
        eq("https://example.com/xiaoqi",
                SyncClient.normalizeBaseUrl("https://example.com/xiaoqi/"), "保留部署子路径");
        eq("http://[::1]:8000", SyncClient.normalizeBaseUrl("http://[::1]:8000/"), "IPv6");
        eq("", SyncClient.normalizeBaseUrl("ftp://1.2.3.4"), "拒绝非 http(s)");
        eq("", SyncClient.normalizeBaseUrl(""), "空输入");
        eq("", SyncClient.normalizeBaseUrl("   "), "空白输入");
    }

    private static void testPayload() {
        String payload = SyncClient.buildPayload(3210, 1789526000000L, "android-abc");
        yes(payload.contains("\"steps\":3210"), "payload steps");
        yes(payload.contains("\"source\":\"android-app\""), "payload source");
        yes(payload.contains("\"device_id\":\"android-abc\""), "payload device");
        yes(payload.contains("\"ts\":1789526000000"), "payload ts");
        String escaped = SyncClient.buildPayload(1, 2, "a\"b\\c\nx");
        yes(escaped.contains("a\\\"b\\\\c\\nx"), "device_id JSON 转义");
        eq(0L, payloadSteps(SyncClient.buildPayload(-5, 2, "x")), "负数步数归零");
    }

    private static long payloadSteps(String payload) {
        Long value = MiniJson.longField(payload, "steps");
        return value == null ? -1 : value;
    }

    private static void testMiniJson() {
        String json = "{\"ok\":true,\"deduped\":false,\"steps\":3210,"
                + "\"error\":\"BAD_TOKEN\",\"msg\":\"a\\\"b\\n\"}";
        eq(Boolean.TRUE, MiniJson.boolField(json, "ok"), "bool true");
        eq(Boolean.FALSE, MiniJson.boolField(json, "deduped"), "bool false");
        eq(3210L, MiniJson.longField(json, "steps"), "long");
        eq("BAD_TOKEN", MiniJson.stringField(json, "error"), "string");
        eq("a\"b\n", MiniJson.stringField(json, "msg"), "unescape");
        eq(null, MiniJson.stringField(json, "missing"), "缺失返回 null");
        eq("中文 \"引号\" \\ 反斜杠",
                MiniJson.unescape(MiniJson.escape("中文 \"引号\" \\ 反斜杠")), "escape/unescape 往返");
    }

    private static void testHttpClient() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        AtomicReference<String> lastBody = new AtomicReference<>("");
        AtomicReference<String> lastToken = new AtomicReference<>("");
        server.createContext("/api/ingest/health", exchange -> {
            String body = readAll(exchange.getRequestBody());
            lastBody.set(body);
            lastToken.set(exchange.getRequestHeaders().getFirst("X-Xiaoqi-Token"));
            if (!"test-token".equals(lastToken.get())) {
                respond(exchange, 401, "{\"ok\":false,\"error\":\"BAD_TOKEN\"}");
                return;
            }
            if (body == null || !body.contains("\"steps\":")) {
                respond(exchange, 400, "{\"ok\":false,\"error\":\"INVALID_FIELD\",\"field\":\"steps\"}");
                return;
            }
            boolean deduped = body.contains("\"steps\":111");
            respond(exchange, 200, "{\"ok\":true,\"deduped\":" + deduped + "}");
        });
        server.createContext("/api/token", exchange ->
                respond(exchange, 200, "{\"token\":\"abc-123\",\"endpoint\":\"/api/ingest/health\"}"));
        server.createContext("/api/health", exchange ->
                respond(exchange, 200, "{\"ok\":true,\"version\":\"0.1.0\",\"clients\":2}"));
        server.createContext("/api/state", exchange ->
                respond(exchange, 200, "{\"v\":1,\"phone\":{\"steps\":3210,"
                        + "\"updated_ts\":1789525000000,\"stale\":false}}"));
        server.start();
        try {
            int port = server.getAddress().getPort();
            String base = "http://127.0.0.1:" + port + "/";
            SyncConfig cfg = new SyncConfig(base, "test-token", "android-test");

            SyncResult result = SyncClient.push(cfg, 4321, 1789526000000L);
            yes(result.ok, "HTTP 200 -> ok");
            no(result.deduped, "非重复 -> deduped=false");
            yes(lastBody.get().contains("\"source\":\"android-app\""), "实际请求包含 source");
            yes(lastBody.get().contains("\"device_id\":\"android-test\""), "实际请求包含 device_id");
            eq("test-token", lastToken.get(), "实际请求带令牌头");

            SyncResult deduped = SyncClient.push(cfg, 111, 1789526001000L);
            yes(deduped.ok && deduped.deduped, "200 + deduped=true 解析");

            SyncClient.TokenResult token = SyncClient.fetchToken(base);
            yes(token.ok && "abc-123".equals(token.token), "取令牌");

            SyncClient.HealthResult health = SyncClient.health(base);
            yes(health.ok && "0.1.0".equals(health.version) && health.clients == 2, "health 探测");

            SyncClient.RemoteState state = SyncClient.fetchState(base);
            yes(state.ok && Long.valueOf(3210L).equals(state.steps)
                    && Long.valueOf(1789525000000L).equals(state.updatedTs)
                    && !state.stale, "state 探测");
        } finally {
            server.stop(0);
        }
    }

    private static void testHttpErrors() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/ingest/health", exchange ->
                respond(exchange, 401, "{\"ok\":false,\"error\":\"BAD_TOKEN\"}"));
        server.start();
        try {
            SyncConfig cfg = new SyncConfig("http://127.0.0.1:" + server.getAddress().getPort(),
                    "wrong", "android-test");
            SyncResult result = SyncClient.push(cfg, 1, 2L);
            no(result.ok, "401 -> not ok");
            yes(result.isAuthError(), "401 -> authError");
            eq(401, result.httpCode, "401 code");
            eq("BAD_TOKEN", result.error, "401 解析 BAD_TOKEN（不能因流式模式丢响应体）");
            yes(result.message.contains("令牌"), "401 文案含令牌");
        } finally {
            server.stop(0);
        }
    }

    private static void respond(HttpExchange exchange, int code, String body) throws java.io.IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(code, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }

    private static String readAll(InputStream in) throws java.io.IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] chunk = new byte[2048];
        int n;
        while ((n = in.read(chunk)) != -1) {
            buffer.write(chunk, 0, n);
        }
        return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
    }

    private static long at(ZoneId zone, int y, int m, int d, int h, int min) {
        return LocalDateTime.of(y, m, d, h, min).atZone(zone).toInstant().toEpochMilli();
    }

    private static void eq(Object expected, Object actual, String name) {
        boolean same = expected == null ? actual == null : expected.equals(actual);
        if (same) {
            passed++;
            System.out.println("  PASS  " + name);
        } else {
            failed++;
            System.out.println("  FAIL  " + name + "  (expected=" + expected + ", actual=" + actual + ")");
        }
    }

    private static void yes(boolean value, String name) {
        eq(Boolean.TRUE, value, name);
    }

    private static void no(boolean value, String name) {
        eq(Boolean.FALSE, value, name);
    }
}
