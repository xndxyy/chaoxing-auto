#!/usr/bin/env python3
"""
超星学习通 自动刷课 + AI自动答题
Playwright 自动化浏览器 + AI模型自动答题

支持3种AI后端:
  1. opencode  — 直接调用本地 OpenCode CLI (免费, 零成本!)
  2. siliconflow — 硅基流动API (注册送免费额度)
  3. openrouter  — OpenRouter API (有免费模型)

使用前:
  pip install playwright httpx
  playwright install chromium

运行:
  python chaoxing_auto.py --no-headless
"""

import asyncio
import json
import re
import sys
import time
import random
import argparse
import subprocess
import shutil
from pathlib import Path

import httpx

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
except ImportError:
    print("请先安装 playwright:  pip install playwright && playwright install chromium")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
#  配 置 — 修改这里
# ═══════════════════════════════════════════════════════════════

CONFIG = {
    # ---- 登录信息 ----
    "phone": "",          # 手机号, 留空则使用扫码登录
    "password": "",       # 密码

    # ---- 课程 ----
    "course_url": "",  # 留空则从课程列表选择, 或粘贴课程页URL

    # ---- 刷课设置 ----
    "video_speed": 8,         # 倍速 (JS注入绕过UI限制,推荐4-16)
    "video_bypass": True,     # True=劫持上报函数, 永远报告"已看完" (防回滚)
    "video_skip": False,      # True=直接跳到末尾秒过 (风险高)
    "video_mute": True,       # 静音
    "auto_next_chapter": True,  # 自动下一章
    "auto_answer": True,      # 自动答题
    "auto_submit": True,      # 自动提交 (AI答完自动提交)
    "random_delay": (1, 3),   # 随机延迟范围(秒), 模拟人类

    # ---- AI 答题配置 ----
    # provider 选择:
    #   "opencode"    — 调用本地 OpenCode CLI, 用它的免费Zen模型, 零成本!
    #   "siliconflow" — 硅基流动API, 注册送免费额度
    #   "openrouter"  — OpenRouter API, 有免费模型
    #   "custom"      — 任何 OpenAI 兼容接口
    "ai": {
        "provider": "opencode",  # <-- 默认用 OpenCode!

        "opencode": {
            "cmd": "opencode",
            "model": "opencode/deepseek-v4-flash-free",  # 免费模型
            "timeout": 120,
        },

        "siliconflow": {
            "api_key": "",
            "model": "deepseek-ai/DeepSeek-V3",
            "base_url": "https://api.siliconflow.cn/v1/chat/completions",
        },

        "openrouter": {
            "api_key": "",
            "model": "deepseek/deepseek-chat-v3-0324:free",
            "base_url": "https://openrouter.ai/api/v1/chat/completions",
        },

        "custom": {
            "api_key": "",
            "model": "",
            "base_url": "",
        },
    },
}


# ═══════════════════════════════════════════════════════════════
#  AI 答题后端
# ═══════════════════════════════════════════════════════════════

class AIBackend:
    """AI答题后端, 支持 OpenCode CLI / SiliconFlow / OpenRouter / 自定义API"""

    def __init__(self, config: dict):
        self.provider = config["ai"]["provider"]
        self.ai_cfg = config["ai"][self.provider]

        if self.provider == "opencode":
            self.opencode_cmd = self.ai_cfg.get("cmd", "opencode")
            self.opencode_model = self.ai_cfg.get("model", "opencode/deepseek-v4-flash-free")
            self.opencode_timeout = self.ai_cfg.get("timeout", 120)
            self._check_opencode()
            self.client = None
        else:
            self.api_key = self.ai_cfg.get("api_key", "")
            self.model = self.ai_cfg.get("model", "")
            self.base_url = self.ai_cfg.get("base_url", "")
            self.client = httpx.AsyncClient(timeout=60)

    def _check_opencode(self):
        """检查 OpenCode CLI 是否可用"""
        path = shutil.which(self.opencode_cmd)
        if path:
            print(f"[AI] OpenCode CLI 已找到: {path}")
            print(f"[AI] 模型: {self.opencode_model}")
        else:
            print(f"[AI] 警告: 未找到 '{self.opencode_cmd}' 命令")
            print("     安装: npm install -g opencode-ai")
            print("     或修改 CONFIG['ai']['provider'] 为其他后端")

    def _build_prompt(self, question: str, options: list[str] = None,
                      q_type: str = "choice") -> str:
        """构建提问 prompt"""
        if q_type == "choice" and options:
            opts_text = "\n".join(f"  {chr(65+i)}. {o}" for i, o in enumerate(options))
            return (
                f"你是一个答题助手。请根据题目选出正确答案。\n"
                f"题目：{question}\n"
                f"选项：\n{opts_text}\n\n"
                f"请只回复正确选项的字母(如 A 或 AB)，不要任何解释。"
            )
        elif q_type == "judge":
            return (
                f"你是一个答题助手。判断题，请判断以下说法是否正确。\n"
                f"题目：{question}\n\n"
                f"请只回复 对 或 错，不要任何解释。"
            )
        else:
            return (
                f"你是一个答题助手。请简洁回答以下题目（20字以内）。\n"
                f"题目：{question}\n\n"
                f"直接给出答案，不要解释。"
            )

    async def ask(self, question: str, options: list[str] = None,
                  q_type: str = "choice") -> str:
        """向AI提问, 返回答案"""
        prompt = self._build_prompt(question, options, q_type)

        if self.provider == "opencode":
            return await self._ask_opencode(prompt)
        else:
            return await self._ask_api(prompt)

    async def _ask_opencode(self, prompt: str) -> str:
        """通过 opencode run -m 非交互模式获取回答 (免费Zen模型)"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._run_opencode, prompt)
            if result:
                answer = self._clean_opencode_output(result)
                print(f"  [AI/OpenCode] 回答: {answer}")
                return answer
            return ""
        except Exception as e:
            print(f"  [AI/OpenCode] 调用失败: {e}")
            return ""

    def _run_opencode(self, prompt: str) -> str:
        """subprocess 调用 opencode run (shell=True 兼容 Windows .CMD)"""
        try:
            # Windows 下 .CMD 文件需要 shell=True 才能被 subprocess 找到
            # prompt 中的引号用 json.dumps 安全转义
            import json as _json
            escaped = _json.dumps(prompt, ensure_ascii=False)
            cmd = f'{self.opencode_cmd} run -m {self.opencode_model} {escaped}'
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.opencode_timeout,
                shell=True,
                encoding="utf-8",
                errors="replace",
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            print(f"  [AI/OpenCode] 超时 ({self.opencode_timeout}s)")
            return ""
        except FileNotFoundError:
            print(f"  [AI/OpenCode] 命令不存在: {self.opencode_cmd}")
            print(f"  安装: npm install -g opencode-ai")
            return ""

    def _clean_opencode_output(self, raw: str) -> str:
        """清理 OpenCode 输出, 去掉 ANSI 转义码和装饰行, 提取核心答案"""
        # 去掉 ANSI 转义码
        ansi_re = re.compile(r'\x1b\[[0-9;]*m')
        raw = ansi_re.sub('', raw)

        lines = raw.strip().splitlines()
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过 opencode 的状态行 ("> build · model-name" 等)
            if line.startswith(">") and "·" in line:
                continue
            if any(skip in line.lower() for skip in [
                "─", "━", "═", "▶", "●", "loading", "thinking",
            ]):
                continue
            cleaned.append(line)

        if cleaned:
            return "\n".join(cleaned).strip()
        return lines[-1].strip() if lines else ""

    async def _ask_api(self, prompt: str) -> str:
        """通过 HTTP API 获取回答 (SiliconFlow/OpenRouter/自定义)"""
        if not self.api_key:
            print("  [AI] 未配置API Key, 跳过自动答题")
            return ""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.1,
            }
            resp = await self.client.post(self.base_url, headers=headers, json=body)
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"].strip()
            print(f"  [AI/{self.provider}] 回答: {answer}")
            return answer
        except Exception as e:
            print(f"  [AI/{self.provider}] 请求失败: {e}")
            return ""

    async def close(self):
        if self.client:
            await self.client.aclose()


# ═══════════════════════════════════════════════════════════════
#  学习通自动化核心
# ═══════════════════════════════════════════════════════════════

class ChaoxingAuto:
    def __init__(self, config: dict, headless: bool = True):
        self.config = config
        self.headless = headless
        self.ai = AIBackend(config)
        self.page: Page = None
        self.context: BrowserContext = None
        self.stats = {"videos": 0, "quizzes": 0, "chapters": 0}

    async def start(self):
        """启动浏览器"""
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        # 注入反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        self.page = await self.context.new_page()
        print("[启动] 浏览器已启动")

    async def random_delay(self):
        lo, hi = self.config["random_delay"]
        delay = random.uniform(lo, hi)
        await asyncio.sleep(delay)

    # ---- 登录 ----
    async def login(self):
        """登录学习通"""
        print("[登录] 正在打开登录页...")
        await self.page.goto("https://passport2.chaoxing.com/login"
                             "?fid=&newversion=true&refer=https://i.chaoxing.com")
        await self.page.wait_for_load_state("domcontentloaded")

        phone = self.config["phone"]
        password = self.config["password"]

        if phone and password:
            # 手机号+密码登录
            print(f"[登录] 使用手机号 {phone[:3]}****{phone[-4:]} 登录")
            # 切换到手机号登录
            phone_tab = self.page.locator("#phoneLoginBtn, .phone-login, "
                                          "a:has-text('手机号登录')")
            if await phone_tab.count() > 0:
                await phone_tab.first.click()
                await asyncio.sleep(1)

            # 填写手机号
            phone_input = self.page.locator("#phone, input[name='phone'], "
                                            "input[placeholder*='手机号']")
            await phone_input.fill(phone)

            # 填写密码
            pwd_input = self.page.locator("#pwd, input[name='pwd'], "
                                          "input[type='password']")
            await pwd_input.fill(password)

            # 勾选同意协议
            agree = self.page.locator("#agree, .agree-checkbox, "
                                       "input[type='checkbox']")
            if await agree.count() > 0:
                checked = await agree.first.is_checked()
                if not checked:
                    await agree.first.click()

            # 点击登录
            login_btn = self.page.locator("#loginBtn, .btn-login, "
                                           "button:has-text('登录')")
            await login_btn.first.click()
            print("[登录] 已点击登录按钮, 等待跳转...")
        else:
            # 扫码登录
            print("[登录] 未配置账号密码, 请扫码登录")
            print("       请在浏览器窗口中扫码, 完成后按回车继续...")
            await asyncio.get_event_loop().run_in_executor(None, input)

        # 等待登录成功 — 检测URL变化
        for _ in range(60):
            url = self.page.url
            if "i.chaoxing.com" in url or "mooc" in url or "mycourse" in url:
                print("[登录] 登录成功!")
                return True
            await asyncio.sleep(1)

        print("[登录] 登录超时, 请检查账号密码")
        return False

    # ---- 课程选择 ----
    async def select_course(self) -> bool:
        """打开课程列表页, 让用户选择, 然后点击课程名链接进入"""
        print("[选课] 正在打开课程列表页面...")

        await self.page.goto(
            "https://mooc2-ans.chaoxing.com/visit/courses/list",
            wait_until="domcontentloaded", timeout=60000
        )
        await asyncio.sleep(4)

        # 从截图看, 课程名是橙色 <a> 链接, 和"移动到"/"退课"混在一起
        # 直接获取所有 <a> 链接, 按文本过滤
        all_links = self.page.locator("a")
        count = await all_links.count()

        courses = []
        junk = {"移动到", "退课", "置顶", "删除", "更多", "编辑", "归档",
                "首页", "课程", "通知", "我的", ""}

        for i in range(count):
            link = all_links.nth(i)
            try:
                text = (await link.text_content() or "").strip()
                href = (await link.get_attribute("href")) or ""

                # 课程链接特征: 文本不是垃圾词, href 指向课程页
                if text in junk or len(text) < 2 or len(text) > 80:
                    continue
                # 课程链接通常包含 courseid 或 clazzid 或 mycourse
                is_course_link = any(kw in href.lower() for kw in
                    ["courseid", "clazzid", "mycourse", "studentstudy",
                     "course/", "clazz/"])
                # 或者文本看起来像课程名 (含年份/学科关键词)
                if is_course_link or href.startswith("/visit/courses/"):
                    courses.append({
                        "name": text,
                        "link_index": i,
                    })
            except Exception:
                continue

        if not courses:
            print("[选课] 未找到课程链接, 将使用配置中的 course_url")
            return False

        # 去重 (同名课程可能出现多次)
        seen = set()
        unique = []
        for c in courses:
            if c["name"] not in seen:
                seen.add(c["name"])
                unique.append(c)
        courses = unique

        # ---- 显示列表 ----
        print(f"\n{'='*60}")
        print(f"  找到 {len(courses)} 门课程")
        print(f"{'='*60}")
        for i, c in enumerate(courses):
            print(f"  [{i+1}] {c['name']}")
        print(f"  [0] 使用配置中的默认课程URL")
        print(f"{'='*60}")

        choice = await asyncio.get_event_loop().run_in_executor(
            None, lambda: input(f"\n请选择课程 (1-{len(courses)}, 0=默认): ").strip()
        )

        try:
            idx = int(choice)
        except ValueError:
            idx = 0

        if idx < 1 or idx > len(courses):
            print("[选课] 使用默认课程URL")
            return False

        selected = courses[idx - 1]
        print(f"[选课] 已选择: {selected['name']}")

        # ---- 点击课程名链接 ----
        link_el = all_links.nth(selected["link_index"])

        # 先尝试捕获新标签页 (学习通常用 target=_blank)
        new_page = None
        try:
            async with self.context.expect_page(timeout=8000) as new_page_info:
                await link_el.click()
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded", timeout=30000)
            print(f"[选课] 新标签页: {new_page.url[:80]}")
            await self.page.close()
            self.page = new_page
        except Exception:
            # 没打开新标签页, 可能是同页面跳转
            await asyncio.sleep(3)
            print(f"[选课] 当前页面: {self.page.url[:80]}")

        await asyncio.sleep(5)

        # 进入章节学习页
        if "studentstudy" not in self.page.url:
            await self._enter_first_chapter()
            await asyncio.sleep(5)

        print(f"[选课] 最终页面: {self.page.url[:100]}")
        print("[选课] 课程页面已加载")
        return True

    async def _enter_first_chapter(self):
        """从课程主页进入第一个章节学习页"""
        print("[选课] 尝试进入章节学习页...")

        # 方式1: 在当前页面或iframe中找章节入口链接
        for selector in [
            "a[href*='studentstudy']",
            "a[href*='chapterId']",
            "a:has-text('开始学习')",
            "a:has-text('章节')",
        ]:
            link = self.page.locator(selector)
            if await link.count() > 0:
                try:
                    async with self.context.expect_page(timeout=8000) as npi:
                        await link.first.click()
                    np = await npi.value
                    await np.wait_for_load_state("domcontentloaded", timeout=30000)
                    await self.page.close()
                    self.page = np
                except Exception:
                    await asyncio.sleep(3)
                if "studentstudy" in self.page.url or "knowledge" in self.page.url:
                    print(f"[选课] 已进入章节页: {self.page.url[:80]}")
                    return

        # 方式2: 在 iframe 里找
        for frame in self.page.frames:
            furl = frame.url or ""
            if "studentstudy" in furl or "knowledge" in furl:
                print(f"[选课] 在iframe中找到章节页: {furl[:80]}")
                return

        # 方式3: 手动兜底
        print("[选课] 未能自动进入章节页")
        print("       请在浏览器中手动点击第一个章节, 然后按回车继续...")
        await asyncio.get_event_loop().run_in_executor(None, input)

    async def _fetch_courses_json(self) -> list:
        """从JSON API获取课程列表(备用方案)"""
        courses = []
        try:
            await self.page.goto(
                "https://mooc1-api.chaoxing.com/mycourse/backclazzdata"
                "?view=json&rss=1",
                wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(2)
            body = await self.page.locator("body").text_content()
            data = json.loads(body)
            for item in data.get("channelList", []):
                content = item.get("content", {})
                if not content:
                    continue
                # 课程名在 course.data[0].name, 不是 content.name(那是班级名)
                course_data = content.get("course", {}).get("data", [])
                if isinstance(course_data, list) and course_data:
                    course_info = course_data[0]
                else:
                    continue
                course_name = course_info.get("name", "")
                class_name = content.get("name", "")
                display = course_name or class_name
                if class_name and course_name and class_name != course_name:
                    display = f"{course_name} ({class_name})"

                course_id = str(course_info.get("id", ""))
                clazzid = str(content.get("id", ""))
                cpi = str(content.get("cpi", ""))

                if display and course_id:
                    # 构造带签名的URL: 通过页面导航获取
                    courses.append({
                        "name": display,
                        "courseId": course_id,
                        "clazzid": clazzid,
                        "cpi": cpi,
                    })
        except Exception as e:
            print(f"[选课] JSON接口请求失败: {e}")

        # 如果拿到了JSON数据, 需要通过页面点击进入(而非拼URL)
        # 回到课程列表页, 以便后续点击
        if courses:
            await self.page.goto(
                "https://i.chaoxing.com/base",
                wait_until="domcontentloaded", timeout=60000
            )
            await asyncio.sleep(3)

        return courses

    # ---- 导航到课程 ----
    async def go_to_course(self):
        """进入课程页面 (使用配置中的URL)"""
        url = self.config["course_url"]
        print(f"[课程] 正在进入课程页面...")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        print("[课程] 课程页面已加载")

    # ---- 获取章节列表 ----
    async def get_chapters(self) -> list[dict]:
        """获取左侧章节列表"""
        chapters = []
        items = self.page.locator(".chapter_unit .chapter_item, "
                                   ".ncells .cells, "
                                   ".prev_ul li[id], "
                                   ".chapter_item[class*='chapter']")
        count = await items.count()
        if count == 0:
            # 备用选择器
            items = self.page.locator(".posCatalog_select li, "
                                       ".catalog_points li")
            count = await items.count()

        for i in range(count):
            item = items.nth(i)
            title = (await item.text_content() or "").strip()[:50]
            chapters.append({"index": i, "title": title, "element": item})

        print(f"[章节] 找到 {len(chapters)} 个章节")
        return chapters

    # ---- 劫持进度上报 (秒过核心) ----
    async def _inject_video_bypass(self):
        """注入JS劫持sendTimePack, 永远向服务器报告已看完视频时长"""
        if not self.config.get("video_bypass", True):
            return

        bypass_js = """
        (function() {
            if (window.__bypass_injected) return;
            window.__bypass_injected = true;
            console.log('[秒过] 开始注入...');

            // 等待iframe#iframe加载, 然后hook params2VideoOpt获取参数
            function tryHook() {
                const outer = document.getElementById('iframe');
                if (!outer || !outer.contentWindow) {
                    setTimeout(tryHook, 1000);
                    return;
                }
                const w = outer.contentWindow;
                if (!w.ans || !w.ans.VideoJs) {
                    setTimeout(tryHook, 1000);
                    return;
                }

                const orig = w.ans.VideoJs.prototype.params2VideoOpt;
                w.ans.VideoJs.prototype.params2VideoOpt = function() {
                    const params = arguments[0];
                    const result = orig.apply(this, arguments);

                    const d = parseInt(params.duration) || 0;
                    if (d <= 0) return result;

                    // 覆盖report函数 — 无论实际播放多久, 都报playingTime=duration
                    const origReport = w.sendTimePack;
                    w.sendTimePack = function(time, cb) {
                        const playTime = d;  // 永远报满总时长
                        const enc = '[' + params.clazzId + '][' + params.userid + '][' +
                            params.jobid + '][' + params.objectId + '][' +
                            (playTime * 1000) + '][d_yHJ!$pdA~5][' +
                            (d * 1000) + '][0_' + d + ']';
                        const signed = w.md5 ? w.md5(enc) : enc;

                        const url = params.reportUrl + '/' + params.dtoken +
                            '?clipTime=0_' + d +
                            '&otherInfo=' + encodeURIComponent(params.otherInfo||'') +
                            '&userid=' + params.userid +
                            '&rt=0.9' +
                            '&jobid=' + params.jobid +
                            '&duration=' + d +
                            '&dtype=Video' +
                            '&objectId=' + params.objectId +
                            '&clazzId=' + params.clazzId +
                            '&view=pc' +
                            '&playingTime=' + playTime +
                            '&isdrag=4' +
                            '&enc=' + signed;

                        console.log('[秒过] 上报完成: playingTime=' + playTime + '/' + d);
                        if (w.jQuery && w.jQuery.get) {
                            w.jQuery.get(url, function(data) {
                                cb(data && data.isPassed);
                            });
                        } else {
                            cb(true);
                        }
                    };

                    // 也hook reportTime (某些版本用这个)
                    if (w.reportTime) {
                        const origRT = w.reportTime;
                        w.reportTime = function() {
                            w.sendTimePack(d, function(passed) {
                                console.log('[秒过] reportTime 已拦截, passed=' + passed);
                            });
                        };
                    }

                    console.log('[秒过] 注入成功! duration=' + d +
                        ' 所有上报将报告已观看' + d + '秒');
                };

                // 如果已有视频加载, 手动触发hook
                const oldIframe = document.querySelector('iframe.ans-insertvideo-online, iframe[src*="video"]');
                if (oldIframe && oldIframe.contentWindow) {
                    const v = oldIframe.contentWindow.document.querySelector('video');
                    if (v && v.duration > 0) {
                        // 视频已存在, 通过已有的params2VideoOpt调用重新hook
                        // 如果不行, 直接删掉video的report
                        console.log('[秒过] 检测到已加载视频, duration=' + v.duration);
                    }
                }
            }

            // 页面可能还在加载, 延迟尝试
            if (document.readyState === 'complete') {
                setTimeout(tryHook, 2000);
            } else {
                window.addEventListener('load', function() {
                    setTimeout(tryHook, 2000);
                });
            }
        })();
        """

        try:
            await self.page.evaluate(bypass_js)
            print("  [秒过] 进度上报劫持已注入 (所有视频将报告已看完)")
        except Exception as e:
            print(f"  [秒过] 注入失败: {e}")

    # ---- 处理视频任务 ----
    async def handle_video(self):
        """处理视频播放任务"""
        print("  [视频] 检测视频任务点...")

        # 学习通视频在多层iframe中: page > #iframe > iframe.ans-insertvideo-online
        # 尝试多种方式定位视频iframe
        video_frame = None

        # 方式1: 通过 #iframe 进入
        outer_iframe = self.page.frame_locator("#iframe")
        inner_frames = outer_iframe.locator(
            "iframe.ans-insertvideo-online, "
            "iframe[src*='video/index'], "
            "iframe[src*='ananas/modules/video']"
        )

        if await inner_frames.count() > 0:
            video_frame = outer_iframe.frame_locator(
                "iframe.ans-insertvideo-online, "
                "iframe[src*='video/index'], "
                "iframe[src*='ananas/modules/video']"
            )
        else:
            # 方式2: 直接在page的frames中查找
            for frame in self.page.frames:
                if "video" in (frame.url or ""):
                    video_frame_obj = frame
                    break

        if video_frame is None:
            print("  [视频] 未找到视频, 跳过")
            return False

        # 等待视频元素加载
        try:
            video_el = video_frame.locator("#video_html5_api, video").first
            await video_el.wait_for(state="attached", timeout=10000)
        except Exception:
            print("  [视频] 视频元素未加载, 跳过")
            return False

        # 设置倍速和静音 — JS直接操作video元素, 绕过DOM限速
        speed = self.config["video_speed"]
        mute = self.config["video_mute"]
        skip = self.config.get("video_skip", False)
        bypass = self.config.get("video_bypass", True)

        # 找到视频所在的实际 frame (直接操作, 不走 FrameLocator)
        video_real_frame = None
        for f in self.page.frames:
            if "video" in (f.url or "") or "ananas" in (f.url or ""):
                try:
                    has_video = await f.evaluate(
                        "() => !!document.querySelector('video')")
                    if has_video:
                        video_real_frame = f
                        break
                except Exception:
                    continue

        if not video_real_frame:
            print("  [视频] 无法直接定位视频frame, 回退到FrameLocator")
            video_real_frame = None  # 后面用 video_frame

        async def run_in_video(js: str):
            """在视频frame中执行JS"""
            if video_real_frame:
                return await video_real_frame.evaluate(js)
            else:
                return await video_frame.locator("body").evaluate(js)

        if skip:
            print(f"  [视频] 秒过模式 — 等待视频元数据加载...")
            dur = 0
            for attempt in range(60):
                # JS 端过滤 NaN/Infinity, 只返回有效数字
                dur = await run_in_video("""() => {
                    const v = document.querySelector('video');
                    if (!v) return 0;
                    const d = v.duration;
                    return (d && isFinite(d) && d > 0) ? d : 0;
                }""")
                if isinstance(dur, (int, float)) and dur > 1:
                    break
                # 尝试触发加载
                if attempt == 5:
                    await run_in_video("() => { const v = document.querySelector('video'); if (v) v.load(); }")
                if attempt == 15:
                    await run_in_video("() => { const v = document.querySelector('video'); if (v) { v.play().catch(()=>{}); } }")
                await asyncio.sleep(1)

            if not isinstance(dur, (int, float)) or dur <= 1:
                print(f"  [视频] 元数据加载失败 (duration={dur}), 改用高速播放")
                skip = False  # 降级到高速模式
            else:
                await run_in_video(f"""() => {{
                    const v = document.querySelector('video');
                    if (v && v.duration > 0 && isFinite(v.duration)) {{
                        v.muted = true;
                        v.volume = 0;
                        v.currentTime = Math.max(0, v.duration - 0.5);
                        v.playbackRate = 16;
                        v.play().catch(() => {{}});
                        setTimeout(() => {{
                            if (!v.ended) v.dispatchEvent(new Event('ended'));
                        }}, 2000);
                    }}
                }}""")
                print(f"  [视频] 已跳到末尾 (duration={int(dur)}s)")
            if bypass:
                print(f"  [视频] bypass已开启 — 服务器将收到完整观看记录")
        else:
            print(f"  [视频] 高速播放 — {speed}x")
            await run_in_video(f"""() => {{
                const v = document.querySelector('video');
                if (v) {{
                    v.muted = {'true' if mute else 'false'};
                    v.volume = 0;
                    v.playbackRate = {speed};
                    v.defaultPlaybackRate = {speed};
                    v.play().catch(() => {{}});
                    // 定时器防止被重置速度
                    if (!window.__speedKeeper) {{
                        window.__speedKeeper = setInterval(() => {{
                            const v2 = document.querySelector('video');
                            if (v2) {{
                                v2.playbackRate = {speed};
                                v2.muted = {'true' if mute else 'false'};
                                v2.volume = 0;
                            }}
                        }}, 3000);
                    }}
                }}
            }}""")
            if speed > 2:
                print(f"  [视频] JS注入绕过UI限速(>2x)")

        # 尝试点击播放按钮
        play_btn = video_frame.locator(".vjs-big-play-button, "
                                        ".vjs-play-control.vjs-paused")
        if await play_btn.count() > 0:
            try:
                await play_btn.first.click()
            except Exception:
                pass

        # 等待视频播放完成
        print("  [视频] 等待播放完成...")
        for tick in range(7200):  # 最多等2小时
            try:
                state = await run_in_video("""() => {
                    const v = document.querySelector('video');
                    if (!v) return {done: true, current: 0, duration: 0};
                    return {
                        done: v.ended || (v.duration > 0 && v.currentTime >= v.duration - 1),
                        current: Math.floor(v.currentTime),
                        duration: Math.floor(v.duration),
                        paused: v.paused
                    };
                }""")

                if state.get("done"):
                    print(f"  [视频] 播放完成! ({state['duration']}s)")
                    self.stats["videos"] += 1
                    return True

                # 如果暂停了(弹题/播放器抽风), 处理弹题后恢复
                if state.get("paused"):
                    await self._handle_video_popup(video_frame)
                    await run_in_video(f"""() => {{
                        const v = document.querySelector('video');
                        if (v) {{
                            v.playbackRate = {speed};
                            v.muted = true;
                            v.volume = 0;
                            if (v.paused) v.play().catch(() => {{}});
                        }}
                    }}""")

                if tick % 30 == 0 and tick > 0:
                    d = state.get("duration", 0)
                    c = state.get("current", 0)
                    pct = int(c / d * 100) if d > 0 else 0
                    print(f"  [视频] 进度: {c}s / {d}s ({pct}%)")

            except Exception:
                pass

            await asyncio.sleep(1)

        return False

    async def _handle_video_popup(self, video_frame):
        """处理视频中弹出的答题 — 使用AI回答"""
        try:
            popup = video_frame.locator(
                ".ans-videoquiz-opts:visible, .ans-videoquiz:visible, "
                ".ans-videoquiz-opt.mq-show, .videoquiz-popup:visible"
            )
            if await popup.count() == 0:
                return

            print("  [视频] 检测到弹题, 用AI作答...")

            # 提取弹题文本
            title_el = popup.locator(
                ".ans-videoquiz-title, .topic-title, h6, .title, "
                ".question-title"
            )
            q_text = ""
            if await title_el.count() > 0:
                q_text = (await title_el.first.text_content() or "").strip()[:100]
            if not q_text:
                full_text = await popup.text_content()
                q_text = (full_text or "").strip()[:100]

            # 提取选项
            opt_els = popup.locator(
                "li, .ans-videoquiz-opt, .option-item, label"
            )
            options = []
            for i in range(min(await opt_els.count(), 6)):
                text = (await opt_els.nth(i).text_content() or "").strip()[:40]
                if text and len(text) > 1:
                    options.append(text)

            # AI答题
            if q_text and options and self.config["auto_answer"]:
                answer = await self.ai.ask(q_text, options, "choice")
                if answer:
                    letters = re.findall(r'[A-D]', answer.upper())
                    for letter in letters:
                        idx = ord(letter) - ord('A')
                        if 0 <= idx < len(options):
                            try:
                                await opt_els.nth(idx).click()
                                print(f"    -> 选择: {letter}")
                                await asyncio.sleep(0.3)
                            except Exception:
                                pass
            else:
                # 没有AI或没有题目信息: 选第一个
                if await opt_els.count() > 0:
                    await opt_els.first.click()

            # 点确认/关闭按钮
            await asyncio.sleep(0.5)
            for btn_sel in [
                ".ans-videoquiz-submit",
                "button:has-text('提交')",
                "button:has-text('确定')",
                ".ans-videoquiz-close",
                ".vjs-modal-dialog-close",
                "button:has-text('关闭')",
            ]:
                btn = video_frame.locator(btn_sel)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    await asyncio.sleep(0.5)
                    break

            # 恢复播放 + 重新加速
            await video_frame.locator("body").evaluate(f"""() => {{
                const v = document.querySelector('video');
                if (v) {{
                    v.playbackRate = {self.config['video_speed']};
                    v.defaultPlaybackRate = {self.config['video_speed']};
                    if (v.paused) v.play().catch(() => {{}});
                }}
            }}""")
            print("  [视频] 弹题已处理, 恢复播放")

        except Exception as e:
            print(f"  [视频] 弹题处理异常: {e}")

    # ---- 处理测验/作业任务 ----
    async def handle_quiz(self):
        """处理章节测验"""
        if not self.config["auto_answer"]:
            print("  [测验] 自动答题已关闭, 跳过")
            return False

        print("  [测验] 检测测验任务点...")

        # 测验在 #iframe 内, 或者在 iframe[src*='work/index'] 中
        outer_iframe = self.page.frame_locator("#iframe")

        # 查找作业/测验iframe
        work_frame = None
        work_locator = outer_iframe.locator(
            "iframe[src*='work/index'], "
            "iframe[src*='work/doHomeWorkNew'], "
            "iframe[src*='exam']"
        )

        if await work_locator.count() > 0:
            work_frame = outer_iframe.frame_locator(
                "iframe[src*='work'], iframe[src*='exam']"
            )
        else:
            work_frame = outer_iframe

        # 查找题目容器
        questions = work_frame.locator(
            ".TiMu, .Cy_TItle, .questionLi, "
            "div[class*='timu'], div[class*='question']"
        )
        q_count = await questions.count()

        if q_count == 0:
            # 也可能直接在outer_iframe里
            questions = outer_iframe.locator(
                ".TiMu, .Cy_TItle, .questionLi"
            )
            q_count = await questions.count()
            if q_count == 0:
                print("  [测验] 未找到题目, 跳过")
                return False
            work_frame = outer_iframe

        print(f"  [测验] 发现 {q_count} 道题目")

        for i in range(q_count):
            q_el = questions.nth(i)
            await self._answer_question(work_frame, q_el, i + 1)
            await self.random_delay()

        self.stats["quizzes"] += q_count

        # 是否自动提交
        if self.config["auto_submit"]:
            submit_btn = work_frame.locator(
                "a.jb_btn:has-text('提交'), "
                "button:has-text('提交'), "
                ".Btn_blue_CX:has-text('提交')"
            )
            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                print("  [测验] 已自动提交!")
                # 处理确认弹窗
                confirm = work_frame.locator(
                    ".layui-layer-btn0, "
                    "a:has-text('确定'), button:has-text('确定')"
                )
                await asyncio.sleep(1)
                if await confirm.count() > 0:
                    await confirm.first.click()
        else:
            print("  [测验] 答题完成, auto_submit=False, 请手动检查并提交")

        return True

    async def _answer_question(self, frame, q_el, num: int):
        """解答单个题目"""
        try:
            # 提取题目文本
            title_el = q_el.locator(
                ".Zy_TItle, .mark_name, h3, "
                "div[class*='title'], p.mark_name"
            ).first
            q_text = (await title_el.text_content() or "").strip()
            # 清理题号
            q_text = re.sub(r'^[\d\s.、]+', '', q_text).strip()

            if not q_text:
                return

            # 判断题型
            q_type = await self._detect_question_type(q_el)
            print(f"  [Q{num}] [{q_type}] {q_text[:60]}...")

            if q_type in ("single", "multi"):
                await self._answer_choice(frame, q_el, q_text, q_type)
            elif q_type == "judge":
                await self._answer_judge(frame, q_el, q_text)
            elif q_type == "fill":
                await self._answer_fill(frame, q_el, q_text)
            else:
                print(f"  [Q{num}] 未知题型, 跳过")

        except Exception as e:
            print(f"  [Q{num}] 处理失败: {e}")

    async def _detect_question_type(self, q_el) -> str:
        """检测题型: single/multi/judge/fill"""
        html = await q_el.inner_html()
        html_lower = html.lower()

        if 'type="radio"' in html_lower:
            return "single"
        if 'type="checkbox"' in html_lower:
            return "multi"
        if "判断" in html or "对错" in html or "正确" in html:
            # 判断题通常用 radio 但只有 对/错 两个选项
            radios = q_el.locator("input[type='radio']")
            if await radios.count() == 2:
                return "judge"
            return "judge"
        if 'type="text"' in html_lower or "textarea" in html_lower:
            return "fill"

        # 默认按单选处理
        radios = q_el.locator("input[type='radio']")
        if await radios.count() > 0:
            return "single"
        checkboxes = q_el.locator("input[type='checkbox']")
        if await checkboxes.count() > 0:
            return "multi"

        return "unknown"

    async def _answer_choice(self, frame, q_el, q_text: str, q_type: str):
        """回答选择题"""
        # 提取选项
        option_els = q_el.locator(
            "li.Zy_ulTk, .answerBg, li[class*='option'], "
            "label.fl, div.option"
        )
        options = []
        for i in range(await option_els.count()):
            text = (await option_els.nth(i).text_content() or "").strip()
            text = re.sub(r'^[A-Z][.、\s]+', '', text).strip()
            options.append(text)

        if not options:
            return

        # 调用AI
        answer = await self.ai.ask(q_text, options, "choice")
        if not answer:
            return

        # 解析AI回答的选项字母 (A, B, AB, ACD 等)
        letters = re.findall(r'[A-Z]', answer.upper())
        if not letters:
            return

        # 点击对应选项
        for letter in letters:
            idx = ord(letter) - ord('A')
            if 0 <= idx < await option_els.count():
                opt = option_els.nth(idx)
                try:
                    # 点击选项的 radio/checkbox 或 label
                    clickable = opt.locator(
                        "input[type='radio'], input[type='checkbox'], "
                        "label, a, .answerBg"
                    )
                    if await clickable.count() > 0:
                        await clickable.first.click()
                    else:
                        await opt.click()
                    print(f"    -> 选择: {letter}")
                except Exception:
                    try:
                        await opt.click()
                    except Exception:
                        pass

    async def _answer_judge(self, frame, q_el, q_text: str):
        """回答判断题"""
        answer = await self.ai.ask(q_text, q_type="judge")
        if not answer:
            return

        is_correct = "对" in answer or "正确" in answer or "是" in answer or "true" in answer.lower()

        options = q_el.locator(
            "li.Zy_ulTk, .answerBg, li[class*='option'], label"
        )
        count = await options.count()

        for i in range(count):
            text = (await options.nth(i).text_content() or "").strip()
            text_is_correct = ("对" in text or "正确" in text or
                               "√" in text or "是" in text or "A" == text.strip())

            should_click = (is_correct and text_is_correct) or \
                           (not is_correct and not text_is_correct)

            if should_click:
                try:
                    clickable = options.nth(i).locator(
                        "input[type='radio'], label, a"
                    )
                    if await clickable.count() > 0:
                        await clickable.first.click()
                    else:
                        await options.nth(i).click()
                    print(f"    -> 判断: {'对' if is_correct else '错'}")
                except Exception:
                    pass
                break

    async def _answer_fill(self, frame, q_el, q_text: str):
        """回答填空题"""
        answer = await self.ai.ask(q_text, q_type="fill")
        if not answer:
            return

        inputs = q_el.locator(
            "input[type='text'], textarea, .edui-body"
        )
        if await inputs.count() > 0:
            try:
                await inputs.first.fill(answer)
                print(f"    -> 填写: {answer[:30]}")
            except Exception:
                pass

    # ---- 处理文档/PPT任务 ----
    async def handle_document(self):
        """处理文档/PPT翻页任务"""
        print("  [文档] 检测文档任务...")
        outer_iframe = self.page.frame_locator("#iframe")

        # PPT/文档通常有翻页按钮
        next_btn = outer_iframe.locator(
            "#img_next, .imglook_nextpage, "
            "a:has-text('下一页'), .next_page"
        )

        if await next_btn.count() == 0:
            return False

        print("  [文档] 发现文档, 自动翻页中...")
        page_count = 0
        while True:
            try:
                if await next_btn.count() == 0:
                    break
                visible = await next_btn.first.is_visible()
                if not visible:
                    break
                await next_btn.first.click()
                page_count += 1
                await asyncio.sleep(random.uniform(2, 4))
            except Exception:
                break

        print(f"  [文档] 翻页完成, 共 {page_count} 页")
        return page_count > 0

    # ---- 处理当前章节的所有任务点 ----
    async def process_current_chapter(self):
        """处理当前章节的所有任务点"""
        await asyncio.sleep(5)  # 等页面和iframe加载

        # 注入视频进度劫持 (让服务器认为每个视频都看完了)
        await self._inject_video_bypass()

        # 调试: 打印当前URL和所有iframe, 帮助定位问题
        print(f"  [调试] 当前URL: {self.page.url}")
        frames = self.page.frames
        print(f"  [调试] 页面共 {len(frames)} 个frame:")
        for f in frames:
            url = f.url or "(空)"
            if url != "about:blank":
                print(f"         - {url[:100]}")

        # 如果当前不在章节学习页, 可能还在课程主页
        if "studentstudy" not in self.page.url:
            print("  [调试] 当前不在章节学习页, 尝试寻找入口...")
            # 尝试在iframe里找到章节学习页
            found = False
            for f in frames:
                if "studentstudy" in (f.url or "") or "knowledge" in (f.url or ""):
                    found = True
                    break
            if not found:
                await self._enter_first_chapter()
                await asyncio.sleep(5)
                frames = self.page.frames
                print(f"  [调试] 重新检测, 共 {len(frames)} 个frame")

        # 检测任务类型并处理
        outer_iframe = self.page.frame_locator("#iframe")

        # 查找所有任务点tab
        tabs = outer_iframe.locator(
            ".prev_tab .tab, .mianmark .mark_tab, "
            ".prev_ul li, div.tamark span"
        )
        tab_count = await tabs.count()

        if tab_count > 1:
            print(f"  [任务] 本章有 {tab_count} 个任务点")
            for t in range(tab_count):
                print(f"  [任务] 处理任务点 {t+1}/{tab_count}")
                try:
                    await tabs.nth(t).click()
                    await asyncio.sleep(2)
                except Exception:
                    pass
                await self._process_single_task()
                await self.random_delay()
        else:
            await self._process_single_task()

    async def _process_single_task(self):
        """处理单个任务点"""
        handled = await self.handle_video()
        if not handled:
            handled = await self.handle_quiz()
        if not handled:
            handled = await self.handle_document()
        if not handled:
            # 尝试在所有frame中找视频 (兜底)
            for frame in self.page.frames:
                url = frame.url or ""
                if "video" in url or "ananas" in url:
                    print(f"  [任务] 在frame中发现视频: {url[:80]}")
                    try:
                        video = frame.locator("video, #video_html5_api").first
                        if await video.count() > 0:
                            speed = self.config["video_speed"]
                            skip = self.config.get("video_skip", False)
                            if skip:
                                # 等duration有效
                                for _ in range(30):
                                    dur = await frame.evaluate("""() => {
                                        const v = document.querySelector('video');
                                        return v ? v.duration : 0;
                                    }""")
                                    if dur and dur > 0 and dur != float('inf'):
                                        break
                                    await asyncio.sleep(1)
                                await frame.evaluate(f"""() => {{
                                    const v = document.querySelector('video');
                                    if (v && v.duration > 0 && isFinite(v.duration)) {{
                                        v.muted = true;
                                        v.currentTime = Math.max(0, v.duration - 0.5);
                                        v.playbackRate = 16;
                                        v.play().catch(() => {{}});
                                        setTimeout(() => {{ if (!v.ended) v.dispatchEvent(new Event('ended')); }}, 2000);
                                    }}
                                }}""")
                                print(f"  [视频] 秒过 - 在frame中强制结束")
                            else:
                                await frame.evaluate(f"""() => {{
                                    const v = document.querySelector('video');
                                    if (v) {{
                                        Object.defineProperty(v, 'playbackRate', {{
                                            get() {{ return {speed}; }}, set() {{ return; }}
                                        }});
                                        v.defaultPlaybackRate = {speed};
                                        v.playbackRate = {speed};
                                        v.muted = true; v.play();
                                    }}
                                }}""")
                                print(f"  [视频] 高速={speed}x - 在frame中播放")
                            # 等待完成 + 处理弹题
                            for tick in range(7200):
                                state = await frame.evaluate("""() => {
                                    const v = document.querySelector('video');
                                    if (!v) return {done: true, paused: false};
                                    return {
                                        done: v.ended || (v.duration > 0 && v.currentTime >= v.duration - 1),
                                        paused: v.paused
                                    };
                                }""")
                                if state["done"]:
                                    print("  [视频] 播放完成!")
                                    self.stats["videos"] += 1
                                    handled = True
                                    break
                                if state["paused"] and not skip:
                                    # 尝试点击弹题选项然后恢复播放
                                    try:
                                        popups = frame.locator(".ans-videoquiz:visible, .videoquiz-popup:visible")
                                        if await popups.count() > 0:
                                            await self._handle_video_popup(frame)
                                    except Exception:
                                        pass
                                    await frame.evaluate("() => { const v = document.querySelector('video'); if (v) v.play(); }")
                                await asyncio.sleep(1)
                    except Exception:
                        pass
                    if handled:
                        break
            if not handled:
                print("  [任务] 未识别到可处理的任务类型")
                # 保存截图便于调试
                try:
                    ss_path = Path(__file__).parent / "debug_screenshot.png"
                    await self.page.screenshot(path=str(ss_path))
                    print(f"  [调试] 截图已保存: {ss_path}")
                except Exception:
                    pass

    # ---- 自动切换下一章 ----
    async def next_chapter(self) -> bool:
        """切换到下一章节"""
        print("[章节] 尝试切换下一节...")

        # 方式1: 页面主体上的"下一节"按钮 (各种变体)
        next_selectors = [
            "#prevNextFocusNext",
            ".orientationright",
            ".nodeItem.r",
            ".next_btn",
            "a:has-text('下一节')",
            "span:has-text('下一节')",
            "div:has-text('下一节') >> visible=true",
            "button:has-text('下一节')",
            "[title='下一节']",
            ".arrow-right",
            ".chapterNext",
        ]
        for sel in next_selectors:
            try:
                btn = self.page.locator(sel)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    self.stats["chapters"] += 1
                    print(f"\n[章节] === 切换到下一节 (已完成 {self.stats['chapters']} 节) ===")
                    await self.page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(5)
                    return True
            except Exception:
                continue

        # 方式2: 左侧章节列表中找当前节, 点击下一个
        current_selectors = [
            ".currents", ".current_chapter", ".chapter_item.current",
            "li.active", ".posCatalog_active", ".ncells .currents",
            "li[class*='current']",
        ]
        for csel in current_selectors:
            current = self.page.locator(csel)
            if await current.count() > 0:
                try:
                    siblings = current.first.locator("xpath=following-sibling::*")
                    if await siblings.count() > 0:
                        await siblings.first.click()
                        self.stats["chapters"] += 1
                        print(f"\n[章节] === 切换到下一节 (已完成 {self.stats['chapters']} 节) ===")
                        await self.page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(5)
                        return True
                except Exception:
                    continue

        # 方式3: 通过JS获取所有章节链接, 找当前章节的下一个
        try:
            result = await self.page.evaluate("""() => {
                // 查找所有可能的章节链接
                const links = document.querySelectorAll(
                    'a[href*="chapterId"], a[href*="studentstudy"], ' +
                    '.ncells a, .chapter_item a, .posCatalog_select a'
                );
                const currentUrl = window.location.href;
                let foundCurrent = false;
                for (const link of links) {
                    if (foundCurrent && link.href && link.href !== currentUrl) {
                        return link.href;
                    }
                    if (link.href === currentUrl || link.classList.contains('currents')
                        || link.parentElement.classList.contains('currents')) {
                        foundCurrent = true;
                    }
                }
                return null;
            }""")
            if result:
                print(f"[章节] 通过JS找到下一节: {result[:80]}")
                await self.page.goto(result, wait_until="domcontentloaded", timeout=60000)
                self.stats["chapters"] += 1
                await asyncio.sleep(5)
                return True
        except Exception:
            pass

        # 方式4: 截图调试 + 手动兜底
        try:
            ss_path = Path(__file__).parent / "debug_next_chapter.png"
            await self.page.screenshot(path=str(ss_path))
            print(f"[章节] 调试截图: {ss_path}")
        except Exception:
            pass

        print("[章节] 未找到下一节按钮")
        manual = await asyncio.get_event_loop().run_in_executor(
            None, lambda: input("       手动点击下一节后按回车, 或输入 q 结束本课: ").strip().lower()
        )
        if manual == "q":
            return False
        # 用户手动点了下一节
        self.stats["chapters"] += 1
        await asyncio.sleep(3)
        return True

    # ---- 主运行循环 ----
    async def run(self):
        """主运行流程"""
        print("=" * 60)
        print("  超星学习通 自动刷课 + AI答题")
        print("=" * 60)

        await self.start()

        # 1. 登录
        if not await self.login():
            print("[错误] 登录失败, 退出")
            return

        await self.random_delay()

        # 2. 选择课程
        selected = await self.select_course()
        if not selected:
            await self.go_to_course()

        # 3. 循环处理章节
        await self.run_chapters()

        # 4. 本课完成, 循环询问是否继续
        while True:
            print(f"\n{'='*60}")
            print(f"  本课刷课完成!")
            print(f"  视频: {self.stats['videos']} 个")
            print(f"  题目: {self.stats['quizzes']} 道")
            print(f"  章节: {self.stats['chapters']} 章")
            print(f"{'='*60}")

            again = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("\n继续刷下一门课? (y/n): ").strip().lower()
            )
            if again not in ("y", "yes", ""):
                break

            self.stats = {"videos": 0, "quizzes": 0, "chapters": 0}
            selected = await self.select_course()
            if not selected:
                print("[选课] 未选择课程, 退出")
                break
            await self.run_chapters()

        # 最终退出确认
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: input("\n按回车键退出...")
        )

    async def run_chapters(self):
        """循环处理当前课程的所有章节"""
        chapter_num = 0
        while True:
            chapter_num += 1
            print(f"\n{'='*60}")
            print(f"  处理第 {chapter_num} 章")
            print(f"{'='*60}")

            await self.process_current_chapter()

            if not self.config["auto_next_chapter"]:
                print("\n[完成] auto_next_chapter=False, 停止自动翻章")
                break

            if not await self.next_chapter():
                break

            await self.random_delay()

    async def cleanup(self):
        """清理资源"""
        await self.ai.close()
        if self.context:
            await self.context.close()
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'pw'):
            await self.pw.stop()


# ═══════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="超星学习通自动刷课")
    parser.add_argument("--no-headless", action="store_true",
                        help="有头模式(显示浏览器窗口)")
    parser.add_argument("--login-only", action="store_true",
                        help="仅登录, 手动操作后脚本接管")
    parser.add_argument("--select-only", action="store_true",
                        help="仅登录后选课, 选完退出 (配合menu.py使用)")
    parser.add_argument("--config", type=str, default="",
                        help="配置文件路径(JSON)")
    args = parser.parse_args()

    config = CONFIG.copy()

    # 从 menu.py 生成的 JSON 加载 (扁平结构 → 嵌套结构)
    if args.config and Path(args.config).exists():
        with open(args.config, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)

        # 映射扁平键到 CONFIG 嵌套结构
        for k, v in user_cfg.items():
            if k == "ai_provider":
                config["ai"]["provider"] = v
            elif k == "ai_siliconflow_key":
                config["ai"]["siliconflow"]["api_key"] = v
            elif k == "ai_openrouter_key":
                config["ai"]["openrouter"]["api_key"] = v
            elif k in config:
                config[k] = v

        print(f"[配置] 已加载: {args.config}")

    # 交互式填写必要信息 (仅在非配置模式时询问)
    if not config["phone"] and not args.config:
        config["phone"] = input("手机号 (留空=扫码登录): ").strip()
        if config["phone"]:
            config["password"] = input("密码: ").strip()

    ai_provider = config["ai"]["provider"]
    if ai_provider == "opencode":
        print(f"\n[AI] 使用 OpenCode CLI 免费模型答题 (零成本!)")
    else:
        ai_key = config["ai"][ai_provider].get("api_key", "")
        if not ai_key and config["auto_answer"] and not args.config:
            print(f"\n当前AI后端: {ai_provider}")
            print("需要API Key才能自动答题。免费获取方式:")
            print("  SiliconFlow: https://cloud.siliconflow.cn (注册送额度)")
            print("  OpenRouter:  https://openrouter.ai (有免费模型)")
            print("  或修改 provider 为 'opencode' 直接用本地免费模型")
            key = input(f"\n输入 {ai_provider} API Key (留空=跳过答题): ").strip()
            if key:
                config["ai"][ai_provider]["api_key"] = key
            else:
                config["auto_answer"] = False
                print("已关闭自动答题, 仅刷视频")

    headless = not args.no_headless
    bot = ChaoxingAuto(config, headless=headless)

    try:
        if args.select_only:
            # 仅选课模式: 登录 → 选课 → 进入章节页 → 退出 (保存URL)
            await bot.start()
            if not await bot.login():
                return
            await bot.random_delay()
            selected = await bot.select_course()
            if selected:
                # 保存选中的URL供后续使用
                saved_url = bot.page.url
                saved = False
                if args.config:
                    user_cfg["course_url"] = saved_url
                    with open(args.config, "w", encoding="utf-8") as f:
                        json.dump(user_cfg, f, ensure_ascii=False, indent=2)
                    saved = True
                print(f"\n[选课] 已定位到章节页")
                if saved:
                    print(f"[选课] URL已保存到 {args.config}")
                print(f"[选课] URL: {saved_url[:120]}")
            print("\n按回车键退出...")
            await asyncio.get_event_loop().run_in_executor(None, input)
        elif args.login_only:
            await bot.start()
            await bot.login()
            print("\n[手动模式] 已登录, 你可以手动操作浏览器")
            print("按回车键退出...")
            await asyncio.get_event_loop().run_in_executor(None, input)
        else:
            await bot.run()
    except KeyboardInterrupt:
        print("\n[中断] 用户手动停止")
    finally:
        await bot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
