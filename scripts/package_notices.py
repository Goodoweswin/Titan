"""Archive release notices while preserving bytes from old upstream packages."""
import argparse
from pathlib import Path
import zipfile


def package_notices(root, destination):
    root=Path(root)
    sources=[(root/'LICENSE',Path('LICENSE')),
             (root/'docs/THIRD_PARTY_NOTICES.md',Path('THIRD_PARTY_NOTICES.md'))]
    folder=root/'release/third-party'
    if not (folder/'inventory.json').is_file() and not folder.is_dir():
        raise ValueError('Generate third-party notices before archiving')
    sources.extend((p,Path('third-party')/p.relative_to(folder))
                   for p in sorted(folder.rglob('*')) if p.is_file())
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    # Some dependencies intentionally ship files with Unix-epoch mtimes.
    # Clamp only ZIP metadata; license bytes and source timestamps stay unchanged.
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as archive:
        for source,name in sources:
            archive.write(source,str(name))
    return len(sources)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('destination')
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    args=parser.parse_args()
    print(f'Archived {package_notices(args.root,args.destination)} notice files')
