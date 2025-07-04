from typing import List, Dict, Any
from pinecone import Pinecone
from openai import OpenAI
import time
from src.config.settings import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    BATCH_SIZE,
    DEFAULT_TOP_K,
    SIMILARITY_THRESHOLD
)
import json
import streamlit as st

class PineconeService:
    def __init__(self):
        """Pineconeサービスの初期化"""
        try:
            # OpenAIクライアントの初期化
            if not OPENAI_API_KEY:
                raise ValueError("OpenAI APIキーが設定されていません")
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
            
            # Pineconeの初期化
            if not PINECONE_API_KEY:
                raise ValueError("Pinecone APIキーが設定されていません")
            if not PINECONE_INDEX_NAME:
                raise ValueError("Pineconeインデックス名が設定されていません")
            
            self.pc = Pinecone(api_key=PINECONE_API_KEY)
            
            # インデックスの存在確認と初期化
            self._initialize_index()
            
            # インデックスの次元数を取得
            stats = self.index.describe_index_stats()
            self.dimension = stats.dimension
            print(f"インデックスの次元数: {self.dimension}")
            
        except Exception as e:
            raise Exception(f"Pineconeサービスの初期化に失敗しました: {str(e)}")

    def _initialize_index(self):
        """インデックスの初期化"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # インデックス名の確認
                if not PINECONE_INDEX_NAME:
                    raise ValueError("インデックス名が設定されていません。Streamlit Cloudのシークレットを確認してください。")
                print(f"使用するインデックス名: {PINECONE_INDEX_NAME}")
                
                # インデックスの存在確認
                existing_indexes = self.pc.list_indexes()
                existing_index_names = [index["name"] for index in existing_indexes]
                print(f"既存のインデックス: {existing_index_names}")
                
                if PINECONE_INDEX_NAME not in existing_index_names:
                    raise ValueError(f"インデックス '{PINECONE_INDEX_NAME}' が見つかりません。Streamlit Cloudのシークレットを確認してください。")
                
                # 既存のインデックスの設定を確認
                index = self.pc.Index(PINECONE_INDEX_NAME)
                stats = index.describe_index_stats()
                print(f"現在のインデックス設定:")
                print(f"- 次元数: {stats.dimension}")
                print(f"- メトリック: {stats.metric}")
                print(f"- ベクトル数: {stats.total_vector_count}")
                
                # 次元数が3072でない場合は警告を表示
                if stats.dimension != 3072:
                    print(f"警告: インデックスの次元数が3072と異なります（現在: {stats.dimension}）")
                    print("新しい埋め込みモデル（text-embedding-3-large）との互換性に問題が発生する可能性があります")
                
                # インデックスの取得
                self.index = index
                break
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"インデックスの初期化に失敗しました（試行 {attempt + 1}/{max_retries}）: {str(e)}")
                    print(f"{retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise Exception(f"インデックスの初期化に失敗しました（最大試行回数到達）: {str(e)}")

    def get_embedding(self, text: str) -> List[float]:
        """テキストの埋め込みベクトルを取得"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-large",  # 新しいモデルを使用
                    input=text,
                    encoding_format="float"  # 明示的にfloat形式を指定
                )
                return response.data[0].embedding
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"埋め込みベクトルの生成に失敗しました（試行 {attempt + 1}/{max_retries}）: {str(e)}")
                    print(f"{retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise Exception(f"埋め込みベクトルの生成に失敗しました（最大試行回数到達）: {str(e)}")

    def upload_chunks(self, chunks: List[Dict[str, Any]], namespace: str = None, batch_size: int = BATCH_SIZE) -> None:
        """チャンクをPineconeにアップロード"""
        if not chunks:
            print("アップロードするチャンクがありません")
            return

        try:
            total_chunks = len(chunks)
            print(f"アップロード開始: 合計{total_chunks}件のチャンク")
            
            # チャンクをバッチに分割
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                batch_num = i // batch_size + 1
                print(f"\nバッチ {batch_num} を処理中... ({len(batch)}件)")
                
                # バッチ内の各チャンクの埋め込みベクトルを取得
                vectors = []
                retry_chunks = []  # 再試行が必要なチャンク
                
                for j, chunk in enumerate(batch, 1):
                    try:
                        print(f"  チャンク {j}/{len(batch)} の埋め込みベクトルを生成中...")
                        
                        # テキスト内容と回答例を結合してベクトル化
                        main_text = chunk["text"]
                        answer_examples = chunk.get("metadata", {}).get("answer_examples", [])
                        
                        # 回答例をテキストに結合（検索時の優先度を向上）
                        combined_text = main_text
                        
                        if answer_examples:
                            # 回答例を文字列に変換（既に文字列の場合はそのまま使用）
                            if isinstance(answer_examples[0], dict):
                                # 辞書形式の場合は自然な形式に変換
                                answers_text = "\n".join([
                                    f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}"
                                    for qa in answer_examples
                                ])
                            else:
                                # 文字列の場合はそのまま結合
                                answers_text = "\n".join(answer_examples)
                            
                            # 回答例をメインテキストの前に配置（検索時の優先度を向上）
                            combined_text = f"回答例:\n{answers_text}\n\n{combined_text}"
                        
                        vector = self.get_embedding(combined_text)
                        
                        # メタデータの設定（CSVファイルのメタデータを含める）
                        metadata = {
                            "text": chunk["text"],
                            "filename": chunk.get("filename", ""),
                            "chunk_id": chunk.get("chunk_id", ""),
                            "main_category": chunk.get("metadata", {}).get("main_category", ""),
                            "sub_category": chunk.get("metadata", {}).get("sub_category", ""),
                            "city": chunk.get("metadata", {}).get("city", ""),
                            "created_date": chunk.get("metadata", {}).get("created_date", ""),
                            "upload_date": chunk.get("metadata", {}).get("upload_date", ""),
                            "source": chunk.get("metadata", {}).get("source", ""),
                            "answer_examples": self._convert_answer_examples_to_strings(chunk.get("metadata", {}).get("answer_examples", [])),
                            "verified": chunk.get("metadata", {}).get("verified", False),
                            "timestamp_type": chunk.get("metadata", {}).get("timestamp_type", "static"),
                            "valid_for": chunk.get("metadata", {}).get("valid_for", []),
                            "latitude": chunk.get("metadata", {}).get("latitude") if chunk.get("metadata", {}).get("latitude") is not None else 0.0,
                            "longitude": chunk.get("metadata", {}).get("longitude") if chunk.get("metadata", {}).get("longitude") is not None else 0.0,
                            "address": chunk.get("metadata", {}).get("address", ""),
                            # CSVファイルのメタデータ
                            "facility_name": chunk.get("metadata", {}).get("facility_name", ""),
                            "walking_distance": chunk.get("metadata", {}).get("walking_distance", 0),
                            "walking_minutes": chunk.get("metadata", {}).get("walking_minutes", 0),
                            "straight_distance": chunk.get("metadata", {}).get("straight_distance", 0),
                            # 検索用の結合テキストも保存
                            "search_text": combined_text
                        }
                        
                        # デバッグ情報の表示
                        print(f"  チャンク {chunk['id']} のメタデータ:")
                        print(f"    - 大カテゴリ: {metadata['main_category']}")
                        print(f"    - 中カテゴリ: {metadata['sub_category']}")
                        print(f"    - 市区町村: {metadata['city']}")
                        print(f"    - ソース: {metadata['source']}")
                        print(f"    - 回答例: {metadata['answer_examples']}")
                        print(f"    - 検証済み: {metadata['verified']}")
                        print(f"    - 更新タイプ: {metadata['timestamp_type']}")
                        print(f"    - 作成年度: {metadata['valid_for']}")
                        print(f"    - 緯度: {metadata['latitude']}")
                        print(f"    - 経度: {metadata['longitude']}")
                        print(f"    - 住所: {metadata['address']}")
                        
                        # ベクトル化に使用されたテキストの情報を表示
                        print(f"  ベクトル化に使用されたテキスト:")
                        print(f"    - 元のテキスト長: {len(main_text)}文字")
                        print(f"    - 回答例数: {len(answer_examples)}個")
                        print(f"    - 結合テキスト長: {len(combined_text)}文字")
                        print(f"    - 結合テキスト（最初の200文字）: {combined_text[:200]}...")
                        
                        # デバッグ情報の表示
                        print(f"  メタデータ: {json.dumps(metadata, ensure_ascii=False)}")
                        
                        vectors.append({
                            "id": chunk["id"],
                            "values": vector,
                            "metadata": metadata
                        })
                    except Exception as e:
                        print(f"  チャンク {chunk['id']} の処理中にエラーが発生しました: {str(e)}")
                        retry_chunks.append(chunk)
                        continue
                
                if vectors:
                    max_retries = 3
                    retry_delay = 2
                    
                    for attempt in range(max_retries):
                        try:
                            # バッチをアップロード（namespaceを指定）
                            print(f"  {len(vectors)}件のベクトルをアップロード中...")
                            self.index.upsert(vectors=vectors, namespace=namespace)
                            print(f"  バッチ {batch_num} のアップロードが完了しました")
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                print(f"  バッチ {batch_num} のアップロードに失敗しました（試行 {attempt + 1}/{max_retries}）: {str(e)}")
                                print(f"  {retry_delay}秒後に再試行します...")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                raise Exception(f"バッチ {batch_num} のアップロードに失敗しました（最大試行回数到達）: {str(e)}")
                
                # 失敗したチャンクを再試行
                if retry_chunks:
                    print(f"\n失敗したチャンク {len(retry_chunks)}件 を再試行します...")
                    self.upload_chunks(retry_chunks, namespace, batch_size)
            
            print("\nアップロード完了")
            
        except Exception as e:
            raise Exception(f"チャンクのアップロードに失敗しました: {str(e)}")

    def query(self, query_text: str, namespace: str = None, top_k: int = DEFAULT_TOP_K, similarity_threshold: float = SIMILARITY_THRESHOLD) -> Dict[str, Any]:
        """クエリに基づいて類似チャンクを検索"""
        max_retries = 3
        retry_delay = 1
        
        # 設定画面で変更された値を取得（引数で渡された値が優先）
        if similarity_threshold == SIMILARITY_THRESHOLD:  # デフォルト値が使用されている場合
            similarity_threshold = st.session_state.get("similarity_threshold", SIMILARITY_THRESHOLD)
        
        for attempt in range(max_retries):
            try:
                # クエリのベクトル化
                query_vector = self.get_embedding(query_text)
                print(f"検索クエリ: {query_text}")
                print(f"類似度しきい値: {similarity_threshold}")
                print(f"取得する候補数: {top_k}")
                
                # 検索を実行
                results = self.index.query(
                    vector=query_vector,
                    top_k=top_k,  # 必要な数だけ取得
                    include_metadata=True,
                    namespace=namespace  # namespaceを指定
                )
                
                print(f"取得した候補数: {len(results.matches)}")
                if results.matches:
                    print("候補のスコア:")
                    for match in results.matches:
                        print(f"スコア: {match.score:.3f}")
                
                # 類似度でフィルタリング（しきい値未満は除外）
                filtered_matches = [
                    match for match in results.matches
                    if match.score >= similarity_threshold
                ]
                
                print(f"しきい値({similarity_threshold})以上の候補数: {len(filtered_matches)}")
                if filtered_matches:
                    print("採用された候補のスコア:")
                    for match in filtered_matches:
                        print(f"スコア: {match.score:.3f}, テキスト: {match.metadata['text'][:100]}...")
                else:
                    print("しきい値以上の候補が見つかりませんでした。")
                
                return {
                    "matches": filtered_matches,
                    "total_matches": len(results.matches),
                    "filtered_matches": len(filtered_matches)
                }
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"検索クエリの実行に失敗しました（試行 {attempt + 1}/{max_retries}）: {str(e)}")
                    print(f"{retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise Exception(f"検索クエリの実行に失敗しました（最大試行回数到達）: {str(e)}")

    def get_index_stats(self, namespace: str = None) -> Dict[str, Any]:
        """インデックスの統計情報を取得"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                stats = self.index.describe_index_stats()
                # 辞書形式で返す
                return {
                    "total_vector_count": stats.total_vector_count,
                    "namespaces": stats.namespaces,
                    "dimension": stats.dimension,
                    "index_fullness": stats.index_fullness,
                    "metric": stats.metric
                }
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"統計情報の取得に失敗しました（試行 {attempt + 1}/{max_retries}）: {str(e)}")
                    print(f"{retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise Exception(f"統計情報の取得に失敗しました（最大試行回数到達）: {str(e)}")

    def clear_index(self, namespace: str = None) -> None:
        """インデックスをクリア"""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            print(f"インデックスをクリアしました（namespace: {namespace if namespace else 'default'}）")
        except Exception as e:
            raise Exception(f"インデックスのクリアに失敗しました: {str(e)}")

    def get_index_data(self) -> List[Dict]:
        """インデックスのデータを取得"""
        try:
            # インデックスの統計情報を取得
            stats = self.index.describe_index_stats()
            
            # インデックスが空の場合は空のリストを返す
            if stats.total_vector_count == 0:
                return []
            
            # 全ベクトルのIDを取得
            all_vectors = []
            for namespace in stats.namespaces:
                # ダミーベクトルを作成（全要素が0のベクトル）
                dummy_vector = [0.0] * self.dimension
                
                # クエリを使用してベクトルIDを取得
                results = self.index.query(
                    vector=dummy_vector,
                    top_k=10000,  # 十分大きな数を指定
                    include_metadata=True,
                    namespace=namespace
                )
                
                if results.matches:
                    # 取得したIDを使用してベクトルを取得
                    vector_ids = [match.id for match in results.matches]
                    fetch_results = self.index.fetch(
                        ids=vector_ids,
                        namespace=namespace
                    )
                    if fetch_results.vectors:
                        all_vectors.extend(fetch_results.vectors.values())
            
            # メタデータを抽出
            data = []
            for vector in all_vectors:
                if 'metadata' in vector:
                    metadata = vector.metadata
                    # 必要なメタデータを抽出
                    item = {
                        'filename': metadata.get('filename', ''),
                        'chunk_id': metadata.get('chunk_id', ''),
                        'main_category': metadata.get('main_category', ''),
                        'sub_category': metadata.get('sub_category', ''),
                        'city': metadata.get('city', ''),
                        'created_date': metadata.get('created_date', ''),
                        'upload_date': metadata.get('upload_date', ''),
                        'source': metadata.get('source', '')
                    }
                    data.append(item)
            
            return data
        except Exception as e:
            raise Exception(f"インデックスデータの取得に失敗しました: {str(e)}")

    def get_stats(self, namespace: str = None) -> dict:
        """指定されたnamespaceの統計情報を取得"""
        try:
            stats = self.index.describe_index_stats()
            if namespace:
                return stats.namespaces.get(namespace, {})
            return stats
        except Exception as e:
            raise Exception(f"統計情報の取得に失敗しました: {str(e)}")

    def list_vectors(self, namespace: str = None, limit: int = 1000) -> list:
        """指定されたnamespaceのベクトルを取得"""
        try:
            # インデックスの統計情報を取得
            stats = self.index.describe_index_stats()
            
            # 指定されたnamespaceが存在しない場合は空のリストを返す
            if namespace and namespace not in stats.namespaces:
                return []
            
            # ダミーベクトルを作成（全要素が0のベクトル）
            dummy_vector = [0.0] * self.dimension
            
            # クエリを使用してベクトルIDを取得
            results = self.index.query(
                vector=dummy_vector,
                top_k=limit,  # 指定された制限数を使用
                include_metadata=True,
                namespace=namespace
            )
            
            if not results.matches:
                return []
            
            # 取得したIDを使用してベクトルを取得
            vector_ids = [match.id for match in results.matches]
            fetch_results = self.index.fetch(
                ids=vector_ids,
                namespace=namespace
            )
            
            # 結果を制限
            vectors = list(fetch_results.vectors.values())[:limit] if fetch_results.vectors else []
            
            return vectors
        except Exception as e:
            raise Exception(f"ベクトルの取得に失敗しました: {str(e)}")

    def get_by_id(self, vector_id: str, namespace: str = None) -> Dict[str, Any]:
        """指定されたIDのベクトルを取得"""
        try:
            # ベクトルを取得
            result = self.index.fetch(ids=[vector_id], namespace=namespace)
            
            if not result.vectors:
                return None
                
            # 最初のベクトルを取得
            vector = result.vectors[vector_id]
            
            # 結果を整形
            return {
                "id": vector.id,
                "values": vector.values,
                "metadata": vector.metadata,
                "text": vector.metadata.get("text", "")
            }
        except Exception as e:
            print(f"ベクトルの取得中にエラーが発生しました: {str(e)}")
            return None

    def _convert_answer_examples_to_strings(self, answer_examples: List[Dict]) -> List[str]:
        """answer_examplesを文字列のリストに変換"""
        if not answer_examples:
            return []
        
        converted_examples = []
        for example in answer_examples:
            if isinstance(example, dict):
                # 辞書の場合は "質問: 内容, 回答: 内容" の形式に変換
                question = example.get('question', '')
                answer = example.get('answer', '')
                if question and answer:
                    converted_examples.append(f"質問: {question}, 回答: {answer}")
                elif question:
                    converted_examples.append(f"質問: {question}")
                elif answer:
                    converted_examples.append(f"回答: {answer}")
            else:
                # 辞書以外の場合は文字列に変換
                converted_examples.append(str(example))
        
        return converted_examples

    def _convert_answer_examples_from_strings(self, answer_examples: List[str]) -> List[Dict]:
        """文字列のリストからanswer_examplesを辞書のリストに変換"""
        if not answer_examples:
            return []
        
        converted_examples = []
        for example in answer_examples:
            if isinstance(example, str):
                # "質問: 内容, 回答: 内容" の形式から辞書に変換
                if "質問:" in example and "回答:" in example:
                    try:
                        # 質問と回答を抽出
                        parts = example.split(", 回答: ")
                        if len(parts) == 2:
                            question_part = parts[0].replace("質問: ", "")
                            answer_part = parts[1]
                            converted_examples.append({
                                "question": question_part,
                                "answer": answer_part
                            })
                        else:
                            # 形式が異なる場合はそのまま文字列として保存
                            converted_examples.append({"question": "", "answer": example})
                    except:
                        # パースに失敗した場合はそのまま文字列として保存
                        converted_examples.append({"question": "", "answer": example})
                else:
                    # 質問と回答の形式でない場合は回答として保存
                    converted_examples.append({"question": "", "answer": example})
            else:
                # 文字列以外の場合はそのまま
                converted_examples.append(example)
        
        return converted_examples 