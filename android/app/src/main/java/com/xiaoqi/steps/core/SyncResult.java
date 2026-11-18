package com.xiaoqi.steps.core;

/** 一次上报/探测的结果。网络失败也返回对象，不抛异常给 UI。 */
public final class SyncResult {

    public final boolean ok;
    public final boolean deduped;
    public final int httpCode;
    public final String error;
    public final String message;
    public final String raw;
    public final long steps;
    public final long ts;

    private SyncResult(boolean ok, boolean deduped, int httpCode, String error,
                       String message, String raw, long steps, long ts) {
        this.ok = ok;
        this.deduped = deduped;
        this.httpCode = httpCode;
        this.error = error;
        this.message = message;
        this.raw = raw;
        this.steps = steps;
        this.ts = ts;
    }

    public static SyncResult configError(String message) {
        return new SyncResult(false, false, 0, "NOT_CONFIGURED", message, "", 0L, 0L);
    }

    public static SyncResult networkError(String message, String raw) {
        return new SyncResult(false, false, 0, "NETWORK", message, raw == null ? "" : raw, 0L, 0L);
    }

    public static SyncResult fromResponse(int httpCode, String body, long steps, long ts) {
        String error = MiniJson.stringField(body, "error");
        Boolean okFlag = MiniJson.boolField(body, "ok");
        boolean ok = httpCode == 200 && Boolean.TRUE.equals(okFlag);
        boolean deduped = Boolean.TRUE.equals(MiniJson.boolField(body, "deduped"));
        String message;
        if (ok) {
            message = deduped ? "已同步（服务端 60 秒内去重）" : "已同步";
        } else {
            message = describeError(httpCode, error);
        }
        return new SyncResult(ok, deduped, httpCode, error, message,
                body == null ? "" : body, steps, ts);
    }

    public static String describeError(int httpCode, String error) {
        if ("BAD_TOKEN".equals(error)) {
            return "令牌错误（HTTP 401）";
        }
        if ("INVALID_FIELD".equals(error)) {
            return "字段不合法（HTTP 400）";
        }
        if (httpCode == 401) {
            return "令牌错误（HTTP 401）";
        }
        if (httpCode == 400) {
            return "请求不合法（HTTP 400）";
        }
        if (httpCode > 0) {
            return "服务端返回 HTTP " + httpCode;
        }
        return "上报失败";
    }

    public boolean isAuthError() {
        return httpCode == 401 || "BAD_TOKEN".equals(error);
    }

    /** 给通知/卡片用的一行文案。 */
    public String shortText() {
        return ok ? message : "同步失败：" + message;
    }
}
