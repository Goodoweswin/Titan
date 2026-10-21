"""Build the scientific executable, including its own Python runtime."""
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
dest=ROOT/'src-tauri/binaries'
dest.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile',
 '--name','wb-engine-aarch64-apple-darwin','--paths',str(ROOT/'backend'),
 '--hidden-import','matplotlib.backends.backend_svg',
 '--distpath',str(dest),'--workpath',str(ROOT/'build/engine'),
 '--specpath',str(ROOT/'build'),str(ROOT/'backend/entry.py')],cwd=ROOT,check=True)
