#!/bin/sh
# Bootstrap for this repository's source-only setup bundle (MIT).
set -eu

if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != aarch64 ]; then
    echo 'このコマンドはSteam Frameの端末で実行してください。' >&2
    exit 1
fi
if [ "$(id -u)" = 0 ]; then
    echo 'sudoを付けず、通常のユーザーで実行してください。' >&2
    exit 1
fi
for command in curl sha256sum tar python3; do
    command -v "$command" >/dev/null 2>&1 || { echo "必要なコマンドがありません: $command" >&2; exit 1; }
done

umask 077
work=$(mktemp -d "${TMPDIR:-/tmp}/frame-jis-bootstrap.XXXXXX")
trap 'rm -rf -- "$work"' 0
trap 'exit 130' 2
trap 'exit 143' 15
archive=frame-jis-setup-0.1.0.tar.gz
url=https://github.com/ji10me/steam-frame-full-JIS-keyboard/releases/download/jis-setup-0.1.0
expected=cda65265de35e9353068d09b24ec285d5063ef618c795803b78ff9dfe29d1bce
echo 'JISセットアップを取得しています…'
curl -fsSL --max-time 90 "$url/$archive" -o "$work/$archive"
if ! (cd "$work" && printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -); then
    echo 'セットアップのSHA256が一致しないため停止しました。' >&2
    exit 1
fi
tar -xzf "$work/$archive" -C "$work"
if [ -t 1 ] && [ -r /dev/tty ]; then
    python3 "$work/frame-jis-setup-0.1.0/extras/setup_jis.py" "$@" </dev/tty
else
    python3 "$work/frame-jis-setup-0.1.0/extras/setup_jis.py" "$@" </dev/null
fi
