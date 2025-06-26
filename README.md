# 地域情報案内チャットシステム

このプロジェクトは、特定の地域の周辺情報を自然言語で検索・案内できるチャットシステムです。不動産購入や賃貸の意思決定を支援することを目的としており、物件情報だけでなく、その地域で生活する上で必要な様々な情報を提供します。

## 主な機能

### 1. 地域情報の検索・案内
- 物件情報（間取り、価格、設備など）
- 教育環境（学校、保育園、塾など）
- 交通アクセス（駅、バス、道路など）
- 生活インフラ（スーパー、病院、公共施設など）
- 安全・防災情報
- 地域コミュニティの状況
- 行政情報（都市計画、再開発など）

### 2. 自然言語での対話
- 日本語での質問応答
- 文脈を考慮した応答生成
- 詳細な情報の提供
- 関連情報の提案

### 3. ファイル管理機能
- テキストファイルのアップロード
- メタデータによる情報分類
- 自動的なテキスト処理
- データベースへの保存

### 4. カスタマイズ機能
- プロンプトテンプレートの編集
- 検索条件の調整
- 表示形式の変更

### 3. RAG検索処理

#### 高度な検索モード（デフォルト）
```
[キーワード抽出]
- OpenAI GPT-4o-miniを使用してクエリから重要なキーワードを抽出
- 地域情報や施設情報に関連する重要な単語を特定
- 正規表現ベースのフォールバック処理も実装
      ↓
[クエリバリエーション生成]
- 元のクエリの異なる表現を生成（最大5個）
- 質問パターンを参考にした自然な表現のバリエーション
- 回答例のパターンも考慮した検索最適化
      ↓
[マルチステップ検索]
- 各クエリバリエーションで個別に検索実行
- 動的しきい値調整（1番目: 0.7, 2番目: 0.6, 3番目: 0.5...）
- 結果の統合とランキング
```

#### ベクトル化処理（回答例を含む）
```
[テキスト結合]
- メインテキストと回答例を結合してベクトル化
- 回答例をメインテキストの前に配置（検索時の優先度向上）
- 辞書形式の回答例は "Q: 質問内容\nA: 回答内容" の形式に変換
      ↓
[ベクトル生成]
- OpenAIEmbeddings(text-embedding-3-large, dimensions=3072)でベクトル化
- 結合されたテキスト全体をベクトル化
- 検索用の結合テキストもメタデータに保存
      ↓
[メタデータ設定]
- 回答例を文字列形式で保存（Pinecone互換性のため）
- 検索時に回答例の内容も考慮される
- 回答例の質問と回答の両方が検索に活用される
```

#### 結果の統合とランキング
```
[スコア調整]
- ベーススコア: Pineconeの類似度スコア（0.0-1.0）
- クエリ順序ペナルティ: 後半のクエリほどスコアを下げる
- 調整されたスコア = ベーススコア - ペナルティ
      ↓
[重複除去]
- 同じIDの結果を統合
- 最高スコアの結果を採用
- クエリ情報を保持
      ↓
[最終フィルタリング]
- adjusted_score >= current_threshold（設定画面の値）
- デフォルト: 0.7
- 回答例を含む検索により、より関連性の高い結果を取得
```

## ローカル環境でのセットアップ

### 1. 仮想環境の作成と有効化

```shell
# Windowsの場合
# PowerShellを開いて以下のコマンドを順番に実行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS/Linuxの場合
# ターミナルを開いて以下のコマンドを順番に実行
python -m venv .venv
source .venv/bin/activate
```

### 2. 必要なパッケージのインストール

```shell
# 仮想環境が有効化されていることを確認（プロンプトの先頭に(.venv)が表示されているはず）
# 以下のコマンドを実行
pip install -r requirements.txt
```

### 3. 環境変数の設定

```shell
# Windowsの場合
copy .env.template .env

# macOS/Linuxの場合
cp .env.template .env
```

`.env`ファイルを開いて、以下の環境変数を設定してください：
```
PINECONE_API_KEY=your_api_key_here
PINECONE_ASSISTANT_NAME=your_assistant_name_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 4. アプリケーションの実行

```shell
# 以下のコマンドを実行
streamlit run streamlit_app.py
```

アプリケーションが起動したら、ブラウザで http://localhost:8501 にアクセスしてください。

## 使用方法

### 1. ファイルのアップロード
1. 「ファイルアップロード」タブを選択
2. テキストファイルをアップロード
3. メタデータを入力（大カテゴリ、中カテゴリ、市区町村など）
4. 「データベースに保存」をクリック

### 2. チャットでの質問
1. 「チャット」タブを選択
2. 質問を入力（例：「この地域の小学校について教えてください」）
3. システムが関連情報を検索し、回答を生成

### 3. 設定のカスタマイズ
1. 「設定」タブを選択
2. プロンプトテンプレートの編集
3. 検索条件の調整
4. 表示形式の変更

## 技術スタック

- フロントエンド: Streamlit
- バックエンド: Python
- データベース: Pinecone
- 言語モデル: OpenAI GPT-3.5-turbo
- テキスト処理: Janome（日本語形態素解析）

## 注意事項

1. 日本語テキストの処理に特化しています
2. 対応エンコーディング: UTF-8、Shift-JIS、CP932、EUC-JP
3. 大量のテキストデータを処理する場合は、適切なチャンクサイズの設定が必要です
4. APIキーは適切に管理してください

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## Configuration

### Install packages

1. For best results, create a [Python virtual environment](https://realpython.com/python-virtual-environments-a-primer/) with 3.10 or 3.11 and reuse it when running any file in this repo.
2. Run

```shell
pip install -r requirements.txt
```

### Environment Variables

Copy `.env.template` to `.env` and `.streamlit/secrets.toml.template` to `.streamlit/secrets.toml`. Fill in your [Pinecone API key](https://app.pinecone.io/organizations/-/projects/-/keys) and the name you want to call your Assistant. The `.env` file will be used by the Jupyter notebook for processing the data and upserting it to Pinecone, whereas `secrets.toml` will be used by Streamlit when running locally.

## Setup Assistant

1. In the [console](https://app.pinecone.io/organizations/-/projects/-/assistant), accept the Terms of Service for Pinecone Assistant.

2. Run all cells in the "assistant-starter" Jupyter notebook to create an assistant and upload files to it.
> [!NOTE]
> If you prefer to create an assistant and upload your files via the UI, skip the notebook and continue to the next section.

## Test the app locally

### [OPTIONAL] Configure the app

In the `streamlit_app.py` file:

- Set your preferred title on [line 18](https://github.com/pinecone-field/assistant-streamlit-starter/blob/f5091cbe5a9bb0fc31f327cda47830824d7a168b/streamlit_app.py#L18)
- Set your preferred prompt on [line 21](https://github.com/pinecone-field/assistant-streamlit-starter/blob/f5091cbe5a9bb0fc31f327cda47830824d7a168b/streamlit_app.py#L21)
- Set your preferred button label on [line 24](https://github.com/pinecone-field/assistant-streamlit-starter/blob/f5091cbe5a9bb0fc31f327cda47830824d7a168b/streamlit_app.py#L24)
- Set your preferred success message on [line 49](https://github.com/pinecone-field/assistant-streamlit-starter/blob/f5091cbe5a9bb0fc31f327cda47830824d7a168b/streamlit_app.py#L49)
- Set your preferred failure message on [line 53](https://github.com/pinecone-field/assistant-streamlit-starter/blob/f5091cbe5a9bb0fc31f327cda47830824d7a168b/streamlit_app.py#L53)

### Run the app

1. Validate that Streamlit is [installed](#install-packages) correctly by running

```shell
streamlit hello
```

You should see a welcome message and the demo should automatically open in your browser. If it doesn't open automatically, manually go to the **Local URL** listed in the terminal output.

2. If the demo ran correctly, run

```shell
streamlit run streamlit_app.py
```

3. Confirm that your app looks good and test queries return successful responses. If so, move on to deployment!

## Deploy the app

1. Create and login to a [Streamlit Community Cloud](https://share.streamlit.io) account.
2. Link your Github account in Workspace settings.
3. On the dashboard, click "New app".
4. Select your Github repo and branch, then enter the filename `streamlit_app.py`.
5. [OPTIONAL] Set your preferred app URL.
6. In "Advanced settings...":
   - Change the Python version to match the one you tested locally
   - Copy the contents of your `secrets.toml` file into "Secrets"
   - Click "Save"
7. Click "Deploy"

## チャット機能の処理フロー

### 1. 初期化処理
```
[アプリケーション起動]
      ↓
[セッション状態の初期化]
- messages: チャット履歴の初期化
- langchain_service: LangChainサービスの初期化
- prompt_templates: プロンプトテンプレートの読み込み
      ↓
[API使用状況の確認]
- OpenAI APIキーの検証
- クォータ状況のチェック
      ↓
[検索モードの設定]
- 高度な検索モード（デフォルト）
- 基本的な検索モード
```

### 2. ユーザー入力処理
```
[ユーザー入力受信]
      ↓
[メッセージの保存]
- タイムスタンプ付きでセッション状態に保存
- ロール: "user"として記録
      ↓
[プロンプトテンプレートの選択]
- サイドバーで選択されたテンプレートを取得
- システムプロンプトと応答テンプレートを設定
      ↓
[物件情報の取得]
- 選択された物件の詳細情報を取得
- 全物件情報または個別物件情報
```

### 3. 検索・コンテキスト取得処理

#### 高度な検索モード（デフォルト）
```
[初期化と設定]
- AdvancedSearchService.__init__()で初期化
- 基本設定：
  * base_similarity_threshold: SIMILARITY_THRESHOLD（デフォルト0.7）
  * max_query_variations: 5（最大クエリバリエーション数）
  * max_results_per_query: 10（クエリあたりの最大結果数）
      ↓
[ステップ1: キーワード抽出]
- extract_keywords()メソッドで実行
- OpenAI GPT-4o-miniを使用したAI抽出：
  * システムプロンプト: "地域情報や施設情報に関連する重要な単語のみを抽出"
  * レスポンス形式: JSON形式
  * 抽出例: "小学校"、"保育園"、"病院"、"スーパー"、"駅"、"公園"など
- フォールバック処理: _extract_basic_keywords()で正規表現ベース抽出
- パターンマッチング：
  * 教育施設: 小学校|中学校|高校|大学|学校
  * 保育施設: 保育園|幼稚園|学童
  * 医療施設: 病院|クリニック|診療所
  * 商業施設: スーパー|コンビニ|ショッピング
  * 交通施設: 駅|バス停|交通
  * 公共施設: 公園|遊び場|施設
  * 位置表現: 近く|周辺|地域|エリア
  * 地域名: 川越|さいたま|埼玉|東京|神奈川|千葉
      ↓
[ステップ2: クエリバリエーション生成]
- generate_query_variations()メソッドで実行
- 元のクエリを最初に追加
- OpenAI GPT-4o-miniを使用したAI生成：
  * システムプロンプト: "地域情報や施設情報の検索に適した形で、同じ意味を表す異なる表現"
  * レスポンス形式: JSON形式
  * 生成例: "小学校"→"小学校について教えて"→"小学校の情報を教えて"
- フォールバック処理: _generate_basic_variations()でキーワードベース生成
- 重複除去と制限: 最大5つのユニークなバリエーション
      ↓
[ステップ3: マルチステップ検索]
- multi_step_search()メソッドで実行
- 各クエリバリエーションに対して：
  * 動的しきい値調整：
    - 1番目のクエリ: base_similarity_threshold（0.7）
    - 2番目以降: max(0.2, similarity_threshold - 0.1)
  * PineconeService.query()で検索実行：
    * query_text: クエリバリエーション
    * top_k: max_results_per_query（10件）
    * similarity_threshold: 動的調整されたしきい値
  * 結果にメタデータ追加：
    * query_variation: 使用されたクエリバリエーション
    * query_index: クエリの順序（0から開始）
      ↓
[ステップ4: 結果統合・ランキング]
- _merge_and_rank_results()メソッドで実行
- 重複除去（IDベース）：
  * 同じIDの結果が複数ある場合、スコアが高い方を保持
- スコア調整：
  * クエリペナルティ: query_index * 0.05
  * adjusted_score = original_score - query_penalty
  * 後半のクエリほど少しペナルティ
- ランキング：
  * adjusted_scoreで降順ソート
  * 現在のしきい値（st.session_state.similarity_threshold）でフィルタリング
      ↓
[検索分析]
- get_search_analytics()メソッドで分析情報を取得
- 統計情報：
  * total_results: 総結果数
  * average_score: 平均スコア
  * score_distribution: スコア分布（0.8以上、0.6-0.8、0.4-0.6、0.4未満）
  * query_effectiveness: クエリ効果分析（各バリエーションの結果数と平均スコア）
```

#### スコア調整ロジックの詳細
```
[ベーススコア]
- Pineconeの類似度スコア（0.0-1.0）
      ↓
[クエリ順序ペナルティ]
- 1番目のクエリ: ペナルティなし
- 2番目のクエリ: -0.05
- 3番目のクエリ: -0.10
- 4番目のクエリ: -0.15
- 5番目のクエリ: -0.20
      ↓
[動的しきい値調整]
- 1番目のクエリ: 0.7（デフォルト）
- 2番目のクエリ: 0.6
- 3番目のクエリ: 0.5
- 4番目のクエリ: 0.4
- 5番目のクエリ: 0.3
- 最小値: 0.2
      ↓
[最終フィルタリング]
- adjusted_score >= current_threshold（設定画面の値）
- デフォルト: 0.7
```

#### エラーハンドリング
```
[キーワード抽出エラー]
- OpenAI APIエラーの場合、正規表現ベースの抽出にフォールバック
- 基本的なパターンマッチングでキーワードを抽出
      ↓
[クエリバリエーション生成エラー]
- OpenAI APIエラーの場合、キーワードベースの生成にフォールバック
- 上位3つのキーワードを使用して基本的なバリエーションを生成
      ↓
[検索エラー]
- 個別のクエリでエラーが発生しても他のクエリは継続実行
- エラーログを出力して処理を継続
- 結果が0件の場合でも空の結果を返す
```

#### 基本的な検索モード
```
[クエリベクトル化]
- LangChainService._get_context_with_basic_search()で処理
- OpenAIEmbeddings(text-embedding-3-large, dimensions=3072)でベクトル化
      ↓
[類似度検索]
- PineconeVectorStore.similarity_search_with_score()で検索実行
- top_k件の候補を取得（デフォルト5件）
      ↓
[フィルタリング]
- 類似度スコアがsimilarity_threshold（デフォルト0.7）以上の結果のみ採用
- スコアによる降順並び替え
- メタデータの簡略化（テキスト500文字制限、メタデータ100文字制限）
```

### 4. 応答生成処理

#### コンテキスト構築
```
[検索結果の処理]
- 検索結果からテキストを抽出・結合
- メタデータ（カテゴリ、質問例、回答例、検証済みフラグなど）を統合
- 検索詳細情報の作成（スコア、クエリバリエーション、順序など）
      ↓
[コンテキストテキスト生成]
- フィルタリングされた結果のテキストを"\n"で結合
- 参照文脈が空の場合は警告メッセージを設定
- トークン数のカウント（tiktoken使用）
```

#### 会話履歴の最適化
```
[トークン数制限の確認]
- 最大10000トークン制限
- システムプロンプトとコンテキスト用に4000トークンを確保
- 利用可能トークン数 = 10000 - 4000 = 6000トークン
      ↓
[メッセージの重要度分類]
- システムメッセージを優先保持
- 最新の1メッセージを保持
- 残りのメッセージを長さでソート（短いものから）
      ↓
[最適化実行]
- 重要メッセージのトークン数を計算
- 残りトークン数に基づいて他のメッセージを追加
- 最適化されたメッセージで履歴を更新
```

#### プロンプト構築
```
[メッセージリストの作成]
- システムプロンプト（選択されたテンプレート）
- MessagesPlaceholder（チャット履歴）
- 参照文脈（検索結果）
- 物件情報（選択された物件の詳細）
- ユーザー入力（質問）
      ↓
[プロンプトテンプレートの設定]
- ChatPromptTemplate.from_messages()でテンプレート作成
- チェーンの初期化（prompt | llm）
```

#### GPT-4o-miniによる応答生成
```
[モデル設定]
- モデル: gpt-4o-mini
- 温度: 0.85（創造性と一貫性のバランス）
- 最大トークン数: 自動調整
- エンコーディング: tiktoken（gpt-4用）
      ↓
[応答生成]
- chain.invoke()でプロンプトを実行
- 以下の情報を渡す：
  * chat_history: 最適化された会話履歴
  * context: 検索結果のテキスト
  * property_info: 物件情報
  * input: ユーザーの質問
      ↓
[トークン数カウント]
- システムプロンプト、チャット履歴、参照文脈、物件情報、ユーザー入力のトークン数を個別カウント
- 合計トークン数を計算
```

#### 応答の後処理
```
[メッセージ履歴の更新]
- ユーザーメッセージを履歴に追加
- AI応答を履歴に追加
      ↓
[詳細情報の作成]
- モデル情報（gpt-4o-mini）
- 会話履歴の状態
- トークン数詳細（各要素のトークン数）
- 送信テキスト（プロンプト、履歴、文脈、物件情報、入力）
- 参照文脈の詳細（検索結果の詳細情報）
```

### 5. 応答処理・表示
```
[応答の保存]
- タイムスタンプ付きでセッション状態に保存
- ロール: "assistant"として記録
- 詳細情報（トークン数、送信テキストなど）を付加
      ↓
[詳細情報の整理]
- トークン数情報
- 送信テキスト（システムプロンプト、チャット履歴、参照文脈など）
- 検索詳細（スコア、メタデータ、質問例など）
      ↓
[UI表示]
- チャットメッセージとして表示
- 詳細情報を展開可能なボタンで提供
- タブ形式で詳細情報を整理表示
```

### 6. 履歴管理処理
```
[履歴の保存]
- CSV形式でチャット履歴をエクスポート
- タイムスタンプ、ロール、内容、詳細情報を含む
      ↓
[履歴の読み込み]
- CSVファイルから履歴を復元
- LangChainの会話履歴も同期更新
      ↓
[履歴のクリア]
- セッション状態のメッセージをクリア
- LangChainのメモリもクリア
```

### 7. エラーハンドリング
```
[API制限エラー]
- OpenAI APIクォータ超過の検出
- 適切なエラーメッセージの表示
- ユーザーへの対応案内
      ↓
[検索エラー]
- Pinecone接続エラーの処理
- 再試行ロジック（最大3回、指数バックオフ）
- フォールバック処理
      ↓
[応答生成エラー]
- GPT APIエラーの処理
- 部分的な応答の提供
- エラー詳細の記録
```

### 8. パフォーマンス最適化
```
[トークン管理]
- 入力トークン数の監視
- 会話履歴の自動最適化
- コンテキスト長の制限
      ↓
[キャッシュ管理]
- 検索結果のキャッシュ
- プロンプトテンプレートのキャッシュ
- セッション状態の効率的な管理
      ↓
[非同期処理]
- 長時間の処理の非同期実行
- ユーザーインターフェースの応答性維持
- プログレス表示の提供
```

## memo
このサービスは地域情報案内チャットシステムで、以下の主要な機能を提供しています：
・チャット機能
自然言語での質問応答
文脈を考慮した応答生成
地域に関する様々な情報の提供
日本語での対話インターフェース
・物件情報管理
物件情報の登録・管理
間取り、価格、設備などの詳細情報
物件情報の検索・表示
・ファイル管理機能
テキストファイルのアップロード
複数のエンコーディング対応（UTF-8、Shift-JIS、CP932、EUC-JP）
メタデータによる情報分類
Pineconeデータベースへの保存
・地域情報検索
教育環境（学校、保育園、塾など）
交通アクセス（駅、バス、道路など）
生活インフラ（スーパー、病院、公共施設など）
安全・防災情報
地域コミュニティの状況
行政情報（都市計画、再開発など）
・設定・カスタマイズ機能
プロンプトテンプレートの編集
検索条件の調整
表示形式の変更
システム設定の管理
・エージェント機能
自動化された情報収集
インテリジェントな情報処理
タスクの自動実行

・技術スタック:
フロントエンド: Streamlit
バックエンド: Python
データベース: Pinecone
言語モデル: OpenAI GPT-3.5-turbo
テキスト処理: Janome（日本語形態素解析）

##チャット機能について、より詳細に説明させていただきます：
・基本機能
自然言語での質問応答
文脈を考慮した会話の継続
物件情報との連携
チャット履歴の管理
・チャットインターフェース
メッセージ入力欄
チャット履歴の表示
詳細情報の展開表示
サイドバーでの設定管理
・プロンプト管理機能
カスタマイズ可能なプロンプトテンプレート
システムプロンプトの設定
応答テンプレートの設定
複数のテンプレートの切り替え
・物件情報連携
物件の選択機能
物件詳細情報の表示
物件情報を考慮した応答生成
物件情報の動的更新
・チャット履歴管理
履歴の保存（CSV形式）
履歴の読み込み
履歴のクリア
タイムスタンプ付きの記録
・高度な応答生成
LangChainを使用した文脈理解
GPT-3.5-turboによる応答生成
関連情報の検索と統合
詳細情報の提供
・エラー処理とフィードバック
エラーメッセージの表示
処理状態の表示
ユーザーフィードバック
システム状態の通知
・セキュリティ機能
APIキーの管理
セッション管理
データの暗号化
アクセス制御
・カスタマイズオプション
応答形式のカスタマイズ
検索パラメータの調整
表示設定の変更
テンプレートの編集
・パフォーマンス最適化
非同期処理
キャッシュ管理
効率的なデータ検索
レスポンス時間の最適化
このチャット機能は、地域情報の提供に特化しており、物件情報や地域の詳細情報を自然な会話形式で提供することができます。ユーザーは直感的なインターフェースを通じて、必要な情報を簡単に取得することができます。

[フロントエンド (Streamlit)]
        ↓
[バックエンド (Python)]
        ↓
[外部サービス]
- OpenAI (GPT-3.5-turbo)
- Pinecone (ベクトルDB)

src/
├── components/          # UIコンポーネント
│   ├── chat.py         # チャット機能
│   ├── file_upload.py  # ファイルアップロード
│   ├── settings.py     # 設定管理
│   └── agent.py        # エージェント機能
├── services/           # ビジネスロジック
│   ├── langchain_service.py    # LangChain処理
│   ├── pinecone_service.py     # Pinecone操作
│   └── question_classifier.py  # 質問分類
└── config/             # 設定ファイル
    └── settings.py     # システム設定

##チャット機能の処理フロー

[ユーザー入力]
      ↓
[入力処理]
- テキストの前処理
- 質問の分類
      ↓
[コンテキスト検索]
- Pineconeでの類似文書検索
- 関連情報の抽出
      ↓
[応答生成]
- プロンプトの構築
- GPT-3.5-turboによる生成
      ↓
[応答処理]
- フォーマット整形
- 詳細情報の付加
      ↓
[履歴管理]
- メッセージの保存
- セッション状態の更新

##データフロー
[ユーザー入力]
      ↓
[Pinecone検索]
- ベクトル化
- 類似度検索
      ↓
[コンテキスト構築]
- 関連文書の抽出
- メタデータの統合
      ↓
[GPT-3.5-turbo処理]
- プロンプトの構築
- 応答の生成
      ↓
[結果の整形]
- フォーマット適用
- 詳細情報の付加
      ↓
[UI表示]
- メッセージの表示
- 詳細情報の展開