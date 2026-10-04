param([int]$Pid2 = 0, [int]$X = 620, [int]$Y = 40, [int]$W = 1100, [int]$H = 720)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MV2 {
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
}
"@
$p = Get-Process -Id $Pid2
[MV2]::MoveWindow($p.MainWindowHandle, $X, $Y, $W, $H, $true)
Write-Output "moved hwnd $($p.MainWindowHandle) to ${X},${Y} ${W}x${H}"
