param(
  [int]$Pid2 = 0,
  [string]$Out = "D:\MRE\VXPstore\CungThuBongDen\build-win32\cap.png",
  [int]$CropX = -1, [int]$CropY = -1, [int]$CropW = 240, [int]$CropH = 320
)
# Capture the MREmu window via PrintWindow (works even when covered), then
# optionally crop the canvas. Canvas offset inside the window must be found
# empirically for the current window size (e.g. 893,58 at width 1100).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PW {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing
$p = Get-Process -Id $Pid2
$hwnd = $p.MainWindowHandle
$r = New-Object PW+RECT
[PW]::GetWindowRect($hwnd, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
[PW]::PrintWindow($hwnd, $hdc, 2) | Out-Null
$g.ReleaseHdc($hdc); $g.Dispose()
if ($CropX -ge 0) {
  $crop = $bmp.Clone([System.Drawing.Rectangle]::new($CropX, $CropY, $CropW, $CropH), $bmp.PixelFormat)
  $bmp.Dispose(); $bmp = $crop
}
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "saved $Out (window ${w}x${h})"
