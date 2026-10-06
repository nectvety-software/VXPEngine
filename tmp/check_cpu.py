import subprocess
result = subprocess.run(["powershell", "-Command", 
    "(Get-CimInstance Win32_Processor).Name"], capture_output=True, text=True)
print("CPU:", result.stdout.strip())

# Check for AVX support via registry
import winreg
try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
    print("Arch:", winreg.QueryInfoKey(key))
except:
    pass

# Simple check via Python
import platform
print("Machine:", platform.machine())
print("Processor:", platform.processor())
print("Python:", platform.python_version())

# Check via environment
import os
print("PROCESSOR_IDENTIFIER:", os.environ.get("PROCESSOR_IDENTIFIER", "N/A"))
print("PROCESSOR_ARCHITECTURE:", os.environ.get("PROCESSOR_ARCHITECTURE", "N/A"))
print("NUMBER_OF_PROCESSORS:", os.environ.get("NUMBER_OF_PROCESSORS", "N/A"))
