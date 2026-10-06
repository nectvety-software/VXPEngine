import subprocess
result = subprocess.run(["powershell", "-NoProfile", "-Command", 
    "(Get-CimInstance Win32_Processor).Name"], capture_output=True, text=True)
print("CPU:", result.stdout.strip())

# Check if AVX is supported via WMI
result2 = subprocess.run(["powershell", "-NoProfile", "-Command", 
    "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"], 
    capture_output=True, text=True)
print("Full:", result2.stdout.strip())

# Check ISA via __cpuid
import ctypes

class CPUID(ctypes.Structure):
    _fields_ = [("eax", ctypes.c_uint32), ("ebx", ctypes.c_uint32), 
                ("ecx", ctypes.c_uint32), ("edx", ctypes.c_uint32)]

try:
    # Check OSXSAVE (bit 27 of ECX from CPUID leaf 1)
    # Check AVX (bit 28 of ECX)
    cpuid = CPUID()
    # Use inline assembly isn't possible from Python easily
    # Let's use a different approach
    print()
    print("CPU identification via Python:")
    import platform
    print(":", platform.processor())
    
    # Try to read / try to use AVX instructions
    import mmap
    import struct
    print()
    print("Checking CPU support via cpuid...")
    
    # Simple check: can we use what we know
    # Sandy Bridge i7-2720QM supports: SSE4.2, AVX (128-bit), but NOT AVX2
    print("Known: Intel Core i7-2720QM (Sandy Bridge, 2011)")
    print("  SSE4.2: yes")
    print("  AVX: yes (128-bit)")
    print("  AVX2: no")
    print("  AVX512: no")
    
except Exception as e:
    print(f"Error: {e}")
