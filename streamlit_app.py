import streamlit as st
import sys
import os
import traceback

# srcディレクトリをPythonパスに追加
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# エラーハンドリングの改善
try:
    from src.utils.text_processing import process_text_file
    from src.services.pinecone_service import PineconeService
    from src.components.file_upload import render_file_upload
    from src.components.chat import render_chat
    from src.components.settings import render_settings
    #from src.components.agent import render_agent
    from src.components.property_upload import render_property_upload
    from src.config.settings import DEFAULT_SYSTEM_PROMPT, DEFAULT_RESPONSE_TEMPLATE
    from langsmith import Client
    from langchain.callbacks.tracers import LangChainTracer
    from langchain.callbacks.manager import CallbackManager
except ImportError as e:
    st.error(f"モジュールのインポートに失敗しました: {str(e)}")
    st.error(f"詳細: {traceback.format_exc()}")
    st.stop()

# LangSmithの設定
try:
    client = Client()
    tracer = LangChainTracer()
    callback_manager = CallbackManager([tracer])
except Exception as e:
    st.warning(f"LangSmithの初期化に失敗しました: {str(e)}")
    callback_manager = None

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
if "response_template" not in st.session_state:
    st.session_state.response_template = DEFAULT_RESPONSE_TEMPLATE

# Pineconeサービスの初期化
pinecone_service = None
try:
    pinecone_service = PineconeService()
    # インデックスの状態を確認
    stats = pinecone_service.get_index_stats()
    if stats['total_vector_count'] == 0:
        st.info("データベースは空です。物件情報を登録してください。")
    else:
        st.write(f"データベースの状態: {stats['total_vector_count']}件のドキュメント")
except Exception as e:
    st.error(f"Pineconeサービスの初期化に失敗しました: {str(e)}")
    st.error("APIキーとインデックス名を確認してください。")
    st.error(f"詳細エラー: {traceback.format_exc()}")
    # サービスが利用できない場合でもアプリは起動する
    pinecone_service = None

def read_file_content(file) -> str:
    """ファイルの内容を適切なエンコーディングで読み込む"""
    encodings = ['utf-8', 'shift-jis', 'cp932', 'euc-jp']
    content = file.getvalue()
    
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    raise ValueError("ファイルのエンコーディングを特定できませんでした。UTF-8、Shift-JIS、CP932、EUC-JPのいずれかで保存されているファイルをアップロードしてください。")

def main():
    try:
        # Pineconeサービスが利用できない場合の警告
        if pinecone_service is None:
            st.warning("⚠️ Pineconeサービスが利用できません。一部の機能が制限されます。")
            st.info("設定画面でAPIキーとインデックス名を確認してください。")
        
        # サイドバーにメニューを配置
        with st.sidebar:
            st.title("管理者メニュー")
            page = st.radio(
                "機能を選択",
                ["チャット", "物件情報登録", "ファイルアップロード", "設定"],
                index={
                    "chat": 0,
                    "property": 1,
                    "upload": 2,
                    "settings": 3
                }[st.session_state.current_page]
            )
            st.session_state.current_page = {
                "チャット": "chat",
                "物件情報登録": "property",
                "ファイルアップロード": "upload",
                "設定": "settings"
            }[page]

        # メインコンテンツの表示
        if st.session_state.current_page == "chat":
            if pinecone_service:
                render_chat(pinecone_service)
            else:
                st.error("チャット機能はPineconeサービスが必要です。")
        elif st.session_state.current_page == "property":
            if pinecone_service:
                render_property_upload(pinecone_service)
            else:
                st.error("物件情報登録機能はPineconeサービスが必要です。")
        elif st.session_state.current_page == "upload":
            if pinecone_service:
                render_file_upload(pinecone_service)
            else:
                st.error("ファイルアップロード機能はPineconeサービスが必要です。")
        else:
            if pinecone_service:
                render_settings(pinecone_service)
            else:
                st.error("設定機能はPineconeサービスが必要です。")
    except Exception as e:
        st.error(f"アプリケーションでエラーが発生しました: {str(e)}")
        st.error(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
