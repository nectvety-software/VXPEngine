param(
  [int]$Pid2 = 0,
  [string]$Out = "D:\MRE\VXPstore\CungThuBongDen\build-win32\ocr.png",
  [int]$CropX = 893, [int]$CropY = 58, [int]$CropW = 240, [int]$CropH = 320,
  [int]$Scale = 3
)
# Capture the MREmu canvas (PrintWindow works when covered), upscale for OCR,
# invert to dark-on-light, then run Windows.Media.Ocr. Prints recognized lines.
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PW2 {
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$p = Get-Process -Id $Pid2
$hwnd = $p.MainWindowHandle
$r = New-Object PW2+RECT
[PW2]::GetWindowRect($hwnd, [ref]$r) | Out-Null
$w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
[PW2]::PrintWindow($hwnd, $hdc, 2) | Out-Null
$g.ReleaseHdc($hdc)

# crop
$crop = $bmp.Clone([System.Drawing.Rectangle]::new($CropX, $CropY, $CropW, $CropH), $bmp.PixelFormat)
$bmp.Dispose()

# upscale with nearest-neighbor to keep pixel edges, invert to dark-on-light
$big = New-Object System.Drawing.Bitmap(($CropW * $Scale), ($CropH * $Scale), [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g2 = [System.Drawing.Graphics]::FromImage($big)
$g2.Clear([System.Drawing.Color]::White)
$g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$g2.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$cm = New-Object System.Drawing.Imaging.ColorMatrix
$cm.Matrix00 = -1; $cm.Matrix11 = -1; $cm.Matrix22 = -1
$cm.Matrix40 = 1;  $cm.Matrix41 = 1;  $cm.Matrix42 = 1
$ia = New-Object System.Drawing.Imaging.ImageAttributes
$ia.SetColorMatrix($cm)
$g2.DrawImage($crop, (New-Object System.Drawing.Rectangle(0, 0, $big.Width, $big.Height)), 0, 0, $CropW, $CropH, [System.Drawing.GraphicsUnit]::Pixel, $ia)
$g2.Dispose()
$big.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$big.Dispose(); $crop.Dispose()

# OCR via WinRT
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Out)) ([Windows.Storage.StorageFile])
$stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap  = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine  = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result  = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
foreach ($ln in $result.Lines) {
  $bx = [int]($ln.Words[0].BoundingRect.X / $Scale)
  $by = [int]($ln.Words[0].BoundingRect.Y / $Scale)
  Write-Output ("[{0},{1}] {2}" -f $bx, $by, $ln.Text)
}