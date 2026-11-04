# インストール方法

[README](README.md) | [使い方](USAGE.ja.md)

通常版 → デスクトップJIS → 必要ならJIS統合ツール、の順で導入します。導入済みのFrameでは、設定を上書きする前に現在の構成を確認してください。

## 1. 必要なもの

- Steam Frameと動作中のSteamVR、KDEデスクトップ。
- Full Keyboard **0.8.2**。JIS統合インストーラーはこのバージョンを確認します。
- Frame側のPython 3、IBus/Anthy、`busctl`、`gio`、`systemd-run`。
- 追加ファイルを転送するPCと、FrameへのSSH接続。

以下では、実行場所を **PC**、**FrameのKDE端末**、**FrameへSSH接続した端末** に分けています。MacやPCではFrame用ARM64実行ファイルやインストーラーを実行しません。

## 2. 通常版Full Keyboardを導入する

**Frameのブラウザー**で[元プロジェクトのリリース一覧](https://github.com/TaiKeid/steam-frame-full-keyboard/releases)を開き、0.8.2の次の2ファイルをDownloadsへ保存します。

- `framekeyboard-0.8.2-aarch64.tar.gz`
- そのリリースの`SHA256SUMS`

**Frameの端末**で実行します。

```sh
cd ~/Downloads
sha256sum -c SHA256SUMS
```

対象ファイルのチェックサムが`OK`と確認できてから、次へ進みます。

```sh
tar -xzf framekeyboard-0.8.2-aarch64.tar.gz
cd framekeyboard-0.8.2-aarch64
bash install.sh
```

アプリ一覧から **Full Keyboard** を一度開き、設定ファイルが作成されることを確認します。通常版のSettings → Experimentalにある **Replace native keyboard** と **Start with SteamOS** はOFFにし、設定を保存してアプリを終了してください。

GitHubの自動生成する「Source code (zip)」は、上記ARM64パッケージの代わりにはなりません。

## 3. JIS追加ファイルをFrameへ転送する

**PC**にこのリポジトリを取得します。すでに保存してある場合は、そのフォルダーを開きます。

```sh
git clone https://github.com/ji10me/steam-frame-full-JIS-keyboard.git
cd steam-frame-full-JIS-keyboard
```

`FRAME_IP`を自分のFrameのIPアドレスに置き換え、PCから転送します。

```sh
FRAME_HOST=steamos@FRAME_IP
scp -r extras/jis-desktop extras/unified-jis "${FRAME_HOST}:~/Downloads/"
```

Frameにはこの2フォルダーだけを転送します。リポジトリ全体のチェックアウトやFrame上でのビルドは必要ありません。

## 4. デスクトップJISとIMEを設定する

**FrameのKDEデスクトップ内の端末**で、[デスクトップJISの設定手順](extras/jis-desktop/README.ja.md#このフォルダーだけをframeへコピーする)を開き、`cd ~/Downloads/jis-desktop`以降のコマンドを順に実行します。

この手順には以下を含みます。バックアップ先を控えてください。

1. 既存の設定・起動スクリプトのバックアップ。
2. JIS配列と言語プロファイルのコピー。
3. 設定と **Full Keyboard（表示／非表示）** 起動項目の作成。
4. [IBus/Anthyと、必要な場合のChrome設定](extras/jis-desktop/README.ja.md#日本語imeとchromeの設定)。

設定後は個人情報を含まない確認用の入力欄で、`nihon` → Space → Enterと入力し、**日本**になることを確認します。**半/全**で英数へ切り替わることも確認してください。

デスクトップだけで使う場合は、ここで導入完了です。[使い方](USAGE.ja.md)へ進めます。

## 5. SteamメニューにもJIS統合を追加する（任意・実験用）

デスクトップJISの動作確認後に行います。標準キーボードの置換にはSteam Developer ModeとSteamの既存のローカル接続が必要です。詳しい条件は[元の置換機能の説明](docs/native-replacement.md)を参照してください。利用できない場合は標準キーボードを使う経路が残ります。

**PC**からFrameへSSH接続します。

```sh
ssh "$FRAME_HOST"
```

ここからは **FrameへSSH接続した端末** で実行します。

```sh
cd ~/Downloads/unified-jis
mkdir -p ~/.config/framekeyboard/languages
cp -n languages/ja-romaji-jis.json ~/.config/framekeyboard/languages/
python3 install.py
```

`cp -n`は同名の既存プロファイルを上書きしません。`ja-romaji-jis`はSteam用の内蔵変換で使うもので、デスクトップ用の`ja-jis-frame`とは別です。

インストーラーは既存の0.8.2から専用の実行環境を作り、専用設定とユーザーサービスを登録します。**JIS制御サービスの自動起動が有効になります。** SteamVRが動作中ならその場で起動し、停止中なら次回のSteamVR起動時に準備します。キーボードは呼び出すまで非表示です。

初回やVRメニューの再起動後には、メニュー表示部分が読み直される場合があります。Steam本体のファイルは変更しません。

## 6. 導入状態を確認する

**FrameへSSH接続した端末**で実行します。

```sh
systemctl --user is-enabled frame-jis-keyboard.service
systemctl --user is-active frame-jis-keyboard.service
```

自動起動が有効なら`enabled`、SteamVR動作中にサービスが起動していれば`active`です。SteamVR停止中の`inactive`だけでは導入失敗とは判断できません。

Frameを装着し、Steamメニューとデスクトップの確認用入力欄で、それぞれ表示・日本語変換・閉じる操作を確認してください。別のFrameへの新規導入を一括して検証済みという意味ではありません。

## 一時停止・元に戻す

以下は **FrameへSSH接続した端末** で行います。JIS統合の自動起動を停止します。

```sh
systemctl --user disable --now frame-jis-keyboard.service
```

再び有効にするには、次を実行します。

```sh
systemctl --user enable --now frame-jis-keyboard.service
```

JIS統合を導入する前のランチャー・ユーザーサービスへ戻すには、次を実行します。

```sh
cd ~/Downloads/unified-jis
python3 restore.py
```

復元用データは`~/.local/state/frame-jis-keyboard/`に保存されています。**復元前に削除しないでください。** 専用の設定やバックアップは復元後も残ります。

`restore.py`が戻すのはJIS統合の導入時に記録したファイルです。手順4のデスクトップJISやChrome設定まで戻す場合は、[デスクトップ設定の復元手順](extras/jis-desktop/README.ja.md#以前の構成へ戻す)も実施してください。

## 更新時の注意

このJIS統合は0.8.2前提です。元アプリだけを更新しても、専用環境やJIS統合が対応するとは限りません。新しい版へ変更する前に、対応状況と復元用バックアップを確認してください。
