#!/usr/bin/env python3
"""
超星学习通 智能刷课 — 交互式菜单
客户无需懂代码, 全部在屏幕上选

运行:
  python menu.py
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path

DIR = Path(__file__).parent
CONFIG_FILE = DIR / "user_config.json"

# 默认配置
DEFAULTS = {
    "phone": "",
    "password": "",
    "video_speed": 8,
    "video_skip": False,
    "video_bypass": True,
    "video_mute": True,
    "auto_answer": True,
    "auto_submit": True,
    "auto_next_chapter": True,
    "ai_provider": "opencode",
    "ai_siliconflow_key": "",
    "ai_openrouter_key": "",
}

MODEL_NAMES = {
    "opencode": "OpenCode DeepSeek V4 Flash (免费)",
    "siliconflow": "硅基流动 DeepSeek V3 (免费额度)",
    "openrouter": "OpenRouter DeepSeek V3 (免费)",
    "custom": "自定义API",
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULTS.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def banner():
    print("""
╔══════════════════════════════════════════════════════╗
║      🎓 超星学习通 智能刷课助手 v2.0               ║
║      自动刷视频 | AI答题 | 免费模型 | 秒过模式       ║
╚══════════════════════════════════════════════════════╝""")


def show_status(cfg):
    skip_text = "⚡ 秒过" if cfg["video_skip"] else f"{cfg['video_speed']}x 倍速"
    bypass_text = "✅ 开" if cfg["video_bypass"] else "❌ 关"
    answer_text = "✅ AI自动" if cfg["auto_answer"] else "❌ 关"
    submit_text = "✅ 自动交" if cfg["auto_submit"] else "📝 手动交"
    mute_text = "🔇 静音" if cfg["video_mute"] else "🔊 有声"
    next_text = "✅ 自动" if cfg["auto_next_chapter"] else "⏸ 手动"

    ai_name = MODEL_NAMES.get(cfg.get("ai_provider", "opencode"), cfg["ai_provider"])
    phone = cfg.get("phone", "")
    if phone:
        login_text = f"📱 {phone[:3]}****{phone[-4:]}"
    else:
        login_text = "📷 扫码登录"

    print(f"""
┌─ 当前配置 ──────────────────────────────────────────┐
│  登录方式: {login_text:<38}│
│  播放模式: {skip_text:<38}│
│  防回滚:   {bypass_text:<38}│
│  答题模式: {answer_text:<38}│
│  提交方式: {submit_text:<38}│
│  音频    : {mute_text:<38}│
│  下一章 : {next_text:<38}│
│  AI后端 : {ai_name:<38}│
└──────────────────────────────────────────────────────┘""")


def main_menu(cfg):
    show_status(cfg)
    print("""
┌─ 主菜单 ────────────────────────────────────────────┐
│  [1] 🚀 开始刷课                                    │
│  [2] 🔗 选择课程 (从课程列表)                        │
│  [3] 📋 填写/修改课程URL                             │
│  [4] ⚙️  播放设置 (速度/秒过/防回滚)                  │
│  [5] 🧠 AI答题设置                                  │
│  [6] 🔑 账号设置                                    │
│  [7] 🧪 测试AI是否正常                              │
│  [8] 📦 检查环境依赖                                │
│  [0] 退出                                          │
└──────────────────────────────────────────────────────┘""")


def speed_menu(cfg):
    clear()
    banner()
    print(f"""
┌─ 播放速度设置 ──────────────────────────────────────┐
│                                                     │
│  当前: {cfg['video_speed']}x 播放 | {'秒过' if cfg['video_skip'] else '正常播放'}                                    │
│                                                     │
│  速度说明:                                          │
│    1x = 正常 (一个40分钟视频要40分钟)                │
│    4x = 较快 (约10分钟)                              │
│    8x = 很快 (约5分钟)                               │
│   12x = 极速 (约3分钟)                               │
│   16x = 极限 (约2.5分钟)                             │
│   ⚡ = 秒过模式 (2秒一个视频, 跳过播放)              │
│                                                     │
│  配合防回滚功能, 所有速度服务器都认为你完整看完了     │
└──────────────────────────────────────────────────────┘

  [1] 1x   (正常)
  [2] 4x   (较快)
  [3] 8x   (很快) 🏷 推荐
  [4] 12x  (极速)
  [5] 16x  (极限)
  [6] ⚡ 秒过模式 (2秒/视频)
  [0] 返回
""")
    c = input("\n  请选择: ").strip()
    speeds = {1: 1, 2: 4, 3: 8, 4: 12, 5: 16}
    if c == "6":
        cfg["video_skip"] = True
        print("  ✅ 已开启秒过模式 (2秒一个视频)")
    elif c.isdigit() and int(c) in speeds:
        cfg["video_skip"] = False
        cfg["video_speed"] = speeds[int(c)]
        print(f"  ✅ 已设置为 {speeds[int(c)]}x 播放")
    save_config(cfg)
    input("\n  按回车返回...")


def ai_menu(cfg):
    clear()
    banner()
    provider = cfg.get("ai_provider", "opencode")
    answer = cfg["auto_answer"]
    submit = cfg["auto_submit"]

    print(f"""
┌─ AI答题设置 ────────────────────────────────────────┐
│                                                     │
│  当前AI: {MODEL_NAMES.get(provider, provider)}        │
│  自动答题: {'✅ 开' if answer else '❌ 关':<36}│
│  自动提交: {'✅ 开' if submit else '❌ 关 (答完等你确认)':<36}│
│                                                     │
└──────────────────────────────────────────────────────┘

  [1] 切换AI后端
  [2] {'关闭' if answer else '开启'}自动答题
  [3] {'开启' if submit else '关闭'}自动提交答案
  [4] 设置 SiliconFlow API Key
  [5] 设置 OpenRouter API Key
  [0] 返回
""")
    c = input("\n  请选择: ").strip()

    if c == "1":
        clear()
        banner()
        print("""
  选择AI后端:

  [1] OpenCode 免费模型 (零成本, 推荐!)
      使用您已安装的 DeepSeek V4 Flash, 完全免费

  [2] 硅基流动 SiliconFlow
      注册送免费额度, 国内直连

  [3] OpenRouter
      有免费模型, 需注册
""")
        c2 = input("  请选择: ").strip()
        providers = {"1": "opencode", "2": "siliconflow", "3": "openrouter"}
        if c2 in providers:
            cfg["ai_provider"] = providers[c2]
            save_config(cfg)
            input(f"\n  ✅ 已切换至 {MODEL_NAMES[providers[c2]]}\n  按回车返回...")
        return ai_menu(cfg)

    elif c == "2":
        cfg["auto_answer"] = not cfg["auto_answer"]
        save_config(cfg)
        return ai_menu(cfg)
    elif c == "3":
        cfg["auto_submit"] = not cfg["auto_submit"]
        save_config(cfg)
        return ai_menu(cfg)
    elif c == "4":
        key = input("  请输入 SiliconFlow API Key: ").strip()
        if key:
            cfg["ai_siliconflow_key"] = key
            save_config(cfg)
            print("  ✅ 已保存")
        input("  按回车返回...")
        return ai_menu(cfg)
    elif c == "5":
        key = input("  请输入 OpenRouter API Key: ").strip()
        if key:
            cfg["ai_openrouter_key"] = key
            save_config(cfg)
            print("  ✅ 已保存")
        input("  按回车返回...")
        return ai_menu(cfg)
    return


def account_menu(cfg):
    clear()
    banner()
    phone = cfg.get("phone", "")
    print(f"""
┌─ 账号设置 ──────────────────────────────────────────┐
│                                                     │
│  当前: {'📱 ' + phone[:3] + '****' + phone[-4:] if phone else '📷 扫码登录 (默认)'}          │
│                                                     │
│  提示: 留空使用扫码登录, 更安全                      │
└──────────────────────────────────────────────────────┘

  [1] 填写手机号和密码
  [2] 清除账号 (改用扫码登录)
  [0] 返回
""")
    c = input("\n  请选择: ").strip()
    if c == "1":
        phone = input("  手机号: ").strip()
        if phone:
            cfg["phone"] = phone
            cfg["password"] = input("  密码: ").strip()
            save_config(cfg)
            print("  ✅ 已保存")
    elif c == "2":
        cfg["phone"] = ""
        cfg["password"] = ""
        save_config(cfg)
        print("  ✅ 已清除, 将使用扫码登录")
    input("  按回车返回...")
    return account_menu(cfg) if c not in ("0",) else None


def test_ai(cfg):
    print("\n  🧠 测试AI答题...")
    try:
        import asyncio
        sys.path.insert(0, str(DIR))
        from chaoxing_auto import AIBackend

        config = {"ai": {"provider": cfg["ai_provider"]}}
        provider = cfg["ai_provider"]

        if provider == "opencode":
            config["ai"]["opencode"] = {
                "cmd": "opencode",
                "model": "opencode/deepseek-v4-flash-free",
                "timeout": 120,
            }
        elif provider == "siliconflow":
            config["ai"]["siliconflow"] = {
                "api_key": cfg.get("ai_siliconflow_key", ""),
                "model": "deepseek-ai/DeepSeek-V3",
                "base_url": "https://api.siliconflow.cn/v1/chat/completions",
            }
        elif provider == "openrouter":
            config["ai"]["openrouter"] = {
                "api_key": cfg.get("ai_openrouter_key", ""),
                "model": "deepseek/deepseek-chat-v3-0324:free",
                "base_url": "https://openrouter.ai/api/v1/chat/completions",
            }

        async def do_test():
            ai = AIBackend(config)
            ans = await ai.ask(
                "中国的首都在哪里？",
                ["上海", "北京", "广州", "深圳"],
                "choice",
            )
            await ai.close()
            return ans

        result = asyncio.run(do_test())
        if result and "B" in result.upper():
            print(f"  ✅ AI工作正常! 回答: {result}")
        elif result:
            print(f"  ⚠️  AI返回了答案但格式可能不对: {result}")
        else:
            print(f"  ❌ AI未返回结果, 请检查配置")
    except Exception as e:
        print(f"  ❌ AI测试失败: {e}")

    input("\n  按回车返回...")


def check_deps():
    print("\n  📦 检查环境...")
    deps_ok = True

    # Python
    print(f"  Python:        {'✅' if sys.version_info >= (3, 8) else '❌'} {sys.version.split()[0]}")

    # pip
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"],
                       capture_output=True, timeout=10)
        print("  pip:           ✅")
    except Exception:
        print("  pip:           ❌")
        deps_ok = False

    # Playwright
    try:
        import importlib
        importlib.import_module("playwright")
        print("  playwright:    ✅")
    except ImportError:
        print("  playwright:    ❌ 运行: pip install playwright")
        deps_ok = False

    # Chromium
    try:
        import subprocess
        r = subprocess.run(["playwright", "install", "chromium", "--dry-run"],
                           capture_output=True, timeout=10)
        print("  Chromium:      ✅")
    except Exception:
        try:
            # Check if chromium already installed
            import playwright
            print("  Chromium:      ✅")
        except Exception:
            print("  Chromium:      ⚠️  运行: playwright install chromium")

    # httpx
    try:
        importlib.import_module("httpx")
        print("  httpx:         ✅")
    except ImportError:
        print("  httpx:         ❌ 运行: pip install httpx")
        deps_ok = False

    # OpenCode
    op = shutil.which("opencode")
    if op:
        print(f"  OpenCode CLI:  ✅ {op}")
    else:
        print("  OpenCode CLI:  ⚠️  未安装, 无法使用免费AI")
        print("                 如需AI答题请运行: npm install -g opencode-ai")

    if deps_ok:
        print("\n  ✅ 环境就绪, 可以开始刷课!")
    else:
        print("\n  ⚠️  部分依赖缺失, 请先安装")

    input("\n  按回车返回...")


def start_auto(cfg):
    """启动刷课脚本"""
    clear()
    banner()

    # 保存配置并启动
    save_config(cfg)

    # 检查 OpenCode
    if cfg["ai_provider"] == "opencode" and not shutil.which("opencode"):
        print("\n  ⚠️  未检测到 OpenCode CLI!")
        print("     AI答题将不可用。")
        print("\n  [1] 继续 (仅刷视频, 不答题)")
        print("  [2] 取消, 切换AI后端")
        c = input("\n  请选择: ").strip()
        if c == "2":
            return

    print("""
  🚀 正在启动浏览器...

  使用提示:
  - 扫码登录完成后, 回到终端按回车继续
  - 课程列表会显示在终端里, 输入编号选择
  - 视频和答题全自动进行
  - 按 Ctrl+C 可随时停止
  - 一门课完成后可选择继续下一门
  """)
    input("  按回车开始...")

    # 运行主脚本
    try:
        subprocess.run(
            [sys.executable, str(DIR / "chaoxing_auto.py"),
             "--no-headless", "--config", str(CONFIG_FILE)],
            cwd=str(DIR),
        )
    except KeyboardInterrupt:
        print("\n\n  ⏹ 已停止")
    except Exception as e:
        print(f"\n  ❌ 运行出错: {e}")

    input("\n  按回车返回主菜单...")


def url_menu(cfg):
    clear()
    banner()
    current = cfg.get("course_url", "")
    if current:
        print(f"\n  当前课程URL:")
        print(f"  {current[:100]}...")
    else:
        print("\n  当前: 未设置 (将使用课程列表选择)")

    print("\n  [1] 输入新的课程URL")
    print("  [2] 清除 (使用课程列表选择)")
    print("  [0] 返回")
    c = input("\n  请选择: ").strip()
    if c == "1":
        url = input("  粘贴课程URL: ").strip()
        if url:
            cfg["course_url"] = url
            save_config(cfg)
            print("  ✅ 已保存")
    elif c == "2":
        cfg.pop("course_url", None)
        save_config(cfg)
        print("  ✅ 已清除, 将使用课程列表")
    input("  按回车返回...")


def main():
    cfg = load_config()

    while True:
        clear()
        banner()
        main_menu(cfg)
        c = input("\n  请选择 [0-8]: ").strip()

        if c == "1":
            start_auto(cfg)
        elif c == "2":
            # 启动选课模式
            save_config(cfg)
            subprocess.run(
                [sys.executable, str(DIR / "chaoxing_auto.py"),
                 "--no-headless", "--config", str(CONFIG_FILE),
                 "--select-only"],
                cwd=str(DIR),
            )
        elif c == "3":
            url_menu(cfg)
        elif c == "4":
            speed_menu(cfg)
        elif c == "5":
            ai_menu(cfg)
        elif c == "6":
            account_menu(cfg)
        elif c == "7":
            test_ai(cfg)
        elif c == "8":
            check_deps()
        elif c == "0":
            print("\n  👋 再见!\n")
            break
        else:
            print("\n  无效选择, 请重试")
            input("  按回车继续...")


if __name__ == "__main__":
    main()
