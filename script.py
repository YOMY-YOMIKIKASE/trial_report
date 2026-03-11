from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import textwrap
import json
import os
import io
import base64
import gspread
from google.oauth2.service_account import Credentials
import requests

st.set_page_config(page_title="体験会コメントシートメーカー")
st.title("体験会コメントシートメーカー")

DEFAULT_BOOKS = ['たんぽぽのぽんちゃん', 'ぼくエスカレーター', 'グルメなペリカン']
DEFAULT_CREWS = ['Zen', 'Cory']

GOOGLE_SERVICE_ACCOUNT_JSON_ENV = "GOOGLE_SERVICE_ACCOUNT_JSON"
GOOGLE_SERVICE_ACCOUNT_FILE = "service_account.json"
CONFIG_SPREADSHEET_ID_ENV = "CONFIG_SPREADSHEET_ID"
BOOKS_SHEET_NAME = "books"
CREWS_SHEET_NAME = "crews"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _book_dict(title, author="", summary="", image_url=""):
    return {"title": title, "author": author, "summary": summary, "image_url": image_url or ""}


def _crew_dict(name, photo_url="", favorite_book=""):
    return {"name": name, "photo_url": photo_url or "", "favorite_book": favorite_book or ""}


def _build_credentials():
    """サービスアカウント Credentials オブジェクトを生成。
    Streamlit Secrets (TOML dict または JSON文字列) → 環境変数 → ローカルファイルの順で試みる。"""
    # Streamlit Secrets から取得（TOML dict形式 or JSON文字列形式）
    try:
        val = st.secrets[GOOGLE_SERVICE_ACCOUNT_JSON_ENV]
        if val:
            info = dict(val) if not isinstance(val, str) else json.loads(val)
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass

    # 環境変数から取得（JSON文字列）
    info_json = os.getenv(GOOGLE_SERVICE_ACCOUNT_JSON_ENV)
    if info_json:
        try:
            return Credentials.from_service_account_info(json.loads(info_json), scopes=SCOPES)
        except Exception:
            pass

    # ローカルファイルから取得
    if os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        try:
            return Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        except Exception:
            pass

    return None


def get_spreadsheet_id():
    """スプレッドシートIDをStreamlit Secrets または環境変数から取得"""
    try:
        return str(st.secrets[CONFIG_SPREADSHEET_ID_ENV])
    except Exception:
        return os.getenv(CONFIG_SPREADSHEET_ID_ENV)


def get_gspread_client():
    creds = _build_credentials()
    if creds is None:
        return None
    try:
        return gspread.authorize(creds)
    except Exception:
        return None


def upload_image_to_drive(file_bytes, filename, mimetype="image/jpeg", use_base64_fallback=False):
    """Google Drive に画像をアップロードし、公開URLを返す。
    use_base64_fallback=True の場合、Drive APIが使えない時はbase64データURLにフォールバックする（クルー写真向け）。"""
    creds = _build_credentials()
    drive_error = None

    if creds is not None:
        try:
            import google.auth.transport.requests as ga_requests
            creds.refresh(ga_requests.Request())
            access_token = creds.token

            boundary = "yomy_upload_boundary"
            metadata = json.dumps({"name": filename}).encode("utf-8")
            body = (
                f"--{boundary}\r\n".encode()
                + b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                + metadata + b"\r\n"
                + f"--{boundary}\r\n".encode()
                + f"Content-Type: {mimetype}\r\n\r\n".encode()
                + file_bytes
                + f"\r\n--{boundary}--".encode()
            )
            headers = {"Authorization": f"Bearer {access_token}"}
            r = requests.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id",
                headers={**headers, "Content-Type": f"multipart/related; boundary={boundary}"},
                data=body,
                timeout=30,
            )
            r.raise_for_status()
            file_id = r.json()["id"]

            # 誰でも閲覧できるように公開設定
            requests.post(
                f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
                headers={**headers, "Content-Type": "application/json"},
                json={"type": "anyone", "role": "reader"},
                timeout=10,
            ).raise_for_status()

            return f"https://drive.google.com/uc?id={file_id}"
        except Exception as e:
            drive_error = e
    else:
        drive_error = "サービスアカウントの認証情報が設定されていません"

    # base64フォールバック（クルー写真など小サイズ画像向け）
    if use_base64_fallback:
        st.info(
            "⚠️ Google Drive APIが有効化されていないため、画像を小さくしてスプレッドシートに保存します。\n\n"
            "高画質で保存したい場合は、Google Cloud Consoleで **Drive API** を有効化してください:\n"
            "https://console.cloud.google.com/apis/library/drive.googleapis.com"
        )
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.thumbnail((150, 150), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=55)
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded}"
        except Exception as e2:
            st.warning(f"画像の変換に失敗しました: {e2}")
            return None

    st.warning(
        f"画像のDriveアップロードに失敗しました: {drive_error}\n\n"
        "**原因**: Google Drive APIが有効化されていない可能性があります。\n"
        "Google Cloud Consoleで Drive API を有効化してください:\n"
        "https://console.cloud.google.com/apis/library/drive.googleapis.com"
    )
    return None


def load_books_from_sheet(client) -> list:
    spreadsheet_id = get_spreadsheet_id()
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
    spreadsheet_id = get_spreadsheet_id()
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
    spreadsheet_id = get_spreadsheet_id()
    if not client or not spreadsheet_id:
        return
    try:
        sh = client.open_by_key(spreadsheet_id)
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
    spreadsheet_id = get_spreadsheet_id()
    if not client or not spreadsheet_id:
        return
    try:
        sh = client.open_by_key(spreadsheet_id)
        try:
            ws = sh.worksheet(CREWS_SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=CREWS_SHEET_NAME, rows="200", cols="3")
        ws.clear()
        if crews:
            ws.update("A1", [[c["name"], c["photo_url"], c["favorite_book"]] for c in crews])
    except Exception:
        pass


def open_template_image(book: dict, crew_name: str) -> Image.Image:
    title = book.get("title", "")
    image_url = (book.get("image_url") or "").strip()
    if image_url:
        if image_url.startswith("data:"):
            try:
                _, b64data = image_url.split(",", 1)
                img_bytes = base64.b64decode(b64data)
                return Image.open(io.BytesIO(img_bytes)).convert("RGB")
            except Exception:
                pass
        else:
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


# ─── 初期データ読み込み ───────────────────────────────────────────────────────
gclient = get_gspread_client()
books = load_books_from_sheet(gclient)
crews = load_crews_from_sheet(gclient)
book_titles = [b["title"] for b in books]
crew_names = [c["name"] for c in crews]

# ─── 管理モード ───────────────────────────────────────────────────────────────
with st.sidebar.expander("管理モード（絵本・クルーの編集）"):
    admin_tab = st.radio("編集したい項目", ["絵本", "クルー"], horizontal=True)

    if not gclient or not get_spreadsheet_id():
        st.warning(
            "Googleスプレッドシート連携が未設定のため、編集内容はサーバー再起動時に失われます。\n\n"
            "**Streamlit Cloud の場合**: アプリの Settings → Secrets に以下を設定してください:\n"
            "- `GOOGLE_SERVICE_ACCOUNT_JSON`\n"
            "- `CONFIG_SPREADSHEET_ID`\n\n"
            "**Render の場合**: Environment Variables で同じキーを設定してください。",
            icon="⚠️",
        )

    if admin_tab == "絵本":
        st.caption("絵本登録：タイトル・作者・あらすじ・テンプレート画像を入力してください。")
        with st.form("add_book_form"):
            new_title = st.text_input("タイトル*")
            new_author = st.text_input("作者")
            new_summary = st.text_area("あらすじ")
            new_image_file = st.file_uploader(
                "テンプレート画像（ドラッグ＆ドロップ可）",
                type=["jpg", "jpeg", "png"],
                key="book_image_upload",
            )
            if st.form_submit_button("絵本を追加"):
                new_title = new_title.strip()
                if new_title and not any(b["title"] == new_title for b in books):
                    # 画像をGoogle Driveにアップロード
                    image_url = ""
                    if new_image_file is not None:
                        with st.spinner("画像をアップロード中..."):
                            uploaded_url = upload_image_to_drive(
                                new_image_file.read(),
                                new_image_file.name,
                                new_image_file.type or "image/jpeg",
                            )
                        if uploaded_url:
                            image_url = uploaded_url
                        else:
                            st.warning("画像のアップロードに失敗しました。スプレッドシート連携を確認してください。")
                    books.append(_book_dict(new_title, new_author.strip(), new_summary.strip(), image_url))
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
        st.caption("クルー登録：名前・写真・好きな絵本を入力してください。")
        with st.form("add_crew_form"):
            new_name = st.text_input("名前*")
            new_photo_file = st.file_uploader(
                "写真（ドラッグ＆ドロップ可）",
                type=["jpg", "jpeg", "png"],
                key="crew_photo_upload",
            )
            new_favorite_book = st.selectbox("好きな絵本", [""] + book_titles)
            if st.form_submit_button("クルーを追加"):
                new_name = new_name.strip()
                if new_name and not any(c["name"] == new_name for c in crews):
                    # 写真をGoogle Driveにアップロード
                    photo_url = ""
                    if new_photo_file is not None:
                        with st.spinner("写真をアップロード中..."):
                            uploaded_url = upload_image_to_drive(
                                new_photo_file.read(),
                                new_photo_file.name,
                                new_photo_file.type or "image/jpeg",
                                use_base64_fallback=True,
                            )
                        if uploaded_url:
                            photo_url = uploaded_url
                        else:
                            st.warning("写真のアップロードに失敗しました。")
                    crews.append(_crew_dict(new_name, photo_url, new_favorite_book))
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

# ─── 本番UI用に再取得 ─────────────────────────────────────────────────────────
books = load_books_from_sheet(gclient)
crews = load_crews_from_sheet(gclient)
book_titles = [b["title"] for b in books]
crew_names = [c["name"] for c in crews]

# ─── メインUI ─────────────────────────────────────────────────────────────────
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
