import os

def generate_html():
    html_content = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>デモアプリケーション</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', Meiryo, sans-serif;
        }
        .hero {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 100px 0;
            text-align: center;
        }
        .card {
            border: none;
            border-radius: 15px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05);
            transition: transform 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
        }
    </style>
</head>
<body>

    <!-- ヘッダー / ヒーローセクション -->
    <header class="hero mb-5">
        <div class="container">
            <h1 class="display-4 fw-bold">変更の反映が完了しました</h1>
            <p class="lead">generated_code.py から index.html へのシームレスな移行が完了しました。</p>
        </div>
    </header>

    <!-- メインコンテンツ -->
    <main class="container">
        <div class="row g-4 justify-content-center">
            <div class="col-md-6 col-lg-4">
                <div class="card h-100 p-4">
                    <div class="card-body">
                        <h5 class="card-title fw-bold text-primary">自動生成スクリプト</h5>
                        <p class="card-text text-muted">Pythonスクリプトを実行することで、最新のUIテンプレートが瞬時に HTML として書き出されます。</p>
                    </div>
                </div>
            </div>
            <div class="col-md-6 col-lg-4">
                <div class="card h-100 p-4">
                    <div class="card-body">
                        <h5 class="card-title fw-bold text-success">モダンなデザイン</h5>
                        <p class="card-text text-muted">Bootstrap 5 を導入し、レスポンシブ対応かつクリーンなインターフェースを提供します。</p>
                    </div>
                </div>
            </div>
            <div class="col-md-6 col-lg-4">
                <div class="card h-100 p-4">
                    <div class="card-body">
                        <h5 class="card-title fw-bold text-info">拡張性</h5>
                        <p class="card-text text-muted">必要に応じてコンポーネントや動的なJavaScript機能を追加し、容易にスケールアップ可能です。</p>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- フッター -->
    <footer class="text-center py-5 mt-5 border-top text-muted">
        <p>&copy; 2024 Generated Code System. All rights reserved.</p>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

    output_path = "index.html"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[Success] '{output_path}' has been successfully generated and updated.")
    except Exception as e:
        print(f"[Error] Failed to write '{output_path}': {e}")

if __name__ == "__main__":
    generate_html()
