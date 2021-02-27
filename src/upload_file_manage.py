# Copyright(c) 2021 gachiham
# This software is released under the MIT License, see LICENSE.

from pathlib import Path
import os
import common


# ログの設定
logger = common.logger_setup(__name__)


# アップロード対象のファイルの拡張子を確認する
def is_uploadable_file_extension(file):
    # 拡張子を取得
    base, extension = os.path.splitext(file)

    # jpegとmp4以外はアップロード対象外
    if extension == '.jpeg' or extension == '.mp4':
        return True
    else:
        return False


# アップロード対象のアルバム名とファイルを取得する
def get_upload_target(upload_file_list, file_list):
    # アップロード対象のファイルがない場合は即終了
    if not len(file_list):
        return ''

    # アップロード時のアルバム名(YYYYmmDD)を取得する
    album_name = os.path.basename(file_list[0])[0:8]
    logger.debug(album_name)

    # アルバム名と同じ年月日のファイルだけリストへ追加する
    for file in file_list:
        logger.debug(file)
        if album_name == os.path.basename(file)[0:8]:
            upload_file_list.append(file)
        else:
            break

    return album_name


# アップロード可能な画像/動画ファイルを取得する
def get_upload_files(camera_path, upload_file_list):
    file_list = []
    # 取得したcameraディレクトリ内の一覧でアップロード対象があるか
    for file in Path(camera_path).glob("*"):

        # ディレクトリの場合、対象外なので次へ
        if not file.is_file():
            logger.debug('dir:{}'.format(file))
            continue

        file_name = str(file)

        # ファイルの更新日を確認する
        if not common.is_uploadable_time_stamp(file_name):
            logger.info('is_uploadable_time_stamp NG :{}'.format(file_name))
            continue

        # ファイルの拡張子を確認する
        if not is_uploadable_file_extension(file_name):
            logger.info(
                'is_uploadable_file_extension NG :{}'.format(file_name))
            continue

        file_list.append(file_name)

    # 日付毎にアップロードするフォルダを変更するため、ソートする
    file_list.sort()

    return get_upload_target(upload_file_list, file_list)
