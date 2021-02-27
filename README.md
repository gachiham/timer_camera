# カメラアプリについて

## 概要

Raspberry Piで画像を5秒間隔で保存するアプリです。  
ネットワークに接続している場合、自動でgoogle photoにアップロードします。

## 使用するライブラリ

### aptでインストールするライブラリ

- gpac

### pipでインストールするライブラリ

- picamera
- RPi.GPIO
- google-api-python-client
- oauth2client

## 注意事項

google photoにアップロードする場合、トークンの取得が必要になります。

## License

The source code is licensed MIT.
