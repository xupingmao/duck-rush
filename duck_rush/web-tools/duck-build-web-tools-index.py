#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Duck Rush - Web 工具索引生成器

该脚本会扫描 web-tools 目录下的 HTML 文件，并自动生成 web-tools-index.html 文件，
包含工具卡片、使用说明和工具列表。
"""

import os
import datetime

def get_tool_info(filename):
    """
    根据文件名获取工具信息
    
    Args:
        filename: HTML 文件名
    
    Returns:
        dict: 包含工具信息的字典
    """
    import re
    
    # 读取 HTML 文件内容
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 meta 标签信息
        name_match = re.search(r'<meta name="tool-name" content="([^"]*)"', content)
        description_match = re.search(r'<meta name="tool-description" content="([^"]*)"', content)
        
        # 构建工具信息
        tool_info = {
            'name': name_match.group(1) if name_match else os.path.splitext(filename)[0].replace('-', ' ').title(),
            'description': description_match.group(1) if description_match else 'Duck Rush 项目中的 Web 工具。'
        }
        
        return tool_info
    except Exception as e:
        # 异常情况下返回默认信息
        name = os.path.splitext(filename)[0].replace('-', ' ').title()
        return {
            'name': name,
            'description': 'Duck Rush 项目中的 Web 工具。'
        }

def generate_html(tools, html_files):
    """
    生成 HTML 内容
    
    Args:
        tools: 工具信息列表
        html_files: HTML 文件列表
    
    Returns:
        str: 生成的 HTML 内容
    """
    current_year = datetime.datetime.now().year
    
    # 生成工具卡片
    tool_cards = []
    for i, tool_info in enumerate(tools):
        filename = html_files[i]
        tool_cards.append(f'''
                    <div class="tool-card">
                        <h3 class="tool-title">{tool_info['name']}</h3>
                        <p class="tool-description">{tool_info['description']}</p>
                        <a href="{filename}" class="tool-link">打开工具</a>
                    </div>
        ''')
    
    # HTML 模板
    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web工具索引 | Duck Rush</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
        }

        body {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #333;
            min-height: 100vh;
            padding: 16px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }

        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 24px 20px;
            text-align: center;
        }

        .header-title {
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 6px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }

        .header-subtitle {
            font-size: 0.9rem;
            opacity: 0.9;
        }

        main {
            padding: 24px 20px;
        }

        .section-title {
            font-size: 1.2rem;
            color: #444;
            margin-bottom: 16px;
            padding-bottom: 6px;
            border-bottom: 2px solid #f0f0f0;
        }

        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }

        .tool-card {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 12px;
            transition: all 0.3s ease;
            border: 1px solid #e9ecef;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .tool-card:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            border-color: #667eea;
        }

        .tool-title {
            font-size: 0.95rem;
            font-weight: 600;
            color: #333;
            margin: 0;
        }

        .tool-description {
            font-size: 0.8rem;
            color: #666;
            margin: 0;
            line-height: 1.3;
            flex-grow: 1;
        }

        .tool-link {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 6px 14px;
            border-radius: 14px;
            text-decoration: none;
            font-weight: 500;
            font-size: 0.8rem;
            transition: all 0.3s ease;
            margin-top: 2px;
            align-self: flex-start;
        }

        .tool-link:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(102, 126, 234, 0.4);
        }

        .info-section {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 18px;
            margin-bottom: 20px;
        }

        .info-title {
            font-size: 1rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 10px;
        }

        .info-content {
            font-size: 0.85rem;
            color: #666;
            line-height: 1.4;
        }

        .info-content ul {
            margin-top: 6px;
            padding-left: 18px;
        }

        .info-content li {
            margin-bottom: 4px;
        }

        footer {
            background: #f8f9fa;
            padding: 12px 20px;
            text-align: center;
            border-top: 1px solid #e9ecef;
        }

        .footer-text {
            color: #666;
            font-size: 0.8rem;
        }

        @media (max-width: 768px) {
            body {
                padding: 8px;
            }

            .container {
                border-radius: 8px;
            }

            header {
                padding: 24px 16px;
            }

            .header-title {
                font-size: 1.6rem;
            }

            main {
                padding: 24px 16px;
            }

            .tools-grid {
                grid-template-columns: 1fr;
            }

            .tool-card {
                padding: 16px;
            }

            .info-section {
                padding: 16px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1 class="header-title">Web工具索引</h1>
            <p class="header-subtitle">Duck Rush 项目的 Web 工具集合</p>
        </header>

        <main>
            <section>
                <h2 class="section-title">🔧 可用工具</h2>
                <div class="tools-grid">
                    {tool_cards}
                </div>
            </section>

            <section class="info-section">
                <h3 class="info-title">📖 使用说明</h3>
                <div class="info-content">
                    <p>本页面是 Duck Rush 项目中 Web 工具的索引中心，包含了以下功能：</p>
                    <ul>
                        <li>快速访问项目中的所有 Web 工具</li>
                        <li>查看每个工具的简要描述</li>
                        <li>通过美观的界面轻松导航</li>
                    </ul>
                    <p>点击上方的工具卡片即可打开对应工具。</p>
                </div>
            </section>
        </main>

        <footer>
            <p class="footer-text">© {current_year} Duck Rush 项目 | Web 工具索引</p>
        </footer>
    </div>
</body>
</html>'''
    
    # 替换占位符
    html_content = html_template.replace('{tool_cards}', ''.join(tool_cards))
    html_content = html_content.replace('{current_year}', str(current_year))
    
    return html_content

def main():
    """
    主函数
    """
    # 获取 web-tools 目录路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 扫描 HTML 文件
    html_files = [f for f in os.listdir(current_dir) if f.endswith('.html') and f != 'web-tools-index.html']
    html_files.sort()
    
    # 获取工具信息
    tools = [get_tool_info(f) for f in html_files]
    
    # 生成 HTML
    html_content = generate_html(tools, html_files)
    
    # 写入文件
    output_file = os.path.join(current_dir, 'web-tools-index.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Web 工具索引已生成：{output_file}")
    print(f"📁 扫描到 {len(html_files)} 个工具文件：")
    for file in html_files:
        print(f"   - {file}")

if __name__ == '__main__':
    main()
