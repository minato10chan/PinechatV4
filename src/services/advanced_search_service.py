from typing import List, Dict, Any, Tuple
from openai import OpenAI
import re
import json
from src.services.pinecone_service import PineconeService
from src.config.settings import OPENAI_API_KEY, SIMILARITY_THRESHOLD
import streamlit as st

class AdvancedSearchService:
    def __init__(self, pinecone_service: PineconeService):
        """高度な検索サービスの初期化"""
        self.pinecone_service = pinecone_service
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        # 検索設定
        self.base_similarity_threshold = SIMILARITY_THRESHOLD
        self.max_query_variations = 5
        self.max_results_per_query = 10
        
    def extract_keywords(self, query: str) -> List[str]:
        """クエリから重要なキーワードを抽出"""
        try:
            # OpenAIを使用してキーワード抽出
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "与えられた質問から重要なキーワードを抽出してください。地域情報や施設情報に関連する重要な単語のみを抽出し、JSON形式で返してください。"},
                    {"role": "user", "content": f"質問: {query}\n\nキーワードを抽出してください。"}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            keywords = result.get("keywords", [])
            
            # 基本的なキーワードも追加
            basic_keywords = self._extract_basic_keywords(query)
            all_keywords = list(set(keywords + basic_keywords))
            
            return all_keywords
            
        except Exception as e:
            print(f"キーワード抽出エラー: {str(e)}")
            return self._extract_basic_keywords(query)
    
    def _extract_basic_keywords(self, query: str) -> List[str]:
        """基本的なキーワード抽出（フォールバック）"""
        # 日本語の重要なキーワードパターン
        patterns = [
            r'小学校|中学校|高校|大学|学校',
            r'保育園|幼稚園|学童',
            r'病院|クリニック|診療所',
            r'スーパー|コンビニ|ショッピング',
            r'駅|バス停|交通',
            r'公園|遊び場|施設',
            r'近く|周辺|地域|エリア',
            r'川越|さいたま|埼玉|東京|神奈川|千葉'
        ]
        
        keywords = []
        for pattern in patterns:
            matches = re.findall(pattern, query)
            keywords.extend(matches)
        
        return list(set(keywords))
    
    def generate_query_variations(self, query: str, keywords: List[str]) -> List[str]:
        """クエリのバリエーションを生成"""
        variations = [query]  # 元のクエリを最初に追加
        
        try:
            # OpenAIを使用してクエリバリエーションを生成
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "与えられた質問の異なる表現を生成してください。地域情報や施設情報の検索に適した形で、同じ意味を表す異なる表現を考えてください。"},
                    {"role": "user", "content": f"質問: {query}\nキーワード: {', '.join(keywords)}\n\n異なる表現を生成してください。"}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            variations.extend(result.get("variations", []))
            
        except Exception as e:
            print(f"クエリバリエーション生成エラー: {str(e)}")
            # フォールバック: キーワードベースのバリエーション
            variations.extend(self._generate_basic_variations(query, keywords))
        
        # 重複を除去して制限数まで
        unique_variations = list(dict.fromkeys(variations))[:self.max_query_variations]
        return unique_variations
    
    def _generate_basic_variations(self, query: str, keywords: List[str]) -> List[str]:
        """基本的なクエリバリエーション生成"""
        variations = []
        
        # キーワードベースのバリエーション
        for keyword in keywords[:3]:  # 上位3つのキーワードのみ使用
            if keyword in query:
                # キーワードを強調したバリエーション
                variations.append(f"{keyword}について教えて")
                variations.append(f"{keyword}の情報を教えて")
        
        # 一般的なパターン
        if "近く" in query or "周辺" in query:
            variations.append(query.replace("近く", "周辺"))
            variations.append(query.replace("周辺", "近く"))
        
        return variations
    
    def multi_step_search(self, query: str, namespace: str = None) -> Dict[str, Any]:
        """マルチステップ検索を実行"""
        print(f"\n=== マルチステップ検索開始 ===")
        print(f"クエリ: {query}")
        
        # ステップ1: キーワード抽出
        print("\nステップ1: キーワード抽出")
        keywords = self.extract_keywords(query)
        print(f"抽出されたキーワード: {keywords}")
        
        # ステップ2: クエリバリエーション生成
        print("\nステップ2: クエリバリエーション生成")
        query_variations = self.generate_query_variations(query, keywords)
        print(f"生成されたクエリバリエーション: {query_variations}")
        
        # ステップ3: 複数クエリでの検索
        print("\nステップ3: 複数クエリでの検索")
        all_results = []
        
        for i, variation in enumerate(query_variations):
            print(f"\nクエリバリエーション {i+1}: {variation}")
            
            # 動的しきい値調整
            similarity_threshold = self.base_similarity_threshold
            if i > 0:  # 2番目以降のクエリはしきい値を下げる
                similarity_threshold = max(0.2, similarity_threshold - 0.1)
            
            try:
                results = self.pinecone_service.query(
                    query_text=variation,
                    namespace=namespace,
                    top_k=self.max_results_per_query,
                    similarity_threshold=similarity_threshold
                )
                
                # 結果にクエリ情報を追加
                for match in results["matches"]:
                    match.query_variation = variation
                    match.query_index = i
                
                all_results.extend(results["matches"])
                print(f"  結果数: {len(results['matches'])}")
                
            except Exception as e:
                print(f"  検索エラー: {str(e)}")
                continue
        
        # ステップ4: 結果の統合とランキング
        print("\nステップ4: 結果の統合とランキング")
        final_results = self._merge_and_rank_results(all_results, query_variations)
        
        print(f"\n=== 検索完了 ===")
        print(f"最終結果数: {len(final_results)}")
        
        return {
            "matches": final_results,
            "total_variations": len(query_variations),
            "keywords": keywords,
            "search_details": {
                "query_variations": query_variations,
                "original_query": query
            }
        }
    
    def _merge_and_rank_results(self, all_results: List, query_variations: List[str]) -> List:
        """検索結果を統合してランキング"""
        if not all_results:
            return []
        
        # 重複除去（IDベース）
        unique_results = {}
        for result in all_results:
            result_id = result.id
            if result_id not in unique_results:
                unique_results[result_id] = result
            else:
                # 既存の結果よりスコアが高い場合は更新
                if result.score > unique_results[result_id].score:
                    unique_results[result_id] = result
        
        # スコアの正規化とランキング
        ranked_results = []
        for result in unique_results.values():
            # クエリバリエーションの順序を考慮したスコア調整
            query_penalty = result.query_index * 0.05  # 後半のクエリは少しペナルティ
            
            adjusted_score = result.score - query_penalty
            
            # 調整されたスコアを追加
            result.adjusted_score = adjusted_score
            ranked_results.append(result)
        
        # 調整されたスコアでソート
        ranked_results.sort(key=lambda x: x.adjusted_score, reverse=True)
        
        # 設定画面のしきい値でフィルタリング
        current_threshold = st.session_state.get("similarity_threshold", self.base_similarity_threshold)
        filtered_results = [
            result for result in ranked_results
            if result.adjusted_score >= current_threshold
        ]
        
        return filtered_results
    
    def get_search_analytics(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """検索分析情報を取得"""
        matches = search_results.get("matches", [])
        
        if not matches:
            return {
                "total_results": 0,
                "average_score": 0,
                "score_distribution": {},
                "query_effectiveness": {}
            }
        
        # スコア統計
        scores = [match.adjusted_score for match in matches]
        average_score = sum(scores) / len(scores)
        
        # スコア分布
        score_distribution = {
            "0.8以上": len([s for s in scores if s >= 0.8]),
            "0.6-0.8": len([s for s in scores if 0.6 <= s < 0.8]),
            "0.4-0.6": len([s for s in scores if 0.4 <= s < 0.6]),
            "0.4未満": len([s for s in scores if s < 0.4])
        }
        
        # クエリ効果分析
        query_effectiveness = {}
        for match in matches:
            variation = getattr(match, 'query_variation', 'unknown')
            if variation not in query_effectiveness:
                query_effectiveness[variation] = {
                    "count": 0,
                    "average_score": 0,
                    "scores": []
                }
            query_effectiveness[variation]["count"] += 1
            query_effectiveness[variation]["scores"].append(match.adjusted_score)
        
        # 平均スコアを計算
        for variation in query_effectiveness:
            scores = query_effectiveness[variation]["scores"]
            query_effectiveness[variation]["average_score"] = sum(scores) / len(scores)
            del query_effectiveness[variation]["scores"]  # 不要なデータを削除
        
        return {
            "total_results": len(matches),
            "average_score": round(average_score, 4),
            "score_distribution": score_distribution,
            "query_effectiveness": query_effectiveness
        } 