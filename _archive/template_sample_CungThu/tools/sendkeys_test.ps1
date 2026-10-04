param(
  [int]$Pid2 = 0,
  [string[]]$Seq = @()   # each item "0x65" (tap) or "0x66:800" (hold 800ms)
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class KBT {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
$target = (Get-Process -Id $Pid2).MainWindowHandle
$Seq = if ($Seq.Count -eq 1) { $Seq[0] -split ',' } else { $Seq }
function Focus {
  if ([KBT]::GetForegroundWindow() -ne $target) {
    [KBT]::SetForegroundWindow($target) | Out-Null
    Start-Sleep -Milliseconds 150
  }
}
foreach ($item in $Seq) {
  $parts = $item.Split(':')
  $vk = [Convert]::ToByte($parts[0], 16)
  $hold = if ($parts.Length -gt 1) { [int]$parts[1] } else { 70 }
  Focus
  [KBT]::keybd_event($vk, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds $hold
  [KBT]::keybd_event($vk, 0, 2, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds 150
}
Write-Output "sent $($Seq.Count) keys"
