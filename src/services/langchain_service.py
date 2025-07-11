from typing import List, Dict, Any, Tuple
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, AIMessage, SystemMessage
import os
import tiktoken
from openai import OpenAI
from src.config.settings import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    OPENAI_API_KEY,
    DEFAULT_TOP_K,
    SIMILARITY_THRESHOLD,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_RESPONSE_TEMPLATE
)
import streamlit as st
from src.services.advanced_search_service import AdvancedSearchService

class LangChainService:
    def __init__(self, callback_manager=None):
        """LangChainサービスの初期化"""
        # OpenAIクライアントの初期化
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        # チャットモデルの初期化
        self.llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model_name="gpt-4o-mini",
            temperature=0.85,
            callback_manager=callback_manager
        )
        
        # 埋め込みモデルの初期化
        self.embeddings = OpenAIEmbeddings(
            api_key=OPENAI_API_KEY,
            model="text-embedding-3-large",
            dimensions=3072
        )
        
        # トークンカウンターの初期化
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        
        # PineconeのAPIキーを環境変数に設定
        os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
        
        # Pineconeベクトルストアの初期化
        self.vectorstore = PineconeVectorStore.from_existing_index(
            index_name=PINECONE_INDEX_NAME,
            embedding=self.embeddings
        )
        
        # チャット履歴の初期化
        self.message_history = ChatMessageHistory()
        
        # デフォルトのプロンプトテンプレート
        self.system_prompt = DEFAULT_SYSTEM_PROMPT
        self.response_template = DEFAULT_RESPONSE_TEMPLATE
        
        # 高度な検索サービスの初期化
        from src.services.pinecone_service import PineconeService
        pinecone_service = PineconeService()
        self.advanced_search = AdvancedSearchService(pinecone_service)
        
        # 検索モードの設定（デフォルトは高度な検索）
        self.use_advanced_search = True

    def check_api_usage(self):
        """OpenAI APIの使用状況を確認"""
        try:
            # 使用状況の取得
            # usage = self.openai_client.usage.retrieve()
            
            # 使用状況の表示
            print("\n=== OpenAI API Usage ===")
            # print(f"Total Tokens: {usage.total_tokens}")
            # print(f"Total Cost: ${usage.total_cost:.4f}")
            # print(f"Usage Period: {usage.period}")
            
            # クォータ情報の取得
            # quota = self.openai_client.quota.retrieve()
            print("\n=== OpenAI API Quota ===")
            # print(f"Total Quota: ${quota.total_quota:.2f}")
            # print(f"Used Quota: ${quota.used_quota:.2f}")
            # print(f"Remaining Quota: ${quota.remaining_quota:.2f}")
            # print(f"Quota Period: {quota.period}")
            
            # 警告メッセージ
            # if quota.remaining_quota < 1.0:
            #     print("\n⚠️ Warning: Remaining quota is less than $1.0")
            # if quota.remaining_quota < 0.1:
            #     print("🚨 Critical: Remaining quota is less than $0.1")
                
        except Exception as e:
            error_message = str(e)
            print(f"\n❌ Error checking API usage: {error_message}")
            
            if "insufficient_quota" in error_message:
                print("\n🚨 Critical: API quota has been exceeded!")
                print("Please check your OpenAI API key and billing settings.")
                print("You can check your usage and quota at: https://platform.openai.com/account/usage")
            elif "object has no attribute" in error_message:
                print("\n⚠️ Warning: Unable to check API usage. This might be due to API changes or permissions.")
                print("Please check your OpenAI API key and ensure it has the necessary permissions.")
            else:
                print("\n⚠️ Warning: Unable to check API usage. Please verify your API key and permissions.")

    def count_tokens(self, text: str) -> int:
        """テキストのトークン数をカウント"""
        return len(self.encoding.encode(text))

    def get_relevant_context(self, query: str, top_k: int = DEFAULT_TOP_K) -> Tuple[str, List[Dict[str, Any]], int]:
        """クエリに関連する文脈を取得（高度な検索を使用）"""
        try:
            # 高度な検索を使用するかどうかを確認
            if self.use_advanced_search:
                return self._get_context_with_advanced_search(query, top_k)
            else:
                return self._get_context_with_basic_search(query, top_k)
                
        except Exception as e:
            error_message = str(e)
            if "insufficient_quota" in error_message:
                print("\n🚨 Critical: API quota has been exceeded!")
                print("Please check your OpenAI API key and billing settings.")
                print("You can check your usage and quota at: https://platform.openai.com/account/usage")
                return "", [{
                    "エラー": True,
                    "エラーメッセージ": "API quota has been exceeded",
                    "エラータイプ": "API Quota Error",
                    "推奨アクション": "Please update your API key in Streamlit Cloud settings"
                }], 0
            else:
                print(f"\n❌ Error in get_relevant_context: {error_message}")
                return "", [{
                    "エラー": True,
                    "エラーメッセージ": error_message,
                    "エラータイプ": "Unknown Error"
                }], 0

    def _get_context_with_advanced_search(self, query: str, top_k: int) -> Tuple[str, List[Dict[str, Any]], int]:
        """高度な検索を使用してコンテキストを取得"""
        print(f"\n=== 高度な検索を使用 ===")
        
        # マルチステップ検索を実行
        search_results = self.advanced_search.multi_step_search(query)
        
        # 検索分析情報を取得
        analytics = self.advanced_search.get_search_analytics(search_results)
        print(f"検索分析: {analytics}")
        
        # 結果を処理
        matches = search_results.get("matches", [])
        
        if not matches:
            return "", [], 0
        
        # コンテキストテキストを作成
        context_text = "\n".join([match.metadata.get("text", "") for match in matches])
        
        # 検索詳細情報を作成
        search_details = []
        for match in matches:
            detail = {
                "スコア": round(getattr(match, 'adjusted_score', match.score), 4),
                "元のスコア": round(match.score, 4),
                "テキスト": match.metadata.get("text", "")[:100] + "...",
                "メタデータ": match.metadata,
                "クエリバリエーション": getattr(match, 'query_variation', 'unknown'),
                "クエリ順序": getattr(match, 'query_index', 0),
                "チャンクID": match.metadata.get("chunk_id", "不明"),
                "回答例": match.metadata.get("answer_examples", []),
                "検証済み": match.metadata.get("verified", False),
                "更新タイプ": match.metadata.get("timestamp_type", "static"),
                "作成年度": match.metadata.get("valid_for", []),
                "位置情報": match.metadata.get("location", {})
            }
            search_details.append(detail)
        
        # コンテキストのトークン数をカウント
        context_tokens = self.count_tokens(context_text)
        print(f"コンテキストのトークン数: {context_tokens}")
        
        return context_text, search_details, context_tokens

    def _get_context_with_basic_search(self, query: str, top_k: int) -> Tuple[str, List[Dict[str, Any]], int]:
        """基本的な検索を使用してコンテキストを取得（従来の方法）"""
        print(f"\n=== 基本的な検索を使用 ===")
        
        # 設定画面で変更されたしきい値を取得（デフォルトはSIMILARITY_THRESHOLD）
        similarity_threshold = st.session_state.get("similarity_threshold", SIMILARITY_THRESHOLD)
        
        # クエリのトークン数をカウント
        query_tokens = self.count_tokens(query)
        print(f"クエリのトークン数: {query_tokens}")
        print(f"使用する類似度しきい値: {similarity_threshold}")
        
        # クエリのベクトル化
        query_vector = self.embeddings.embed_query(query)
        
        # 検索を実行
        docs = self.vectorstore.similarity_search_with_score(query, k=top_k)
        
        # メタデータを簡略化して保持
        simplified_docs = []
        for doc in docs:
            # メタデータを簡略化
            simplified_metadata = {}
            for key, value in doc[0].metadata.items():
                if isinstance(value, str):
                    # メタデータの値を短くする（最大100文字）
                    simplified_metadata[key] = value[:100] + "..." if len(value) > 100 else value
            
            # テキストを短くする（最大500文字）
            content = doc[0].page_content
            if len(content) > 500:
                content = content[:500] + "..."
            
            # 簡略化したドキュメントを作成
            simplified_doc = {
                "content": content,
                "metadata": simplified_metadata,
                "score": doc[1]
            }
            simplified_docs.append(simplified_doc)
        
        # スコアでフィルタリング（しきい値未満は除外）
        filtered_docs = [
            doc for doc in simplified_docs
            if doc["score"] >= similarity_threshold
        ]
        
        print(f"取得した候補数: {len(simplified_docs)}")
        print(f"しきい値({similarity_threshold})以上の候補数: {len(filtered_docs)}")
        if filtered_docs:
            print("採用された候補のスコア:")
            for doc in filtered_docs:
                print(f"スコア: {doc['score']:.3f}, テキスト: {doc['content'][:100]}...")
        else:
            print("しきい値以上の候補が見つかりませんでした。")
        
        # コンテキストテキストを作成（メタデータを含めない）
        if filtered_docs:
            context_text = "\n".join([doc["content"] for doc in filtered_docs])
        else:
            # 関連情報が見つからない場合は空文字列を返す
            context_text = ""
        
        # コンテキストのトークン数をカウント
        context_tokens = self.count_tokens(context_text)
        print(f"コンテキストのトークン数: {context_tokens}")
        
        search_details = []
        for doc in filtered_docs:
            detail = {
                "スコア": round(doc["score"], 4),
                "テキスト": doc["content"][:100] + "...",
                "メタデータ": doc["metadata"],
                "チャンクID": doc["metadata"].get("chunk_id", "不明"),
                "回答例": doc["metadata"].get("answer_examples", []),
                "検証済み": doc["metadata"].get("verified", False),
                "更新タイプ": doc["metadata"].get("timestamp_type", "static"),
                "作成年度": doc["metadata"].get("valid_for", []),
                "位置情報": doc["metadata"].get("location", {})
            }
            search_details.append(detail)
        
        return context_text, search_details, context_tokens

    def set_search_mode(self, use_advanced: bool = True):
        """検索モードを設定"""
        self.use_advanced_search = use_advanced
        print(f"検索モードを {'高度な検索' if use_advanced else '基本的な検索'} に設定しました")

    def get_response(self, query: str, system_prompt: str = None, response_template: str = None, property_info: str = None, chat_history: list = None) -> Tuple[str, Dict[str, Any]]:
        """クエリに対する応答を生成"""
        try:
            # プロンプトの設定
            system_prompt = system_prompt or self.system_prompt
            response_template = response_template or self.response_template
            
            # メッセージリストの作成
            messages = [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("system", "参照文脈:\n{context}")
            ]
            
            # 物件情報がある場合は追加
            if property_info:
                messages.append(("system", "物件情報:\n{property_info}"))
            
            # ユーザー入力の追加
            messages.append(("human", "{input}"))
            
            # プロンプトテンプレートの設定
            prompt = ChatPromptTemplate.from_messages(messages)
            
            # チェーンの初期化
            chain = prompt | self.llm
            
            # 関連する文脈を取得
            context, search_details, context_tokens = self.get_relevant_context(query)
            
            # 参照文脈が空の場合の処理
            if not context.strip():
                # 参照文脈が空の場合は、AIに明確な指示を与える
                context = "【重要】参照文脈に情報がありません。この場合、絶対に推測や一般的な知識で回答せず、情報がないことを明確に伝えてください。"
                print("⚠️ 参照文脈が空のため、情報がないことを明確に伝えるよう指示します")
            
            # チャット履歴を設定
            if chat_history:
                self.message_history.messages = []
                for role, content in chat_history:
                    if role == "human":
                        self.message_history.add_user_message(content)
                    elif role == "ai":
                        self.message_history.add_ai_message(content)
            
            # 会話履歴を最適化
            self.optimize_chat_history()
            
            # プロンプトのトークン数をカウント
            prompt_tokens = self.count_tokens(system_prompt)
            print(f"システムプロンプトのトークン数: {prompt_tokens}")
            
            # チャット履歴のトークン数をカウント
            history_tokens = sum(self.count_tokens(msg.content) for msg in self.message_history.messages)
            print(f"チャット履歴のトークン数: {history_tokens}")
            
            # デバッグ出力：送信されるすべてのテキストを表示
            print("\n=== 送信されるテキスト ===")
            print("\n--- システムプロンプト ---")
            print(system_prompt)
            print("\n--- チャット履歴 ---")
            for msg in self.message_history.messages:
                print(f"\n[{msg.type}]: {msg.content}")
            print("\n--- 参照文脈 ---")
            print(context)
            if property_info:
                print("\n--- 物件情報 ---")
                print(property_info)
            print("\n--- ユーザー入力 ---")
            print(query)
            
            # 応答を生成
            response = chain.invoke({
                "chat_history": self.message_history.messages,
                "context": context,
                "property_info": property_info or "物件情報はありません。",
                "input": query
            })
            
            # 応答のトークン数をカウント
            response_tokens = self.count_tokens(response.content)
            print(f"応答のトークン数: {response_tokens}")
            
            # メッセージを履歴に追加
            self.message_history.add_user_message(query)
            self.message_history.add_ai_message(response.content)
            
            # 詳細情報の作成
            details = {
                "モデル": "gpt-4o-mini",
                "会話履歴": "有効",
                "トークン数": {
                    "システムプロンプト": prompt_tokens,
                    "チャット履歴": history_tokens,
                    "参照文脈": context_tokens,
                    "物件情報": self.count_tokens(property_info) if property_info else 0,
                    "ユーザー入力": self.count_tokens(query),
                    "合計": prompt_tokens + history_tokens + context_tokens + (self.count_tokens(property_info) if property_info else 0)
                },
                "送信テキスト": {
                    "システムプロンプト": system_prompt,
                    "チャット履歴": [{"type": msg.type, "content": msg.content} for msg in self.message_history.messages],
                    "参照文脈": context,
                    "参照文脈の詳細": search_details,
                    "物件情報": property_info,
                    "ユーザー入力": query
                }
            }
            
            return response.content, details
            
        except Exception as e:
            error_message = str(e)
            if "insufficient_quota" in error_message:
                error_response = "申し訳ありません。APIの利用制限に達しました。\n\n" + \
                               "以下の手順で対応をお願いします：\n" + \
                               "1. OpenAIのアカウント設定を確認してください\n" + \
                               "2. 新しいAPIキーを取得してください\n" + \
                               "3. Streamlit Cloudの設定で新しいAPIキーを更新してください\n\n" + \
                               "詳細はこちらで確認できます：\n" + \
                               "https://platform.openai.com/account/usage"
            else:
                error_response = f"エラーが発生しました：{error_message}"
            
            error_details = {
                "エラー": True,
                "エラーメッセージ": error_message,
                "エラータイプ": "API Quota Error" if "insufficient_quota" in error_message else "Unknown Error"
            }
            
            return error_response, error_details

    def optimize_chat_history(self, max_tokens: int = 10000) -> None:
        """会話履歴を最適化し、重要なメッセージのみを保持"""
        if not self.message_history.messages:
            return

        # システムプロンプトとコンテキスト用のトークン数を確保（約4000トークン）
        reserved_tokens = 4000
        available_tokens = max_tokens - reserved_tokens

        # 現在のトークン数を計算
        current_tokens = sum(self.count_tokens(msg.content) for msg in self.message_history.messages)
        
        # トークン数が制限を超えていない場合は何もしない
        if current_tokens <= available_tokens:
            return

        # メッセージを重要度で分類
        important_messages = []
        other_messages = []
        
        # システムメッセージを保持
        for msg in self.message_history.messages:
            if isinstance(msg, SystemMessage):
                important_messages.append(msg)
                continue
            other_messages.append(msg)

        # 最新の1メッセージのみを保持
        if other_messages:
            important_messages.append(other_messages[-1])
            other_messages = other_messages[:-1]

        # 重要メッセージのトークン数を計算
        important_tokens = sum(self.count_tokens(msg.content) for msg in important_messages)
        
        # 残りのトークン数
        remaining_tokens = available_tokens - important_tokens

        # 残りのトークン数に基づいて、他のメッセージを追加
        # メッセージを長さでソート（短いものから）
        other_messages.sort(key=lambda x: self.count_tokens(x.content))
        
        for msg in other_messages:
            msg_tokens = self.count_tokens(msg.content)
            if msg_tokens <= remaining_tokens:
                important_messages.insert(0, msg)  # 先頭に追加
                remaining_tokens -= msg_tokens
            else:
                break

        # 最適化されたメッセージで履歴を更新
        self.message_history.messages = important_messages

        # デバッグ情報の出力
        final_tokens = sum(self.count_tokens(msg.content) for msg in self.message_history.messages)
        print(f"\n=== Chat History Optimization ===")
        print(f"Original tokens: {current_tokens}")
        print(f"Final tokens: {final_tokens}")
        print(f"Messages kept: {len(self.message_history.messages)}")
        print(f"Available tokens: {available_tokens}")
        print(f"Remaining tokens: {remaining_tokens}")

    def clear_memory(self):
        """会話メモリをクリア"""
        self.message_history.clear() 