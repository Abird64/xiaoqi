package com.xiaoqi.steps.core;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 极小的 JSON 读写工具。
 *
 * <p>App 只与本项目后端通信，请求体字段固定、响应体结构固定，因此不引入任何
 * 第三方 JSON 库（离线也能编译，APK 也小）。这里只做三件事：字符串转义、
 * 按 key 取字符串/布尔/长整数。遇到格式错误一律返回 null，由调用方降级为
 * “无法解析”，绝不抛异常把同步线程打死。</p>
 */
public final class MiniJson {

    private MiniJson() {
    }

    public static String escape(String value) {
        if (value == null) {
            return "";
        }
        StringBuilder out = new StringBuilder(value.length() + 8);
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"':
                    out.append("\\\"");
                    break;
                case '\\':
                    out.append("\\\\");
                    break;
                case '\n':
                    out.append("\\n");
                    break;
                case '\r':
                    out.append("\\r");
                    break;
                case '\t':
                    out.append("\\t");
                    break;
                case '\b':
                    out.append("\\b");
                    break;
                case '\f':
                    out.append("\\f");
                    break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        return out.toString();
    }

    public static String quote(String value) {
        return "\"" + escape(value) + "\"";
    }

    /** 取字符串字段；字段缺失、类型不对或 JSON 非法时返回 null。 */
    public static String stringField(String json, String key) {
        if (json == null || key == null) {
            return null;
        }
        Matcher m = patternForKey(key, true).matcher(json);
        if (!m.find()) {
            return null;
        }
        return unescape(m.group(1));
    }

    /** 取布尔字段；缺失返回 null。 */
    public static Boolean boolField(String json, String key) {
        if (json == null || key == null) {
            return null;
        }
        Matcher m = patternForKey(key, false).matcher(json);
        if (!m.find()) {
            return null;
        }
        return Boolean.valueOf("true".equalsIgnoreCase(m.group(1)));
    }

    /** 取整数字段；允许负数、前后空白；不是整数返回 null。 */
    public static Long longField(String json, String key) {
        if (json == null || key == null) {
            return null;
        }
        Matcher m = patternForKey(key, false).matcher(json);
        if (!m.find()) {
            return null;
        }
        try {
            return Long.valueOf(m.group(1).trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static Pattern patternForKey(String key, boolean quoted) {
        String value = quoted ? "\"((?:\\\\.|[^\"\\\\])*)\"" : "(-?\\d+|true|false|null)";
        return Pattern.compile("\"" + Pattern.quote(key) + "\"\\s*:\\s*" + value);
    }

    public static String unescape(String raw) {
        StringBuilder out = new StringBuilder(raw.length());
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (c != '\\' || i + 1 >= raw.length()) {
                out.append(c);
                continue;
            }
            char n = raw.charAt(++i);
            switch (n) {
                case '"':
                    out.append('"');
                    break;
                case '\\':
                    out.append('\\');
                    break;
                case '/':
                    out.append('/');
                    break;
                case 'n':
                    out.append('\n');
                    break;
                case 'r':
                    out.append('\r');
                    break;
                case 't':
                    out.append('\t');
                    break;
                case 'b':
                    out.append('\b');
                    break;
                case 'f':
                    out.append('\f');
                    break;
                case 'u':
                    if (i + 4 < raw.length()) {
                        try {
                            out.append((char) Integer.parseInt(raw.substring(i + 1, i + 5), 16));
                            i += 4;
                        } catch (NumberFormatException e) {
                            out.append('u');
                        }
                    } else {
                        out.append('u');
                    }
                    break;
                default:
                    out.append(n);
            }
        }
        return out.toString();
    }
}
