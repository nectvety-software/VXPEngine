"""Link a sample-specific harness against an existing VXPEmu build.

The emulator sources/build are read only; all generated files stay in reports.
Requires the local MSVC/Qt layout used for VXPEmu build-new.
"""
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT.parents[1]
EMU=Path(os.environ.get('VXPE_EMU_SOURCE','D:/MRE/VXPEmu'))
BUILD=EMU/'build-new'
OUT=ENGINE/'reports/vaelora-duel'
QT=Path('D:/Qt/6.7.0/msvc2019_64')
VC=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # Reuse actual emulator object files, replacing only its test main.
    objects=(BUILD/'CMakeFiles/VXPTest.dir/objects1.rsp').read_text(encoding='utf-8-sig').split()
    objects=[str((BUILD/p).resolve()) for p in objects if not p.endswith('/tools/VXPTest.cpp.obj')]
    objects.append(str(OUT/'smoke.obj'))
    rsp=OUT/'objects.rsp'
    rsp.write_text('\n'.join('"'+p+'"' for p in objects))
    cpp=ROOT/'tests/vxpemu_smoke.cpp'
    compiler=VC/'Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe'
    linker=compiler.with_name('link.exe')
    executable=OUT/'FoxRiftSmoke.exe'
    includes=[EMU/'src',QT/'include',QT/'include/QtCore',QT/'include/QtGui',QT/'mkspecs/win32-msvc']
    compile_args=[str(compiler),'/nologo','/MD','/EHsc','/std:c++20','/Zc:__cplusplus','/O2','/DNOMINMAX','/DQT_NO_DEBUG',
        *['/I'+str(p) for p in includes],'/Fo'+str(OUT/'smoke.obj'),'/c',str(cpp)]
    libs=[QT/'lib/Qt6Core.lib',QT/'lib/Qt6Gui.lib',BUILD/'unicorn_build/unicorn.lib']
    link_args=[str(linker),'/nologo','/OUT:'+str(executable),'@'+str(rsp),*map(str,libs),
        'winmm.lib','ws2_32.lib','mpr.lib','userenv.lib','d3d11.lib','dxgi.lib','dxguid.lib','d3d12.lib',
        'kernel32.lib','user32.lib','gdi32.lib','winspool.lib','shell32.lib','ole32.lib','oleaut32.lib',
        'uuid.lib','comdlg32.lib','advapi32.lib']
    batch=OUT/'build_smoke.bat'
    batch.write_text('@echo off\ncall "'+str(VC/'Auxiliary/Build/vcvars64.bat')+'" >nul\n'
        +subprocess.list2cmdline(compile_args)+'\nif errorlevel 1 exit /b 1\n'
        +subprocess.list2cmdline(link_args)+'\nif errorlevel 1 exit /b 1\n')
    subprocess.run(['cmd','/c',str(batch)],check=True,cwd=OUT)
    env=dict(os.environ);env['PATH']=str(QT/'bin')+';'+str(BUILD)+';'+env.get('PATH','')
    subprocess.run([str(executable),str(ROOT/'build-arm/main/vaelora_duel.vxp'),str(OUT),
        str(ROOT/'assets/backgrounds/arena.png')],check=True,env=env)

if __name__=='__main__': main()
