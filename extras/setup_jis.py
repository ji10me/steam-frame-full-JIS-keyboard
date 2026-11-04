#!/usr/bin/env python3
"""User-local JIS setup. No key delivery, system packages or Steam file edits."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

VERSION = "0.1.0"
BASE_URL = "https://github.com/TaiKeid/steam-frame-full-keyboard/releases/download/0.8.2/framekeyboard-0.8.2-aarch64.tar.gz"
BASE_SHA256 = "7ca723e13b288d8a2b6599e494bf1a6f5f37bc0764b47f2b91184779c15bfa64"
UNITS = ("frame-jis-keyboard.service", "framekeyboard-autostart.service", "framekeyboard-jis-local.service")
FILES = (
    ".config/framekeyboard", ".config/framekeyboard-unified-jis",
    ".local/share/framekeyboard/unified-jis", ".local/state/frame-jis-keyboard",
    ".config/environment.d/60-framekeyboard-jis.conf",
    ".local/share/applications/framekeyboard.desktop",
    ".local/bin/framekeyboard-toggle", ".local/bin/frame-jis-ime-start",
    ".local/bin/frame-jis-keyboard", ".local/bin/frame-jis-systemui-session",
    ".local/bin/frame_jis_vr.py", ".local/bin/frame_jis_cdp.py", ".local/bin/frame_jis_pc.py",
    *tuple(".config/systemd/user/" + unit for unit in UNITS[:2]),
    ".config/systemd/user/steamvr.service.wants/frame-jis-keyboard.service",
    ".local/share/flatpak/overrides/com.google.Chrome",
    ".var/app/com.google.Chrome/config/chrome-flags.conf",
)
SCHEMA = "org.freedesktop.ibus.engine.anthy.common"
IME_KEYS = ("typing-method", "input-mode")


class SetupError(RuntimeError):
    pass


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=90, **kwargs)


def atomic_text(path, text, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".jis-setup-", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(text)
        staged.chmod(mode)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def save_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def copy_entry(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, target, symlinks=True)
    else:
        shutil.copy2(source, target)


def remove_entry(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def extract_base(archive, destination):
    """Only ordinary files/directories below the pinned package root."""
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if len(members) > 3000 or sum(member.size for member in members) > 64 * 1024 * 1024:
            raise SetupError("通常版パッケージのサイズが想定外です。")
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or not path.parts
                    or path.parts[0] != "framekeyboard-0.8.2-aarch64"
                    or not (member.isfile() or member.isdir())):
                raise SetupError("通常版パッケージに対応外の項目があります。")
        for member in members:
            target = destination / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)


def download_base(destination):
    request = urllib.request.Request(BASE_URL, headers={"User-Agent": "frame-jis-setup/" + VERSION})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=45) as response, destination.open("wb") as output:
        if not response.geturl().startswith("https://"):
            raise SetupError("HTTPS以外のダウンロード先には接続しません。")
        while chunk := response.read(65536):
            size += len(chunk)
            if size > 8 * 1024 * 1024:
                raise SetupError("通常版パッケージが想定サイズを超えました。")
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != BASE_SHA256:
        raise SetupError("通常版のSHA256が一致しません。実行せずに停止しました。")


class Installer:
    def __init__(self, home, source, command=run):
        self.home, self.source, self.run = Path(home), Path(source), command
        self.state = self.home / ".local/state/frame-jis-setup"
        self.record = self.state / "installation.json"
        self.release = self.home / ".local/share/framekeyboard/current"

    def unit(self, action, name):
        try:
            return self.run(["systemctl", "--user", action, name]).stdout.strip()
        except subprocess.CalledProcessError as exc:
            if exc.returncode in (1, 3, 4):
                return ""
            raise

    def check(self, mode, chrome=False):
        if platform.system() != "Linux" or platform.machine() not in ("aarch64", "arm64") or os.geteuid() == 0:
            raise SetupError("Steam Frameの一般ユーザーで実行してください。sudoは不要です。")
        dependencies = ("bash", "flock", "systemctl", "systemd-run", "busctl", "gio", "gsettings", "ibus")
        missing = [name for name in dependencies if not shutil.which(name)]
        if missing:
            raise SetupError("必要なコマンドがありません: " + ", ".join(missing))
        if not Path("/opt/steamvr/bin/linuxarm64/vrcmd").is_file():
            raise SetupError("対応するSteamVRが見つかりません。")
        if any(character in str(self.home) for character in ('\n', '\r', '"', '%', '\\')):
            raise SetupError("このホームディレクトリ名には対応していません。")
        if self.record.exists() and json.loads(self.record.read_text())["status"] != "restored":
            raise SetupError("導入記録があります。再導入する場合は先に --restore で元に戻してください。")
        for relative in FILES:
            target = self.home / relative
            if not target.parent.resolve().is_relative_to(self.home.resolve()):
                raise SetupError("ホーム外を指す設定パスがあるため停止しました。")
            if relative.startswith(".config/systemd/user/") and target.is_symlink() and "/steamvr.service.wants/" not in relative:
                raise SetupError("リンクで管理された既存のサービスは変更しません。")
        config = self.home / ".config/framekeyboard"
        if config.is_symlink() or any(path.is_symlink() for path in config.rglob("*")):
            raise SetupError("シンボリックリンクで管理された設定には自動導入しません。")
        for relative in (".config/framekeyboard-unified-jis", ".local/share/framekeyboard/unified-jis",
                         ".local/state/frame-jis-keyboard", ".config/systemd/user/frame-jis-keyboard.service",
                         ".local/bin/frame-jis-keyboard", ".local/bin/frame-jis-systemui-session",
                         ".local/bin/frame_jis_vr.py", ".local/bin/frame_jis_cdp.py", ".local/bin/frame_jis_pc.py"):
            if os.path.lexists(self.home / relative):
                raise SetupError("既存のJIS統合を検出しました。現在の構成を保持して停止します。")
        if any(self.unit("is-active", unit) == "active" for unit in UNITS):
            raise SetupError("Full Keyboardを終了してから、もう一度実行してください。")
        for process in Path("/proc").glob("[0-9]*"):
            try:
                if process.stat().st_uid == os.getuid() and (process / "exe").resolve().name.removesuffix(" (deleted)") == "framekeyboard":
                    raise SetupError("Full Keyboardが動作中です。Settingsから終了してください。")
            except (OSError, RuntimeError) as exc:
                if isinstance(exc, SetupError):
                    raise
        binary = self.release / "bin/framekeyboard"
        if binary.exists():
            if not self.run([str(binary), "--help"]).stdout.startswith("Full Keyboard for Steam Frame 0.8.2\n"):
                raise SetupError("別バージョンのFull Keyboardがあります。自動で置き換えません。")
        elif os.path.lexists(self.release):
            raise SetupError("既存の通常版の配置を確認してください。自動で置き換えません。")
        preferences = self.home / ".config/framekeyboard/config.json"
        if preferences.exists():
            value = json.loads(preferences.read_text())
            if value.get("replace_native_keyboard") or value.get("start_with_steamos"):
                raise SetupError("通常版のReplace native keyboardとStart with SteamOSをOFFにしてください。")
            if value.get("schema_version", 1) != 1 or not isinstance(value.get("active", {}), dict):
                raise SetupError("対応外の既存設定です。設定を変更せずに停止しました。")
        for key in IME_KEYS:
            self.run(["gsettings", "get", SCHEMA, key])
        if chrome:
            if not shutil.which("flatpak"):
                raise SetupError("Flatpak版Chromeが必要です。--chromeを外して再実行してください。")
            self.run(["flatpak", "info", "com.google.Chrome"])

    def ensure_base(self):
        if (self.release / "bin/framekeyboard").exists():
            return
        print("通常版0.8.2を取得し、SHA256を確認しています…")
        with tempfile.TemporaryDirectory(prefix="frame-jis-base-") as directory:
            temporary = Path(directory)
            archive = temporary / "base.tar.gz"
            download_base(archive)
            extract_base(archive, temporary)
            self.run(["bash", str(temporary / "framekeyboard-0.8.2-aarch64/install.sh")])

    def snapshot(self, mode, chrome):
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Restore must also work after the temporary download has been removed.
        atomic_text(self.state / "restore_setup.py", Path(__file__).read_text())
        backup = Path(tempfile.mkdtemp(prefix="backup-", dir=self.state))
        files = list(FILES if chrome else FILES[:-2])
        for relative in files:
            path = self.home / relative
            if os.path.lexists(path):
                copy_entry(path, backup / "before" / relative)
        record = {"status": "installing", "version": VERSION, "mode": mode, "chrome": chrome,
                  "backup": backup.name, "files": files, "ime": {}, "enabled": {}}
        for key in IME_KEYS:
            record["ime"][key] = self.run(["gsettings", "get", SCHEMA, key]).stdout.strip()
        for unit in UNITS[:2]:
            record["enabled"][unit] = self.unit("is-enabled", unit) == "enabled"
        save_json(self.record, record)
        return record

    def configure(self, mode, chrome):
        config = self.home / ".config/framekeyboard"
        preferences = config / "config.json"
        base_config = self.release / "share/framekeyboard/config/default.json"
        value = json.loads((preferences if preferences.exists() else base_config).read_text())
        value.setdefault("active", {}).update(layout="ja-jis-frame-full", language="ja-jis-frame")
        value["active"].setdefault("theme", "graphite")
        for kind in ("layouts", "languages"):
            target = config / kind / "ja-jis-frame.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(target, (self.source / "jis-desktop" / kind / target.name).read_text())
        atomic_text(config / "languages/ja-romaji-jis.json", (self.source / "unified-jis/languages/ja-romaji-jis.json").read_text())
        save_json(preferences, value)
        for name in ("framekeyboard-toggle", "frame-jis-ime-start"):
            target = self.home / ".local/bin" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_text(target, (self.source / "jis-desktop/bin" / name).read_text(), 0o755)
        environment = self.home / ".config/environment.d/60-framekeyboard-jis.conf"
        environment.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(environment, "FRAMEKEYBOARD_TARGET_LANGUAGE=ja-jis-frame\n", 0o644)
        desktop = self.home / ".local/share/applications/framekeyboard.desktop"
        desktop.parent.mkdir(parents=True, exist_ok=True)
        atomic_text(desktop, '[Desktop Entry]\nType=Application\nName=Full Keyboard (show/hide)\n'
                           'Name[ja]=Full Keyboard（表示／非表示）\nExec="' +
                           str(self.home / ".local/bin/framekeyboard-toggle") +
                           '"\nIcon=input-keyboard\nTerminal=false\nCategories=Utility;Accessibility;\n', 0o644)
        self.run([str(self.release / "bin/framekeyboard"), "--check", "--config-dir", str(config),
                  "--data-dir", str(self.release / "share/framekeyboard")])
        for key in IME_KEYS:
            self.run(["gsettings", "set", SCHEMA, key, "0"])
        if chrome:
            self.run(["flatpak", "override", "--user", "--env=GTK_IM_MODULE=xim",
                      "--env=XMODIFIERS=@im=ibus", "com.google.Chrome"])
            flags = self.home / ".var/app/com.google.Chrome/config/chrome-flags.conf"
            flags.parent.mkdir(parents=True, exist_ok=True)
            text = flags.read_text() if flags.exists() else ""
            # Keep the existing text for rollback; X11 must be the final platform override.
            atomic_text(flags, text.rstrip("\n") + "\n--ozone-platform=x11\n")
        if mode == "unified":
            self.run([sys.executable, str(self.source / "unified-jis/install.py")])
        if shutil.which("update-desktop-database"):
            self.run(["update-desktop-database", str(desktop.parent)])

    def restore(self):
        record = json.loads(self.record.read_text())
        if record["status"] == "restored":
            print("すでに元の設定へ復元済みです。")
            return
        backup = self.state / record["backup"]
        if backup.parent.resolve() != self.state.resolve() or not backup.is_dir():
            raise SetupError("復元用バックアップを確認できません。")
        files = record["files"]
        if not isinstance(files, list) or len(files) != len(set(files)) or any(item not in FILES for item in files):
            raise SetupError("復元対象の一覧を確認してください。")
        if set(record["ime"]) != set(IME_KEYS) or set(record["enabled"]) != set(UNITS[:2]):
            raise SetupError("復元用の設定記録を確認してください。")
        for unit in UNITS:
            self.unit("stop", unit)
        self.unit("disable", UNITS[0])
        # Preserve post-install edits as well as the pre-install files.
        after = Path(tempfile.mkdtemp(prefix="after-", dir=backup))
        for relative in files:
            target = self.home / relative
            if not target.parent.resolve().is_relative_to(self.home.resolve()):
                raise SetupError("ホーム外を指す復元先を検出しました。")
            if os.path.lexists(target):
                copy_entry(target, after / relative)
            remove_entry(target)
            saved = backup / "before" / relative
            if os.path.lexists(saved):
                copy_entry(saved, target)
        for key, value in record["ime"].items():
            if key not in IME_KEYS:
                raise SetupError("復元用IME設定を確認してください。")
            self.run(["gsettings", "set", SCHEMA, key, value])
        self.run(["systemctl", "--user", "daemon-reload"])
        for unit, enabled in record["enabled"].items():
            if unit not in UNITS[:2]:
                raise SetupError("復元用サービス設定を確認してください。")
            self.unit("enable" if enabled else "disable", unit)
        record["status"] = "restored"
        save_json(self.record, record)
        print("JIS導入前の設定へ戻しました。バックアップと通常版アプリは残しています。")

    def install(self, mode, chrome=False):
        self.ensure_base()
        record = self.snapshot(mode, chrome)
        try:
            self.configure(mode, chrome)
            record["status"] = "installed"
            save_json(self.record, record)
        except BaseException:
            print("導入を中断し、JIS設定を復元しています…", file=sys.stderr)
            self.restore()
            raise


def main():
    parser = argparse.ArgumentParser(description="Steam Frame用JISかんたんセットアップ")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--desktop", action="store_true", help="デスクトップJISのみ（自動起動なし）")
    group.add_argument("--unified", action="store_true", help="Steamメニューにも統合（自動起動を有効化）")
    group.add_argument("--restore", action="store_true", help="このセットアップによる変更を復元")
    parser.add_argument("--chrome", action="store_true", help="Flatpak版ChromeをX11/XIMへ設定")
    parser.add_argument("--check", action="store_true", help="導入条件の確認のみ。ファイルを変更しない")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() not in ("aarch64", "arm64") or os.geteuid() == 0:
        raise SetupError("Steam Frameの一般ユーザーで実行してください。sudoは不要です。")
    # Konsole in the nested desktop may inherit a different session bus.
    runtime = "/run/user/" + str(os.getuid())
    os.environ.update(XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS="unix:path=" + runtime + "/bus")
    installer = Installer(Path.home(), Path(__file__).resolve().parent)
    mode = "unified" if args.unified else "desktop"
    if not (args.desktop or args.unified or args.restore or args.check):
        print("JISキーボードの導入先を選んでください。\n"
              "  1: デスクトップ（手動で開閉）\n"
              "  2: Steamメニューとデスクトップ（SteamVRと連動して起動）\n"
              "通常版0.8.2がなければ取得します。Anthyをローマ字・ひらがなへ設定します。")
        choice = input("番号を入力 [1/2、Enterは1、qで終了]: ").strip()
        if choice.lower() == "q":
            return
        if choice not in ("", "1", "2"):
            raise SetupError("1または2を選んでください。")
        mode = "unified" if choice == "2" else "desktop"
    if args.check:
        installer.check(mode, args.chrome)
        print("導入条件の確認が通りました。設定は変更していません。")
        return
    installer.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (installer.state / "install.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SetupError("別のセットアップが実行中です。") from exc
        if args.restore:
            installer.restore()
            return
        installer.check(mode, args.chrome)
        installer.install(mode, args.chrome)
    print("導入が完了しました。Frameのデスクトップを開き、Full Keyboard（表示／非表示）から試してください。")
    if args.chrome:
        print("Chromeは一度終了して開き直してください。")
    print("復元: python3 ~/.local/state/frame-jis-setup/restore_setup.py --restore")


if __name__ == "__main__":
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except (SetupError, OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as exc:
        # External command output may contain machine-specific information.
        message = str(exc) if isinstance(exc, SetupError) else "処理を完了できませんでした。前提条件とバックアップを確認してください。"
        print(message, file=sys.stderr)
        sys.exit(1)
