# Copyright(c) 2021 gachiham
# This software is released under the MIT License, see LICENSE.

import os
from time import sleep
import subprocess
import shlex
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
import common
import upload_file_manage
import upload_process

# ログの設定
logger = common.logger_setup(__name__, True)


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


# アップロード対象のファイルがなくなるまでアップロードを繰り返す
def upload():
    while True:
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
            break


# 実行中のプロセス内にtimer_camera.pyがあるか確認する
def is_run_camera():
    try:
        cmd = 'ps aux | grep timer_camera.py | grep -v grep | wc -l'
        if subprocess.check_output(cmd, shell=True).decode(
                'utf-8').strip() == '0':
            return False
    except Exception as e:
        logger.error(e)

    return True


def main():
    logger.info('--- UPLOADER START ---')
    # アップロード処理が重複しないようにカメラが動作していないことを確認する
    if not is_run_camera():
        # インターネット接続出来ているか確認する
        if is_internet_access():
            logger.info('Internet access OK')
            if convert_h264_to_mp4():
                # 変換した動画もアップロード対象にしたいので70秒待つ
                sleep(70)

            upload()
        else:
            logger.info('Internet access NG')
    else:
        logger.info("The camera is running, so it won't upload.")

    logger.info('--- UPLOADER END   ---')


if __name__ == '__main__':
    main()
