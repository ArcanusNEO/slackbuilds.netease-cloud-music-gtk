#!/usr/bin/env python3
"""Build-time pkg-config relocation and runtime-only package cleanup."""

from pathlib import Path
import shutil
import subprocess
import sys


def relocate_pc(runtime, prefix, libdir):
    # Only staging .pc files are rewritten; installed ELF/data paths stay final.
    for base in (runtime / libdir, runtime / 'share'):
        for path in base.rglob('*.pc'):
            text = path.read_text()
            if str(runtime) not in text:
                path.write_text(text.replace(prefix, str(runtime)))


def prune(runtime, libdir):
    for name in ('include', 'share/aclocal', 'share/bash-completion',
                 'share/doc', 'share/gtk-doc', 'share/man', 'share/vala',
                 'share/glib-2.0/codegen', 'share/gdb', 'share/gettext',
                 libdir + '/pkgconfig', libdir + '/glib-2.0'):
        shutil.rmtree(runtime / name, ignore_errors=True)
    # Retain the tools used by install hooks and useful multimedia diagnostics.
    keep = {'netease-cloud-music-gtk4', 'glib-compile-schemas',
            'gio-querymodules', 'gtk4-update-icon-cache', 'gst-inspect-1.0',
            'gst-launch-1.0', 'gst-play-1.0', 'gst-discoverer-1.0'}
    for path in (runtime / 'bin').iterdir():
        if path.name not in keep:
            path.unlink()
    for path in list(runtime.rglob('*')):
        if path.is_file() and path.suffix in ('.a', '.la', '.pc'):
            path.unlink()
        elif path.name == '__pycache__' and path.is_dir():
            shutil.rmtree(path)


def check_elf(runtime, workdir):
    count = 0
    for path in runtime.rglob('*'):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        dynamic = subprocess.run(['readelf', '-d', str(path)], check=True,
                                 text=True, stdout=subprocess.PIPE).stdout
        for line in dynamic.splitlines():
            if ('RPATH' in line or 'RUNPATH' in line) and (
                    workdir in line or '/tmp/' in line):
                raise SystemExit(f'Build-directory RPATH in {path}: {line}')
        subprocess.run(['strip', '--strip-unneeded', str(path)], check=True)
        count += 1
    print(f'Checked runtime paths and stripped {count} ELF files')


if __name__ == '__main__':
    action, root, *args = sys.argv[1:]
    if action == 'relocate-pc':
        relocate_pc(Path(root), *args)
    elif action == 'prune':
        prune(Path(root), *args)
    elif action == 'check-elf':
        check_elf(Path(root), *args)
    else:
        raise SystemExit(f'Unknown operation: {action}')
