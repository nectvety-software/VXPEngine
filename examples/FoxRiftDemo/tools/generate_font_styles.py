from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/"app"))
from pixel_fonts import load,save
save(ROOT,load(ROOT))
print("Generated project pixel font styles")
