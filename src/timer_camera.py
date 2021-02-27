# Copyright(c) 2021 gachiham
# This software is released under the MIT License, see LICENSE.

from datetime import datetime
from time import sleep
from picamera import PiCamera
from picamera import PiCameraCircularIO
import os
import RPi.GPIO as GPIO
import subprocess
import shlex
from threading import Thread
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
import common
import upload_file_manage
import upload_process


# カメラの設定関係
CAMERA_RESOLUTION = (1280, 720)  # 画像/動画の解像度
CAMERA_FRAMERATE = 30            # 動画のフレームレート

# タイマー関係
INTERVAL_TIME = 5             # シャッターの間隔(秒単位で指定)
VIDEO_TIME = 60               # 動画の録画時間(秒単位で指定)
THREAD_SLEEP_TIME = 30 * 60   # アップロードスレッドの実行間隔(秒単位で指定)

# GPIO関係
VIDEO_INT_PIN = 6             # 動画撮影用のGPIOピン
SHUTDOWN_INT_PIN = 13         # シャットダウン用のGPIOピン

# フラグ関係
is_video_shooting = False     # 動画撮影フラグ
is_end = False                # 終了フラグ

# ログの設定
logger = common.logger_setup(__name__, True)


# GPIOの初期設定
def gpio_setup():
    # GPIO.BCM:ピン指定を役割ピン番号にする
    GPIO.setmode(GPIO.BCM)
    # 動画撮影スイッチの設定
    # pull_up_down=GPIO.PUD_DOWN:内部でプルダウン
    GPIO.setup(VIDEO_INT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # GPIO.RISING:立ち上がりエッジ検出
    # bouncetime:チャタリング対策用でエッジ検出を無視する時間(msec単位)
    GPIO.add_event_detect(
        VIDEO_INT_PIN,
        GPIO.RISING,
        callback=callback_video_shooting,
        bouncetime=200)

    # リセットスイッチの設定
    # pull_up_down=GPIO.PUD_DOWN:内部でプルダウン
    GPIO.setup(SHUTDOWN_INT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # GPIO.RISING:立ち上がりエッジ検出
    # bouncetime:チャタリング対策用でエッジ検出を無視する時間(msec単位)
    GPIO.add_event_detect(
        SHUTDOWN_INT_PIN,
        GPIO.RISING,
        callback=callback_shutdown,
        bouncetime=200)


# 動画撮影スイッチ押下時のコールバック関数
def callback_video_shooting(gpio_pin):
    # フラグを変更できるように宣言
    global is_video_shooting
    logger.debug('callback_video_shooting {}'.format(gpio_pin))

    if not is_video_shooting:
        is_video_shooting = True


# シャットダウンスイッチ押下時のコールバック関数
def callback_shutdown(gpio_pin):
    # フラグを変更できるように宣言
    global is_end
    logger.debug('callback_shutdown {}'.format(gpio_pin))

    # 長押し(2秒間)の判定
    sw = 0
    for count in range(10):
        sleep(0.2)
        sw = GPIO.input(gpio_pin)
        logger.debug('count:{},sw:{}'.format(count, sw))
        if sw == 0:
            break

    # スイッチが押しっぱなしだった場合、終了フラグを立てる
    if sw == 1:
        if not is_end:
            is_end = True
            logger.debug('is_end = True')


# インターネットに接続出来るか確認する
def is_internet_access():
    try:
        # google.comにアクセス出来るか
        # Proxy環境とかは考慮してない
        urlopen('https://www.google.com', timeout=1)

    # 例外としてエラーが返ってくる場合、アクセスできないとみなす
    except URLError as e:
        logger.error(e)
        return False

    return True


# .h264形式の動画を.mp4へ変換する
def convert_h264_to_mp4():
    is_convert = False
    camera_path = common.get_camera_path()
    for file in Path(camera_path).glob("*.h264"):

        file_name = str(file)
        if not common.is_uploadable_time_stamp(file_name):
            continue

        logger.info('Convert h264 to mp4 start :{}'.format(file_name))
        # コマンド生成
        cmd = 'MP4Box -fps 30 -add ' + file_name + \
            ' -new ' + file_name.rstrip('h264') + 'mp4'
        logger.debug(cmd)
        args = shlex.split(cmd)
        logger.debug(str(args))
        subprocess.run(args)
        logger.info('Convert h264 to mp4 end')

        # 変換前のファイルは削除する
        os.remove(file_name)
        is_convert = True

    return is_convert


# 別スレッドでGoogle Photoへ画像/動画ファイルをアップロードする
# ただし、動画はh264だとアップロード出来ないため、mp4に変換する
def thread_upload_photo():
    logger.info('- thread_upload_photo start -')
    sleep_count = THREAD_SLEEP_TIME
    while True:
        if is_end:
            break

        if sleep_count < THREAD_SLEEP_TIME:
            sleep(60)
            sleep_count += 60
            continue
        else:
            sleep_count = 0

        # インターネット接続出来ているか確認する
        if is_internet_access():
            logger.info('Internet access OK')
            if convert_h264_to_mp4():
                # 変換した動画もアップロード対象にしたいので70秒待つ
                sleep(70)

            upload_file_list = []
            album_name = upload_file_manage.get_upload_files(
                common.get_camera_path(), upload_file_list)

            logger.info(
                'album_name:{}, upload file={}'.format(
                    album_name,
                    len(upload_file_list)))

            if len(upload_file_list):
                upload_process.file_upload(album_name, upload_file_list)

        else:
            logger.info('Internet access NG')
            convert_h264_to_mp4()

    logger.info('- thread_upload_photo end   -')


def main():
    logger.info('--- TIMER CAMERA APP START ---')

    # フラグを変更出来るように宣言
    global is_video_shooting

    # 直下にcameraフォルダがない場合、作成する
    # Python3.2以降はフォルダが既に存在していてもエラーにならないようにフラグを立てる
    # Python3.2以前を使用する場合は、例外処理を追加しないとエラーになるため注意！
    camera_path = common.get_camera_path()
    os.makedirs(camera_path, exist_ok=True)

    # GPIOの初期設定
    gpio_setup()

    # カメラの初期設定解像度の設定)
    camera = PiCamera(resolution=CAMERA_RESOLUTION)
    camera.framerate = CAMERA_FRAMERATE
    stream = PiCameraCircularIO(camera, seconds=VIDEO_TIME)
    camera.start_preview()
    # camera.annotate_text='How is your progress?'
    sleep(2)

    # スリープは0.1秒周期なのでカウントは10倍する
    interval = INTERVAL_TIME * 10
    sleep_count = interval        # 初回は動作させるため、0クリアしない

    # Google Photoへのアップロードスレッド生成
    thread = Thread(target=thread_upload_photo)
    thread.start()
    try:
        while True:
            # 終了スイッチが長押しされた
            if is_end:
                logger.info('- End process start -')
                break

            # 動画撮影スイッチが押下された
            elif is_video_shooting:
                logger.info('Video shooting start')

                # 動画ファイル名をフルパスで作成
                video_name = camera_path + datetime.now().strftime('%Y%m%d%H%M%S') + '.h264'

                # 動画撮影
                stream.clear()
                camera.start_recording(stream, format='h264', quality=23)
                camera.wait_recording(VIDEO_TIME)
                camera.stop_recording()
                stream.copy_to(video_name)

                logger.info('Video shooting end')
                is_video_shooting = False

            # インターバル以上にスリープした
            elif sleep_count >= interval:
                # シャッターの間隔は、画像取得〜保存の処理時間を考慮したいので
                # 開始時点の時間をUNIXTIMEで取得
                start_time = datetime.now().strftime('%s')
                logger.debug('start_time  :{}'.format(start_time))

                # 画像ファイル名をフルパスで作成
                file_name = camera_path + datetime.now().strftime('%Y%m%d%H%M%S') + '.jpeg'

                # 画像を保存
                camera.capture(file_name, format='jpeg')

                end_time = datetime.now().strftime('%s')
                logger.debug('end_time    :{}'.format(end_time))

                interval = (INTERVAL_TIME -
                            (int(end_time) - int(start_time))) * 10
                logger.debug('interval    :{}'.format(interval))
                sleep_count = 0
            else:
                sleep(0.1)
                sleep_count += 1

    # CTRL+Cが押下された
    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt')

    # 終了処理
    camera.stop_preview()
    GPIO.cleanup()
    camera.close()
    # シャットダウンスイッチが押下された
    if is_end:
        # 別スレッドの終了待ち
        thread.join()
        logger.info('shutdown process start')
        # シャットダウンコマンドを実行
        args = shlex.split("sudo shutdown -h now")
        subprocess.run(args)

    logger.info('--- TIMER CAMERA APP END   ---')


if __name__ == '__main__':
    main()
