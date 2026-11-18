package com.xiaoqi.steps;

import android.app.Activity;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.os.Build;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * 纯代码 UI 工具：不依赖 AndroidX / Material，保证离线（无 Gradle 依赖）也能编译。
 * 视觉与小栖房间保持一致：深色底、暖白字、绿色主色、圆角卡片。
 */
final class Ui {

    static final int BG = 0xFF0F1318;
    static final int BG_SOFT = 0xFF131920;
    static final int CARD = 0xFF1A212A;
    static final int CARD_2 = 0xFF202933;
    static final int STROKE = 0xFF2A3542;
    static final int TEXT = 0xFFF1F5F7;
    static final int DIM = 0xFF93A0AE;
    static final int DIM_2 = 0xFF6C7987;
    static final int GREEN = 0xFF8BD97B;
    static final int GREEN_DEEP = 0xFF5FA85A;
    static final int GREEN_INK = 0xFF0E1A10;
    static final int AMBER = 0xFFE0A458;
    static final int RED = 0xFFE2726A;
    static final int BLUE = 0xFF7FB2E5;

    private Ui() {
    }

    static int dp(Context context, float value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static TextView text(Context context, CharSequence value, float sizeSp, int color) {
        return text(context, value, sizeSp, color, Typeface.NORMAL, "sans-serif");
    }

    static TextView text(Context context, CharSequence value, float sizeSp, int color,
                         int style, String family) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(sizeSp);
        view.setTextColor(color);
        view.setTypeface(Typeface.create(family, style));
        view.setIncludeFontPadding(true);
        view.setLineSpacing(dp(context, 2), 1f);
        return view;
    }

    static LinearLayout column(Context context) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    static LinearLayout row(Context context) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(android.view.Gravity.CENTER_VERTICAL);
        return layout;
    }

    static GradientDrawable rounded(int color, float radiusDp, Context context) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    static GradientDrawable stroked(int color, int strokeColor, float radiusDp, Context context) {
        GradientDrawable drawable = rounded(color, radiusDp, context);
        drawable.setStroke(dp(context, 1), strokeColor);
        return drawable;
    }

    static GradientDrawable gradient(int top, int bottom, float radiusDp, Context context) {
        GradientDrawable drawable = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR, new int[]{top, bottom});
        drawable.setCornerRadius(dp(context, radiusDp));
        return drawable;
    }

    static LinearLayout card(Context context) {
        LinearLayout card = column(context);
        card.setPadding(dp(context, 18), dp(context, 16), dp(context, 18), dp(context, 16));
        card.setBackground(stroked(CARD, STROKE, 22, context));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(context, 14);
        card.setLayoutParams(params);
        return card;
    }

    static TextView sectionTitle(Context context, String value) {
        TextView view = text(context, value, 12, DIM,
                Typeface.BOLD, "sans-serif-medium");
        view.setLetterSpacing(0.12f);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = dp(context, 10);
        view.setLayoutParams(params);
        return view;
    }

    static TextView pill(Context context, String value, int foreground, int background) {
        TextView view = text(context, value, 12, foreground,
                Typeface.BOLD, "sans-serif-medium");
        view.setPadding(dp(context, 10), dp(context, 5), dp(context, 10), dp(context, 5));
        view.setBackground(rounded(background, 99, context));
        return view;
    }

    static Button primaryButton(Context context, String label) {
        return button(context, label, GREEN, GREEN_INK, 0);
    }

    static Button secondaryButton(Context context, String label) {
        return button(context, label, CARD_2, TEXT, STROKE);
    }

    private static Button button(Context context, String label, int fill, int textColor,
                                 int strokeColor) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextSize(15);
        button.setAllCaps(false);
        button.setTextColor(textColor);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        button.setGravity(android.view.Gravity.CENTER);
        button.setMinHeight(0);
        button.setMinimumHeight(0);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(dp(context, 16), dp(context, 13), dp(context, 16), dp(context, 13));
        GradientDrawable shape = strokeColor == 0
                ? rounded(fill, 16, context)
                : stroked(fill, strokeColor, 16, context);
        Drawable ripple = new RippleDrawable(ColorStateList.valueOf(0x33FFFFFF), shape, null);
        button.setBackground(ripple);
        button.setStateListAnimator(null);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            button.setElevation(0f);
        }
        return button;
    }

    static LinearLayout.LayoutParams margins(Context context, View view,
                                             float left, float top, float right, float bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(dp(context, left), dp(context, top), dp(context, right), dp(context, bottom));
        view.setLayoutParams(params);
        return params;
    }

    static void weight(View view, float weight) {
        ViewGroup.LayoutParams params = view.getLayoutParams();
        if (params instanceof LinearLayout.LayoutParams) {
            ((LinearLayout.LayoutParams) params).weight = weight;
            ((LinearLayout.LayoutParams) params).width = 0;
            view.setLayoutParams(params);
        }
    }

    static LinearLayout rowItem(Context context, String label, String value) {
        LinearLayout row = row(context);
        row.setPadding(0, dp(context, 6), 0, dp(context, 6));
        TextView left = text(context, label, 13, DIM);
        TextView right = text(context, value, 13, TEXT,
                Typeface.BOLD, "sans-serif-medium");
        right.setGravity(android.view.Gravity.END);
        LinearLayout.LayoutParams leftParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        row.addView(left, leftParams);
        LinearLayout.LayoutParams rightParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        row.addView(right, rightParams);
        return row;
    }

    static View divider(Context context) {
        View view = new View(context);
        view.setBackgroundColor(0xFF232C36);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(context, 1));
        params.topMargin = dp(context, 8);
        params.bottomMargin = dp(context, 8);
        view.setLayoutParams(params);
        return view;
    }

    static void systemBars(Activity activity) {
        Window window = activity.getWindow();
        window.setStatusBarColor(BG);
        window.setNavigationBarColor(BG);
        int flags = window.getDecorView().getSystemUiVisibility();
        flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            flags &= ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        }
        window.getDecorView().setSystemUiVisibility(flags);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            window.setNavigationBarDividerColor(BG);
        }
        window.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(BG));
    }

    static TextView bigNumber(Context context, String value) {
        TextView view = text(context, value, 58, TEXT,
                Typeface.NORMAL, "sans-serif-light");
        view.setLetterSpacing(-0.02f);
        return view;
    }

    static void setTextOrGone(TextView view, String value) {
        if (value == null || value.isEmpty()) {
            view.setVisibility(View.GONE);
        } else {
            view.setVisibility(View.VISIBLE);
            view.setText(value);
        }
    }

    static int alpha(int color, int alpha) {
        return Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color));
    }
}
