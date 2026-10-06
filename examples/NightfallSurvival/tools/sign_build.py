from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
engine = root.parents[1]
sys.path.insert(0, str(engine / 'app'))
from signing_service import signer_arguments

source = root / 'build-arm/main/nightfall_survival.vxp'
output = source.with_name('nightfall_survival_signed.vxp')
subprocess.run([sys.executable, *signer_arguments(source, output, root)], check=True)
