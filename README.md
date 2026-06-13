# 封标大师

封标大师是一个面向内容创作者的 B 站封面与标题研究工具。它会围绕小黑自己的历史视频和一份标杆博主清单，定期记录公开视频的封面、标题、发布时间和播放变化，逐步建立“封标知识库”，帮助判断在选题成立的前提下，什么样的标题表达、封面元素和发布后调整更可能放大点击。

## 当前阶段

- 已创建 T7 项目目录：`/Volumes/CodexT7/workspaces/封标大师`
- 已初始化 Git 仓库
- 当前只做产品与技术规划，不采集账号数据，不读取浏览器资料，不绕过验证码
- Claude 只读 Plan 会保存在 `.reviews/claude-plan.md`

## 目标

1. 维护一个“值得学习的博主清单”。
2. 定期抓取这些博主的新视频公开元数据。
3. 保存封面、标题、粉丝数、播放快照和封面/标题变更记录。
4. 计算相对 UP 主自身基线的表现倍数、播放/粉丝比和前 48 小时增速。
5. 把样本组织成按选题赛道检索的“参考墙”，每张样本卡带封面、标题、表现指标和一句话人工判断。
6. 未来输入一个选题时，能基于可追溯历史样本给出封面与标题建议。

## MVP 边界

- 输入：博主清单、采集频率、每位博主的新视频范围。
- 输出：本地知识库、可检索样本卡、选题赛道参考墙、基础分析报告。
- 数据：只使用公开视频公开信息，例如标题、封面地址、播放量、发布时间、UP 主、视频链接。
- 不做：登录态采集、弹幕/评论深挖、自动发布、刷量判断、绕过平台限制、第一期模型训练。

## 建议目录

```text
config/
  creators.example.yaml
data/
  db/
  covers/
docs/
  plans/
  research/
src/
tests/
```

## 后续

第一期优先做“采集 + 入库 + 相对表现计算 + 样本卡参考墙”。模型训练、OCR、复杂视觉特征和建议引擎等样本稳定后再做。

## 本机前后端同步入口

后端同步服务默认只监听本机：

```bash
PYTHONPATH=src python3 -m fengbiao.cli sync-server
```

前端开发服务：

```bash
cd apps/web
npm run dev
```

前端会优先读取 `GET /api/snapshot`。同步服务运行时，这个接口会从 SQLite 导出最新快照并返回给前端；同步服务不在时，前端会回退到 `apps/web/public/fengbiao-snapshot.json`。

需要让后端先跑一次日常公开数据刷新，再导出给前端时，可以调用：

```bash
curl -X POST http://127.0.0.1:8765/api/sync
```

也可以直接跑完整通道体检：

```bash
./scripts/check_channels.sh
```

它会检查本机同步 API、Vite 代理 API、静态快照回退和当前前端首页是否连通。

## GitHub Pages 在线站

当前线上 MVP 不引入需要密钥的云数据库；线上“数据库”是从本机 SQLite 导出的公开静态快照：

- `fengbiao-snapshot.json`
- `covers/` 里的网页轻量封面副本

主分支保存代码和脚本，`gh-pages` 分支保存可公开访问的静态网站。发布命令：

```bash
./scripts/publish_github_pages.sh
```

需要在发布前先跑一次公开数据刷新时：

```bash
./scripts/publish_github_pages.sh --sync
```

发布脚本会：

1. 导出前端快照；
2. 把本地原始封面转换成较轻的网页封面副本；
3. 按 GitHub Pages 子路径构建前端；
4. 推送 `apps/web/dist` 到 `gh-pages` 分支。

本机每日同步可安装 LaunchAgent：

```bash
./scripts/install_pages_sync_launch_agent.sh
```

默认每天 10:30 运行 `./scripts/publish_github_pages.sh --sync`，日志写入 `data/logs/pages-sync.*.log`。脚本不会提交本地 SQLite、原始封面缓存、日志、浏览器资料或 `.env`。

安装后不会立刻触发同步；需要立刻跑一次时使用：

```bash
./scripts/install_pages_sync_launch_agent.sh --run-now
```
