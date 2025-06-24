import streamlit as st
from src.utils.text_processing import process_text_file
from src.services.pinecone_service import PineconeService
from src.services.category_classifier import CategoryClassifier
from src.services.response_templates import QuestionExampleGenerator
from src.config.settings import METADATA_CATEGORIES
from datetime import datetime
import pandas as pd
import json
import traceback
import io
import re
from typing import List, Dict, Any

def read_file_content(file) -> str:
    """ファイルの内容を適切なエンコーディングで読み込む"""
    encodings = ['utf-8', 'shift-jis', 'cp932', 'euc-jp']
    content = file.getvalue()
    
    for encoding in encodings:
        try:
            # バイト列を文字列にデコード
            decoded_content = content.decode(encoding)
            # デコードした文字列を再度エンコードして元のバイト列と比較
            if decoded_content.encode(encoding) == content:
                return decoded_content
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    
    # すべてのエンコーディングで失敗した場合
    try:
        # UTF-8で強制的にデコードを試みる（一部の文字が化ける可能性あり）
        return content.decode('utf-8', errors='replace')
    except Exception as e:
        raise ValueError(f"ファイルのエンコーディングを特定できませんでした。エラー: {str(e)}")

def process_csv_file(file):
    """CSVファイルを処理してチャンクに分割"""
    try:
        # エンコーディングのリスト（日本語のCSVで一般的なエンコーディング）
        encodings = ['utf-8', 'shift-jis', 'cp932', 'euc-jp']
        
        # 各エンコーディングで試行
        for encoding in encodings:
            try:
                # ファイルの内容をバイト列として読み込む
                content = file.getvalue()
                # 指定したエンコーディングでデコード
                decoded_content = content.decode(encoding)
                # デコードした内容をStringIOに変換
                file_like = io.StringIO(decoded_content)
                # CSVとして読み込む
                df = pd.read_csv(file_like, header=None, names=[
                    "大カテゴリ", "中カテゴリ", "施設名", "緯度", "経度", "徒歩距離", "徒歩分数", "直線距離"
                ])
                break  # 成功したらループを抜ける
            except (UnicodeDecodeError, pd.errors.EmptyDataError):
                continue  # 失敗したら次のエンコーディングを試す
        
        if 'df' not in locals():
            raise ValueError("CSVファイルのエンコーディングを特定できませんでした。")
        
        # デバッグ情報の表示
        st.write("CSVファイルの内容:")
        st.dataframe(df)
        
        # 各列を結合してテキストを作成
        chunks = []
        for index, row in df.iterrows():
            try:
                # 各行をテキストに変換
                text = f"{row['施設名']}は{row['大カテゴリ']}の{row['中カテゴリ']}です。"
                if text.strip():
                    # NaN値を適切に処理し、型変換を確実に行う
                    metadata = {
                        "main_category": str(row['大カテゴリ']) if pd.notna(row['大カテゴリ']) else "",
                        "sub_category": str(row['中カテゴリ']) if pd.notna(row['中カテゴリ']) else "",
                        "facility_name": str(row['施設名']) if pd.notna(row['施設名']) else "",
                        "latitude": float(row['緯度']) if pd.notna(row['緯度']) else 0.0,
                        "longitude": float(row['経度']) if pd.notna(row['経度']) else 0.0,
                        "walking_distance": int(float(row['徒歩距離'])) if pd.notna(row['徒歩距離']) else 0,
                        "walking_minutes": int(float(row['徒歩分数'])) if pd.notna(row['徒歩分数']) else 0,
                        "straight_distance": int(float(row['直線距離'])) if pd.notna(row['直線距離']) else 0
                    }
                    
                    # デバッグ情報の表示
                    st.write(f"行 {index + 1} のメタデータ:")
                    st.json(metadata)
                    
                    chunks.append({
                        "id": f"csv_{index}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "text": text,
                        "metadata": metadata
                    })
            except Exception as e:
                st.error(f"行 {index + 1} の処理中にエラーが発生しました: {str(e)}")
                continue
        
        if not chunks:
            raise ValueError("有効なデータが1件も見つかりませんでした。")
            
        return chunks
    except Exception as e:
        raise ValueError(f"CSVファイルの処理に失敗しました: {str(e)}")

def manual_chunk_split(text: str, chunk_separators: str = "---") -> List[Dict[str, Any]]:
    """手動でチャンクを分割"""
    chunks = []
    
    # セパレータでテキストを分割
    if chunk_separators:
        # 複数のセパレータをサポート（改行で区切る）
        separators = [sep.strip() for sep in chunk_separators.split('\n') if sep.strip()]
        
        # 最初のセパレータで分割
        if separators:
            parts = text.split(separators[0])
        else:
            parts = [text]
    else:
        parts = [text]
    
    # 各部分をチャンクとして処理
    for i, part in enumerate(parts):
        part = part.strip()
        if part:  # 空でない部分のみをチャンクとして追加
            chunks.append({
                "id": f"manual_chunk_{i}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "text": part,
                "metadata": {
                    "chunk_type": "manual",
                    "chunk_index": i
                }
            })
    
    return chunks

def advanced_manual_chunk_split(text: str, chunk_separators: str = "---") -> List[Dict[str, Any]]:
    """高度な手動チャンク分割（複数セパレータ対応）"""
    chunks = []
    
    if not chunk_separators:
        # セパレータがない場合は全体を1つのチャンクとして扱う
        if text.strip():
            chunks.append({
                "id": f"manual_chunk_0_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "text": text.strip(),
                "metadata": {
                    "chunk_type": "manual",
                    "chunk_index": 0
                }
            })
        return chunks
    
    # 複数のセパレータをサポート（改行で区切る）
    separators = [sep.strip() for sep in chunk_separators.split('\n') if sep.strip()]
    
    if not separators:
        # 有効なセパレータがない場合
        if text.strip():
            chunks.append({
                "id": f"manual_chunk_0_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "text": text.strip(),
                "metadata": {
                    "chunk_type": "manual",
                    "chunk_index": 0
                }
            })
        return chunks
    
    # 最初のセパレータで分割
    parts = text.split(separators[0])
    
    # 各部分を処理
    chunk_index = 0
    for part in parts:
        part = part.strip()
        if not part:  # 空の部分はスキップ
            continue
        
        # 追加のセパレータがある場合は、さらに分割を試みる
        if len(separators) > 1:
            sub_parts = []
            current_part = part
            
            for sep in separators[1:]:
                if sep in current_part:
                    sub_parts.extend(current_part.split(sep))
                    current_part = ""
                    break
                else:
                    sub_parts = [current_part]
                    break
            
            # サブパーツを処理
            for sub_part in sub_parts:
                sub_part = sub_part.strip()
                if sub_part:  # 空でない部分のみをチャンクとして追加
                    chunks.append({
                        "id": f"manual_chunk_{chunk_index}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "text": sub_part,
                        "metadata": {
                            "chunk_type": "manual",
                            "chunk_index": chunk_index,
                            "separators_used": separators
                        }
                    })
                    chunk_index += 1
        else:
            # 単一セパレータの場合
            chunks.append({
                "id": f"manual_chunk_{chunk_index}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "text": part,
                "metadata": {
                    "chunk_type": "manual",
                    "chunk_index": chunk_index,
                    "separators_used": separators
                }
            })
            chunk_index += 1
    
    return chunks

def preview_chunks(text: str, chunk_separators: str = "---") -> List[Dict[str, Any]]:
    """チャンク分割のプレビューを生成"""
    return advanced_manual_chunk_split(text, chunk_separators)

def render_file_upload(pinecone_service: PineconeService):
    """ファイルアップロード機能のUIを表示"""
    st.title("ファイルアップロード")
    st.write("テキストファイルをアップロードして、Pineconeデータベースに保存します。")
    
    uploaded_file = st.file_uploader("テキストファイルをアップロード", type=['txt', 'csv'])
    
    if uploaded_file is not None:
        # ファイルの種類に応じて処理を分岐
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension == 'csv':
            # CSVファイルの場合はメタデータ入力フォームを表示しない
            if st.button("データベースに保存"):
                try:
                    with st.spinner("ファイルを処理中..."):
                        chunks = process_csv_file(uploaded_file)
                        st.write(f"ファイルを{len(chunks)}個のチャンクに分割しました")
                        
                        with st.spinner("Pineconeにアップロード中..."):
                            pinecone_service.upload_chunks(chunks)
                            st.success("アップロードが完了しました！")
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")
        else:
            # テキストファイルの場合はメタデータ入力フォームを表示
            st.subheader("メタデータ入力")
            
            # 市区町村の選択
            city = st.selectbox(
                "市区町村",
                METADATA_CATEGORIES["市区町村"],
                index=None,
                placeholder="市区町村を選択してください（任意）"
            )
            
            # データ作成日の選択（デフォルトで当日、表示非表示）
            created_date = datetime.now().date()
            
            # ソース元の入力
            source = st.text_input(
                "ソース元",
                placeholder="ソース元を入力してください（任意）"
            )
            
            # データ検証状況
            st.markdown("#### 📋 データ検証・有効性設定")
            
            # 検証済みフラグ
            verified = st.checkbox(
                "データ検証済み",
                value=False,
                help="このデータが検証済みであることを示します"
            )
            
            # タイムスタンプタイプ（ラジオボタン）
            timestamp_type = st.radio(
                "📅 データ更新タイプ",
                options=[
                    ("fixed", "固定データ"),
                    ("yearly", "年次更新"),
                    ("dated", "日付指定")
                ],
                format_func=lambda x: x[1],
                index=0,
                help="データの更新頻度を選択してください"
            )
            # タプルから文字列に変換
            timestamp_type = timestamp_type[0] if isinstance(timestamp_type, tuple) else timestamp_type
            
            # 有効期間（テキスト入力）- 小さくする
            st.markdown("**📆 データの作成年度**")
            st.markdown("このデータの作成年度を入力してください（例：令和6年度、複数可）")
            
            valid_for_text = st.text_input(
                "作成年度",
                value="令和6年度",
                placeholder="作成年度を入力してください（例：令和6年度、令和5年度、2024年度）",
                help="このデータの作成年度を入力してください（複数の場合はカンマ区切り）"
            )
            selected_periods = [p.strip() for p in valid_for_text.split(',') if p.strip()] if valid_for_text.strip() else []
            
            # アップロード日（自動設定）
            upload_date = datetime.now()
            
            # チャンク分割方法の選択
            st.subheader("📝 チャンク分割設定")
            st.info("チャンク分割は手動で行います。テキストを編集してチャンクの境界を指定してください。")
            
            # ファイル内容の読み込み
            file_content = read_file_content(uploaded_file)
            
            # 手動分割モード（唯一の選択肢）
            st.markdown("### ✏️ 手動チャンク分割")
            st.markdown("テキストを編集してチャンクの境界を指定してください。")
            
            # チャンクセパレータの設定
            st.markdown("#### 📋 チャンクセパレータ")
            st.markdown("チャンクを区切る文字列を指定してください。複数のセパレータを使用する場合は改行で区切ってください。")
            
            # よく使われるセパレータの例
            with st.expander("💡 よく使われるセパレータの例", expanded=False):
                st.markdown("**基本的なセパレータ:**")
                st.code("---\n###\n##\n#")
                
                st.markdown("**段落区切り:**")
                st.code("\\n\\n\n---\n***")
                
                st.markdown("**見出し区切り:**")
                st.code("第1章\n第2章\n第3章\n\n1.\n2.\n3.")
                
                st.markdown("**カスタム区切り:**")
                st.code("【物件概要】\n【交通アクセス】\n【周辺環境】\n\n=== 物件情報 ===\n=== アクセス情報 ===")
                
                st.markdown("**使用方法:**")
                st.markdown("1. 上記の例から適切なセパレータをコピー")
                st.markdown("2. 下のテキストエリアに貼り付け")
                st.markdown("3. 必要に応じてカスタマイズ")
                st.markdown("4. テキスト内にセパレータを追加してチャンクを区切る")
            
            default_separators = "---\n###\n##"
            chunk_separators = st.text_area(
                "チャンクセパレータ",
                value=default_separators,
                height=100,
                help="チャンクを区切る文字列を入力してください。複数のセパレータを使用する場合は改行で区切ってください。例：---, ###, ## など"
            )
            
            # テキストエディタ
            st.markdown("#### 📝 テキスト編集")
            st.markdown("必要に応じてテキストを編集し、セパレータを追加してチャンクを区切ってください。")
            
            edited_text = st.text_area(
                "テキスト内容",
                value=file_content,
                height=400,
                help="テキストを編集してチャンクの境界を指定してください"
            )
            
            # プレビューボタン
            if st.button("👁️ チャンク分割をプレビュー"):
                # プレビューチャンクを生成
                preview_chunks_list = preview_chunks(edited_text, chunk_separators)
                
                # セッション状態に保存
                st.session_state['preview_chunks'] = preview_chunks_list
                st.session_state['show_preview'] = True
                
                st.success(f"✅ {len(preview_chunks_list)}個のチャンクをプレビュー用に生成しました")
            
            # プレビューが表示されている場合
            if st.session_state.get('show_preview', False) and 'preview_chunks' in st.session_state:
                preview_chunks_list = st.session_state['preview_chunks']
                
                st.markdown("#### 📋 チャンク分割プレビュー")
                
                if preview_chunks_list:
                    st.success(f"✅ {len(preview_chunks_list)}個のチャンクに分割されました")
                    
                    # 統計情報を表示
                    total_chars = sum(len(chunk['text']) for chunk in preview_chunks_list)
                    avg_chars = total_chars // len(preview_chunks_list) if preview_chunks_list else 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("チャンク数", len(preview_chunks_list))
                    with col2:
                        st.metric("総文字数", total_chars)
                    with col3:
                        st.metric("平均文字数", avg_chars)
                    
                    # 各チャンクを表示
                    for i, chunk in enumerate(preview_chunks_list):
                        # チャンクの概要情報を作成
                        chunk_summary = f"📄 チャンク {i+1}"
                        if 'ai_classification' in chunk:
                            ai_result = chunk['ai_classification']
                            main_cat = ai_result.get('main_category', '未分類')
                            sub_cat = ai_result.get('sub_category', '未分類')
                            chunk_summary += f" | 🏷️ {main_cat}/{sub_cat}"
                        elif 'manual_main_category' in chunk and chunk['manual_main_category']:
                            chunk_summary += f" | 🏷️ {chunk['manual_main_category']}/{chunk.get('manual_sub_category', '')}"
                        else:
                            chunk_summary += " | 🏷️ 未分類"
                        
                        chunk_summary += f" | 📝 {len(chunk['text'])}文字"
                        
                        # 位置情報がある場合は表示
                        if chunk.get('chunk_location', {}).get('latitude') is not None:
                            chunk_summary += " | 📍 位置情報あり"
                        
                        # 質問例がある場合は表示
                        if chunk.get('question_examples'):
                            chunk_summary += f" | 💬 {len(chunk['question_examples'])}個の質問例"
                        
                        # 回答例がある場合は表示
                        if chunk.get('answer_examples'):
                            chunk_summary += f" | 💡 {len(chunk['answer_examples'])}個の回答例"
                        
                        # セッション状態で開閉状態を管理
                        expander_key = f"chunk_expander_{i}"
                        if expander_key not in st.session_state:
                            st.session_state[expander_key] = False
                        
                        # 質問例生成やAI分類が実行された場合は開いた状態にする
                        if (f"generate_questions_{i}" in st.session_state and st.session_state[f"generate_questions_{i}"]) or \
                           (f"improve_questions_{i}" in st.session_state and st.session_state[f"improve_questions_{i}"]) or \
                           (f"ai_classify_{i}" in st.session_state and st.session_state[f"ai_classify_{i}"]):
                            st.session_state[expander_key] = True
                            # ボタンの状態をリセット
                            st.session_state[f"generate_questions_{i}"] = False
                            st.session_state[f"improve_questions_{i}"] = False
                            st.session_state[f"ai_classify_{i}"] = False
                        
                        with st.expander(chunk_summary, expanded=st.session_state[expander_key]):
                            # チャンクの詳細情報
                            st.markdown(f"**チャンクID:** {chunk['id']}")
                            st.markdown(f"**文字数:** {len(chunk['text'])}文字")
                            if 'separators_used' in chunk['metadata']:
                                st.markdown(f"**使用セパレータ:** {', '.join(chunk['metadata']['separators_used'])}")
                            
                            # チャンク内容の表示
                            st.text_area(
                                f"チャンク {i+1} の内容",
                                value=chunk['text'],
                                height=150,
                                key=f"preview_chunk_{i}"
                            )
                            
                            # カテゴリ設定セクション
                            st.markdown("#### 🏷️ カテゴリ設定")
                            
                            # カテゴリ分類器を初期化
                            classifier = CategoryClassifier()
                            
                            # AI分類ボタン（チャンクごと）
                            if st.button(f"🤖 AIでカテゴリを自動判定", key=f"ai_classify_{i}"):
                                # セッション状態を設定してexpanderを開いた状態にする
                                st.session_state[f"ai_classify_{i}"] = True
                                st.session_state[f"chunk_expander_{i}"] = True
                                
                                try:
                                    with st.spinner(f"チャンク {i+1} を分析中..."):
                                        # AI分類を実行
                                        classification = classifier.classify_text(chunk['text'])
                                        
                                        # 分類結果をチャンクに保存
                                        chunk['ai_classification'] = classification
                                        
                                        # セッション状態を即座に更新
                                        st.session_state['preview_chunks'] = preview_chunks_list
                                        
                                        st.success(f"✅ チャンク {i+1} の分類が完了しました！")
                                        st.write(f"分類結果: {classification.get('main_category', '未分類')} / {classification.get('sub_category', '未分類')}")
                                        
                                except Exception as e:
                                    st.error(f"AI分類中にエラーが発生しました: {str(e)}")
                            
                            # AI分類結果の表示
                            if 'ai_classification' in chunk:
                                ai_result = chunk['ai_classification']
                                st.markdown("**🤖 AI分類結果:**")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown(f"**大カテゴリ:** {ai_result.get('main_category', '未分類')}")
                                    st.markdown(f"**中カテゴリ:** {ai_result.get('sub_category', '未分類')}")
                                with col2:
                                    confidence = ai_result.get('confidence', 0.0)
                                    st.markdown(f"**確信度:** {confidence:.2%}")
                                
                                st.markdown(f"**分類理由:** {ai_result.get('reasoning', '理由なし')}")
                                
                                # 確信度に応じた色分け
                                if confidence >= 0.8:
                                    st.success("✅ 高確信度")
                                elif confidence >= 0.6:
                                    st.warning("⚠️ 中確信度")
                                else:
                                    st.error("❌ 低確信度")
                            
                            # 手動カテゴリ編集
                            st.markdown("**✏️ カテゴリ手動編集:**")
                            
                            # 現在のAI分類結果を初期値として使用
                            current_main = ai_result.get('main_category', '') if 'ai_classification' in chunk else ''
                            current_sub = ai_result.get('sub_category', '') if 'ai_classification' in chunk else ''
                            
                            # 大カテゴリの選択
                            main_category_options = [''] + classifier.get_main_categories()
                            main_category_index = main_category_options.index(current_main) if current_main in main_category_options else 0
                            
                            selected_main = st.selectbox(
                                "大カテゴリ",
                                options=main_category_options,
                                index=main_category_index,
                                key=f"main_cat_{i}"
                            )
                            
                            # 中カテゴリの選択
                            if selected_main:
                                sub_category_options = [''] + classifier.get_sub_categories(selected_main)
                                sub_category_index = sub_category_options.index(current_sub) if current_sub in sub_category_options else 0
                                
                                selected_sub = st.selectbox(
                                    "中カテゴリ",
                                    options=sub_category_options,
                                    index=sub_category_index,
                                    key=f"sub_cat_{i}"
                                )
                            else:
                                selected_sub = ""
                            
                            # 編集されたカテゴリをチャンクに保存
                            chunk['manual_main_category'] = selected_main
                            chunk['manual_sub_category'] = selected_sub
                            
                            # デバッグ出力を追加
                            st.write(f"  - チャンク {i+1} の手動カテゴリ設定: {selected_main} / {selected_sub}")
                            
                            # セッション状態を即座に更新
                            st.session_state['preview_chunks'] = preview_chunks_list
                            
                            # チャンク固有のメタデータ設定
                            st.markdown("#### 🔧 チャンク固有設定")
                            st.markdown("このチャンクに特有の設定を行います")
                            
                            # チャンク固有の位置情報
                            st.markdown("**📍 このチャンクの位置情報**")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                chunk_latitude = st.number_input(
                                    "緯度",
                                    min_value=-90.0,
                                    max_value=90.0,
                                    value=chunk.get('chunk_location', {}).get('latitude', None),
                                    step=0.0001,
                                    format="%.4f",
                                    key=f"chunk_latitude_{i}",
                                    help="緯度を入力してください（例：35.9056）"
                                )
                                
                                chunk_longitude = st.number_input(
                                    "経度",
                                    min_value=-180.0,
                                    max_value=180.0,
                                    value=chunk.get('chunk_location', {}).get('longitude', None),
                                    step=0.0001,
                                    format="%.4f",
                                    key=f"chunk_longitude_{i}",
                                    help="経度を入力してください（例：139.4852）"
                                )
                            
                            with col2:
                                chunk_address = st.text_input(
                                    "住所",
                                    value=chunk.get('chunk_location', {}).get('address', ""),
                                    placeholder="住所を入力してください（任意）",
                                    key=f"chunk_address_{i}",
                                    help="詳細な住所を入力してください"
                                )
                                
                                # チャンク固有の位置情報の検証
                                if chunk_latitude is not None and chunk_longitude is not None:
                                    st.success(f"✅ 位置情報が設定されています")
                                    st.write(f"緯度: {chunk_latitude}, 経度: {chunk_longitude}")
                                    if chunk_address:
                                        st.write(f"住所: {chunk_address}")
                                else:
                                    st.info("ℹ️ 位置情報は任意です。必要に応じて入力してください。")
                            
                            # チャンク固有の設定を保存
                            chunk['chunk_location'] = {
                                'latitude': chunk_latitude,
                                'longitude': chunk_longitude,
                                'address': chunk_address
                            }
                            
                            # セッション状態を即座に更新
                            st.session_state['preview_chunks'] = preview_chunks_list
                            
                            # 質問例設定セクション
                            st.markdown("#### 💬 質問例設定")
                            st.markdown("このチャンクに関連する質問例をAIで生成・編集できます（検索時に優先されます）")
                            
                            # 質問例生成器を初期化
                            question_generator = QuestionExampleGenerator()
                            
                            # 既存の質問例を取得
                            existing_examples = chunk.get('question_examples', [])
                            existing_text = '\n'.join(existing_examples) if existing_examples else ''
                            
                            # AI生成ボタン
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"🤖 AIで質問例を生成", key=f"generate_questions_{i}"):
                                    # セッション状態を設定してexpanderを開いた状態にする
                                    st.session_state[f"generate_questions_{i}"] = True
                                    st.session_state[f"chunk_expander_{i}"] = True
                                    
                                    try:
                                        with st.spinner(f"チャンク {i+1} の質問例を生成中..."):
                                            # カテゴリ情報を取得
                                            category = ""
                                            subcategory = ""
                                            if 'ai_classification' in chunk:
                                                ai_result = chunk['ai_classification']
                                                category = ai_result.get('main_category', '')
                                                subcategory = ai_result.get('sub_category', '')
                                            elif 'manual_main_category' in chunk and chunk['manual_main_category']:
                                                category = chunk['manual_main_category']
                                                subcategory = chunk.get('manual_sub_category', '')
                                            
                                            # 質問例を生成
                                            generated_questions = question_generator.generate_question_examples(
                                                chunk['text'], 
                                                category, 
                                                subcategory
                                            )
                                            
                                            if generated_questions:
                                                # 生成された質問例をチャンクに保存
                                                chunk['question_examples'] = generated_questions
                                                
                                                # セッション状態を即座に更新
                                                st.session_state['preview_chunks'] = preview_chunks_list
                                                
                                                st.success(f"✅ チャンク {i+1} の質問例を生成しました！")
                                                st.write(f"生成された質問例: {len(generated_questions)}個")
                                            else:
                                                st.warning("⚠️ 質問例の生成に失敗しました。")
                                                
                                    except Exception as e:
                                        st.error(f"質問例生成中にエラーが発生しました: {str(e)}")
                            
                            with col2:
                                if existing_examples:
                                    if st.button(f"🔧 既存の質問例を改善", key=f"improve_questions_{i}"):
                                        # セッション状態を設定してexpanderを開いた状態にする
                                        st.session_state[f"improve_questions_{i}"] = True
                                        st.session_state[f"chunk_expander_{i}"] = True
                                        
                                        try:
                                            with st.spinner(f"チャンク {i+1} の質問例を改善中..."):
                                                # カテゴリ情報を取得
                                                category = ""
                                                subcategory = ""
                                                if 'ai_classification' in chunk:
                                                    ai_result = chunk['ai_classification']
                                                    category = ai_result.get('main_category', '')
                                                    subcategory = ai_result.get('sub_category', '')
                                                elif 'manual_main_category' in chunk and chunk['manual_main_category']:
                                                    category = chunk['manual_main_category']
                                                    subcategory = chunk.get('manual_sub_category', '')
                                                
                                                # 質問例を改善
                                                improved_questions = question_generator.improve_question_examples(
                                                    chunk['text'],
                                                    existing_examples,
                                                    category,
                                                    subcategory
                                                )
                                                
                                                if improved_questions:
                                                    # 改善された質問例をチャンクに保存
                                                    chunk['question_examples'] = improved_questions
                                                    
                                                    # セッション状態を即座に更新
                                                    st.session_state['preview_chunks'] = preview_chunks_list
                                                    
                                                    st.success(f"✅ チャンク {i+1} の質問例を改善しました！")
                                                    st.write(f"改善された質問例: {len(improved_questions)}個")
                                                else:
                                                    st.warning("⚠️ 質問例の改善に失敗しました。")
                                                    
                                        except Exception as e:
                                            st.error(f"質問例改善中にエラーが発生しました: {str(e)}")
                            
                            # 現在の質問例を表示・編集
                            current_examples = chunk.get('question_examples', [])
                            current_text = '\n'.join(current_examples) if current_examples else ''
                            
                            # 質問例の入力・編集
                            question_examples_text = st.text_area(
                                "質問例（編集可能）",
                                value=current_text,
                                placeholder="このチャンクに関連する質問例を入力してください（1行に1つの質問）\n例：\nこの物件の完成時期はいつですか？\n最寄り駅までの距離は？\n周辺の学校について教えてください",
                                height=150,
                                key=f"question_examples_{i}",
                                help="このチャンクに関連する質問例を1行に1つずつ入力してください。入力された質問例は検索時に優先されます。"
                            )
                            
                            # 質問例をリストに変換してチャンクに保存
                            if question_examples_text.strip():
                                chunk_question_examples = [q.strip() for q in question_examples_text.split('\n') if q.strip()]
                                chunk['question_examples'] = chunk_question_examples
                            else:
                                chunk['question_examples'] = []
                            
                            # 質問例の統計情報を表示
                            if chunk['question_examples']:
                                st.info(f"📊 現在の質問例: {len(chunk['question_examples'])}個")
                                # 質問例のプレビュー
                                with st.expander("👀 質問例プレビュー", expanded=False):
                                    for j, question in enumerate(chunk['question_examples'], 1):
                                        st.write(f"{j}. {question}")
                            else:
                                st.info("ℹ️ 質問例が設定されていません。AI生成ボタンを使用して質問例を生成してください。")
                            
                            # 回答例設定セクション
                            st.markdown("#### 💡 回答例設定")
                            st.markdown("このチャンクに関連する質問と回答のペアをAIで生成・編集できます")
                            
                            # 既存の回答例を取得
                            existing_qa_pairs = chunk.get('answer_examples', [])
                            
                            # AI生成ボタン
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"🤖 AIで回答例を生成", key=f"generate_answers_{i}"):
                                    # セッション状態を設定してexpanderを開いた状態にする
                                    st.session_state[f"generate_answers_{i}"] = True
                                    st.session_state[f"chunk_expander_{i}"] = True
                                    
                                    try:
                                        with st.spinner(f"チャンク {i+1} の回答例を生成中..."):
                                            # カテゴリ情報を取得
                                            category = ""
                                            subcategory = ""
                                            if 'ai_classification' in chunk:
                                                ai_result = chunk['ai_classification']
                                                category = ai_result.get('main_category', '')
                                                subcategory = ai_result.get('sub_category', '')
                                            elif 'manual_main_category' in chunk and chunk['manual_main_category']:
                                                category = chunk['manual_main_category']
                                                subcategory = chunk.get('manual_sub_category', '')
                                            
                                            # 回答例を生成
                                            generated_qa_pairs = question_generator.generate_answer_examples(
                                                chunk['text'], 
                                                category, 
                                                subcategory
                                            )
                                            
                                            if generated_qa_pairs:
                                                # 生成された回答例をチャンクに保存
                                                chunk['answer_examples'] = generated_qa_pairs
                                                
                                                # セッション状態を即座に更新
                                                st.session_state['preview_chunks'] = preview_chunks_list
                                                
                                                st.success(f"✅ チャンク {i+1} の回答例を生成しました！")
                                                st.write(f"生成された回答例: {len(generated_qa_pairs)}個")
                                            else:
                                                st.warning("⚠️ 回答例の生成に失敗しました。")
                                                
                                    except Exception as e:
                                        st.error(f"回答例生成中にエラーが発生しました: {str(e)}")
                            
                            with col2:
                                if existing_qa_pairs:
                                    if st.button(f"🔧 既存の回答例を改善", key=f"improve_answers_{i}"):
                                        # セッション状態を設定してexpanderを開いた状態にする
                                        st.session_state[f"improve_answers_{i}"] = True
                                        st.session_state[f"chunk_expander_{i}"] = True
                                        
                                        try:
                                            with st.spinner(f"チャンク {i+1} の回答例を改善中..."):
                                                # カテゴリ情報を取得
                                                category = ""
                                                subcategory = ""
                                                if 'ai_classification' in chunk:
                                                    ai_result = chunk['ai_classification']
                                                    category = ai_result.get('main_category', '')
                                                    subcategory = ai_result.get('sub_category', '')
                                                elif 'manual_main_category' in chunk and chunk['manual_main_category']:
                                                    category = chunk['manual_main_category']
                                                    subcategory = chunk.get('manual_sub_category', '')
                                                
                                                # 回答例を改善
                                                improved_qa_pairs = question_generator.improve_answer_examples(
                                                    chunk['text'],
                                                    existing_qa_pairs,
                                                    category,
                                                    subcategory
                                                )
                                                
                                                if improved_qa_pairs:
                                                    # 改善された回答例をチャンクに保存
                                                    chunk['answer_examples'] = improved_qa_pairs
                                                    
                                                    # セッション状態を即座に更新
                                                    st.session_state['preview_chunks'] = preview_chunks_list
                                                    
                                                    st.success(f"✅ チャンク {i+1} の回答例を改善しました！")
                                                    st.write(f"改善された回答例: {len(improved_qa_pairs)}個")
                                                else:
                                                    st.warning("⚠️ 回答例の改善に失敗しました。")
                                                    
                                        except Exception as e:
                                            st.error(f"回答例改善中にエラーが発生しました: {str(e)}")
                            
                            # 現在の回答例を表示・編集
                            current_qa_pairs = chunk.get('answer_examples', [])
                            
                            # 回答例の表示・編集
                            if current_qa_pairs:
                                st.info(f"📊 現在の回答例: {len(current_qa_pairs)}個")
                                
                                # 回答例の編集用UI
                                for j, qa_pair in enumerate(current_qa_pairs):
                                    with st.expander(f"回答例 {j+1}", expanded=False):
                                        # 質問の編集
                                        question = st.text_area(
                                            "質問",
                                            value=qa_pair.get('question', ''),
                                            key=f"answer_question_{i}_{j}",
                                            help="質問を編集してください"
                                        )
                                        
                                        # 回答の編集
                                        answer = st.text_area(
                                            "回答",
                                            value=qa_pair.get('answer', ''),
                                            key=f"answer_answer_{i}_{j}",
                                            help="回答を編集してください"
                                        )
                                        
                                        # 更新されたペアを保存
                                        current_qa_pairs[j] = {
                                            "question": question,
                                            "answer": answer
                                        }
                                
                                # 新しい回答例を追加
                                if st.button(f"➕ 新しい回答例を追加", key=f"add_answer_{i}"):
                                    current_qa_pairs.append({
                                        "question": "",
                                        "answer": ""
                                    })
                                    st.session_state['preview_chunks'] = preview_chunks_list
                                    st.rerun()
                                
                                # 回答例をチャンクに保存
                                chunk['answer_examples'] = current_qa_pairs
                                
                                # 回答例のプレビュー
                                with st.expander("👀 回答例プレビュー", expanded=False):
                                    for j, qa_pair in enumerate(current_qa_pairs, 1):
                                        st.markdown(f"**{j}. 質問:** {qa_pair.get('question', '')}")
                                        st.markdown(f"**回答:** {qa_pair.get('answer', '')}")
                                        st.markdown("---")
                            else:
                                st.info("ℹ️ 回答例が設定されていません。AI生成ボタンを使用して回答例を生成してください。")
                            
                            # セッション状態を即座に更新
                            st.session_state['preview_chunks'] = preview_chunks_list
                    
                    # 分割の品質チェック
                    st.markdown("#### 🔍 分割品質チェック")
                    
                    # 短すぎるチャンクの警告
                    short_chunks = [chunk for chunk in preview_chunks_list if len(chunk['text']) < 50]
                    if short_chunks:
                        st.warning(f"⚠️ {len(short_chunks)}個のチャンクが50文字未満です。内容が不十分な可能性があります。")
                    
                    # 長すぎるチャンクの警告
                    long_chunks = [chunk for chunk in preview_chunks_list if len(chunk['text']) > 2000]
                    if long_chunks:
                        st.warning(f"⚠️ {len(long_chunks)}個のチャンクが2000文字を超えています。さらに分割することを検討してください。")
                    
                    # 推奨事項
                    if not short_chunks and not long_chunks:
                        st.success("✅ チャンク分割の品質は良好です。")
                    
                    # セパレータの使用状況
                    st.markdown("#### 📊 セパレータ使用状況")
                    separator_counts = {}
                    for chunk in preview_chunks_list:
                        if 'separators_used' in chunk['metadata']:
                            for sep in chunk['metadata']['separators_used']:
                                separator_counts[sep] = separator_counts.get(sep, 0) + 1
                    
                    if separator_counts:
                        for sep, count in separator_counts.items():
                            st.markdown(f"- `{sep}`: {count}回使用")
                    else:
                        st.info("セパレータの使用状況は記録されていません。")
                else:
                    st.warning("⚠️ チャンクが生成されませんでした。セパレータを確認してください。")
                    
                    # セパレータの確認を促す
                    st.markdown("#### 💡 セパレータの確認")
                    st.markdown("以下の点を確認してください：")
                    st.markdown("1. セパレータが正しく入力されているか")
                    st.markdown("2. テキスト内にセパレータが含まれているか")
                    st.markdown("3. セパレータの前後に適切な改行があるか")
                    
                    # 現在のセパレータを表示
                    st.markdown("**現在のセパレータ:**")
                    st.code(chunk_separators)
            
            # 保存ボタン
            if st.button("💾 データベースに保存"):
                try:
                    with st.spinner("ファイルを処理中..."):
                        # セッション状態からチャンクを取得、ない場合は新しく生成
                        if 'preview_chunks' in st.session_state:
                            chunks = st.session_state['preview_chunks']
                            st.info(f"セッション状態から{len(chunks)}個のチャンクを取得しました")
                        else:
                            chunks = advanced_manual_chunk_split(edited_text, chunk_separators)
                            st.info(f"新しく{len(chunks)}個のチャンクを生成しました")
                        
                        if not chunks:
                            st.error("チャンクが生成されませんでした。セパレータを確認してください。")
                            return
                        
                        st.write(f"ファイルを{len(chunks)}個のチャンクに分割しました")
                        
                        # メタデータを追加
                        for i, chunk in enumerate(chunks):
                            # デバッグ情報の表示
                            st.write(f"チャンク {i+1} の処理:")
                            st.write(f"  - 手動カテゴリ: {chunk.get('manual_main_category', 'なし')} / {chunk.get('manual_sub_category', 'なし')}")
                            st.write(f"  - AI分類: {chunk.get('ai_classification', 'なし')}")
                            st.write(f"  - 質問例: {chunk.get('question_examples', [])}")
                            st.write(f"  - 回答例: {chunk.get('answer_examples', [])}")
                            st.write(f"  - 検証済み: {verified}")
                            st.write(f"  - 更新タイプ: {timestamp_type}")
                            st.write(f"  - 位置情報: 緯度{chunk.get('chunk_location', {}).get('latitude', None)}, 経度{chunk.get('chunk_location', {}).get('longitude', None)}, 住所{chunk.get('chunk_location', {}).get('address', '')}")
                            
                            # 基本メタデータ
                            metadata = {
                                "main_category": "",
                                "sub_category": "",
                                "city": city if city else "",
                                "created_date": created_date.isoformat() if created_date else "",
                                "upload_date": upload_date.isoformat(),
                                "source": source if source else "",
                                "question_examples": chunk.get('question_examples', []),
                                "answer_examples": chunk.get('answer_examples', []),
                                "verified": verified,
                                "timestamp_type": timestamp_type,
                                "valid_for": selected_periods if selected_periods else [],
                                "latitude": chunk.get('chunk_location', {}).get('latitude') if chunk.get('chunk_location', {}).get('latitude') is not None else 0.0,
                                "longitude": chunk.get('chunk_location', {}).get('longitude') if chunk.get('chunk_location', {}).get('longitude') is not None else 0.0,
                                "address": chunk.get('chunk_location', {}).get('address', '')
                            }
                            
                            # カテゴリの設定（優先順位: 手動編集 > AI分類）
                            st.write(f"  - カテゴリ設定の確認:")
                            st.write(f"    - manual_main_category: {chunk.get('manual_main_category', 'なし')}")
                            st.write(f"    - manual_sub_category: {chunk.get('manual_sub_category', 'なし')}")
                            st.write(f"    - ai_classification: {chunk.get('ai_classification', 'なし')}")
                            
                            if 'manual_main_category' in chunk and chunk['manual_main_category']:
                                metadata["main_category"] = chunk['manual_main_category']
                                metadata["sub_category"] = chunk.get('manual_sub_category', '')
                                st.write(f"  - 手動カテゴリを設定: {metadata['main_category']} / {metadata['sub_category']}")
                            elif 'ai_classification' in chunk:
                                ai_result = chunk['ai_classification']
                                metadata["main_category"] = ai_result.get('main_category', '')
                                metadata["sub_category"] = ai_result.get('sub_category', '')
                                # AI分類の詳細情報も保存
                                metadata["ai_confidence"] = ai_result.get('confidence', 0.0)
                                metadata["ai_reasoning"] = ai_result.get('reasoning', '')
                                st.write(f"  - AI分類を設定: {metadata['main_category']} / {metadata['sub_category']}")
                            else:
                                st.write(f"  - カテゴリ未設定")
                            
                            # チャンクの基本情報
                            chunk["metadata"] = metadata
                            chunk["filename"] = uploaded_file.name
                            chunk["chunk_id"] = chunk["id"]
                            
                            # AI分類情報がある場合は追加
                            if 'ai_classification' in chunk:
                                chunk["metadata"]["ai_classification"] = chunk['ai_classification']
                            
                            # 最終的なメタデータを表示
                            st.write(f"  - 最終メタデータ: {metadata}")
                        
                        with st.spinner("Pineconeにアップロード中..."):
                            pinecone_service.upload_chunks(chunks)
                            st.success("アップロードが完了しました！")
                            
                            # セッション状態をクリア
                            if 'preview_chunks' in st.session_state:
                                del st.session_state['preview_chunks']
                            if 'show_preview' in st.session_state:
                                del st.session_state['show_preview']
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}") 