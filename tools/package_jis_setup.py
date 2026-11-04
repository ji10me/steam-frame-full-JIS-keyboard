#!/usr/bin/env python3
"""Build only the setup scripts/profiles; exclude live state and binaries."""
import gzip
import hashlib
import io
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extras"))
from setup_jis import VERSION

ADDON = ("frame-jis-keyboard", "frame-jis-systemui-session", "frame_jis_vr.py", "frame_jis_pc.py",
         "frame_jis_cdp.py", "install.py", "restore.py", "patch_runtime.py", "systemui_router.js",
         "languages/ja-romaji-jis.json")
FILES = ("LICENSE", "extras/setup_jis.py", "extras/jis-desktop/bin/framekeyboard-toggle",
         "extras/jis-desktop/bin/frame-jis-ime-start", "extras/jis-desktop/layouts/ja-jis-frame.json",
         "extras/jis-desktop/languages/ja-jis-frame.json", *tuple("extras/unified-jis/" + name for name in ADDON))


def build(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    name = "frame-jis-setup-" + VERSION
    files = {relative: (ROOT / relative).read_bytes() for relative in FILES}
    files["install.sh"] = b'#!/bin/sh\nset -eu\ncd -- "$(dirname -- "$0")"\nexec python3 extras/setup_jis.py "$@"\n'
    files["README.txt"] = ("Steam Frame用 JISセットアップ " + VERSION + "\n\n"
        "Frameの端末で sh install.sh を実行し、番号を選んでください。PCやsudoは不要です。\n"
        "1はデスクトップ用、2はSteamメニューへの統合（SteamVR連動の自動起動）です。\n"
        "必要なら通常版0.8.2をSHA256確認付きで取得します。Anthyをローマ字・ひらがなへ設定します。\n"
        "Flatpak版Chromeの設定も変える場合: sh install.sh --unified --chrome\n"
        "元に戻す: python3 ~/.local/state/frame-jis-setup/restore_setup.py --restore\n"
        "通常版アプリとバックアップは復元後も残ります。既存の手動JIS統合には上書きしません。\n"
        "手順: https://github.com/ji10me/steam-frame-full-JIS-keyboard/blob/main/INSTALL.ja.md\n"
        "ライセンス: 同梱LICENSE（MIT）。元のFull KeyboardはTaiKeid and contributorsの著作物です。\n").encode()
    files["MANIFEST.sha256"] = "".join(hashlib.sha256(data).hexdigest() + "  " + relative + "\n"
                                       for relative, data in sorted(files.items())).encode()
    archive = destination / (name + ".tar.gz")
    with archive.open("wb") as output, gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as bundle:
            for relative, data in sorted(files.items()):
                entry = tarfile.TarInfo(name + "/" + relative)
                entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
                bundle.addfile(entry, io.BytesIO(data))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / "SHA256SUMS").write_text(digest + "  " + archive.name + "\n")
    return archive, digest


if __name__ == "__main__":
    archive, digest = build(ROOT / "out/jis-setup")
    print(archive)
    print(digest)
