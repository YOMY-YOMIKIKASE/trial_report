from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import textwrap
import json
import os
import gspread
from google.oauth2.service_account import Credentials

#st.title("体験会用コメントシート")
st.set_page_config(page_title="体験会コメントシートメーカー")
st.title("体験会コメントシートメーカー")


DEFAULT_BOOKS = ['たんぽぽのぽんちゃん', 'ぼくエスカレーター', 'グルメなペリカン']
DEFAULT_CREWS = ['Zen', 'Cory']

GOOGLE_SERVICE_ACCOUNT_JSON_ENV = "GOOGLE_SERVICE_ACCOUNT_JSON"
GOOGLE_SERVICE_ACCOUNT_FILE = "service_account.json"
CONFIG_SPREADSHEET_ID_ENV = "CONFIG_SPREADSHEET_ID"
BOOKS_SHEET_NAME = "books"
CREWS_SHEET_NAME = "crews"


def get_gspread_client():
    """サービスアカウントから gspread クライアントを作成"""
    info_json = os.getenv(GOOGLE_SERVICE_ACCOUNT_JSON_ENV)
    credentials = None

    if info_json:
        try:
            info = json.loads(info_json)
            credentials = Credentials.from_service_account_info(
                info,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
        except Exception:
            credentials = None

    if credentials is None and os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        try:
            credentials = Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
        except Exception:
            credentials = None

    if credentials is None:
        return None

    try:
        return gspread.authorize(credentials)
    except Exception:
        return None


def load_list_from_sheet(client, sheet_name: str, default: list[str]) -> list[str]:
    spreadsheet_id = os.getenv(CONFIG_SPREADSHEET_ID_ENV)
    if not client or not spreadsheet_id:
        return default

    try:
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet(sheet_name)
        values = ws.col_values(1)
        cleaned = [v.strip() for v in values if v.strip()]
        return cleaned or default
    except Exception:
        return default


def save_list_to_sheet(client, sheet_name: str, values: list[str]) -> None:
    spreadsheet_id = os.getenv(CONFIG_SPREADSHEET_ID_ENV)
    if not client or not spreadsheet_id:
        return

    try:
        sh = client.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_name, rows="100", cols="2")

        # 既存内容をクリアしてから書き込み
        ws.clear()
        if values:
            ws.update("A1", [[v] for v in values])
    except Exception:
        # 永続化に失敗してもアプリ本体は止めない
        pass


gclient = get_gspread_client()

# 設定シートから絵本・クルーのリストを読み込み（失敗したらデフォルト）
books = load_list_from_sheet(gclient, BOOKS_SHEET_NAME, DEFAULT_BOOKS)
crews = load_list_from_sheet(gclient, CREWS_SHEET_NAME, DEFAULT_CREWS)


# 管理用の簡易モード（アプリ内で絵本・クルーを追加/削除）
with st.sidebar.expander("管理モード（絵本・クルーの編集）"):
    admin_tab = st.radio("編集したい項目", ["絵本", "クルー"], horizontal=True)

    if not gclient or not os.getenv(CONFIG_SPREADSHEET_ID_ENV):
        st.warning(
            "Googleスプレッドシート連携が未設定のため、この編集内容はサーバー再起動時に失われる可能性があります。",
            icon="⚠️",
        )

    if admin_tab == "絵本":
        st.caption("※ ここで追加・削除した絵本は、上部のセレクトボックスに反映されます。")
        new_book = st.text_input("絵本名を追加")
        if st.button("絵本を追加"):
            new_book = new_book.strip()
            if new_book and new_book not in books:
                books.append(new_book)
                save_list_to_sheet(gclient, BOOKS_SHEET_NAME, books)
                st.success(f"「{new_book}」を追加しました。")
            elif new_book in books:
                st.info("すでに同じ名前の絵本があります。")

        if books:
            remove_book = st.selectbox("削除する絵本を選択", books)
            if st.button("選択した絵本を削除"):
                if remove_book in DEFAULT_BOOKS and len(books) <= len(DEFAULT_BOOKS):
                    st.warning("初期の絵本のみの状態には削除できません。")
                else:
                    books = [b for b in books if b != remove_book]
                    save_list_to_sheet(gclient, BOOKS_SHEET_NAME, books)
                    st.success(f"「{remove_book}」を削除しました。")

    else:  # クルー
        st.caption("※ ここで追加・削除したクルーは、上部のセレクトボックスに反映されます。")
        new_crew = st.text_input("クルー名を追加")
        if st.button("クルーを追加"):
            new_crew = new_crew.strip()
            if new_crew and new_crew not in crews:
                crews.append(new_crew)
                save_list_to_sheet(gclient, CREWS_SHEET_NAME, crews)
                st.success(f"「{new_crew}」を追加しました。")
            elif new_crew in crews:
                st.info("すでに同じ名前のクルーがあります。")

        if crews:
            remove_crew = st.selectbox("削除するクルーを選択", crews)
            if st.button("選択したクルーを削除"):
                if remove_crew in DEFAULT_CREWS and len(crews) <= len(DEFAULT_CREWS):
                    st.warning("初期のクルーのみの状態には削除できません。")
                else:
                    crews = [c for c in crews if c != remove_crew]
                    save_list_to_sheet(gclient, CREWS_SHEET_NAME, crews)
                    st.success(f"「{remove_crew}」を削除しました。")


book = st.selectbox(
    'どの絵本ですか？',
    books,
)

crew = st.selectbox(
    '読み手は誰ですか?',
    crews,
)
upload_image = st.file_uploader("画像をアップロードしてください", type=["jpg", "jpeg", "png"])
name = st.text_input("こどものなまえ(〇〇ちゃん/くん)")
comment = st.text_area("コメント(難しい漢字は表示されないよ！)")

if upload_image is not None:

    if st.button("実行"):

        if book == "たんぽぽのぽんちゃん" and crew =="Cory":
            img = Image.open("Assets/1.jpg")
        elif book == "たんぽぽのぽんちゃん" and crew =="Zen":
            img = Image.open("Assets/3.jpg")
        elif book == "ぼくエスカレーター" and crew == "Cory":
            img = Image.open("Assets/2.jpg")
        elif book == "ぼくエスカレーター" and crew == "Zen":
            img = Image.open("Assets/4.jpg") 
        elif book == "グルメなペリカン" and crew == "Cory":
            img = Image.open("Assets/5.jpg") 
        else:
            img = Image.open("Assets/6.jpg") 




        ss_image = Image.open(upload_image).convert('RGBA')

        if ss_image is not None and name != "" and comment !="":
            # 画像を開く

            width = 1050 # 指定したい画像の幅
            height = int(ss_image.size[1] * (width / ss_image.size[0]))
            ss_image = ss_image.resize((width, height))
            img.paste(ss_image, (192, 1638), ss_image)

            # テキストを描画する
            draw = ImageDraw.Draw(img)
            font_name = ImageFont.truetype("Assets/b.ttc", 90) # フォントとサイズを指定する
            draw.text((1820, 300), name, fill=("white"), font=font_name)

            wrap_list = textwrap.wrap(comment, 22)  
            font_comment = ImageFont.truetype("Assets/c.otf", 90) # フォントとサイズを指定する
            line_counter = 0

            for line in wrap_list:
                y = line_counter*100+2734
                draw.multiline_text((313, y), line, fill=("black"), font=font_comment)
                line_counter = line_counter +1

            filename = 'line_followup.txt'  # 読み込むファイル名を指定する

# ファイルを読み込んで、文章全体を1つの変数に格納する
            with open(filename) as file:
                line_text = file.read()

            line_text = line_text.format(name)

            # 画像を保存する
            img.save("result.jpg", quality=100)
            with open("result.jpg", "rb") as file:
                btn = st.download_button(
                label="画像をダウンロード",
                data=file,
                file_name="comment_"+name+".jpg",
                mime="image/ipg"
            )
            
            st.image("result.jpg")
            st.subheader("LINE用フォローアップ")
            st.code('', line_text)

        else:
            st.warning('コメントと名前を記入してから実行してください！', icon="⚠️")