from typing import Dict, Any, List
from dataclasses import dataclass
from langchain.prompts import ChatPromptTemplate
from openai import OpenAI
from src.config.settings import OPENAI_API_KEY
import streamlit as st

@dataclass
class ResponseTemplate:
    """回答テンプレートの基本クラス"""
    template: str
    required_fields: List[str]

class ResponseTemplates:
    def __init__(self):
        self.templates = {
            "facility": ResponseTemplate(
                template="""{name}についてお調べしました。

場所は{address}にあります。
{distance}の場所にあります。

{additional_info}

他に気になることはありますか？""",
                required_fields=["name", "address", "distance"]
            ),
            "area": ResponseTemplate(
                template="""{area_name}の地域情報についてお伝えします。

治安状況は{safety}です。
交通アクセスは{transportation}です。
教育環境は{education}です。

{additional_info}

他に気になることはありますか？""",
                required_fields=["area_name", "safety", "transportation"]
            ),
            "property": ResponseTemplate(
                template="""{property_name}の物件情報についてお伝えします。

価格は{price}です。
間取りは{layout}です。
面積は{area}です。
設備は{facilities}です。

{additional_info}

他に気になることはありますか？""",
                required_fields=["property_name", "price", "layout"]
            )
        }

    def get_template(self, question_type: str) -> ResponseTemplate:
        """質問タイプに応じたテンプレートを取得"""
        if question_type not in self.templates:
            raise ValueError(f"Unknown question type: {question_type}")
        return self.templates[question_type]

    def format_response(self, question_type: str, data: Dict[str, Any]) -> str:
        """テンプレートを使用して回答を生成"""
        template = self.get_template(question_type)
        
        # 必須フィールドのチェック
        missing_fields = [field for field in template.required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # テンプレートにデータを適用
        return template.template.format(**data)

class QuestionExampleGenerator:
    def __init__(self):
        """質問例・回答例生成サービスの初期化"""
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI APIキーが設定されていません")
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

    def generate_question_examples(self, text: str, category: str = "", subcategory: str = "", max_questions: int = 5) -> List[str]:
        """テキスト内容に基づいて質問例を生成"""
        try:
            # カテゴリ情報を含むプロンプトを作成
            category_info = ""
            if category and subcategory:
                category_info = f"\n\nこのテキストは「{category}」の「{subcategory}」カテゴリに分類されています。"
            elif category:
                category_info = f"\n\nこのテキストは「{category}」カテゴリに分類されています。"

            prompt = f"""以下のテキスト内容を読んで、このテキストに関連する質問例を{max_questions}個生成してください。

テキスト内容:
{text}{category_info}

生成する質問の条件:
1. テキストの内容に基づいて具体的な質問を作成
2. 実際のユーザーが尋ねそうな自然な質問
3. テキストから答えられる質問のみ
4. 質問は1行に1つずつ、番号なしで出力
5. 質問の最後に「？」を付ける

例:
この物件の完成時期はいつですか？
最寄り駅までの距離は？
周辺の学校について教えてください
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは質問例生成の専門家です。テキスト内容に基づいて適切な質問例を生成してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            # 応答から質問例を抽出
            response_text = response.choices[0].message.content.strip()
            
            # 改行で分割して質問例を抽出
            questions = []
            for line in response_text.split('\n'):
                line = line.strip()
                if line and not line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                    # 番号や箇条書き記号を除去
                    if line.startswith(('1', '2', '3', '4', '5')):
                        line = line[line.find('.')+1:].strip()
                    if line.startswith(('-', '•')):
                        line = line[1:].strip()
                    
                    # 質問の最後に「？」がない場合は追加
                    if line and not line.endswith('？') and not line.endswith('?'):
                        line += '？'
                    
                    if line:
                        questions.append(line)

            # 最大数に制限
            return questions[:max_questions]

        except Exception as e:
            st.error(f"質問例の生成中にエラーが発生しました: {str(e)}")
            return []

    def generate_answer_examples(self, text: str, category: str = "", subcategory: str = "", max_answers: int = 3) -> List[Dict[str, str]]:
        """テキスト内容に基づいて回答例を生成"""
        try:
            # カテゴリ情報を含むプロンプトを作成
            category_info = ""
            if category and subcategory:
                category_info = f"\n\nこのテキストは「{category}」の「{subcategory}」カテゴリに分類されています。"
            elif category:
                category_info = f"\n\nこのテキストは「{category}」カテゴリに分類されています。"

            prompt = f"""以下のテキスト内容を読んで、このテキストに関連する質問と回答のペアを{max_answers}個生成してください。

テキスト内容:
{text}{category_info}

生成する質問・回答の条件:
1. テキストの内容に基づいて具体的な質問と回答を作成
2. 実際のユーザーが尋ねそうな自然な質問
3. テキストから答えられる質問のみ
4. 回答は簡潔で分かりやすく
5. 以下の形式で出力してください：
質問: [質問内容]
回答: [回答内容]

例:
質問: この物件の完成時期はいつですか？
回答: この物件は2024年3月に完成予定です。

質問: 最寄り駅までの距離は？
回答: 最寄り駅は○○駅で、徒歩約5分の距離です。

質問: 周辺の学校について教えてください
回答: 近隣には○○小学校、○○中学校があり、教育環境が整っています。
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは質問・回答例生成の専門家です。テキスト内容に基づいて適切な質問・回答例を生成してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            # 応答から質問・回答例を抽出
            response_text = response.choices[0].message.content.strip()
            
            # 質問・回答ペアを抽出
            qa_pairs = []
            current_question = ""
            current_answer = ""
            
            for line in response_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('質問:'):
                    # 前のペアがあれば保存
                    if current_question and current_answer:
                        qa_pairs.append({
                            "question": current_question,
                            "answer": current_answer
                        })
                    current_question = line[3:].strip()
                    current_answer = ""
                elif line.startswith('回答:'):
                    current_answer = line[3:].strip()
            
            # 最後のペアを保存
            if current_question and current_answer:
                qa_pairs.append({
                    "question": current_question,
                    "answer": current_answer
                })

            # 最大数に制限
            return qa_pairs[:max_answers]

        except Exception as e:
            st.error(f"回答例の生成中にエラーが発生しました: {str(e)}")
            return []

    def improve_question_examples(self, text: str, existing_questions: List[str], category: str = "", subcategory: str = "") -> List[str]:
        """既存の質問例を改善・追加"""
        try:
            # 既存の質問例を文字列に変換
            existing_text = "\n".join([f"- {q}" for q in existing_questions]) if existing_questions else "なし"

            category_info = ""
            if category and subcategory:
                category_info = f"\n\nこのテキストは「{category}」の「{subcategory}」カテゴリに分類されています。"
            elif category:
                category_info = f"\n\nこのテキストは「{category}」カテゴリに分類されています。"

            prompt = f"""以下のテキスト内容と既存の質問例を確認して、より良い質問例を生成してください。

テキスト内容:
{text}{category_info}

既存の質問例:
{existing_text}

改善のポイント:
1. 既存の質問例が良い場合は保持
2. 重複する質問は削除
3. テキスト内容により適した質問を追加
4. 具体的で実用的な質問に改善
5. 質問は1行に1つずつ、番号なしで出力
6. 質問の最後に「？」を付ける

改善された質問例を生成してください:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは質問例改善の専門家です。既存の質問例を分析して、より良い質問例を提案してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            # 応答から質問例を抽出
            response_text = response.choices[0].message.content.strip()
            
            # 改行で分割して質問例を抽出
            questions = []
            for line in response_text.split('\n'):
                line = line.strip()
                if line and not line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                    # 番号や箇条書き記号を除去
                    if line.startswith(('1', '2', '3', '4', '5')):
                        line = line[line.find('.')+1:].strip()
                    if line.startswith(('-', '•')):
                        line = line[1:].strip()
                    
                    # 質問の最後に「？」がない場合は追加
                    if line and not line.endswith('？') and not line.endswith('?'):
                        line += '？'
                    
                    if line:
                        questions.append(line)

            return questions

        except Exception as e:
            st.error(f"質問例の改善中にエラーが発生しました: {str(e)}")
            return existing_questions

    def improve_answer_examples(self, text: str, existing_qa_pairs: List[Dict[str, str]], category: str = "", subcategory: str = "") -> List[Dict[str, str]]:
        """既存の回答例を改善・追加"""
        try:
            # 既存の質問・回答例を文字列に変換
            existing_text = ""
            for qa in existing_qa_pairs:
                existing_text += f"質問: {qa.get('question', '')}\n回答: {qa.get('answer', '')}\n\n"
            
            if not existing_text:
                existing_text = "なし"

            category_info = ""
            if category and subcategory:
                category_info = f"\n\nこのテキストは「{category}」の「{subcategory}」カテゴリに分類されています。"
            elif category:
                category_info = f"\n\nこのテキストは「{category}」カテゴリに分類されています。"

            prompt = f"""以下のテキスト内容と既存の質問・回答例を確認して、より良い質問・回答例を生成してください。

テキスト内容:
{text}{category_info}

既存の質問・回答例:
{existing_text}

改善のポイント:
1. 既存の質問・回答例が良い場合は保持
2. 重複する質問は削除
3. テキスト内容により適した質問・回答を追加
4. 具体的で実用的な質問・回答に改善
5. 以下の形式で出力してください：
質問: [質問内容]
回答: [回答内容]

改善された質問・回答例を生成してください:"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "あなたは質問・回答例改善の専門家です。既存の質問・回答例を分析して、より良い質問・回答例を提案してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            # 応答から質問・回答例を抽出
            response_text = response.choices[0].message.content.strip()
            
            # 質問・回答ペアを抽出
            qa_pairs = []
            current_question = ""
            current_answer = ""
            
            for line in response_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('質問:'):
                    # 前のペアがあれば保存
                    if current_question and current_answer:
                        qa_pairs.append({
                            "question": current_question,
                            "answer": current_answer
                        })
                    current_question = line[3:].strip()
                    current_answer = ""
                elif line.startswith('回答:'):
                    current_answer = line[3:].strip()
            
            # 最後のペアを保存
            if current_question and current_answer:
                qa_pairs.append({
                    "question": current_question,
                    "answer": current_answer
                })

            return qa_pairs

        except Exception as e:
            st.error(f"回答例の改善中にエラーが発生しました: {str(e)}")
            return existing_qa_pairs 