package com.xiaoqi.steps;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.util.AttributeSet;
import android.view.View;
import android.view.animation.DecelerateInterpolator;

/**
 * 270° 圆环进度。纯 Canvas 绘制，无第三方库。
 * 轨道 + 渐变进度 + 末端圆点 + 外圈刻度，和深色卡片一起构成主视觉。
 */
public final class RingView extends View {

    private static final float START_ANGLE = 135f;
    private static final float SWEEP_ANGLE = 270f;
    private static final int TICKS = 60;

    private final Paint trackPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint arcPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint tickPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF oval = new RectF();

    private float animatedProgress;
    private float targetProgress;
    private ValueAnimator animator;
    private int colorStart = 0xFF9BE38A;
    private int colorEnd = 0xFF5FA85A;

    private float centerX;
    private float centerY;
    private float radius;
    private float strokeWidth;

    public RingView(Context context) {
        super(context);
        init();
    }

    public RingView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    public RingView(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init();
    }

    private void init() {
        setLayerType(LAYER_TYPE_SOFTWARE, null);
        strokeWidth = dp(11);
        trackPaint.setStyle(Paint.Style.STROKE);
        trackPaint.setStrokeWidth(strokeWidth);
        trackPaint.setStrokeCap(Paint.Cap.ROUND);
        trackPaint.setColor(0xFF27313D);

        arcPaint.setStyle(Paint.Style.STROKE);
        arcPaint.setStrokeWidth(strokeWidth);
        arcPaint.setStrokeCap(Paint.Cap.ROUND);
        arcPaint.setColor(colorStart);
        arcPaint.setShadowLayer(dp(9), 0f, 0f, 0x668BD97B);

        tickPaint.setStyle(Paint.Style.STROKE);
        tickPaint.setStrokeWidth(dp(1));
        tickPaint.setColor(0x22FFFFFF);

        dotPaint.setStyle(Paint.Style.FILL);
        dotPaint.setColor(0xFFF1F5F7);
        dotPaint.setShadowLayer(dp(6), 0f, 0f, 0xAA9BE38A);

        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
    }

    public void setProgress(float progress, boolean animate) {
        float clamped = Math.max(0f, Math.min(1f, progress));
        targetProgress = clamped;
        if (animator != null) {
            animator.cancel();
            animator = null;
        }
        if (!animate) {
            animatedProgress = clamped;
            invalidate();
            return;
        }
        animator = ValueAnimator.ofFloat(animatedProgress, clamped);
        animator.setDuration(900L);
        animator.setInterpolator(new DecelerateInterpolator());
        animator.addUpdateListener(animation -> {
            animatedProgress = (float) animation.getAnimatedValue();
            invalidate();
        });
        animator.start();
    }

    public void setAccentColors(int start, int end) {
        colorStart = start;
        colorEnd = end;
        arcPaint.setColor(start);
        dotPaint.setShadowLayer(dp(6), 0f, 0f, Ui.alpha(end, 0xAA));
        invalidate();
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int desired = dp(260);
        int width = resolveSize(desired, widthMeasureSpec);
        int height = resolveSize(desired, heightMeasureSpec);
        int size = Math.min(width, height);
        setMeasuredDimension(size, size);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        centerX = w / 2f;
        centerY = h / 2f;
        radius = Math.min(w, h) / 2f - strokeWidth / 2f - dp(16);
        oval.set(centerX - radius, centerY - radius, centerX + radius, centerY + radius);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (radius <= 0f) {
            return;
        }

        for (int i = 0; i < TICKS; i++) {
            double angle = Math.toRadians(START_ANGLE + SWEEP_ANGLE * i / (TICKS - 1f));
            float cos = (float) Math.cos(angle);
            float sin = (float) Math.sin(angle);
            float inner = radius + dp(8);
            float outer = radius + dp(12);
            canvas.drawLine(centerX + cos * inner, centerY + sin * inner,
                    centerX + cos * outer, centerY + sin * outer, tickPaint);
        }

        canvas.drawArc(oval, START_ANGLE, SWEEP_ANGLE, false, trackPaint);

        float sweep = SWEEP_ANGLE * animatedProgress;
        if (sweep > 0.1f) {
            arcPaint.setShader(new LinearGradient(
                    oval.left, oval.bottom, oval.right, oval.top,
                    colorStart, colorEnd, Shader.TileMode.CLAMP));
            canvas.drawArc(oval, START_ANGLE, sweep, false, arcPaint);
            arcPaint.setShader(null);

            double endAngle = Math.toRadians(START_ANGLE + sweep);
            float dotX = centerX + (float) Math.cos(endAngle) * radius;
            float dotY = centerY + (float) Math.sin(endAngle) * radius;
            canvas.drawCircle(dotX, dotY, dp(4.5f), dotPaint);
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        if (animator != null) {
            animator.cancel();
            animator = null;
        }
        super.onDetachedFromWindow();
    }

    public float getTargetProgress() {
        return targetProgress;
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
