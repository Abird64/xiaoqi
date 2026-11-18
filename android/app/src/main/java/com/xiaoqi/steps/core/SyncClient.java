package com.xiaoqi.steps.core;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * 小栖手机接入协议客户端（纯 Java，不依赖 Android）。
 *
 * <p>协议依据：{@code docs/02-需求与设计/接口协议.md} §4
 * {@code POST /api/ingest/health}：</p>
 * <pre>
 * Header  X-Xiaoqi-Token: &lt;配对令牌&gt;
 * Body    {"steps":3210,"ts":1789526000000,"source":"android-app","device_id":"..."}
 * 200     {"ok":true,"deduped":false}
 * 400     {"ok":false,"error":"INVALID_FIELD","field":"steps"}
 * 401     {"ok":false,"error":"BAD_TOKEN"}
 * </pre>
 *
 * <p>只使用 {@link HttpURLConnection}，不引入 OkHttp/Retrofit，保证离线可编译、
 * APK 体积小，也让同一份代码能在 JVM 上直接跑联调测试。</p>
 */
public final class SyncClient {

    /** 协议 §4：D-009 新增的 Android App 来源标识。 */
    public static final String SOURCE_ANDROID_APP = "android-app";
    public static final String API_INGEST = "/api/ingest/health";
    public static final String API_TOKEN = "/api/token";
    public static final String API_HEALTH = "/api/health";
    public static final String API_STATE = "/api/state";

    private SyncClient() {
    }

    /**
     * 把用户输入整理成“根地址”。容忍这些写法：
     * <ul>
     *   <li>{@code 192.168.1.5:8000} → {@code http://192.168.1.5:8000}</li>
     *   <li>{@code http://192.168.1.5:8000/} → 去掉尾斜杠</li>
     *   <li>直接粘贴完整上报地址 {@code .../api/ingest/health} → 去掉已知接口后缀</li>
     * </ul>
     * 非法/空输入返回空串，调用方据此提示“未配置”。
     */
    public static String normalizeBaseUrl(String raw) {
        if (raw == null) {
            return "";
        }
        String s = raw.trim();
        if (s.isEmpty()) {
            return "";
        }
        if (s.startsWith("//")) {
            s = "http:" + s;
        }
        if (!s.matches("^[a-zA-Z][a-zA-Z0-9+.-]*://.*$")) {
            s = "http://" + s;
        }
        URI uri;
        try {
            uri = new URI(s);
        } catch (Exception e) {
            return "";
        }
        String scheme = uri.getScheme();
        if (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme)) {
            return "";
        }
        String host = uri.getHost();
        if (host == null || host.isEmpty()) {
            return "";
        }
        if (host.indexOf(':') >= 0 && !host.startsWith("[")) {
            host = "[" + host + "]";
        }
        int port = uri.getPort();
        String path = uri.getPath() == null ? "" : uri.getPath();
        while (path.endsWith("/")) {
            path = path.substring(0, path.length() - 1);
        }
        String[] knownSuffixes = {API_INGEST, API_TOKEN, API_HEALTH, API_STATE, "/api"};
        boolean trimmed = true;
        while (trimmed) {
            trimmed = false;
            for (String suffix : knownSuffixes) {
                if (path.equals(suffix)) {
                    path = "";
                    trimmed = true;
                } else if (path.endsWith(suffix)) {
                    path = path.substring(0, path.length() - suffix.length());
                    while (path.endsWith("/")) {
                        path = path.substring(0, path.length() - 1);
                    }
                    trimmed = true;
                }
            }
        }
        StringBuilder out = new StringBuilder();
        out.append(scheme.toLowerCase()).append("://").append(host);
        if (port > 0) {
            out.append(':').append(port);
        }
        if (!path.isEmpty()) {
            if (!path.startsWith("/")) {
                out.append('/');
            }
            out.append(path);
        }
        return out.toString();
    }

    public static String buildPayload(long steps, long ts, String deviceId) {
        long safeSteps = Math.max(0L, steps);
        long safeTs = ts > 0L ? ts : System.currentTimeMillis();
        String device = deviceId == null || deviceId.trim().isEmpty()
                ? "android-unknown" : deviceId.trim();
        return "{\"steps\":" + safeSteps
                + ",\"ts\":" + safeTs
                + ",\"source\":\"" + SOURCE_ANDROID_APP + "\""
                + ",\"device_id\":" + MiniJson.quote(device)
                + "}";
    }

    /** 上报一次当日累计步数。 */
    public static SyncResult push(SyncConfig cfg, long steps, long ts) {
        if (cfg == null) {
            return SyncResult.configError("未配置同步参数");
        }
        String base = normalizeBaseUrl(cfg.baseUrl);
        if (base.isEmpty()) {
            return SyncResult.configError("未配置电脑地址");
        }
        if (cfg.token.isEmpty()) {
            return SyncResult.configError("未配置配对令牌");
        }
        String payload = buildPayload(steps, ts, cfg.deviceId);
        HttpURLConnection conn = null;
        try {
            conn = open(base + API_INGEST, cfg.connectTimeoutMs, cfg.readTimeoutMs);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("X-Xiaoqi-Token", cfg.token);
            byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
            // 注意：不要用 setFixedLengthStreamingMode —— JDK/Android 的
            // HttpURLConnection 在 401 时会尝试“重试认证”，流式模式下直接抛
            // HttpRetryException 并丢掉服务端返回的 BAD_TOKEN 响应体。
            // 请求体只有几十字节，默认缓冲模式更稳，也会自动带 Content-Length。
            try (OutputStream out = conn.getOutputStream()) {
                out.write(bytes);
            }
            int code = conn.getResponseCode();
            String body = readResponse(conn, code);
            return SyncResult.fromResponse(code, body, steps, ts);
        } catch (Exception e) {
            return SyncResult.networkError(describeException(e), "");
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /** GET /api/token —— 参考后端该接口不鉴权，用于手机端一键取令牌（局域网演示定位）。 */
    public static TokenResult fetchToken(String baseUrl) {
        String base = normalizeBaseUrl(baseUrl);
        if (base.isEmpty()) {
            return new TokenResult(false, "", "未配置电脑地址");
        }
        HttpURLConnection conn = null;
        try {
            conn = open(base + API_TOKEN, 5000, 8000);
            int code = conn.getResponseCode();
            String body = readResponse(conn, code);
            String token = MiniJson.stringField(body, "token");
            if (code == 200 && token != null && !token.isEmpty()) {
                return new TokenResult(true, token, "");
            }
            return new TokenResult(false, "", "取令牌失败（HTTP " + code + "）");
        } catch (Exception e) {
            return new TokenResult(false, "", describeException(e));
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /** GET /api/health —— 只用来“测试连接”，不改变任何数据。 */
    public static HealthResult health(String baseUrl) {
        String base = normalizeBaseUrl(baseUrl);
        if (base.isEmpty()) {
            return new HealthResult(false, "", 0, "未配置电脑地址");
        }
        HttpURLConnection conn = null;
        try {
            conn = open(base + API_HEALTH, 5000, 8000);
            int code = conn.getResponseCode();
            String body = readResponse(conn, code);
            boolean ok = code == 200 && Boolean.TRUE.equals(MiniJson.boolField(body, "ok"));
            String version = MiniJson.stringField(body, "version");
            Long clients = MiniJson.longField(body, "clients");
            if (ok) {
                return new HealthResult(true, version == null ? "" : version,
                        clients == null ? 0 : clients.intValue(), "");
            }
            return new HealthResult(false, "", 0, "服务不可用（HTTP " + code + "）");
        } catch (Exception e) {
            return new HealthResult(false, "", 0, describeException(e));
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /** GET /api/state —— 读取服务端当前已有的手机步数，用于设置页“连接检查”。 */
    public static RemoteState fetchState(String baseUrl) {
        String base = normalizeBaseUrl(baseUrl);
        if (base.isEmpty()) {
            return new RemoteState(false, null, null, false, "未配置电脑地址");
        }
        HttpURLConnection conn = null;
        try {
            conn = open(base + API_STATE, 5000, 8000);
            int code = conn.getResponseCode();
            String body = readResponse(conn, code);
            if (code != 200) {
                return new RemoteState(false, null, null, false, "HTTP " + code);
            }
            int phoneIndex = body.indexOf("\"phone\"");
            String phoneJson = phoneIndex >= 0 ? body.substring(phoneIndex) : body;
            Long steps = MiniJson.longField(phoneJson, "steps");
            Long updated = MiniJson.longField(phoneJson, "updated_ts");
            Boolean stale = MiniJson.boolField(phoneJson, "stale");
            return new RemoteState(true, steps, updated,
                    Boolean.TRUE.equals(stale), "");
        } catch (Exception e) {
            return new RemoteState(false, null, null, false, describeException(e));
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static HttpURLConnection open(String url, int connectTimeout, int readTimeout)
            throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(connectTimeout);
        conn.setReadTimeout(readTimeout);
        conn.setUseCaches(false);
        conn.setRequestProperty("User-Agent", "XiaoqiSteps/1.0.0 (Android)");
        return conn;
    }

    private static String readResponse(HttpURLConnection conn, int code) throws IOException {
        InputStream in = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        if (in == null) {
            return "";
        }
        try (InputStream input = in) {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int n;
            while ((n = input.read(chunk)) != -1) {
                buffer.write(chunk, 0, n);
            }
            return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static String describeException(Exception e) {
        String message = e.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = e.getClass().getSimpleName();
        }
        if (e instanceof java.net.SocketTimeoutException) {
            return "连接超时：检查手机与电脑是否同一 Wi-Fi、防火墙是否放行";
        }
        if (e instanceof java.net.ConnectException) {
            return "连不上电脑：检查地址/端口/防火墙";
        }
        if (e instanceof java.net.UnknownHostException) {
            return "域名解析失败：检查地址";
        }
        return message;
    }

    /** /api/token 的解析结果。 */
    public static final class TokenResult {
        public final boolean ok;
        public final String token;
        public final String error;

        TokenResult(boolean ok, String token, String error) {
            this.ok = ok;
            this.token = token;
            this.error = error;
        }
    }

    /** /api/health 的解析结果。 */
    public static final class HealthResult {
        public final boolean ok;
        public final String version;
        public final int clients;
        public final String error;

        HealthResult(boolean ok, String version, int clients, String error) {
            this.ok = ok;
            this.version = version;
            this.clients = clients;
            this.error = error;
        }
    }

    /** /api/state 里 phone 快照的解析结果。 */
    public static final class RemoteState {
        public final boolean ok;
        public final Long steps;
        public final Long updatedTs;
        public final boolean stale;
        public final String error;

        RemoteState(boolean ok, Long steps, Long updatedTs, boolean stale, String error) {
            this.ok = ok;
            this.steps = steps;
            this.updatedTs = updatedTs;
            this.stale = stale;
            this.error = error;
        }
    }
}
