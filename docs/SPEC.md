# icoda-smm specification

## Goal
Monthly plan of 10 posts (about 5 with an image) for X and the ICODA LinkedIn company page. The owner approves everything in a Telegram bot. Approved posts publish on schedule. Urgent topics are added with /add and merged into the plan.

## State
plans/YYYY-MM.json is the source of truth. Post status: draft -> approved -> scheduled -> published, plus rejected and failed. Plan status: draft, needs_review, approved. Each post stores per-platform publish state (x and linkedin: pending, published, failed) so a retry never double-posts.

## Global rules
- Python 3.11, type hints, small modules, pytest. Tests never touch the network: mock Anthropic, OpenAI, Telegram and publishers.
- Secrets only in .env. Never log secrets.
- NEVER publish a post unless its status is approved and its date and time are due.
- Writes to plan files are atomic (temp file + rename) and protected by a file lock.
- Do not edit knowledge/ files. Do not weaken validator rules. Existing tests stay green.
- Everything the bot says to the owner is in Russian. Post copy is in English.
- Verify every external API detail (OpenAI Images, Telegram Bot API, X, LinkedIn, schedulers) against current official documentation. Model names, parameters, limits, prices and access requirements are never taken from memory.
- After each stage: run tests, commit, give a 5-line summary, stop.

## Stage 4: images (scripts/generate_images.py)
For every post with a non-null visual and no valid image:
1. Build the prompt from knowledge/visual_prompt.yaml (fill OBJECT, HAND, CAMERA, HEADLINE, LAYOUT).
2. Call the OpenAI Images edit endpoint with ALL files in refs/ as style references. Model from env IMAGE_MODEL (default in config.yaml). Check the current docs for the model name, parameters, size options and response format.
3. If native 16:9 is unavailable, generate the closest supported size and crop to 16:9 with Pillow. Output images/{post_id}.png, 1600x900 or larger.
4. QA: send the image to Claude with vision, with the expected headline, and require JSON only: {"headline_exact": bool, "headline_read": str, "logo_icoda_ok": bool, "text_zone_clear": bool, "style_match": bool, "issues": [str]}. Pass requires headline_exact, logo_icoda_ok and text_zone_clear all true.
5. On failure regenerate up to 2 more times, adding the QA issues to the prompt. If it still fails, keep the best attempt and set post.image_qa = "needs_manual" with the issues. One bad image never blocks the run.
6. Save image_path (relative) into the plan. Idempotent. Flag --force-post POST_ID regenerates one image.
Tests: prompt assembly for every layout, hand and camera value; QA retry logic with mocked clients; idempotency.

## Stage 5: Telegram bot (bot/ package, python-telegram-bot, async)
Only TELEGRAM_CHAT_ID may use the bot; ignore everyone else.
- Plan delivery: a Russian summary (month, count, calendar list), then one message per post in date order: the image if any, separate text messages for X and LinkedIn (captions are limited to 1024 characters), date and time, type, business line, validator warnings and image_qa flags.
- Inline buttons per post: Approve, Edit, Regenerate text, Regenerate image, Remove. Plus Approve all under the summary.
- Edit: the bot asks for instructions, I reply in free text, Claude rewrites that one post following the "Regenerate one post" task in CLAUDE.md (same id, date, business line, type), the result passes validate_plan and is shown again. Edited posts return to draft.
- Remove: status rejected after a confirm button, then offer to fill the slot (Claude proposes a replacement that respects the mix and schedule rules).
- /add [urgent] <text or link>: append an item to inbox/inbox.json, then run the "Add an inbox item to the plan" task from CLAUDE.md. Validate, then show only changed or new posts for approval. Published posts and posts due today are never moved.
- /plan shows plan status. /status shows pending approvals, next scheduled posts and recent failures. /help in Russian.
- When every non-rejected post is approved, set the plan to approved and tell me.
Tests: handlers with mocked Telegram objects, the authorization check, state transitions.

## Stage 6: publishing (scripts/publish/)
Step 1, research, then STOP: write docs/publishing-options.md comparing, from current official docs and pricing pages: the direct X API (posting, image upload, polls, threads, access tier and cost), the LinkedIn Community Management API for company pages (approval requirements and timeline), and schedulers with an API (Buffer, Typefully, Make or n8n). For each: X and LinkedIn company page support, images, polls, threads, scheduling, cost, setup effort, risks. End with a recommendation and wait for my choice.
Step 2, after my answer: a Publisher interface (publish(post, platform) -> PublishResult with remote id and url). DryRunPublisher (logs what it would do) is the default. The real publisher needs env PUBLISH_LIVE=true. Per-platform state prevents double posting; retries use exponential backoff, max 3; on final failure mark failed and notify me in Telegram with the error and a Retry button.
Tests: idempotency, retry, failure notification, dry run as default.

## Stage 7: runner and deployment
- scripts/run_scheduler.py: loop or single-run mode for cron. Finds approved posts that are due (config timezone and publish_time), publishes through the Publisher, updates state, notifies me on success and failure.
- scripts/monthly_job.py: build next month's plan, generate images, send the plan to Telegram. Meant to run around the 25th of each month. Refuses to overwrite an existing plan without --force.
- Dockerfile and docker-compose.yml: services bot (long-running) and scheduler; documented cron line or systemd timer for the monthly job; volumes for plans/, images/, inbox/, knowledge/; healthcheck for the bot.
- Logging to stdout with timestamps, one line per action.
- README.md in English: setup, env vars, first run, a one-command full demo with mocked services (make demo), key rotation.
- End-to-end test: plan fixture -> images (mocked) -> Telegram approval (mocked) -> scheduler with DryRunPublisher. Assert nothing publishes before approval.

## Definition of done
All tests pass; the demo runs end to end without real credentials; nothing can publish without approval and DryRun is the default; docs/ARCHITECTURE.md and README.md match the code; the final summary lists what I must configure, what was verified against current docs, and every assumption made.
