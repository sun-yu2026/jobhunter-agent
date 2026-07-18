"""
连通性冒烟测试 - Step 2 验证脚本

目的:确认 .env 里配置的 ARK_API_KEY / LLM_MODEL / LLM_BASE_URL 三件套
能真正调通火山方舟 CodingPlan 的 API。

预期输出:模型的一句自我介绍。
如果报错,把错误全文贴回来分析。
"""
import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 让 print 的中文在 Windows 上不乱码
sys.stdout.reconfigure(encoding="utf-8")

# 从 .env 读取配置
load_dotenv()

api_key = os.getenv("ARK_API_KEY")
base_url = os.getenv("LLM_BASE_URL")
model = os.getenv("LLM_MODEL")

# 先打印一下读到的配置(key 只显示前 12 位,不泄露)
print("=" * 50)
print("配置检查:")
print(f"  ARK_API_KEY = {api_key[:12]}... (长度 {len(api_key)})" if api_key else "  ARK_API_KEY = ❌ 未读到")
print(f"  LLM_BASE_URL = {base_url}")
print(f"  LLM_MODEL = {model}")
print("=" * 50)

if not all([api_key, base_url, model]):
    print("❌ .env 里有配置缺失,请检查")
    sys.exit(1)

# 构造 LLM 客户端
llm = ChatOpenAI(
    api_key=api_key,
    base_url=base_url,
    model=model,
    temperature=0,
)

# 发一句最短的调用
print("\n正在调用模型...")
resp = llm.invoke("用一句话介绍你自己,不超过 20 个字。")

print("\n" + "=" * 50)
print("✅ 调用成功!模型回复:")
print(resp.content)
print("=" * 50)
