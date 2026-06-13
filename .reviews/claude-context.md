# Claude Plan Context: 封标大师

## Role

You are a read-only planner. Do not modify files, run commands, deploy, or ask for secrets. Produce a practical implementation plan for Codex to execute later.

## Local Facts

- Project name: 封标大师
- Project path: `/Volumes/CodexT7/workspaces/封标大师`
- Git repo: initialized on branch `main`
- Current stage: planning only
- User: content creator 懒狗小黑
- Main platforms: Bilibili and Douyin, with Bilibili as the first target for this tool
- Current input available from user: concept only; creator list will be provided later

## Product Goal

Build a local tool that tracks Xiaohei's own historical Bilibili videos plus selected benchmark creators, regularly collects their public thumbnail/title/performance data, stores it as a "封标知识库", and later uses grounded historical sample cards to provide practical thumbnail and title suggestions for new video topics.

## Hard Constraints

- Use only public video metadata.
- Do not use or request cookies, login state, browser profiles, private messages, private data, or secrets.
- Do not bypass captcha, rate limits, or platform protections.
- Keep requests conservative with rate limiting, retry caps, and source attribution.
- Separate data collection, storage, analysis, and recommendation layers.
- First milestone should be testable without needing the final large creator list.

## Desired First Milestone

Design an MVP that can:

1. Read a creator config file.
2. Fetch recent public videos for each configured creator.
3. Store video identity, title, cover URL, publish time, creator, creator follower count, and play-count snapshots.
4. Cache cover images safely.
5. Detect title/cover changes across snapshots.
6. Produce sample cards and a simple report showing which videos overperformed each creator's own baseline, which videos grew fastest in the first 48 hours, and what their title/cover hooks look like.

## Future Direction

Later versions should support:

- Title pattern classification.
- Same-topic comparison between overperforming and underperforming samples.
- Semantic search over past cases.
- LLM-assisted suggestions for a new topic, grounded in retrieved historical examples.
- OCR and visual feature extraction after the first sample-card workflow is stable.

## Requested Output

Write a Chinese plan with:

1. Product scope and phased milestones.
2. Recommended architecture and tech stack.
3. Data model.
4. Data acquisition strategy for Bilibili public data.
5. Scheduler design.
6. Analysis and recommendation design.
7. Testing strategy.
8. Risks and compliance notes.
9. Concrete next steps for Codex.

Keep the plan practical. Prefer a small reliable sample-card MVP before any model training, OCR, or visual feature extraction. Do not treat absolute play count as a direct proxy for thumbnail/title quality.
