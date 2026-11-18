package com.xiaoqi.steps.core;

import java.util.Locale;

/**
 * 命令行联调工具：用 App 同一份 {@link SyncClient} 向上报接口发一次请求。
 *
 * <p>用法：</p>
 * <pre>
 * java -cp ... SyncHarness push &lt;base&gt; &lt;token&gt; &lt;steps&gt; &lt;deviceId&gt;
 * java -cp ... SyncHarness token &lt;base&gt;
 * java -cp ... SyncHarness health &lt;base&gt;
 * java -cp ... SyncHarness state &lt;base&gt;
 * </pre>
 * push 成功 exit 0，失败 exit 1；输出为单行 key=value，方便 Python 解析。
 */
public final class SyncHarness {

    public static void main(String[] args) {
        if (args.length < 2) {
            usage();
            System.exit(2);
        }
        String mode = args[0];
        try {
            switch (mode) {
                case "push": {
                    if (args.length < 5) {
                        usage();
                        System.exit(2);
                    }
                    SyncConfig cfg = new SyncConfig(args[1], args[2], args[4]);
                    SyncResult result = SyncClient.push(cfg, Long.parseLong(args[3]),
                            System.currentTimeMillis());
                    System.out.println(String.format(Locale.US,
                            "HTTP=%d OK=%s DEDUPED=%s ERROR=%s MESSAGE=%s",
                            result.httpCode, result.ok, result.deduped,
                            result.error == null ? "" : result.error,
                            result.message.replace(' ', '_')));
                    System.out.println("RAW=" + result.raw.replace('\n', ' ').replace('\r', ' '));
                    System.exit(result.ok ? 0 : 1);
                    break;
                }
                case "token": {
                    SyncClient.TokenResult result = SyncClient.fetchToken(args[1]);
                    System.out.println("OK=" + result.ok + " TOKEN=" + result.token
                            + " ERROR=" + result.error);
                    System.exit(result.ok ? 0 : 1);
                    break;
                }
                case "health": {
                    SyncClient.HealthResult result = SyncClient.health(args[1]);
                    System.out.println("OK=" + result.ok + " VERSION=" + result.version
                            + " CLIENTS=" + result.clients + " ERROR=" + result.error);
                    System.exit(result.ok ? 0 : 1);
                    break;
                }
                case "state": {
                    SyncClient.RemoteState result = SyncClient.fetchState(args[1]);
                    System.out.println("OK=" + result.ok + " STEPS=" + result.steps
                            + " UPDATED_TS=" + result.updatedTs
                            + " STALE=" + result.stale + " ERROR=" + result.error);
                    System.exit(result.ok ? 0 : 1);
                    break;
                }
                default:
                    usage();
                    System.exit(2);
            }
        } catch (Exception e) {
            System.out.println("EXCEPTION=" + e.getClass().getSimpleName() + ":" + e.getMessage());
            System.exit(3);
        }
    }

    private static void usage() {
        System.err.println("usage: SyncHarness push <base> <token> <steps> <deviceId>");
        System.err.println("       SyncHarness token|health|state <base>");
    }
}
