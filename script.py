from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import textwrap
import json
import os
import io
import gspread
from google.oauth2.service_account import Credentials
import requests

#st.title("体験会用コメントシート")
st.set_page_config(page_title="体験会コメントシートメーカー")
st.title("体験会コメントシートメーカー")


DEFAULT_BOOKS = ['たんぽぽのぽんちゃん', 'ぼくエスカレーター', 'グルメなペリカン']
DEFAULT_CREWS = ['Zen', 'Cory']

# 絵本: タイトル, 作者, あらすじ, 画像URL
# クルー: 名前, 写真URL, 好きな絵本
def _book_dict(title, author="", summary="", image_url=""):
    return {"title": title, "author": author, "summary": summary, "image_url": image_url or ""}


def _crew_dict(name, photo_url="", favorite_book=""):
    return {"name": name, "photo_url": photo_url or "", "favorite_book": favorite_book or ""}


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


def load_books_from_sheet(client) -> list:
    """絵本一覧を読み込み。1列ならタイトルのみ、4列ならタイトル・作者・あらすじ・画像URL"""
    spreadsheet_id = os.getenv(CONFIG_SPREADSHEET_ID_ENV)
    if not client or not spreadsheet_id:
        return [_book_dict(t) for t in DEFAULT_BOOKS]

    try:
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet(BOOKS_SHEET_NAME)
        rows = ws.get_all_values()
    except Exception:
        return [_book_dict(t) for t in DEFAULT_BOOKS]

    if not rows:
        return [_book_dict(t) for t in DEFAULT_BOOKS]

    out = []
    for row in rows:
        row = [str(c).strip() for c in row]
        if not row or not row[0]:
            continue
        title = row[0]
        author = row[1] if len(row) > 1 else ""
        summary = row[2] if len(row) > 2 else ""
        image_url = row[3] if len(row) > 3 else ""
        out.append(_book_dict(title, author, summary, image_url))

    return out or [_book_dict(t) for t in DEFAULT_BOOKS]


def load_crews_from_sheet(client) -> list:
    """クルー一覧を読み込み。1列なら名前のみ、3列なら名前・写真URL・好きな絵本"""
    spreadsheet_id = os.getenv(CONFIG_SPREADSHEET_ID_ENV)
    if not client or not spreadsheet_id:
        return [_crew_dict(n) for n in DEFAULT_CREWS]

    try:
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet(CREWS_SHEET_NAME)
        rows = ws.get_all_values()
    except Exception:
        return [_crew_dict(n) for n in DEFAULT_CREWS]

    if not rows:
        return [_crew_dict(n) for n in DEFAULT_CREWS]

    out = []
    for row in rows:
        row = [str(c).strip() for c in row]
        if not row or not row[0]:
            continue
        name = row[0]
        photo_url = row[1] if len(row) > 1 else ""
        favorite_book = row[2] if len(row) > 2 else ""
        out.append(_crew_dict(name, photo_url, favorite_book))

    return out or [_crew_dict(n) for n in DEFAULT_CREWS]


def save_books_to_sheet(client, books: list) -> None:
    if not client or not os.getenv(CONFIG_SPREADSHEET_ID_ENV):
        return
    try:
        sh = client.open_by_key(os.getenv(CONFIG_SPREADSHEET_ID_ENV))
        try:
            ws = sh.worksheet(BOOKS_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=BOOKS_SHEET_NAME, rows="200", cols="4")
        ws.clear()
        if books:
            ws.update("A1", [[b["title"], b["author"], b["summary"], b["image_url"]] for b in books])
    except Exception:
        pass


def save_crews_to_sheet(client, crews: list) -> None:
    if not client or not os.getenv(CONFIG_SPREADSHEET_ID_ENV):
        return
    try:
        sh = client.open_by_key(os.getenv(CONFIG_SPREADSHEET_ID_ENV))
        try:
            ws = sh.worksheet(CREWS_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=CREWS_SHEET_NAME, rows="200", cols="3")
        ws.clear()
        if crews:
            ws.update("A1", [[c["name"], c["photo_url"], c["favorite_book"]] for c in crews)
    except Exception:
        pass


def open_template_image(book: dict, crew_name: str) -> Image.Image:
    """絵本の画像URLがあればURLから読み、なければ既存の (絵本, クルー) マッピングで Assets を使用"""
    title = book.get("title", "")
    image_url = (book.get("image_url") or "").strip()

    if image_url:
        try:
            r = requests.get(image_url, timeout=10)
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            pass

    # 既存マッピング（Assets）
    if title == "たんぽぽのぽんちゃん" and crew_name == "Cory":
        return Image.open("Assets/1.jpg")
    if title == "たんぽぽのぽんちゃん" and crew_name == "Zen":
        return Image.open("Assets/3.jpg")
    if title == "ぼくエスカレーター" and crew_name == "Cory":
        return Image.open("Assets/2.jpg")
    if title == "ぼくエスカレーター" and crew_name == "Zen":
        return Image.open("Assets/4.jpg")
    if title == "グルメなペリカン" and crew_name == "Cory":
        return Image.open("Assets/5.jpg")
    return Image.open("Assets/6.jpg")


gclient = get_gspread_client()
books = load_books_from_sheet(gclient)
crews = load_crews_from_sheet(gclient)
book_titles = [b["title"] for b in books]
crew_names = [c["name"] for c in crews]


# 管理モード（絵本・クルーの編集）
with st.sidebar.expander("管理モード（絵本・クルーの編集）"):
    admin_tab = st.radio("編集したい項目", ["絵本", "クルー"], horizontal=True)

    if not gclient or not os.getenv(CONFIG_SPREADSHEET_ID_ENV):
        st.warning(
            "Googleスプレッドシート連携が未設定のため、この編集内容はサーバー再起動時に失われる可能性があります。Render の「Environment」で GOOGLE_SERVICE_ACCOUNT_JSON と CONFIG_SPREADSHEET_ID を設定してください。",
            icon="⚠️",
        )

    if admin_tab == "絵本":
        st.caption("絵本登録：タイトル・作者・あらすじ・画像URLを入力してください。")
        with st.form("add_book_form"):
            new_title = st.text_input("タイトル*")
            new_author = st.text_input("作者")
            new_summary = st.text_area("あらすじ")
            new_image_url = st.text_input("画像URL（テンプレート用。未入力なら既存テンプレを使用）")
            if st.form_submit_button("絵本を追加"):
                new_title = new_title.strip()
                if new_title and not any(b["title"] == new_title for b in books):
                    books.append(_book_dict(new_title, new_author.strip(), new_summary.strip(), new_image_url.strip()))
                    save_books_to_sheet(gclient, books)
                    st.success(f"「{new_title}」を追加しました。")
                    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()
                elif new_title and any(b["title"] == new_title for b in books):
                    st.info("すでに同じタイトルの絵本があります。")

        if books:
            remove_title = st.selectbox("削除する絵本を選択", book_titles)
            if st.button("選択した絵本を削除"):
                if remove_title in DEFAULT_BOOKS and len(books) <= len(DEFAULT_BOOKS):
                    st.warning("初期の絵本のみの状態には削除できません。")
                else:
                    books = [b for b in books if b["title"] != remove_title]
                    save_books_to_sheet(gclient, books)
                    st.success(f"「{remove_title}」を削除しました。")
                    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()

    else:  # クルー
        st.caption("クルー登録：名前・写真URL・好きな絵本を入力してください。")
        with st.form("add_crew_form"):
            new_name = st.text_input("名前*")
            new_photo_url = st.text_input("写真URL")
            new_favorite_book = st.selectbox("好きな絵本", [""] + book_titles)
            if st.form_submit_button("クルーを追加"):
                new_name = new_name.strip()
                if new_name and not any(c["name"] == new_name for c in crews):
                    crews.append(_crew_dict(new_name, new_photo_url.strip(), new_favorite_book))
                    save_crews_to_sheet(gclient, crews)
                    st.success(f"「{new_name}」を追加しました。")
                    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()
                elif new_name and any(c["name"] == new_name for c in crews):
                    st.info("すでに同じ名前のクルーがあります。")

        if crews:
            remove_name = st.selectbox("削除するクルーを選択", crew_names)
            if st.button("選択したクルーを削除"):
                if remove_name in DEFAULT_CREWS and len(crews) <= len(DEFAULT_CREWS):
                    st.warning("初期のクルーのみの状態には削除できません。")
                else:
                    crews = [c for c in crews if c["name"] != remove_name]
                    save_crews_to_sheet(gclient, crews)
                    st.success(f"「{remove_name}」を削除しました。")
                    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()


# 本番UI用に再取得（管理モードで変更した場合）
books = load_books_from_sheet(gclient)
crews = load_crews_from_sheet(gclient)
book_titles = [b["title"] for b in books]
crew_names = [c["name"] for c in crews]

book = st.selectbox("どの絵本ですか？", book_titles)
crew = st.selectbox("読み手は誰ですか?", crew_names)
upload_image = st.file_uploader("画像をアップロードしてください", type=["jpg", "jpeg", "png"])
name = st.text_input("こどものなまえ(〇〇ちゃん/くん)")
comment = st.text_area("コメント(難しい漢字は表示されないよ！)")

if upload_image is not None:
    if st.button("実行"):
        book_obj = next((b for b in books if b["title"] == book), books[0])
        img = open_template_image(book_obj, crew)

        ss_image = Image.open(upload_image).convert("RGBA")

        if ss_image is not None and name != "" and comment != "":
            width = 1050
            height = int(ss_image.size[1] * (width / ss_image.size[0]))
            ss_image = ss_image.resize((width, height))
            img.paste(ss_image, (192, 1638), ss_image)

            draw = ImageDraw.Draw(img)
            font_name = ImageFont.truetype("Assets/b.ttc", 90)
            draw.text((1820, 300), name, fill=("white"), font=font_name)

            wrap_list = textwrap.wrap(comment, 22)
            font_comment = ImageFont.truetype("Assets/c.otf", 90)
            line_counter = 0
            for line in wrap_list:
                y = line_counter * 100 + 2734
                draw.multiline_text((313, y), line, fill=("black"), font=font_comment)
                line_counter = line_counter + 1

            filename = "line_followup.txt"
            with open(filename) as file:
                line_text = file.read()
            line_text = line_text.format(name)

            img.save("result.jpg", quality=100)
            with open("result.jpg", "rb") as file:
                btn = st.download_button(
                    label="画像をダウンロード",
                    data=file,
                    file_name="comment_" + name + ".jpg",
                    mime="image/jpeg",
                )

            st.image("result.jpg")
            st.subheader("LINE用フォローアップ")
            st.code(line_text)

        else:
            st.warning("コメントと名前を記入してから実行してください！", icon="⚠️")
