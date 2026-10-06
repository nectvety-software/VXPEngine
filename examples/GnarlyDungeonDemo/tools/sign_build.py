from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root.parents[1]/'app'))
from signing_service import signer_arguments
source=root/'build-arm/main/gnarly_dungeon.vxp'
subprocess.run([sys.executable,*signer_arguments(source,source.with_name('gnarly_dungeon_signed.vxp'),root)],check=True)
