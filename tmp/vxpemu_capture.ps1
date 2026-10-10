param([string]$Vxp, [string]$Out, [string]$Out2, [string]$Key, [int]$WaitSeconds = 4)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinCap3 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
  public const uint LDOWN = 0x0002, LUP = 0x0004;
}
"@
function Grab([IntPtr]$h, [string]$path) {
  $r = New-Object WinCap3+RECT
  [WinCap3]::GetWindowRect($h, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $ht = $r.Bottom - $r.Top
  $bmp = New-Object System.Drawing.Bitmap $w, $ht
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $hdc = $g.GetHdc()
  [WinCap3]::PrintWindow($h, $hdc, 2) | Out-Null
  $g.ReleaseHdc($hdc); $g.Dispose()
  # PrintWindow fails (all black) on some composited windows: fall back to the screen.
  $sample = @()
  for ($i=0; $i -lt 40; $i++) { $c = $bmp.GetPixel([int]($w/2), [int]($i*$ht/40)); $sample += $c.R + $c.G + $c.B }
  if (($sample | Where-Object { $_ -gt 12 }).Count -eq 0) {
    [WinCap3]::BringWindowToTop($h) | Out-Null
    [WinCap3]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 800
    $g2 = [System.Drawing.Graphics]::FromImage($bmp)
    $g2.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size $w, $ht))
    $g2.Dispose()
    Write-Output "  (PrintWindow was black, used screen capture)"
  }
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  Write-Output "saved $path ($w x $ht)"
}
$exe = 'D:\MRE\VXPEmu\build\Release\VXPEmu.exe'
$p = Start-Process -FilePath $exe -ArgumentList @($Vxp, '--autostart') -PassThru
$h = [IntPtr]::Zero
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 250
  $p.Refresh()
  if ($p.HasExited) { throw "VXPEmu exited early with code $($p.ExitCode)" }
  if ($p.MainWindowHandle -ne 0) { $h = $p.MainWindowHandle; break }
}
if ($h -eq [IntPtr]::Zero) { throw 'VXPEmu main window never appeared' }
$sb = New-Object System.Text.StringBuilder 256
[WinCap3]::GetWindowTextW($h, $sb, 256) | Out-Null
Write-Output "window title: $($sb.ToString())"
[WinCap3]::ShowWindow($h, 5) | Out-Null
[WinCap3]::BringWindowToTop($h) | Out-Null
[WinCap3]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Seconds $WaitSeconds
Grab $h $Out
if ($Key) {
  $r = New-Object WinCap3+RECT
  [WinCap3]::GetWindowRect($h, [ref]$r) | Out-Null
  # Device framebuffer sits at (504,140) size 300x400 inside this window: click its centre,
  # which the demo maps to the "enter city" pen action in the title state.
  $cx = $r.Left + 504 + 150; $cy = $r.Top + 140 + 200
  [WinCap3]::SetCursorPos($cx, $cy) | Out-Null
  Start-Sleep -Milliseconds 400
  [WinCap3]::mouse_event([WinCap3]::LDOWN, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 120
  [WinCap3]::mouse_event([WinCap3]::LUP, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Seconds 3
  Grab $h $Out2
}
Stop-Process -Id $p.Id -Force
Write-Output 'VXPEmu stopped'
