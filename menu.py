#!/usr/bin/env python3
"""
超星学习通 智能刷课 — 交互式菜单
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path

DIR = Path(__file__).parent
CONFIG_FILE = DIR / "user_config.json"

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
    "opencode_model": "opencode/deepseek-v4-flash-free",
    "custom_base_url": "",
    "custom_api_key": "",
    "custom_model": "",
}

# OpenCode 免费模型列表
OPENCODE_MODELS = {
    "1": ("opencode/deepseek-v4-flash-free", "DeepSeek V4 Flash"),
    "2": ("opencode/big-pickle", "Big Pickle"),
    "3": ("opencode/mimo-v2.5-free", "MiMo V2.5"),
    "4": ("opencode/minimax-m3-free", "MiniMax M3"),
    "5": ("opencode/nemotron-3-super-free", "Nemotron 3 Super"),
}

# 主流中转站/API 预设
API_PRESETS = {
    "1": ("SiliconFlow (硅基流动)", "https://api.siliconflow.cn/v1/chat/completions", "deepseek-ai/DeepSeek-V3"),
    "2": ("OpenRouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat-v3-0324:free"),
    "3": ("DeepSeek 官方", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
    "4": ("OpenAI", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "5": ("通义千问 (DashScope)", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-plus"),
    "6": ("自定义中转站", "", ""),
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULTS.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULTS.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def banner():
    print("""
╔══════════════════════════════════════════════════════╗
║        超星学习通 智能刷课助手 v2.0                  ║
╚══════════════════════════════════════════════════════╝""")


def show_status(cfg):
    skip_text = "⚡ 秒过 (2秒/视频)" if cfg["video_skip"] else f"{cfg['video_speed']}x 倍速"
    if cfg["ai_provider"] == "opencode":
        model = cfg.get("opencode_model", "").split("/")[-1]
        ai_text = f"OpenCode {model}"
    elif cfg["ai_provider"] == "custom":
        ai_text = f"API: {cfg.get('custom_model', '?')}"
    else:
        ai_text = cfg["ai_provider"]

    print(f"""
┌──────────────────────────────────────────────────────┐
│  播放: {skip_text:<46}│
│  AI  : {ai_text:<46}│
│  答题: {'自动答题+自动提交' if cfg['auto_answer'] else '关闭':<46}│
└──────────────────────────────────────────────────────┘""")


def main_menu(cfg):
    show_status(cfg)
    print("""
  [1] 🚀 开始刷课
  [2] ⚙️  播放设置
  [3] 🧠 AI设置
  [0] 退出
""")


# ═══════════════════════════════════════════════════════
#  播放设置
# ═══════════════════════════════════════════════════════

def speed_menu(cfg):
    clear()
    banner()
    current = "⚡ 秒过" if cfg["video_skip"] else f"{cfg['video_speed']}x"
    print(f"""
  当前: {current}

  ── 倍速播放 ──────────────────────────────
  [1]  4x   40分钟视频 → 约10分钟
  [2]  8x   40分钟视频 → 约5分钟    ← 推荐
  [3] 12x   40分钟视频 → 约3分钟
  [4] 16x   40分钟视频 → 约2.5分钟

  ── 秒过 ──────────────────────────────────
  [5] ⚡ 秒过  每个视频2秒完成

  [0] 返回
""")
    c = input("  请选择: ").strip()
    speeds = {"1": 4, "2": 8, "3": 12, "4": 16}
    if c in speeds:
        cfg["video_skip"] = False
        cfg["video_speed"] = speeds[c]
        print(f"\n  ✅ 已设置 {speeds[c]}x 倍速")
    elif c == "5":
        cfg["video_skip"] = True
        print("\n  ✅ 已开启秒过模式")
    save_config(cfg)
    if c != "0":
        input("  按回车返回...")


# ═══════════════════════════════════════════════════════
#  AI 设置
# ═══════════════════════════════════════════════════════

def ai_menu(cfg):
    while True:
        clear()
        banner()

        if cfg["ai_provider"] == "opencode":
            model = cfg.get("opencode_model", "").split("/")[-1]
            print(f"\n  当前: OpenCode {model} (免费)")
        elif cfg["ai_provider"] == "custom":
            print(f"\n  当前: {cfg.get('custom_model', '?')} @ {cfg.get('custom_base_url', '?')[:40]}")
        else:
            print(f"\n  当前: {cfg['ai_provider']}")

        print(f"""
  [1] OpenCode 免费模型 (选择模型)
  [2] API 接入 (主流平台/自定义中转站)
  [3] {'关闭' if cfg['auto_answer'] else '开启'}自动答题
  [0] 返回
""")
        c = input("  请选择: ").strip()

        if c == "1":
            opencode_model_menu(cfg)
        elif c == "2":
            api_menu(cfg)
        elif c == "3":
            cfg["auto_answer"] = not cfg["auto_answer"]
            save_config(cfg)
        elif c == "0":
            return


def opencode_model_menu(cfg):
    clear()
    banner()
    current = cfg.get("opencode_model", "")
    print(f"\n  当前模型: {current}\n")
    print("  ── OpenCode 免费模型 ─────────────────────")
    for k, (model_id, name) in OPENCODE_MODELS.items():
        marker = " ←" if model_id == current else ""
        print(f"  [{k}] {name}{marker}")
    print("\n  [0] 返回\n")

    c = input("  请选择: ").strip()
    if c in OPENCODE_MODELS:
        model_id, name = OPENCODE_MODELS[c]
        cfg["ai_provider"] = "opencode"
        cfg["opencode_model"] = model_id
        save_config(cfg)
        print(f"\n  ✅ 已选择 {name}")
        input("  按回车返回...")


def api_menu(cfg):
    clear()
    banner()
    print("""
  ── 选择API平台 ───────────────────────────
  [1] SiliconFlow 硅基流动  (注册送额度, 国内直连)
  [2] OpenRouter            (有免费模型)
  [3] DeepSeek 官方         (极低价)
  [4] OpenAI                (需API Key)
  [5] 通义千问 DashScope    (阿里云)
  [6] 自定义中转站          (填URL+Key+模型名)

  [0] 返回
""")
    c = input("  请选择: ").strip()

    if c not in API_PRESETS or c == "0":
        return

    name, base_url, model = API_PRESETS[c]

    if c == "6":
        print(f"\n  ── 自定义中转站配置 ──")
        base_url = input("  API Base URL (如 https://xxx.com/v1/chat/completions): ").strip()
        model = input("  模型名称 (如 gpt-4o-mini): ").strip()
    else:
        print(f"\n  已选择: {name}")
        print(f"  地址: {base_url}")
        print(f"  模型: {model}")
        custom_model = input(f"\n  更换模型名? (回车保持 {model}): ").strip()
        if custom_model:
            model = custom_model

    api_key = input("  API Key: ").strip()
    if not api_key:
        print("\n  ❌ 未输入API Key, 取消")
        input("  按回车返回...")
        return

    cfg["ai_provider"] = "custom"
    cfg["custom_base_url"] = base_url
    cfg["custom_api_key"] = api_key
    cfg["custom_model"] = model
    save_config(cfg)
    print(f"\n  ✅ 已配置 {name}: {model}")
    input("  按回车返回...")


# ═══════════════════════════════════════════════════════
#  启动刷课
# ═══════════════════════════════════════════════════════

def start_auto(cfg):
    clear()
    banner()

    if cfg["ai_provider"] == "opencode" and not shutil.which("opencode"):
        print("\n  ⚠️  未检测到 OpenCode CLI, AI答题不可用")
        print("  [1] 继续 (仅刷视频)")
        print("  [2] 返回设置AI")
        if input("\n  请选择: ").strip() == "2":
            return

    # 登录方式选择
    print("""
  ── 登录方式 ──────────────────────────────
  [1] 📷 扫码登录 (推荐)
  [2] 📱 手机号+密码登录
""")
    login = input("  请选择: ").strip()
    if login == "2":
        phone = cfg.get("phone", "")
        if phone:
            print(f"  已有账号: {phone[:3]}****{phone[-4:]}")
            use = input("  使用此账号? (y/n): ").strip().lower()
            if use not in ("y", "yes", ""):
                phone = ""
        if not phone:
            phone = input("  手机号: ").strip()
            cfg["password"] = input("  密码: ").strip()
        cfg["phone"] = phone
    else:
        cfg["phone"] = ""
        cfg["password"] = ""

    save_config(cfg)

    print("""
  🚀 即将启动...

  操作流程:
  1. 浏览器弹出 → 登录
  2. 选择课程
  3. 手动点击要刷的章节
  4. 回到终端按回车 → 自动开始
  5. Ctrl+C 随时停止
""")
    input("  按回车开始...")

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


# ═══════════════════════════════════════════════════════
#  主循环
# ═══════════════════════════════════════════════════════

def main():
    cfg = load_config()

    while True:
        clear()
        banner()
        main_menu(cfg)
        c = input("  请选择 [0-3]: ").strip()

        if c == "1":
            start_auto(cfg)
        elif c == "2":
            speed_menu(cfg)
        elif c == "3":
            ai_menu(cfg)
        elif c == "0":
            print("\n  再见!\n")
            break


if __name__ == "__main__":
    main()
