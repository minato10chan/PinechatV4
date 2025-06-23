from typing import Dict, List, Tuple, Optional
from openai import OpenAI
from src.config.settings import OPENAI_API_KEY, METADATA_CATEGORIES
import json
import streamlit as st

class CategoryClassifier:
    def __init__(self):
        """カテゴリ分類器の初期化"""
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI APIキーが設定されていません")
        
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.categories = METADATA_CATEGORIES

    def classify_text(self, text: str) -> Dict[str, str]:
        """テキストのカテゴリとサブカテゴリを自動分類"""
        try:
            # カテゴリとサブカテゴリの情報を準備
            category_info = self._prepare_category_info()
            
            # プロンプトを作成
            prompt = f"""以下のテキストを分析して、最も適切な大カテゴリと中カテゴリを選択してください。

利用可能なカテゴリ:
{category_info}

テキスト:
{text}

以下のJSON形式で回答してください:
{{
    "main_category": "選択した大カテゴリ",
    "sub_category": "選択した中カテゴリ",
    "confidence": 0.85,
    "reasoning": "選択理由の説明"
}}

注意事項:
- 大カテゴリと中カテゴリは上記のリストから正確に選択してください
- 複数のカテゴリが該当する場合は、最も主要なものを選択してください
- confidenceは0.0から1.0の間で、確信度を表してください
- reasoningには選択理由を簡潔に説明してください
"""

            # OpenAI APIを呼び出し
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは不動産・地域情報の専門家です。テキストを分析して適切なカテゴリを分類してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # レスポンスを解析
            response_text = response.choices[0].message.content.strip()
            
            # JSONを抽出してパース
            result = self._extract_json_from_response(response_text)
            
            # 結果を検証
            if not self._validate_classification(result):
                # 検証に失敗した場合はデフォルト値を返す
                return {
                    "main_category": "",
                    "sub_category": "",
                    "confidence": 0.0,
                    "reasoning": "分類に失敗しました"
                }
            
            return result
            
        except Exception as e:
            st.error(f"カテゴリ分類中にエラーが発生しました: {str(e)}")
            return {
                "main_category": "",
                "sub_category": "",
                "confidence": 0.0,
                "reasoning": f"エラー: {str(e)}"
            }

    def classify_multiple_chunks(self, chunks):
        """複数のチャンクを一括で分類"""
        results = []
        
        for i, chunk in enumerate(chunks):
            try:
                st.write(f"チャンク {i+1}/{len(chunks)} を分類中...")
                
                # テキストを取得
                text = chunk.get("text", "")
                if not text:
                    continue
                
                # カテゴリを分類
                classification = self.classify_text(text)
                
                # 結果をチャンクに追加
                chunk_with_classification = chunk.copy()
                chunk_with_classification["ai_classification"] = classification
                
                results.append(chunk_with_classification)
                
            except Exception as e:
                st.error(f"チャンク {i+1} の分類中にエラーが発生しました: {str(e)}")
                # エラーが発生した場合も元のチャンクを保持
                chunk_with_classification = chunk.copy()
                chunk_with_classification["ai_classification"] = {
                    "main_category": "",
                    "sub_category": "",
                    "confidence": 0.0,
                    "reasoning": f"エラー: {str(e)}"
                }
                results.append(chunk_with_classification)
        
        return results

    def _prepare_category_info(self) -> str:
        """カテゴリ情報をプロンプト用に整形"""
        category_info = []
        
        for main_cat, sub_cats in self.categories["中カテゴリ"].items():
            category_info.append(f"大カテゴリ: {main_cat}")
            category_info.append("  中カテゴリ:")
            for sub_cat in sub_cats:
                category_info.append(f"    - {sub_cat}")
            category_info.append("")
        
        return "\n".join(category_info)

    def _extract_json_from_response(self, response_text: str) -> Dict:
        """レスポンスからJSONを抽出"""
        try:
            # JSONの開始と終了を探す
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSONが見つかりませんでした")
            
            json_text = response_text[start_idx:end_idx]
            return json.loads(json_text)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"JSONの解析に失敗しました: {str(e)}")

    def _validate_classification(self, result) -> bool:
        """分類結果を検証"""
        required_fields = ["main_category", "sub_category", "confidence", "reasoning"]
        
        # 必須フィールドの存在確認
        for field in required_fields:
            if field not in result:
                return False
        
        # カテゴリの妥当性確認
        main_cat = result.get("main_category", "")
        sub_cat = result.get("sub_category", "")
        
        if main_cat not in self.categories["中カテゴリ"]:
            return False
        
        if sub_cat not in self.categories["中カテゴリ"].get(main_cat, []):
            return False
        
        # 確信度の範囲確認
        confidence = result.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            return False
        
        return True

    def get_available_categories(self) -> Dict[str, List[str]]:
        """利用可能なカテゴリを取得"""
        return self.categories["中カテゴリ"]

    def get_main_categories(self) -> List[str]:
        """大カテゴリのリストを取得"""
        return list(self.categories["中カテゴリ"].keys())

    def get_sub_categories(self, main_category: str) -> List[str]:
        """指定された大カテゴリに対応する中カテゴリのリストを取得"""
        return self.categories["中カテゴリ"].get(main_category, []) 