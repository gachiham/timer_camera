# Copyright(c) 2021 gachiham
# This software is released under the MIT License, see LICENSE.

from pathlib import Path
import os
from datetime import datetime
import logging


# ログフォルダのパスを取得(絶対パス)
def get_log_path():
    return str(Path(__file__).parent.resolve()) + '/log/'


# 画像/動画保存フォルダのパスを取得(絶対パス)
def get_camera_path():
    return str(Path(__file__).parent.resolve()) + '/camera/'


# 書き込み途中のファイルをアップロード対象としないため、
# ファイルの更新日が現在の時刻から60秒以上離れているか確認
def is_uploadable_time_stamp(file):
    check_time = int(datetime.now().strftime('%s'))
    file_time = int(os.path.getmtime(file))

    if check_time > file_time + 60:
        return True
    else:
        return False


# ログの設定
def logger_setup(name, is_add_console=False):
    # 直下logフォルダがない場合、作成する
    # Python3.2以降はフォルダが既に存在していてもエラーにならないようにフラグを立てる
    # Python3.2以前を使用する場合は、例外処理を追加しないとエラーになるため注意！
    os.makedirs(get_log_path(), exist_ok=True)

    # ログのデータフォーマットと書き込むファイルの設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(module)-20s %(funcName)-20s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M',
        filename=get_log_path() +
        datetime.now().strftime('%Y%m%d') +
        '.log',
        filemode='a+')

    if is_add_console:
        # コンソールにも出力する。
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(module)-20s: %(funcName)-20s %(levelname)-8s %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

    return logging.getLogger(name)
