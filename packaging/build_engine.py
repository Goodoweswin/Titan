"""Build the scientific executable on its target OS, including Python."""
import platform
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def binary_name(system, machine):
    targets={('Darwin','arm64'):'aarch64-apple-darwin',
             ('Darwin','x86_64'):'x86_64-apple-darwin',
             ('Windows','amd64'):'x86_64-pc-windows-msvc',
             ('Windows','x86_64'):'x86_64-pc-windows-msvc'}
    target=targets.get((system,machine.lower()))
    if target is None:
        raise ValueError(f'Unsupported native build platform: {system}/{machine}')
    return 'wb-engine-'+target


def main():
    name=binary_name(platform.system(),platform.machine())
    dest=ROOT/'src-tauri/engine';dest.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
     '--name','wb-engine','--paths',str(ROOT/'backend'),
     '--hidden-import','matplotlib.backends.backend_svg',
     '--hidden-import','matplotlib.backends.backend_pdf',
     # TIFF codecs are loaded on demand by imagecodecs.
     '--collect-submodules','imagecodecs',
     '--add-data',str(ROOT/'backend/titan_wb/assets')+os.pathsep+'titan_wb/assets',
     '--distpath',str(dest),'--workpath',str(ROOT/'build/engine'),
     '--specpath',str(ROOT/'build'),str(ROOT/'backend/entry.py')],cwd=ROOT,check=True)


if __name__=='__main__':
    main()
