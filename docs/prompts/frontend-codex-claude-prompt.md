# 封标大师前端 Codex 委派提示词

你是一个新的 Codex 线程，请在 `/Volumes/CodexT7/workspaces/封标大师` 专心完成前端搭建。请先阅读项目根目录的 `AGENTS.md`，按项目规则走：

`Claude Plan -> Codex 实现 -> Claude Review -> Codex 修复`

Claude 只做只读 Plan 和只读 Review，不允许修改文件、不允许运行命令、不允许读取浏览器资料、cookie、Keychain、token 或任何私密文件。Claude 模型使用当前可用的最新模型，effort/max。如果用户要求的 Fiber/Fable/Fiber 5 在本机不可用，请把它标记为“Claude 协作基础设施/模型不可用”，不要阻塞 Codex 本地实现。

## 项目背景

项目名：封标大师。

目标用户是内容创作者“懒狗小黑”。工具要帮助他积累 B 站和 YouTube 科技/生活方式创作者的“封标”样本，也就是封面、标题、播放表现和标签，以后用于新选题的灵感检索和封标建议。

当前这个线程只做前端，不要重写后端采集器。后端已经能跑通：

- 数据库：`data/db/fengbiao.sqlite3`
- 本地封面：`data/covers/`
- 已采样：22 位创作者、75 条视频、75 张封面
- 后端命令：
  - `PYTHONPATH=src python3 -m fengbiao.cli stats`
  - `PYTHONPATH=src python3 -m fengbiao.cli daily-run`
- 每天 10:00 的后端自动采集任务已经由主线程创建，不要重复创建。

## 后端数据结构

可只读读取这些表：

- `creators`
- `videos`
- `video_snapshots`
- `cover_assets`
- `sample_cards`
- `change_log`
- `fetch_runs`

推荐前端读取 SQL：

```sql
SELECT
  v.id,
  c.platform,
  c.name AS creator_name,
  c.tags,
  c.note AS creator_note,
  v.platform_video_id,
  v.title,
  v.url,
  v.published_at,
  v.first_seen_at,
  v.last_seen_at,
  s.play_count,
  s.like_count,
  s.coin_count,
  s.favorite_count,
  s.danmaku_count,
  s.follower_count,
  ca.local_path AS cover_path,
  ca.source_url AS cover_source_url,
  sc.track,
  sc.human_note,
  sc.status,
  sc.metrics_json
FROM videos v
JOIN creators c ON c.id = v.creator_id
LEFT JOIN sample_cards sc ON sc.video_id = v.id
LEFT JOIN cover_assets ca ON ca.id = v.current_cover_id
LEFT JOIN (
  SELECT video_id, MAX(id) AS snapshot_id
  FROM video_snapshots
  GROUP BY video_id
) latest ON latest.video_id = v.id
LEFT JOIN video_snapshots s ON s.id = latest.snapshot_id
ORDER BY v.last_seen_at DESC, v.id DESC;
```

注意：

- `creators.tags` 是 JSON 字符串，需要 parse。
- `sample_cards.metrics_json` 是 JSON 字符串，需要 parse，里面目前有 `baseline_play_count`, `relative_to_baseline`, `views_per_follower`。
- `cover_path` 是本地相对路径，例如 `data/covers/bilibili/25910292/BVxxxx_a586c50c.jpg`。
- YouTube 的播放量可能为空，这是 RSS 源限制，不要当作前端 bug。

## 建议技术路线

优先使用 Vite + React + TypeScript，放在 `apps/web`。这是一个本地工具，不需要做营销落地页。

第一版建议做一个后端到前端的只读快照导出脚本，避免前端直接碰 SQLite：

- 新增脚本：`scripts/export_frontend_snapshot.py`
- 输出：`apps/web/public/fengbiao-snapshot.json`
- 同步复制或映射封面图片，让前端能用真实图片加载。可选方案：
  - 把 JSON 里的 `coverUrl` 写成相对 URL，由本地 dev server 暴露；
  - 或把封面复制到 `apps/web/public/covers/...`，JSON 指向 `/covers/...`。

不要把 `data/db` 或 `data/covers` 提交进 Git。

## 前端体验

视觉方向结合此前 1 号和 5 号方案：

- 1 号：电影海报墙。第一屏就是大量真实封面组成的沉浸式墙，像逛片库，而不是后台表格。
- 5 号：样本卡档案馆。点击封面后出现档案抽屉/侧栏，展示标题、博主、平台、播放量、相对表现、标签和可借鉴点。

必须实现：

- 首页直接进入封面墙，不做 landing page。
- 搜索框：输入“智能眼镜”“3D 打印”“别墅 DIY”“科技评测”“想做一期 iPhone 选题”之类的想法，能关联标题、博主、平台、标签、备注、指标里的样本。
- 筛选：平台、创作者、标签、表现区间。
- 排序：最近收录、播放量、相对表现。
- 详情面板：真实封面大图、标题、创作者、平台、播放量、相对同创作者基线、发布时间、原视频链接、标签、可复用观察。
- 收藏/标记可以先做本地前端状态，不要改后端数据库。

## 视觉约束

- 使用真实封面图片，不能用纯占位色块糊弄。
- 海报墙要有密度、有浏览感，移动端也要可用。
- 整体可以偏暗，但不要一整屏单色深蓝/紫色；不要渐变球、装饰光斑、营销式 hero。
- 不要卡片套卡片。
- 所有文字在桌面和手机都不能溢出、重叠或遮挡核心封面。
- 工具类按钮使用清晰图标和 tooltip。

## 后端自审结论

后端可以支撑第一版前端读取和展示，但有两个限制需要前端知道：

- B 站当前通过公开搜索结果拿近期视频，通常每个账号约 3 条。前端不要声称这是“全量历史库”。
- `refresh_metrics` 当前基线是该创作者库内样本的中位数，不是严格同发布时间窗口对比。前端文案写“库内相对表现”更准确。

## 验收方式

完成后必须做：

1. 运行后端测试：`PYTHONPATH=src python3 -m unittest discover -s tests -v`
2. 导出前端快照并确认 JSON 里有 75 条样本和真实封面路径。
3. 启动前端 dev server，给出本地 URL。
4. 用浏览器打开，检查桌面和手机宽度：
   - 首页能看到真实封面墙；
   - 搜索能返回关联封标；
   - 点击封面能打开详情；
   - 图片没有大片空白；
   - 文字没有溢出/重叠。
5. Claude Review 后修严重问题。
6. 最终汇报时分开说明：
   - Claude Plan 是否完成；
   - Codex 实现是否完成；
   - Claude Review 是否完成；
   - 测试/浏览器验证是否通过；
   - 是否需要小黑下一步动作。

## 额外提醒

不要修改系统网络、代理、DNS、Tailscale、Clash。不要读取或提交任何 `.env`、密钥、cookie、浏览器 profile。完成项目修改后按 T7 规则运行 `codex-sync --dry-run`，不要执行 real-run。
