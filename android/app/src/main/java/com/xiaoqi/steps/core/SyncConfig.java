package com.xiaoqi.steps.core;

/** 上报所需的最小配置。纯 Java，方便在 JVM 上做联调测试。 */
public final class SyncConfig {

    public final String baseUrl;
    public final String token;
    public final String deviceId;
    public final int connectTimeoutMs;
    public final int readTimeoutMs;

    public SyncConfig(String baseUrl, String token, String deviceId) {
        this(baseUrl, token, deviceId, 5000, 8000);
    }

    public SyncConfig(String baseUrl, String token, String deviceId,
                      int connectTimeoutMs, int readTimeoutMs) {
        this.baseUrl = baseUrl == null ? "" : baseUrl.trim();
        this.token = token == null ? "" : token.trim();
        this.deviceId = deviceId == null ? "" : deviceId.trim();
        this.connectTimeoutMs = Math.max(1000, connectTimeoutMs);
        this.readTimeoutMs = Math.max(1000, readTimeoutMs);
    }

    public boolean isConfigured() {
        return !SyncClient.normalizeBaseUrl(baseUrl).isEmpty() && !token.isEmpty();
    }
}
