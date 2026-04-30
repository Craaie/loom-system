import os
import asyncio
import sys
from dotenv import load_dotenv

# 确保能导入 src 下的模块
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from google import genai  # 用于列出可用模型
except ImportError:
    print("❌ 报错: 缺少必要库。请执行以下命令安装：")
    print("   pip install langchain-google-genai google-generativeai")
    sys.exit(1)

async def test_model(model_name, api_key):
    print(f"\n🔍 正在测试模型: [{model_name}] ...")
    try:
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)
        response = await llm.ainvoke("你好，请简短确认 API 可用。")
        
        # 修复：处理可能的列表响应
        if isinstance(response.content, list):
            content = response.content[0] if response.content else ""
        else:
            content = response.content
        
        print(f"✅ 成功! 响应内容: {str(content).strip()}")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 失败! 错误详情:")
        if "404" in error_msg:
            print("   -> 原因: 404 NOT_FOUND。该模型名称可能不存在，或你的 Key 没有该模型权限。")
        elif "403" in error_msg:
            print("   -> 原因: 403 Permission Denied。API Key 权限受限，或区域被屏蔽。")
        elif "401" in error_msg:
            print("   -> 原因: 401 Unauthorized。API Key 无效或过期。")
        else:
            print(f"   -> {error_msg}")
        return False

async def list_available_models(api_key):
    """列出当前 API Key 实际可用的模型（调试神器）"""
    print("\n🔍 正在查询当前可用的 Gemini 模型列表...")
    try:
        client = genai.Client(api_key=api_key)
        available = []
        for m in client.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name.replace("models/", "")  # 去掉前缀
                available.append(model_name)
        if available:
            print("可用模型（部分）：")
            for name in available[:10]:  # 只显示前10个，避免太长
                print(f"  - {name}")
            if len(available) > 10:
                print(f"  ... 共 {len(available)} 个模型")
        else:
            print("未找到任何可用模型。请检查：")
            print("  1. API Key 是否正确")
            print("  2. 项目是否已启用 Generative Language API")
            print("  3. 是否绑定了 billing account")
    except Exception as e:
        print(f"查询模型列表失败: {str(e)}")

async def main():
    # 强制从当前目录加载 .env
    load_dotenv(override=True)
    api_key = os.getenv("GOOGLE_API_KEY")
    
    print("========================================")
    print("   织影系统 (Loom) - Google Gemini API 诊断工具（2026版）")
    print("========================================")
    
    if not api_key or api_key.startswith("your_") or len(api_key) < 20:
        print("❌ 错误: 未在 .env 中检测到有效的 GOOGLE_API_KEY")
        print("   请编辑 .env 文件并填入正确的格式：")
        print("   GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        return

    print(f"💡 检测到 API Key: {api_key[:8]}...{api_key[-4:]}")

    # 先列出可用模型（强烈推荐先看这个）
    await list_available_models(api_key)

    # 测试列表（2026年3月推荐模型）
    test_models = [
        "gemini-flash-latest",      # 最稳定通用版（推荐默认）
        "gemini-2.5-flash",         # 高性能 Flash
        "gemini-2.5-pro",           # Pro 版
        # "gemini-3.1-flash-preview", # 如果你想测试 Gemini 3 预览版，可取消注释
    ]
    
    print("\n开始测试以上模型...")
    results = []
    for model in test_models:
        success = await test_model(model, api_key)
        results.append((model, success))
    
    print("\n========================================")
    print("✨ 诊断总结:")
    for model, success in results:
        status = "✅ 可用" if success else "❌ 不可用"
        print(f"- {model}: {status}")
    print("========================================")
    
    print("\n提示：")
    print("1. 如果全部失败，请检查 Google AI Studio (aistudio.google.com) 是否能用同一个 Key 调用模型。")
    print("2. 确认项目已启用 'Generative Language API' 并绑定 billing。")
    print("3. 如需更多模型，运行上面的 list_available_models 输出列表。")

if __name__ == "__main__":
    asyncio.run(main())