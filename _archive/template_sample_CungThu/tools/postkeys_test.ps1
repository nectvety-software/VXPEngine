param(
  [int]$Pid2 = 0,
  [string[]]$Seq = @()   # each item "0x65" (tap) or "0x66:800" (hold 800ms)
)
# Focus-independent key sender: posts WM_KEYDOWN/WM_KEYUP straight to the
# MREmu window queue (SFML turns them into KeyPressed/KeyReleased events).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PM {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
}
"@
$p = Get-Process -Id $Pid2
$hwnd = $p.MainWindowHandle
$Seq = if ($Seq.Count -eq 1) { $Seq[0] -split ',' } else { $Seq }
$WM_KEYDOWN = 0x0100
$WM_KEYUP   = 0x0101
$MAPVK_VK_TO_VSC = 0
$sent = 0
foreach ($item in $Seq) {
  $parts = $item.Split(':')
  $vk = [Convert]::ToInt32($parts[0], 16)
  $hold = if ($parts.Length -gt 1) { [int]$parts[1] } else { 70 }
  $scan = [PM]::MapVirtualKey($vk, $MAPVK_VK_TO_VSC)
  $lpDown = [IntPtr](1 -bor ($scan -shl 16))
  $lpUp   = [IntPtr]((1 -bor ($scan -shl 16)) -bor 0xC0000000)
  [PM]::PostMessage($hwnd, $WM_KEYDOWN, [IntPtr]$vk, $lpDown) | Out-Null
  Start-Sleep -Milliseconds $hold
  [PM]::PostMessage($hwnd, $WM_KEYUP, [IntPtr]$vk, $lpUp) | Out-Null
  Start-Sleep -Milliseconds 120
  $sent++
}
Write-Output "posted $sent keys to hwnd $hwnd"
