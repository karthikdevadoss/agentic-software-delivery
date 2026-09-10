# Best-effort Windows human-attention notifier for Claude Code development
# hooks (see agent/claude_code_hook.py). Always invoked detached/async —
# never awaited by the hook, so any failure here costs nothing but a
# missed notification, never a slow/broken Claude Code session.
#
# Three independent, non-blocking channels, each wrapped so one failing
# never prevents the others:
#   1. A native Windows toast notification (no extra module install —
#      uses the well-known pre-registered "Windows PowerShell" AUMID,
#      which is the standard way un-packaged PowerShell scripts can show
#      a real toast on Windows 10/11 without registering a new app).
#   2. An explicit system sound, independent of toast sound (which Focus
#      Assist can silently mute) — this fires even if the toast doesn't.
#   3. A best-effort taskbar flash of whatever window is currently in the
#      foreground (very likely the terminal the user is looking at, since
#      this fires immediately after the permission/attention event).
#
# Deliberately does NOT steal keyboard focus — no SetForegroundWindow,
# no window activation, just a toast + sound + a flashing taskbar icon.

param(
    [string]$Title = "Claude needs your attention",
    [string]$Message = "Waiting for you."
)

$ErrorActionPreference = "SilentlyContinue"

try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null

    $escapedTitle = [System.Security.SecurityElement]::Escape($Title)
    $escapedMessage = [System.Security.SecurityElement]::Escape($Message)

    $template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$escapedTitle</text>
      <text>$escapedMessage</text>
    </binding>
  </visual>
  <audio src="ms-winsoundevent:Notification.Reminder"/>
</toast>
"@

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml

    # Pre-registered AUMID for legacy Windows PowerShell — works without
    # registering a new app or installing a module (e.g. BurntToast).
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
} catch {
    # Toast failed (older Windows, restricted policy, etc.) — sound/flash below still run.
}

try {
    [System.Media.SystemSounds]::Exclamation.Play()
    Start-Sleep -Milliseconds 300  # let the async sound actually play before the process can exit
} catch {}

try {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ClaudeAttentionFlash {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [StructLayout(LayoutKind.Sequential)]
    public struct FLASHWINFO { public uint cbSize; public IntPtr hwnd; public uint dwFlags; public uint uCount; public uint dwTimeout; }
    [DllImport("user32.dll")] public static extern bool FlashWindowEx(ref FLASHWINFO pwfi);
    public static void FlashTaskbar(IntPtr hwnd) {
        FLASHWINFO fi = new FLASHWINFO();
        fi.cbSize = (uint)Marshal.SizeOf(fi);
        fi.hwnd = hwnd;
        fi.dwFlags = 0x00000002 | 0x0000000C; // FLASHW_TRAY | FLASHW_TIMERNOFG
        fi.uCount = 5;
        fi.dwTimeout = 0;
        FlashWindowEx(ref fi);
    }
}
"@ -ErrorAction SilentlyContinue

    $hwnd = [ClaudeAttentionFlash]::GetForegroundWindow()
    if ($hwnd -ne [IntPtr]::Zero) {
        [ClaudeAttentionFlash]::FlashTaskbar($hwnd)
    }
} catch {
    # Best-effort only — never fatal, never required for the other two channels.
}
