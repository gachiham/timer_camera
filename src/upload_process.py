# Copyright(c) 2021 gachiham
# This software is released under the MIT License, see LICENSE.

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
import pathlib
import requests
import os
import common


SCOPES = ['https://www.googleapis.com/auth/photoslibrary']
API_SERVICE_NAME = 'photoslibrary'
API_VERSION = 'v1'
APPLICATION_NAME = 'camera'
CLIENT_SECRET_FILE = 'client_secret.json'
TOKEN_FILE = 'google_photos_token.json'
UPLOAD_MAX = 50


# ログの設定
logger = common.logger_setup(__name__)


# google apiを使用するための認証情報を取得する
def get_credentials():
    # .credentials/google_photos_token.jsonに認証情報を保存
    # jsonファイルがない初回は、ブラウザ起動で認証しないといけない
    credentials_dir = str(pathlib.Path(
        __file__).parent.resolve()) + '/.credentials'
    os.makedirs(credentials_dir, exist_ok=True)
    credential_path = os.path.join(credentials_dir, TOKEN_FILE)

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, None)
        logger.debug('Storing credentials to {}'.format(credential_path))
    return build(
        API_SERVICE_NAME,
        API_VERSION,
        http=credentials.authorize(Http()),
        cache_discovery=False)


# Google Photoにあるアルバム名を取得する
def get_album_list(service):
    album_id_list = {}
    while True:
        nextPageToken = ''
        album_list = execute_service_api(
            service.albums().list(
                pageSize=50,
                pageToken=nextPageToken),
            'service.albums().list().execute()')
        for album in album_list['albums']:
            # 各アルバムの名前と ID を保存
            album_id_list[album['title']] = album['id']
        # nextPageToken が無ければ、取得完了
        if 'nextPageToken' not in album_list:
            break
        nextPageToken = album_list['nextPageToken']
    return album_id_list


# Google Photoにファイルをアップロードする
def execute_service_api(service_api, service_name):
    try:
        response = service_api.execute()
        return response

    except Exception as e:
        logger.error(e)


# Google Photoに新しいアルバムを作成する
def create_new_album(service, album_name):
    try:
        logger.info('create album: {}'.format(album_name))
        new_album = {'album': {'title': album_name}}
        response = service.albums().create(body=new_album).execute()
        logger.info(
            'id: {}, title: {}'.format(
                response['id'],
                response['title']))
        return response['id']

    except Exception as e:
        logger.error(e)


# Google Photoに画像/動画ファイルのバイナリデータをアップロードする
def upload_process(service, image_file, album_id):
    logger.info('upload_process start')
    upload_list = []
    try:
        for image in image_file:
            # service object がアップロードに対応していないので、
            # ここでは requests を使用
            with open(str(image), 'rb') as image_data:
                url = 'https://photoslibrary.googleapis.com/v1/uploads'
                headers = {
                    'Authorization': "Bearer " + service._http.request.credentials.access_token,
                    'Content-Type': 'application/octet-stream',
                    'X-Goog-Upload-File-Name': os.path.basename(image),
                    'X-Goog-Upload-Protocol': "raw",
                }
                response = requests.post(url, data=image_data, headers=headers)
            # アップロードの応答で upload token が返る
            upload_token = response.content.decode('utf-8')
            upload_list.append({
                'simpleMediaItem': {'uploadToken': upload_token}
            })

        new_item = {'albumId': album_id, 'newMediaItems': upload_list}
        response = execute_service_api(service.mediaItems().batchCreate(
            body=new_item), 'service.mediaItems().batchCreate().execute()')
        status = response['newMediaItemResults'][0]['status']
        logger.info('batchCreate status: {}'.format(status))
        return status

    except Exception as e:
        logger.error(e)


# Google Photoへ画像/動画ファイルをアップロードする
def file_upload(album_name, file_list):
    # 認証を行い、API呼び出し用のオブジェクトを取得する
    service = get_credentials()

    if not service:
        logger.info('Credentials acquisition failure')
        return

    # アルバム名を取得する
    album_id_list = get_album_list(service)

    # 取得したアルバム一覧にアップロード先のアルバム名が存在すれば、そのアルバムに追加する
    if album_name in album_id_list:
        logger.info('album: {} exists'.format(album_name))
        album_id = album_id_list[album_name]
    else:
        # アルバムを新規作成する
        logger.info('album: {} not exists'.format(album_name))
        album_id = create_new_album(service, album_name)
        logger.info('album: {} created'.format(album_name))

    while True:
        upload_list = []
        for file in file_list:
            upload_list.append(file)
            # 50ファイル以上ある場合は、一回アップロードする
            if len(upload_list) >= UPLOAD_MAX:
                logger.info('Reached upload limit')
                break

        # アップロードを実行する
        status = upload_process(service, upload_list, album_id)
        if status:
            # アップロードに成功したのでファイル削除
            for cnt in range(len(upload_list)):
                os.remove(upload_list[cnt])
                file_list.remove(upload_list[cnt])

            # アップロードするファイルがなくなったら終了
            if not len(file_list):
                logger.info('Uploaded all files')
                break
        else:
            # アップロードに失敗したので終了
            logger.error('upload_process: {}'.format(status))
            break
