# -*- coding: utf-8 -*-
# Copyright (c) 2021 Tachibana Securities Co., Ltd. All rights reserved.

# 2021.07.09,   yo.
# 2023.08.30 reviced,   yo.
# 2025.07.27 reviced,   yo.
# 2026.06.27 reviced,   yo.
#
# 立花証券ｅ支店ＡＰＩ利用のサンプルコード
#
# 動作確認
# Python 3.13.5 / debian13
# API v4r9
#
# ------------------------------------------------------------------
#
# APIの基本設計について
# 
# 本APIは、プログラミング初心者や非ITエンジニアの方にも
# 利用しやすいよう、URLにJSON形式のパラメーターを付加して
# 送信する独自方式を採用しています。
# 
# 一般的なWeb APIとは異なる構成ですが、
# HTTPヘッダーやPOSTデータなどの知識を最小限に
# 抑えながら利用できることを重視しています。
# 
# このため、本APIは、URLとJSON文字列を組み立てて
# 送信するだけで利用でき、特別な知識を必要とせず、
# 各種スクリプト言語からも実装しやすいことを
# 優先した設計となっています。
#  
# ------------------------------------------------------------------
# 
# 固定IP指定の推奨
# 
# 秘密鍵、第2パスワードファイル、またはログインレスポンスファイルが
# 万が一流出した場合、第三者に不正ログインされるリスクがあります。
# 
# 安全のため、接続元を固定IPに限定する設定（IP制限）を
# 行っての利用を強く推奨いたします。
# 
# ------------------------------------------------------------------
#
# 機能: ニュースヘッダー取得
#
# 必要な設定項目
# 取得したいカテゴリコード: P_CG     未指定時は全て対象。100:QUICKニュース、110:ＡＩ市況状況速報、120:AI開示速報（決算関連）、129:ＡＩ開示速報（その他）
# 取得したい銘柄コード: P_IS       未指定時は全て対象。
# ニュース日付（YYYYMMDD）範囲指定（from）: P_DT_FROM
# ニュース日付（YYYYMMDD）範囲指定（to）: P_DT_TO      p_DT_FROM <= p_DT_TOで設定する。
# レコード取得位置: P_REC_OFST   デフォルト＝０、直近先頭の意味。
# レコード取得件数最大: P_REC_LIMT     デフォルト＝100。1回に取得できる最大件数は100。
# 出力ファイル名: FNAME_OUTPUT  （デフォルトは、'news_header_[銘柄コード].csv'）
#
# 
# 利用方法: 
# 事前に「e_api_login_pubkey.py」を実行して、仮想URL等を取得しておいてください。
# 実行は「e_api_login_pubkey.py」と同じディレクトリで行ってください。
#
# ファイル構成：
# ~/e_api/                              ← API実行基盤（権限: 700 / 所有者のみアクセス可）
# ├── .auth/                        ← 鍵・暗号化データ格納（権限: 700）
# │   ├── file_pwd2.txt             ← 第2パスワード保存ファイル（手動作成。注文・訂正・取消以外は不要）
# │   └── file_login_response.txt   ← ログイン応答出力先（自動生成）
# ├── file_url_info.txt             ← API接続情報ファイル（手動作成）
# ├── e_api_login_pubkey.py
# │
# └── [本実行プログラム]
# 
# 
# ~/e_api/file_url_info.txtの内容例：
# {
#     "sUrl": "https://demo-kabuka.e-shiten.jp/e_api_v4r9/",
#     "sJsonOfmt": "5"
# }
#
#
# == ご注意: ========================================
#   本番環境にに接続した場合、実際に市場に注文が出ます。
#   市場で約定した場合取り消せません。
# ==================================================
#
#

import urllib3
import datetime
import json
import os
import urllib.parse
from zoneinfo import ZoneInfo
import base64                   # ニュース取得用

# =========================================================================
# --- 設定項目（定数定義） ---
# =========================================================================
# コマンド用パラメーター -------------------    
P_CG = ''            # 取得したいカテゴリコードを１つ指定。未指定時は全て対象。100:QUICKニュース、110:ＡＩ市況状況速報、120:AI開示速報（決算関連）、129:ＡＩ開示速報（その他）
P_IS = ''            # 取得したい銘柄コードを１つ指定する。未指定時は全て対象。
P_DT_FROM = ''       # ニュース日付（YYYYMMDD）範囲指定（from）。
P_DT_TO = ''         # ニュース日付（YYYYMMDD）範囲指定（to）。 p_DT_FROM <= p_DT_TOで設定する。
P_REC_OFST = ''      # レコード取得位置（デフォルト＝０、直近先頭の意味）。
P_REC_LIMT = ''      # レコード取得件数最大（デフォルト＝１００）。1度に取得できる最大値は100。

FNAME_OUTPUT = 'news_header_' + P_IS + '.csv'   # 書き込むファイル名。カレントディレクトリに上書きモードでファイルが作成される。

# --- 共通設定項目 ------------------------------------------------------------
FNAME_URL_INFO = "file_url_info.txt"                # API接続情報ファイル
FNAME_PASSWD2 = "./.auth/file_pwd2.txt"              # 第二パスワード保存ファイル
FNAME_LOGIN_RESPONSE = "./.auth/file_login_response.txt"  # ログイン応答保存先
FNAME_INFO_P_NO = "file_info_p_no.txt"              # p_no保存ファイル

# --- 通信堅牢化のための設定項目 ---
API_TIMEOUT_SECONDS = 15.0  # タイムアウト時間（秒）: 応答がない場合15秒で切り上げる
MAX_RETRY_COUNT = 3         # 最大リトライ回数: 通信エラー時に自動再試行する回数
RETRY_INTERVAL_SECONDS = 5  # リトライ間隔（秒）: 再試行する前に待機する時間
# =========================================================================



# --- 共通ユーティリティ関数 ----------------------------------------------

def func_p_sd_date():
    """
    機能: システム時刻を"p_sd_date"の書式の文字列で返す。
    返値: "p_sd_date"の書式の文字列。 API規定書式 "YYYY.MM.DD-hh:mm:ss.sss"
    引数1: なし
    備考: 
        日本標準時（Japan Standard Time、JST）を利用のこと。
    """
    dt_now = datetime.datetime.now(
        # 日本標準時（Japan Standard Time、JST）を利用
        ZoneInfo("Asia/Tokyo")
    )
    # 年.月.日-時:分:秒 の部分を作成
    str_date = dt_now.strftime("%Y.%m.%d-%H:%M:%S")
    
    # マイクロ秒（6桁ゼロ埋め）から先頭の3桁を切り出してミリ秒を作成
    str_micro = f"{dt_now.microsecond:06d}"
    str_ms = str_micro[0:3]
    
    # ドットで結合してAPI規定書式を完成
    return str_date + "." + str_ms


def func_replace_urlencode(str_input):
    """
    URLエンコードを行う。

    URLでは、スペースや「&」「+」「?」などの記号が
    特別な意味を持つため、そのまま送信できない場合がある。
    そのため、これらの文字を「%xx」形式へ変換する。

    例:
        "A B+C" → "A%20B%2BC"

    本サンプルでは Python標準ライブラリの
    urllib.parse.quote() を利用してURLエンコードを行う。

    他言語へ移植する場合も、自前で変換処理を作成するのではなく、
    各言語が提供する標準のURLエンコード関数を利用することを推奨する。

    主な対応例:
        Python      : urllib.parse.quote()
        Java        : java.net.URLEncoder.encode()
        C#          : Uri.EscapeDataString()
        JavaScript  : encodeURIComponent()
        Go          : url.QueryEscape()

    Parameters
    ----------
    str_input : str
        URLエンコード対象文字列

    Returns
    -------
    str
        URLエンコード後の文字列
    """
    return urllib.parse.quote(str_input, safe='')


def func_read_from_file(str_fname):
    """ファイルから文字情報を一括読み込み（BOMを排除）"""
    str_read = ''
    try:
        # utf-8-sig を指定してBOMを自動的に排除しファイルを開く
        with open(str_fname, 'r', encoding='utf-8-sig') as fin:
            while True:
                line = fin.readline()
                if not line:
                    break
                str_read = str_read + line
        return str_read
    except IOError as e:
        print(f"[エラー] ファイルを読み込めません: {str_fname}")
        raise e


def func_write_to_file(str_fname_output, str_data):
    """ファイルに書き込み、権限を所有者のみ(600)に制限"""
    try:
        # 出力先フォルダの存在を確認し、存在しない場合は自動作成
        str_dir = os.path.dirname(str_fname_output)
        if str_dir and not os.path.exists(str_dir):
            os.makedirs(str_dir, exist_ok=True)

        # データをファイルへ書き込み
        with open(str_fname_output, 'w', encoding='utf-8') as fout:
            fout.write(str_data)
        
        # パーミッションを600（所有者のみ読み書き可能）に制限
        os.chmod(str_fname_output, 0o600)
    except IOError as e:
        print(f"[エラー] ファイルに書き込めません: {str_fname_output}")
        raise e


def func_get_url_info(fname):
    """
    file_url_info.txt からAPI接続設定を取得

    機能: API接続情報をファイルから取得し辞書型で返す
    引数1: 接続先情報を保存したファイル名: fname_url_info

    サポートへの問い合わせは、sJsonOfmt:'5'でお願いします。
    """
    str_url_info = func_read_from_file(fname)
    # JSON形式の文字列を辞書型で取り出す
    return  json.loads(str_url_info)    


def func_get_login_response(str_fname):
    '''
    ログインレスポンスを取得
    '''
    str_login_response = func_read_from_file(str_fname)
    dic_login_response = json.loads(str_login_response)
    return dic_login_response
    

def func_get_p_no(fname):
    """ 
    機能: p_noをファイルから取得する
    引数1: p_noを保存したファイル名（fname_info_p_no = "e_api_info_p_no.txt"）
    """
    str_p_no_info = func_read_from_file(fname)
    # JSON形式の文字列を辞書型で取り出す
    json_p_no_info = json.loads(str_p_no_info)
    int_p_no = int(json_p_no_info.get('p_no'))
    return int_p_no


def func_save_p_no(str_fname_output, int_p_no):
    """p_noを保存するためのJSONファイルを生成"""
    p_no_dict = {"p_no": str(int_p_no)}
    json_data = json.dumps(p_no_dict, indent=4)
    func_write_to_file(str_fname_output, json_data)
    print(f'現在の "p_no" を保存しました。 p_no = {int_p_no} -> {str_fname_output}')


def func_make_url_request_from_dic(
                                    auth_flg,       # ログインFlag。    login:true   login以外:false
                                    url_target,     # 接続先URL
                                    work_dic_req    # API要求項目
):
    '''
    API問合せ用完全URL（クエリパラメータ付）を作成
    
    ------------------------------------------------------------------

    APIの基本設計について

    本APIは、プログラミング初心者や非ITエンジニアの方にも
    利用しやすいよう、URLにJSON形式のパラメーターを付加して
    送信する独自方式を採用しています。

    一般的なWeb APIとは異なる構成ですが、
    HTTPヘッダーやPOSTデータなどの知識を最小限に
    抑えながら利用できることを重視しています。

    このため、本APIは、URLとJSON文字列を組み立てて
    送信するだけで利用でき、特別な知識を必要とせず、
    各種スクリプト言語からも実装しやすいことを
    優先した設計となっています。
    
    ------------------------------------------------------------------
    JSONをHTTPボディではなくURLに付加して送信します。
    詳細はAPIマニュアル参照。
    備考：
        サポートへの問い合わせを考慮し、項目ごとの改行とタブを入れてあります。
    '''
    str_url = url_target
    if auth_flg:
        str_url = urllib.parse.urljoin(str_url, 'auth/')
    json_param = json.dumps(work_dic_req, indent=4, ensure_ascii=False)
    return f"{str_url}?{json_param}"


def func_api_req(str_request_method, str_url): 
    """
    APIリクエストの送信と、Shift-JIS応答のデコード（リトライ・タイムアウト対応版）
    """
    # HTTP通信ライブラリ urllib3 を利用します。
    #
    # requests ライブラリでも同様の処理は可能ですが、
    # 本サンプルでは APIサーバーへの接続処理が分かりやすいよう、
    # より基本的な urllib3 を利用しています。
    #
    # 他言語へ移植する場合も、
    # 「HTTPクライアント生成 → リクエスト送信 → レスポンス受信」
    # の流れを対応するライブラリへ置き換えてください。

    print('--- 送信電文 -------------------------------------------')
    print(str_url)

    # 接続および読み込みのタイムアウト時間を設定
    timeout_config = urllib3.Timeout(connect=API_TIMEOUT_SECONDS, read=API_TIMEOUT_SECONDS)
    http = urllib3.PoolManager()
    
    response_data = None
    status_code = None

    # 最大試行回数に達するまで通信をリトライ
    for attempt in range(1, MAX_RETRY_COUNT + 1):
        try:
            # 2回目以降の試行（再接続）の前に、指定されたインターバル時間待機
            if attempt > 1:
                print(f"[{attempt}/{MAX_RETRY_COUNT} 回目] 再接続を試みます...（{RETRY_INTERVAL_SECONDS}秒待機）")
                time.sleep(RETRY_INTERVAL_SECONDS)

            req = http.request(str_request_method, str_url, timeout=timeout_config)
            status_code = req.status
            response_data = req.data
            break  # 正常に通信できた場合はループを抜ける

        except (TimeoutError, MaxRetryError) as ce:
            print(f"\n[警告] 通信エラーが発生しました (試行: {attempt}/{MAX_RETRY_COUNT})")
            print(f"エラー詳細: {ce}")
            
            # 最大リトライ回数を超えて失敗した場合はConnectionErrorを発生
            if attempt == MAX_RETRY_COUNT:
                raise ConnectionError(
                    f"APIサーバーへの接続に規定回数失敗しました。サーバーがメンテナンス中か、停止している可能性があります。\n"
                    f"設定されたタイムアウト時間: {API_TIMEOUT_SECONDS}秒"
                )
        except Exception as ex:
            print(f"\n[警告] 予期せぬネットワーク例外が発生しました: {ex}")
            if attempt == MAX_RETRY_COUNT:
                raise ex

    print(f"HTTP Status: {status_code}")

    # 受信した電文をShift-JISからUTF-8へデコード（不正なバイトは無視）
    str_response = response_data.decode("shift-jis", errors="ignore")
    print('--- 受信電文 -------------------------------------------')
    print(str_response[:2000])
    print('--------------------------------------------------------')

    return str_response


def func_api_request_from_dic(
                                flg_login,          # ログインFlag。    login:true   login以外:false
                                destination_url,    # 接続先URL。
                                                    #   ログイン時は、FNAME_URL_INFOから取得する接続先。
                                                    #   それ以外はログインレスポンスで指定される仮想URL。
                                dic_req_item        # API要求項目
):
    '''
    APIへの問い合わせを実行する。
    '''
    # URL文字列の作成
    str_url = func_make_url_request_from_dic(
                                                flg_login,          # ログインFlag。    login:true   login以外:false
                                                destination_url,    # 接続先URL
                                                dic_req_item        # API要求項目
    )

    # APIへの問い合わせ。
    # リクエストメソッドの指定('GET'、'POST'どちらでも動作します。)
    str_api_response = func_api_req('POST', str_url)

    # apiの返り値（JSON形式の文字列）を辞書型で取り出す
    dic_api_response = json.loads(str_api_response)
    
    return dic_api_response

# --- 共通ユーティリティ関数 ----------------------------------------------





# 'sCLMID:CLMMfdsGetNewsHead'の利用方法
#
# 接続に使う仮想url: master用仮想URL
#
# 資料
# API専用ページ
# ５．マニュアル 
# １．共通説明
# （３）ブラウザからの利用方法
# 別紙「ｅ支店・ＡＰＩ、ブラウザからの利用方法」参照 のリンクをクリック。
# エクセルファイル「api_web_access.xlsx」を取得し開く。
# 「ニュース」シートを選択。
# 「ｅ支店・ＡＰＩ（ｖ４ｒ４）、ブラウザからの利用方法・ニュース情報取得編」
# 
##２－１．追加機能一覧								
##  No	機能ID			概要
##  1	CLMMfdsGetNewsHead      ニュースヘッダー問合取得I/F、ニュース一覧を（ニュースを取得した）降順に取得する。
##  2	CLMMfdsGetNewsBody      ニュースボディー問合取得I/F、個別のニュース内容を取得する。
##  ※ニュース関連システムの仕様で取得情報．ニュースIDの降順（取得順に採番される仕様）にソートしたリストを取得する。								
##  よって、データとしてニュース日付、ニュース時刻を返すが、その順序はニュース関連システムの仕様で保証されない。								
##
##（１）ニュースヘッダー問合取得I/F																		
##	【要求】																			
##	No  項目	    設定値												
##	1   sCLMID      CLMMfdsGetNewsHead												
##	2   p_CG ※１    取得したいカテゴリコードを１つ指定する。未指定時は全て対象。												
##	                コード     説明									
##	                100     QUICKニュース									
##	                110     ＡＩ市況状況速報									
##	                120     AI開示速報（決算関連）									
##	                129	ＡＩ開示速報（その他）									
##																				
##	    p_IS ※１         取得したい銘柄コードを１つ指定する。未指定時は全て対象。												
##	    p_DT_FROM ※１    ニュース日付（YYYYMMDD）範囲指定（from）。												N≧fromで検索。
##	    p_DT_TO ※１      ニュース日付（YYYYMMDD）範囲指定（to）。												N≦toで検索。
##	    p_REC_OFST ※１   レコード取得位置（デフォルト＝０、直近先頭の意味）。												指定条件検索後の位置。
##	    p_REC_LIMT ※１   レコード取得件数最大（デフォルト＝１００）。												指定条件検索後の件数。
##	※１、該当項目はオプション項目で指定した項目についてAND条件でデータ取得を実行する。
#
#
##【応答】																				
##No 項目		設定値													
##1 sCLMID		CLMMfdsGetNewsHead													
##2 p_REC_MAX	        取得（検索した）レコード数。													
##3 aCLMMfdsNewsHead    取得（検索した）レコード情報リスト（配列）。													
##	1 p_ID      ニュースID（レコード毎にユニーク）。													
##	2 p_DT	    ニュース日付（YYYYMMDD）。													
##	3 p_TM	    ニュース時刻（HHMMSS）。													
##	4 p_CGL	    ニュースカテゴリリスト。複数設定時は「,」区切り。	※１
##	5 p_GNL	    ニュースジャンルリスト。複数設定時は「,」区切り。	※１
##	6 p_ISL	    ニュース関連銘柄コードリスト。複数設定時は「,」区切り。						
##	7 p_HDL	    ニュースヘッドライン（タイトル）。   ※２						
##※１、カテゴリ及びジャンルについては別紙「立花証券・ｅ支店・ＡＰＩ、EVENT I/F 利用方法、データ仕様」３．（５）NSを参照。																				
##※２、ShiftJIS 日本語コード文字列を BASE64 変換し設定。取得側で各デコード後利用する。																				

#
# 補足1
# p_HDL、p_TXは、元の文字列をパーセントエンコード(URLエンコード)してから、base64変換されている。
# 元の文字列に戻すためには、base64でデコードしてから、パーセントエンコードのデコードを行う。
#
# 補足2
# p_DT_FROM <= p_DT_TO で設定する。p_DT_FROM > p_DT_TO では取得できない。
#
# 補足3
# p_REC_LIMT の最大値は100。
#
# 注意
# ニュースヘッダーは、時間軸で降順に取得される。
# このため当日分の取得の場合、新しいニュースが配信されると、
# p_REC_OFST で指定する起点の位置が新しく配信されたニュース分だけ後方にずれていく。
# 100を超えるニュースヘッダーを重複と漏れが無いように取得するためには、
# p_ID（ニュースID）を利用したチェックが必要になる。


# --- 以上資料 --------------------------------------------------------





# 機能: ニュース用タイトル行を出力ファイルに書き込む
# 引数1: 出力ファイル名
# 備考: 指定ファイルを開き、１行目に項目コード、２行目に項目名を書き込む。
def func_write_news_header_title(str_fname_output):
    try:
        with open(str_fname_output, 'w', encoding = 'shift_jis') as fout:
            print('file open at w, "fout": ', str_fname_output )
            # 項目コード
            str_text_out = ''
            str_text_out = str_text_out + 'p_ID' + ','
            str_text_out = str_text_out + 'p_DT' + ','
            str_text_out = str_text_out + 'p_TM' + ','
            str_text_out = str_text_out + 'p_CGL' + ','
            str_text_out = str_text_out + 'p_GNL' + ','
            str_text_out = str_text_out + 'p_ISL' + ','
            str_text_out = str_text_out + 'p_HDL' + '\n'
            fout.write(str_text_out)     # １行目に列名を書き込む

            # 項目名
            str_text_out = ''
            str_text_out = str_text_out + 'ニュースID（レコード毎にユニーク）。' + ','
            str_text_out = str_text_out + 'ニュース日付（YYYYMMDD）' + ','
            str_text_out = str_text_out + 'ニュース時刻（HHMMSS）' + ','
            str_text_out = str_text_out + 'ニュースカテゴリリスト' + ','
            str_text_out = str_text_out + 'ニュースジャンルリスト' + ','
            str_text_out = str_text_out + 'ニュース関連銘柄コードリスト' + ','
            str_text_out = str_text_out + 'ニュースヘッドライン（タイトル）' + '\n'
            fout.write(str_text_out)     # 2行目に列名を書き込む

    except IOError as e:
        print('Can not Write!!!')
        print(type(e))





# 機能: ニュースヘッドライン（タイトル）、ニュースボディー（本文）をデコードする。
# 引数1: テキスト。string型。
# 備考:
# p_HDL、p_TXは、
# 元の文字列はcp932で、それをパーセントエンコード(URLエンコード)して、base64変換されている。
# 元の文字列に戻すためには、base64でデコードしてから、パーセントエンコードのデコードを行う。
#
# base64のデコード（base64.b64decode）は、引数の文字列をバイト型にしてから実行する。
# パーセントエンコード(URLエンコード)のデコード（urllib.parse.unquote）は、string型にしてから実行する。
# 
# デコードは、次の手順で行なう。
# string型で取得 →
#   byte型に変換 →
#       base64デコード: base64.b64decode() →
#           string型に変換 →
#               パーセントエンコードのデコード: urllib.parse.unquote()
def func_decode_base64_data(str_encoded_text):
    byte_base64_text = str_encoded_text.encode()        # string型のp_HDLをbyte型に変換
    byte_escape_text = base64.b64decode(byte_base64_text)  # base64でデコード。デコードされた文字列は、元のパーセントエンコード(URLエンコード)された文字列。
    str_escape_text = byte_escape_text.decode()         # urllib.parse.unquoteは引数がstring型。
    str_text = urllib.parse.unquote(
                                        str_escape_text, 
                                        encoding='cp932')   # urllib.parse.unquote の第1引数は、string型。
    return str_text




# 機能: 取得したニュースヘッダーを追記モードでファイルに書き込む
# 引数1: 出力ファイル名
# 引数2: 取得したニュースヘッダー（リスト型）
# 備考:
#   指定ファイルを開き、1〜2行目に取得する情報名を書き込み、3行目以降で取得した情報を書き込む。
#   v4r9対応バージョンから、保存をutf-8に変更しました。
def func_write_news_header_data(str_fname_output, list_return):
    try:
        with open(str_fname_output, 'a', encoding = 'utf-8') as fout:
            print('file open at a, "fout": ', str_fname_output )
            # 取得した情報から行データを作成し書き込む
            str_text_out = ''
            
            # ニュースヘッダーを取得できた場合。
            if list_return != None :
                for i in range(len(list_return)):
                    str_p_HDL = func_decode_base64_data(list_return[i].get('p_HDL'))
                    # 行データ作成
                    str_text_out = ''
                    str_text_out = str_text_out + list_return[i].get('p_ID') + ',' 
                    str_text_out = str_text_out + list_return[i].get('p_DT') + ','
                    str_text_out = str_text_out + list_return[i].get('p_TM') + ','
                    str_text_out = str_text_out + list_return[i].get('p_CGL') + ','
                    str_text_out = str_text_out + list_return[i].get('p_GNL') + ','
                    str_text_out = str_text_out + '"' + list_return[i].get('p_ISL') + '"' + ','
                    str_text_out = str_text_out + '"' + str_p_HDL + '"' +'\n'

                    fout.write(str_text_out)     # 処理済みのニュースヘッダーをファイルに書き込む
                    print(str_text_out)
                    print('----')
    
                print('取得件数 len(list_return):', len(list_return))
                    
            # ニュースヘッダーを取得できない場合。
            else :
                str_text_out = 'ニュースヘッダーを取得できません。\n'
                print(str_text_out)
            

    except IOError as e:
        print('Can not Write!!!')
        print(type(e))
        


    




    
# ======================================================================================================
# ==== プログラム始点 =================================================================================
# ======================================================================================================
# 必要な設定項目
# 取得したいカテゴリコード: P_CG     未指定時は全て対象。100:QUICKニュース、110:ＡＩ市況状況速報、120:AI開示速報（決算関連）、129:ＡＩ開示速報（その他）
# 取得したい銘柄コード: P_IS       未指定時は全て対象。
# ニュース日付（YYYYMMDD）範囲指定（from）: P_DT_FROM
# ニュース日付（YYYYMMDD）範囲指定（to）: P_DT_TO      p_DT_FROM <= p_DT_TOで設定する。
# レコード取得位置: P_REC_OFST   デフォルト＝０、直近先頭の意味。
# レコード取得件数最大: P_REC_LIMT     デフォルト＝100。1回に取得できる最大件数は100。
# 出力ファイル名: FNAME_OUTPUT  （デフォルトは、'news_header_[銘柄コード].csv'）

# ======================================================================================================
#     プログラム始点 
# ======================================================================================================
if __name__ == "__main__":

    # 表示形式を接続情報ファイルから読み込む。
    dic_url_info = func_get_url_info(FNAME_URL_INFO)
    str_sJsonOfmt = dic_url_info.get("sJsonOfmt")

    # ログイン応答を保存した「file_login_response.txt」から、仮想URLと口座情報を取得
    dic_login_property = func_get_login_response(FNAME_LOGIN_RESPONSE)

    # 現在（前回利用した）のp_noをファイルから取得する
    my_p_no = func_get_p_no(FNAME_INFO_P_NO)
    my_p_no = my_p_no + 1
    # 更新した"p_no"を保存する。
    func_save_p_no(FNAME_INFO_P_NO, my_p_no)
    
    print()
    print('-- ニュースヘッダー 取得  -------------------------------------------------------------')

    
    # API要求項目のセット
    # 機能: ニュースヘッダー取得
    # 備考: 引数4-9の項目で指定した項目についてAND条件でデータ取得を実行する。
    dic_req_item = {
        'p_no':                 str(my_p_no),
        'p_sd_date':            func_p_sd_date(),

        'sCLMID':               'CLMMfdsGetNewsHead',   # ニュースヘッダー問合取得
        'p_CG':                 P_CG,                   # カテゴリコード	対象カテゴリコードを１つ指定 
                                                        #       未指定時は全て対象。
                                                        #       コード  説明									
                                                        #	    100     QUICKニュース									
                                                        #	    110     ＡＩ市況状況速報									
                                                        #	    120     AI開示速報（決算関連）									
                                                        #	    129	    ＡＩ開示速報（その他）

        'p_IS':                 P_IS,                   # カテゴリコード	対象銘柄コードを１つ指定する
        'p_DT_FROM':            P_DT_FROM,	            # 日付（From)	ニュース日付（YYYYMMDD）範囲指定（from）
                                                        # N≧fromで検索

        'p_DT_TO':              P_DT_TO,	            # 日付（To）	ニュース日付（YYYYMMDD）範囲指定（to）
                                                        # N≦toで検索

        'p_REC_OFST':           P_REC_OFST,	            # レコード取得位置	レコード取得位置（デフォルト＝０、直近先頭の意味）
                                                        # 指定条件検索後の位置

        'p_REC_LIMT':           P_REC_LIMT,	            # レコード取得件数最大	レコード取得件数最大（デフォルト＝１００）
                                                        # 指定条件検索後の件数（最大１００）

        'sJsonOfmt':            str_sJsonOfmt           # 表示形式（サポートへの問い合わせでは'5'を指定指定した送信電文と受信電文で。）
    }

    # 'CLMMfdsGetNewsHead'は、仮想URL:'sUrlMaster'
    str_connection_url = dic_login_property.get('sUrlMaster')
    # API問い合わせ実行
    dic_return = func_api_request_from_dic(
                                                False,                  # ログインFlag。    login:true   login以外:false
                                                str_connection_url,     # 接続先URL。
                                                                        #    ログイン時は、FNAME_URL_INFOから取得する接続先。
                                                                        #   それ以外はログインレスポンスで指定される仮想URL。
                                                dic_req_item            # API要求項目
                                            )

    if dic_return is None:
        print('API接続自体の失敗')
        print('JSON形式の受信電文ではありません。接続先も含めて送信電文、受信電文を確認してください。')
    else:
        if dic_return.get('p_errno') != '-2' and dic_return.get('p_errno') != '2':
            # 出力ファイルにタイトル行を書き込む。
            func_write_news_header_title(FNAME_OUTPUT)
            
            # ニュースヘッダー部分をリスト型で抜き出す。
            my_list_return = dic_return.get('aCLMMfdsNewsHead')

            # 取得したニュースヘッダーを追記モードでファイルに書き込む。
            func_write_news_header_data(FNAME_OUTPUT, my_list_return)

        elif dic_return.get('p_errno') == '-2' :
            print()
            print('p_errno', dic_return.get('p_errno'))
            print('p_err', dic_return.get('p_err'))
            print("パラメーターの設定に誤りが有ります。")

        # 仮想URLが無効になっている場合
        # if dic_return.get('p_errno') == '2':
        else:
            print()
            print('p_errno', dic_return.get('p_errno'))
            print('p_err', dic_return.get('p_err'))
            print("仮想URLが有効ではありません。")
            print("e_api_login_pubkey.py")
            print("の実行を再度行い、新しく仮想URL（1日券）を取得してください。")
                    
    print()    
    print()
    # 最終の'p_no'を保存する。
    func_save_p_no(FNAME_INFO_P_NO, my_p_no)