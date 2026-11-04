# インストール方法

[README](README.md) | [使い方](USAGE.ja.md)

## かんたんセットアップ（試験版）

操作はSteam Frame上で行います。Steamの設定で開発者モードを有効にし、Konsole（端末）を開いて、次の1行を実行してください。

```sh
curl -fsSL https://raw.githubusercontent.com/ji10me/steam-frame-full-JIS-keyboard/main/install-jis.sh | sh
```

導入先を聞かれるので、番号を入力します。

| 番号 | 導入するもの |
| --- | --- |
| **1**（Enterでも選択） | デスクトップ用JIS。アプリ一覧から手動で開閉します |
| **2** | SteamメニューとデスクトップのJIS統合。SteamVR連動の自動起動を有効にします |

**「導入が完了しました」**と表示されたら、Frameのデスクトップを開き、アプリ一覧の **Full Keyboard（表示／非表示）** から試してください。2を選んだ場合は、対応するSteam入力欄やウィンドウのキーボードボタンからも呼び出せます。

### Chromeでも日本語入力したい場合

Flatpak版Chromeを使う場合は、上のコマンドの代わりに次を実行します。既存のChrome設定をバックアップしたうえで、X11/XIM設定を追加します。

```sh
curl -fsSL https://raw.githubusercontent.com/ji10me/steam-frame-full-JIS-keyboard/main/install-jis.sh | sh -s -- --chrome
```

導入後、Chromeを一度終了して開き直してください。

## セットアップが行うこと

- 通常版Full Keyboard 0.8.2がなければ、元プロジェクトから取得して、固定のSHA256と照合して導入します。
- 既存設定をバックアップし、JISプロファイルと表示／非表示ランチャーを用意します。
- ユーザーのAnthy設定をローマ字入力・ひらがなモードへ合わせます。
- 2を選んだ場合だけJIS統合サービスを導入し、自動起動を有効にします。
- `--chrome`を付けた場合だけ、Flatpak版Chromeの入力設定を変更します。

Steam本体のファイルやシステムパッケージは変更しません。管理者権限は使いません。必要なコマンドやIMEがない場合は、その内容を表示して停止します。

別バージョンのFull Keyboardや既存の手動JIS統合を見つけた場合は、自動で置き換えず停止します。すでにJIS統合を使えているFrameに、このセットアップを重ねて実行する必要はありません。

## 途中で失敗した場合

JIS設定の変更が始まった後でエラーになった場合は、バックアップから復元を試みます。後から設定を戻す場合も、Frameの端末で次の1行を実行できます。

```sh
python3 ~/.local/state/frame-jis-setup/restore_setup.py --restore
```

復元ではJIS導入前の設定・ランチャー・サービス設定・Anthy設定を戻します。`--chrome`を使った場合はChrome設定も対象です。復元直前のファイルも別のバックアップへ保存します。

**通常版Full Keyboardとバックアップは復元後も残ります。** バックアップと復元用スクリプトは`~/.local/state/frame-jis-setup/`にあるため、復元前にこのフォルダーを削除しないでください。

もう一度導入する場合は、先に上の復元コマンドを実行します。旧版からの自動更新には対応していません。

## ダウンロードしてから実行する方法

[セットアップ配布ページ](https://github.com/ji10me/steam-frame-full-JIS-keyboard/releases/tag/jis-setup-0.1.0)から、`frame-jis-setup-0.1.0.tar.gz`と`SHA256SUMS`をFrameのDownloadsへ保存します。

```sh
cd ~/Downloads
sha256sum -c SHA256SUMS
```

対象ファイルが`OK`と確認できてから実行します。

```sh
tar -xzf frame-jis-setup-0.1.0.tar.gz
cd frame-jis-setup-0.1.0
sh install.sh
```

ソースリポジトリの自動生成ZIPには、実行に必要なARM64本体は含まれません。かんたんセットアップは、その本体を必要に応じて別途取得します。

## 確認できている範囲

設定の保存・復元・失敗時の処理を自動テストしています。Frame上ではARM64アプリによるJISプロファイルの検査と、既存JIS統合を上書きしない動作を確認しました。別のFrameでの新規インストール全工程と、導入後の実際の日本語入力は未検証です。

個別の設定手順を確認したい場合は[手動インストール](docs/install-manual.ja.md)、操作方法は[使い方](USAGE.ja.md)を参照してください。
