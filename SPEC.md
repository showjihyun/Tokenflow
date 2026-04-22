# Token Flow — SPEC

> 버전 0.3-impl · 2026-04-20 · 현재 구현 기준으로 정리. 코드보다 SPEC이 더 타당한 항목은 §12에 별도 추적.

### v0.3 구현 정합성 요약
- KPI 포뮬러 정의: **Efficiency Score**, **Query Quality Score**, **Opus overuse 임계값**
- Waste 패턴 구체적 임계값 확정 (window, similarity, LOC 기준)
- **§4.4** — 현재 onboarding 구현 기준 반영 (hook 자동 설치, API 키, ccprophet 후보 감지)
- **§6.x 신규** — 뷰별 empty/first-run state
- **§6.5** — 과거 세션 picker UI 추가
- Better prompt LLM 모드 프롬프트 템플릿 정의
- Waste detection 스캔/스윕 API 구현 기준 반영
- **§10** — 에러 taxonomy 추가, 스케일 가정 명시
- **§11** — 데이터 retention/pricing 업데이트 정책
- SSE ticker 재연결 / backpressure 정책
- Pause tracking, Export session, Import REST API, Query Quality API 등 SPEC 우선 항목의 구현 상태는 §12에 추적

---

## 0. 이 문서의 위치

이 문서는 Token Flow의 **무엇을/왜** 만들지를 정의합니다. 시각 디자인(컬러·타이포·컴포넌트 스타일·레이아웃 디테일)은 별도 `DESIGN.md`에 정리합니다.

- 연관 레퍼런스
  - `C:\Users\BV-CHOIJIHYUN\AppData\Local\Temp\tf-design\new-project\` — Claude Design 핸드오프 번들
  - `https://github.com/showjihyun/ccprophet.git` — 재사용 대상 코어 엔진
  - `https://code.claude.com/docs/en/hooks` — Claude Code Hooks 공식

---

## 1. 제품 개요

**Token Flow** 는 **로컬 PC에서 돌아가는 개인용 Claude Code 토큰 추적·분석·코칭 웹 대시보드**.

- **한 줄 정의**: Claude Code 세션의 토큰 흐름을 실시간으로 관찰하고, 낭비 패턴을 잡아내고, 대화형 코치로 다음 질문을 더 싸게·똑똑하게 하도록 돕는다.
- **작동 방식**: Claude Code 훅이 `tokenflow-hook` 로 이벤트를 흘리고, transcript tailer 가 JSONL 에서 토큰·비용을 추출해 DuckDB 에 저장. FastAPI 가 집계해 React 대시보드에 전달.
- **외부 네트워크 호출**: 기본 OFF. AI Coach (Sonnet 4.6) + Better prompt LLM 모드 사용 시에만 Anthropic API 호출.
- **데이터 저장**: `~/.tokenflow/events.duckdb`

### 1.1 대상 사용자
- **Primary**: 개인 시니어 개발자. 월 $100–200 Claude Code 지출.
- **Non-goals**: 팀·조직·모바일 (v1 제외)

### 1.2 사용자가 해결하려는 문제
1. 현재 세션 비용 실시간 인지
2. 월 예산 초과 예측
3. 낭비 패턴 자동 발견
4. 더 효율적인 질문 방식 학습
5. 과거 비싼 세션 분석 (replay)

### 1.3 Goals / Non-goals

| | In scope (v1) | Non-goals (v1) |
|---|---|---|
| 플랫폼 | 웹 대시보드 (브라우저) + 로컬 CLI harness | 데스크톱 앱, 모바일 |
| 사용자 | 개인 개발자 1명 | 팀·조직, SSO, RBAC |
| 인증 | 로컬 전용 127.0.0.1 | 원격 배포, OAuth |
| 데이터 원천 | Claude Code 훅 + JSONL transcript | IDE 플러그인, 프록시 |
| 예산 하드 차단 | 알림만 | 요청 차단 (v2) |
| AI Coach | Sonnet 4.6 대화 | 멀티 에이전트, 자동 코드 수정 |
| Better prompt | 정적 + LLM, 사용자 선택 | 자동 적용 (수동 복사만) |
| 과거 데이터 | ccprophet import CLI + REST job | 타 도구 import |
| 국제화 | 한국어/영어 | 기타 언어 |

---

## 2. ccprophet과의 관계

Token Flow = ccprophet 코어 흡수 + 새 UI.

### 2.1 재사용 매핑

| ccprophet 경로 | Token Flow 경로 | 재사용 | 비고 |
|---|---|---|---|
| `src/ccprophet/domain/` | `backend/tokenflow/domain/` | ~100% | 엔티티·값 객체·도메인 서비스 그대로 |
| `src/ccprophet/use_cases/` | `backend/tokenflow/use_cases/` | ~80% | Coach·Better prompt·Import 신규 |
| `src/ccprophet/adapters/persistence/duckdb/` | `backend/tokenflow/adapters/persistence/` | ~95% | V1–V5 계승, V6+ 신규 |
| `src/ccprophet/adapters/hook/receiver.py` | `backend/tokenflow/adapters/hook/` | 100% | stdin JSON 수신 |
| `migrations/V1..V5.sql` | `backend/migrations/V1..V5.sql` | 100% | import 호환 |
| `adapters/web/app.py` | 폐기 → 새 FastAPI | 0% | API 재설계 |
| `web/index.html` | 폐기 → React SPA | 0% | UI 전면 교체 |

### 2.2 신규 개발 항목
1. **Transcript tailer** — JSONL → 토큰·비용
2. **AI Coach 엔진** — Sonnet 4.6
3. **Waste 패턴 탐지기 확장**: `repeat-question`, `wrong-model`, `tool-loop`
4. **Routing rules 엔진**
5. **Better prompt 제안기** (static + LLM)
6. **Activity ticker SSE 스트리밍**
7. **사용자 설정 저장소** (budget/routing/notif/tweaks/api_key)
8. **ccprophet DB import CLI + REST job API**
9. **Onboarding flow** (hook 자동 설치)

---

## 3. 기술 스택

| 레이어 | 선택 | 비고 |
|---|---|---|
| Backend | Python 3.11 + FastAPI | |
| ASGI | uvicorn | |
| DB | DuckDB (임베디드) | |
| Transcript watch | byte-offset polling tailer | watchdog 전환은 v1.1 후보 |
| Frontend | React 18 + TypeScript strict | |
| Build | Vite | |
| Styling | CSS Variables + CSS Modules | Tailwind 없이 |
| State | Zustand | |
| Data fetching | TanStack Query v5 | |
| Real-time | SSE (EventSource) + Last-Event-ID | |
| Charts | 직접 SVG | |
| Icons | Lucide React | |
| AI Coach LLM | Claude Sonnet 4.6 | |
| Test | pytest + vitest + @testing-library/react + Playwright (e2e) | |
| Lint | ruff + mypy strict + eslint | prettier 는 현재 미도입 |
| 패키징 | uv + npm | frontend 는 `package-lock.json` 기준 |
| 배포 | 로컬 실행만 | |

---

## 4. 시스템 아키텍처

```
┌─────────────────────────┐      ┌──────────────────────────────────┐
│  Claude Code (CLI)      │      │  Browser (React SPA @ :8765)     │
│  + settings.json hook   │      │                                  │
│  + transcript JSONL     │      └──────┬───────────────────────────┘
└────┬────────────┬───────┘             │ HTTP + SSE
     │ stdin JSON │ JSONL append         ▼
     ▼            ▼
┌───────────────────────────────────────────────────────────┐
│  Token Flow local server (FastAPI @ 127.0.0.1:8765)       │
│  ┌───────────────────────────────────────────────────┐    │
│  │  adapters/                                         │    │
│  │   ├─ hook/receiver   (stdin event ingest)         │    │
│  │   ├─ transcript/tailer (JSONL watch → tokens)     │    │
│  │   ├─ web/routes       (REST + SSE)                │    │
│  │   ├─ persistence/duckdb (repositories)            │    │
│  │   └─ coach/claude_client (Anthropic SDK)          │    │
│  ├───────────────────────────────────────────────────┤    │
│  │  use_cases/  (기존 + 신규)                         │    │
│  ├───────────────────────────────────────────────────┤    │
│  │  domain/  (entities, values, services)            │    │
│  └───────────────────────────────────────────────────┘    │
│  Storage: ~/.tokenflow/events.duckdb                       │
│           ~/.tokenflow/secret.json  (API key, 0600)        │
│           ~/.tokenflow/events.ndjson (hook append log)     │
│           ~/.tokenflow/logs/                                │
└───────────────────────────────────────────────────────────┘
             │ (선택) outbound HTTPS
             ▼
       Claude API  (Coach + LLM better prompt)
```

### 4.1 실행 모드

- `tokenflow serve` — FastAPI + React 정적 + transcript tailer 단일 프로세스
- `tokenflow-hook` — Claude Code `settings.json` 에 등록, 이벤트 수신 후 즉시 종료
- `tokenflow import --from-ccprophet <path>` — ccprophet DuckDB 에서 import
- `tokenflow doctor` — hook 설치 상태·API 키·DB 무결성 체크

### 4.2 폴더 구조

```
tokenflow/
├── backend/
│   ├── tokenflow/
│   │   ├── domain/
│   │   ├── use_cases/
│   │   ├── adapters/
│   │   │   ├── hook/
│   │   │   ├── transcript/
│   │   │   ├── persistence/
│   │   │   ├── coach/
│   │   │   └── web/
│   │   └── harness/
│   ├── migrations/     # V1–V10 SQL
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── views/       # LiveMonitor, Analytics, WasteRadar, AICoach, Replay, Settings, Onboarding
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api/
│   │   ├── lib/
│   │   └── styles/
│   ├── vite.config.ts
│   └── package.json
├── SPEC.md
├── DESIGN.md
└── README.md
```

### 4.3 데이터 원천 — 훅 vs transcript

Claude Code 훅 payload 에 **토큰 카운트 없음** (공식 문서 확인). 따라서 2채널 수집:

| 채널 | 소스 | 담당 데이터 | 주기 |
|---|---|---|---|
| Hook events | `tokenflow-hook` stdin | 세션 경계, 툴 호출, 프롬프트, 환경 변화 | 즉시 |
| Transcript tail | `transcript_path` JSONL | 메시지, input/output/cache_read/cache_write 토큰, 모델 | append 감지 |

매칭: `session_id` + `transcript_path` 로 채널 간 조인.

### 4.4 최초 실행 onboarding (신규)

`tokenflow serve` 를 처음 실행했을 때 React Onboarding 뷰가 현재 상태를 표시한다. 구현은 hook 설치, API 키 입력, ccprophet 후보 감지, 완료 처리를 제공한다.

**Step 1 — Hook 설치 상태 감지**
- Claude Code 설정 파일 경로 자동 탐색 (macOS/Linux: `~/.claude/settings.json`, Windows: `%USERPROFILE%\.claude\settings.json`). XDG 존중.
- 파일 내 `hooks.SessionStart` 이하에 `tokenflow-hook` 존재 여부 체크
- **현재 상태값**: `not_installed` / `partial` / `installed` / `unknown`

**Step 2 — Hook 자동 설치 제안**
- `not_installed` 또는 `partial` 이면 "Install hook into Claude Code?" 액션 표시
- `Allow` → `settings.json` 에 다음 hook 블록 append (기존 설정 보존, 타임스탬프 + 랜덤 suffix `.bak` 백업)
  ```json
  {
    "hooks": {
      "SessionStart":     [{ "matcher": "",  "hooks": [{ "type": "command", "command": "<absolute path to tokenflow-hook>" }]}],
      "PostToolUse":      [{ "matcher": ".*","hooks": [{ "type": "command", "command": "<absolute path to tokenflow-hook>" }]}],
      "SessionEnd":       [{ "matcher": "",  "hooks": [{ "type": "command", "command": "<absolute path to tokenflow-hook>" }]}],
      "UserPromptSubmit": [{ "matcher": "",  "hooks": [{ "type": "command", "command": "<absolute path to tokenflow-hook>" }]}]
    }
  }
  ```
- `command` 절대경로는 `installer.resolve_hook_command()` 가 결정: ① `shutil.which("tokenflow-hook")` → ② `Path(sys.executable).parent / "tokenflow-hook[.exe]"` → ③ POSIX `<prefix>/bin/tokenflow-hook` → ④ bare name fallback. Claude Code 는 hook 을 venv 밖에서 실행하므로 bare 이름을 박으면 silent "command not found" 실패가 발생 — v1.1 에서 bug fix 됨.
- `Skip` → 수동 설치 안내 화면 (복사 가능한 JSON 스니펫)

**Step 3 — Claude API 키 입력 (선택)**
- Coach / LLM better prompt 기능은 API 키 필요
- `Add later` 로 건너뛰면 해당 뷰는 read-only 배너 표시
- 입력 시 `~/.tokenflow/secret.json` 에 0600 권한으로 저장한다. 현재 구현은 저장 여부만 확인하며 즉시 API ping test 는 하지 않는다.

**Step 4 — ccprophet DB 후보 감지**
- `~/.claude-prophet/events.duckdb` 가 존재하면 자동 감지
- 현재 UI/API는 후보 경로와 존재 여부를 표시한다. import 실행은 CLI `tokenflow import --from-ccprophet <path>` 로 수행한다.

**Step 5 — 완료**
- "Claude Code 를 한 번 시작하면 Live Monitor 가 활성화됩니다" 안내
- Live Monitor 로 이동

**Hook 연결 상태 pill** (topbar, §7.2): `/system/health` 의 `hook` 값은 마지막 DB event 시각 기준 `ok` / `stale`(>10분) / `disconnected` 로 반환한다.

---

## 5. 데이터 모델

ccprophet 엔티티 계승 (`TokenCount`, `Money`, `Session`, `Event`, `ToolCall`, `FileAccess`, `Phase`, `PricingRate`, `CostBreakdown`, `BloatReport`, `QualitySeries`).

### 5.1 신규 엔티티

| Entity | 필드 | 용도 |
|---|---|---|
| `Config` (`tf_config`) | `monthly_budget_usd`, `alert_thresholds_pct`, `hard_block`, `better_prompt_mode`, `theme`, `density`, `chart_style`, `sidebar_pos`, `alert_level`, `lang`, `llm_model`, `onboarded_at` | Settings + Onboarding |
| `RoutingRule` | `id`, `condition_pattern`, `target_model`, `enabled`, `priority` | Model routing |
| `NotificationPref` | `key`, `enabled`, `channel:in_app|system` | 알림 설정 |
| `WastePattern` | `id`, `kind`, `severity`, `title`, `meta`, `body_html`, `save_tokens`, `save_usd`, `sessions`, `dismissed_at`, `detected_at` | Waste Radar |
| `CoachThread` | `id`, `title`, `started_at`, `last_msg_at`, `cost_usd_total` | AI Coach |
| `CoachMessage` | `id`, `thread_id`, `role:ai|me`, `content`, `time`, `context_snapshot_json`, `cost_usd` | 대화 기록 |
| `ReplayEvent` | `t`, `query`, `tokens_in`, `tokens_out`, `model`, `cost_usd`, `waste_flag`, `waste_reason` | Replay |
| `BetterPromptSuggestion` (`tf_better_prompt`) | `session_id`, `msg_index`, `suggested_text`, `est_save_tokens`, `mode:static|llm`, `cached_at` | Replay detail |
| `TweaksConfig` | `theme`, `density`, `chartStyle`, `sidebarPos`, `alertLevel`, `lang`, `better_prompt_mode` | UI (localStorage + server 싱크) |

### 5.2 Waste 패턴 탐지 사양

| kind | 구체 임계값 | 심각도 규칙 |
|---|---|---|
| `big-file-load` | 같은 `file_path` 전체 로드 ≥2회, 합 ≥10k 토큰, 세션 내 | ≥100k 토큰=high, ≥30k=med, else low |
| `repeat-question` | **Window 30분, TF-IDF 코사인 유사도 ≥0.9, 3회+**. 임베딩은 v1.1 | 3회=med, 5회+=high |
| `wrong-model` | **Opus 호출이면서 diff <50 LOC + file_edits==1 + 출력 <2000 tokens** | 건당 비용 차이 ≥$0.05=med, else low |
| `context-bloat` | 컨텍스트 사용률 ≥70%가 10분+ 지속 | ≥85%=high, ≥70%=med |
| `tool-loop` | 동일 `tool_name` + 동일 에러 메시지 해시 3회+ in 5분 window | 3회=low, 5+ 또는 비용>$0.50=med |

### 5.3 KPI 포뮬러 (정의)

**Efficiency Score** (0–100, Live Monitor §6.1, Session Summary 알림):
```
base       = 100
penalty    = (waste_ratio × 40) + (opus_misuse_ratio × 30) + (context_bloat_ratio × 30)
score      = max(0, min(100, base - penalty))
```
- `waste_ratio` = wasted_tokens / total_tokens (세션 또는 일 단위)
- `opus_misuse_ratio` = Opus 로 처리된 simple edits 비율
- `context_bloat_ratio` = context ≥70% 상태 지속 시간 / 세션 시간
- 표기: ≥85=green, ≥60=amber, <60=red

**Query Quality Score** (A–D, AI Coach §6.4):
```
signals (0–25 each, total 100):
 - specificity   : query length ≥12 words AND has verb? (25)
 - has_context   : references file/function/line? (25)
 - model_match   : chosen model matches task complexity? (25)
 - scope_bounded : explicit expected output format? (25)
A ≥ 85, B ≥ 70, C ≥ 55, D < 55
```

**Opus 의존도 임계값** (Monthly Budget 카드 경고, `wrong-model` waste 트리거):
- 권장 상한: **Opus 월 비용 / 전체 월 비용 ≤ 15%**
- 초과 시 Monthly Budget 카드에 "Opus 의존도 X% · 권장 15%↓" 경고
- Notification "Opus 과사용": 7일 롤링 Opus 비용 점유율 ≥25%

### 5.4 데이터 retention & pricing 업데이트

**Retention**:
- 상세 `events`, `tf_messages` 는 180일 보관한다.
- 180일 이전 `tf_messages` 는 삭제 전 `daily_aggregate` 로 day/project/model 단위 rollup 한다.
- 자동 retention 은 앱 시작 시 수행하고, `/system/vacuum` 실행 시에도 retention 후 DuckDB vacuum 을 수행한다.
- `/system/backups` 는 생성된 `.duckdb` 백업 목록을 반환한다.

**Pricing rates**:
- `PricingRate` 테이블은 마이그레이션 V1 에서 seed (Sonnet 4.5, 4.6, Opus 4, Haiku 4.5 등 출시 가격)
- Anthropic 가격 변경 시 `migrations/VN__pricing_update.sql` 로 새 버전 row 추가 (기존 row `effective_until` 설정)
- 사용자 override: `~/.tokenflow/pricing_overrides.json` 파일이 있으면 해당 모델/키에 한해 덮어씀
- 모든 계산은 이벤트 발생 시점의 `effective_at` rate 로 고정 (소급 변경 없음)

### 5.5 DB 마이그레이션

- V1–V5: ccprophet 호환 기반 테이블
- V6: `tf_messages`, `tf_transcript_offsets`, `tf_hook_offset`, `tf_config`
- V7: `tf_waste_patterns`, `tf_coach_threads`, `tf_coach_messages`, `tf_better_prompt`, `tf_routing_rules`, `tf_notification_prefs`
- V9: `tf_config.llm_model`
- V10: `tf_messages.paused`, `daily_aggregate`
- V11: `budget_threshold`, `api_error` notification preferences
- V12: `tf_notifications` persisted in-app notification history

마이그레이션은 현재 **forward-only** 로 적용된다. pending migration 적용 전 DB 파일 백업은 수행한다. 실패 로그/자동 복원은 추가 개선 항목이다.

---

## 6. 기능 명세 (6개 뷰 + Onboarding)

사이드바 기본 순서: **Live Monitor → Analytics → Waste Radar → AI Coach → Session Replay → Settings**.

### 6.1 Live Monitor (기본 랜딩)

**구성**:
1. KPI 4개: 현재 세션 Tokens, Today Total, **Efficiency Score (§5.3 포뮬러)**, Wasted Tokens
2. Token Flow 영역 차트 (60분, Opus/Sonnet/Haiku/Cache hit 4 stacked)
3. Context Window 링 게이지 — ≥70% 에서 `/compact` 추천 배너
4. Model Distribution (오늘)
5. Monthly Budget 카드 — 사용량 + forecast + Opus 의존도 경고
6. Live Activity ticker (SSE, ring buffer 10개)
7. Projects 테이블 (이번 주)

**상호작용**:
- `Pause tracking`: 서버의 `ingestion_paused` 플래그 토글. hook 은 계속 실행되지만 event 는 `paused=true` 마커로 기록 (삭제 아님, 분석 제외)
- `Export session`: 현재 세션의 `Session + ReplayEvent[]` JSON 다운로드. schema: `tokenflow.export.v1`. 기본값은 paused transcript message 제외, `include_paused=true` 로 forensic/debug export 가능

**Empty state (hook 연결 직후, 이벤트 없음)**:
- KPI 카드 대신 "Waiting for first event from Claude Code…" 스켈레톤
- ticker 자리 "No activity yet. Start a Claude Code session."
- Budget/Projects 는 비어있으면 "Last 7 days empty · Import past data" CTA

**Ticker 이벤트 taxonomy**:
`edited` (Write/Edit tool) · `read` (Read tool) · `grep` (Grep/Glob tool) · `bash` (Bash tool) · `reply` (assistant message) · `tool` (기타 MCP) — 각각 아이콘·색상 매핑

**Projects 7d trend 스파크라인 데이터**: `GET /api/projects/{name}/trend?range=7d` (§8)

### 6.2 Usage Analytics

**구성**:
1. Range picker: 24H / 7D / 30D / 90D / All (All 은 최대 1년)
2. KPI 4개 — Total tokens, Total cost, Avg session length, Cost per session
3. Daily Usage stacked area (30일)
4. Cost Breakdown 링 — Input/Output/Cache write/Cache read + cache utilization 텍스트
5. Top Waste Patterns 리스트 (4개)
6. Activity Heatmap (7×24)

**Project 필터**: 상단 pill "All projects ▾" 드롭다운 — 선택 시 모든 차트·테이블이 해당 프로젝트로 필터링

**Empty state**: "No usage data in this range." + "Switch range" 또는 "Import from ccprophet" CTA

### 6.3 Waste Radar

**구성**:
1. Summary strip — 이번 주 절감 가능 총액, 심각도별 카운트
2. Waste 카드 리스트 (좌 2/3)
3. Waste Sources 도넛 (우 1/3)
4. Optimization tips

**Apply fix 동작** (패턴별):
- `big-file-load`: CLAUDE.md 규칙 추가 제안 (diff preview)
- `repeat-question`: CLAUDE.md FAQ 섹션 제안
- `wrong-model`: Routing rule 자동 생성 → Settings
- `context-bloat`: 안내만
- `tool-loop`: CLAUDE.md 에러 규칙 추가

**탐지 스케줄링** (§5.2 임계값 기반):
- `/wastes/scan?session_id=`: 특정 세션 또는 최근 24시간 범위에서 5종 패턴 평가 → 매칭 시 `WastePattern` insert
- `/wastes/sweep`: 시간당 sweep 과 동일한 전체 탐지 동작을 수동 실행. 최근 24시간 내 세션을 크로스 세션 관점으로 재평가
- 매칭 결과는 SSE `waste-detected` 이벤트로 푸시 → Bell 알림 + Waste Radar 자동 갱신

**Empty state**: "No waste patterns detected. 🎉" + "Explore optimization tips" 링크

### 6.4 AI Coach

**LLM**: Claude Sonnet 4.6

**레이아웃**: 3열 (Threads / 대화 / Context 패널)

**Query Quality Score** (§5.3 포뮬러) — Context 패널에 A–D 등급 + 부족 신호 툴팁

**비용 가시성**: 대화 헤더 우측 "This thread · $0.14" 라이브 누적 표시. 메시지 전송 전 "Est. cost: ~$0.008" 힌트

**컨텍스트 주입 (프라이버시)**:
- 시스템 프롬프트 JSON: `{sessions_summary, daily_tokens, model_shares, waste_summary, project_names}`
- **주입 금지**: 질문 원문, 파일 내용, API 응답 본문, 전체 파일 경로 (basename 만)

**API 키 미설정 상태**: "Add your Claude API key to enable AI Coach" 배너 + Settings 이동 버튼

**Empty state (스레드 없음)**: welcome 메시지 + 제안 칩 5개 클릭 시 첫 스레드 자동 생성

### 6.5 Session Replay

**세션 picker**:
- 뷰 진입 시 좌측 slim sidebar 에 세션 리스트 (기본 최근 20개, 무한 스크롤)
- 각 항목: 시작 시각, 프로젝트, 총 토큰, 총 비용, waste 아이콘. paused transcript message 는 totals/messages/cost/search 에서 제외
- 클릭 시 해당 세션 replay. 기본 landing = 가장 최근 세션
- 상단 필터: 프로젝트, 기간, "has waste only"
- 검색창: 쿼리 텍스트로 세션 검색

**구성** (선택된 세션):
1. 상단 요약 바
2. 스크럽 바 차트
3. 메시지 테이블
4. Detail 패널 + Better prompt

**Paused transcript 처리**:
- `session_replay` 기본 응답은 paused transcript message 를 제외한다.
- 원본 디버깅/감사용 조회는 `include_paused=true` 로 요청한다.
- `export_session` 도 동일하게 기본 제외, `include_paused=true` 포함 정책을 따른다.

**Better prompt — 2모드**:

| 측면 | static | llm |
|---|---|---|
| 응답 | <50ms | 1–3초 |
| 비용 | $0 | ~$0.01/query |
| 결정성 | 매 호출 동일 | 미세 차이 |
| 기본값 | Tweaks 의 `better_prompt_mode` 기본값 `static` |

**LLM 모드 프롬프트 템플릿**:
```
System: You are a Claude Code usage coach. Rewrite the user's query to be more efficient.
Rules:
- Max 3 lines
- Suggest tool usage (grep/glob) when full-file-read is wasteful
- Recommend smaller model if appropriate
- Never suggest running bash commands
Context:
 - waste_reason: {{reason}}
 - original_query: {{query}}
 - tokens_used: {{tokens_in}} in / {{tokens_out}} out
 - model_used: {{model}}
Output: a rewritten query only (no explanation).
```
- 모델: Sonnet 4.6, max_tokens=200, temperature=0.2
- 캐시: `source_message_id` 별 24시간

**정적 템플릿 5종**:
1. `big-file-load` → "grep `<pattern>` in `<basename>` — no need to load full file"
2. `repeat-question` → "Save answer to CLAUDE.md: `<topic>`"
3. `wrong-model` → "Use `/model haiku` — this is a simple edit"
4. `context-bloat` → "Run `/compact` or branch a new session"
5. `tool-loop` → "Add to CLAUDE.md: `error <X>` → `fix <Y>`"

**Playback 버튼**: v1 제외, "coming soon" disabled

**Empty state**: "No sessions yet. Start Claude Code to record your first session."

### 6.6 Settings

**섹션**:
1. **Monthly budget** — Hard limit + Alert thresholds (50/75/90%). "Hard block · v2" 배지
2. **Model routing rules** — 조건→모델 매핑, 토글, Add rule
3. **Notifications** — 8종 토글
   - In-app: 항상 가능
   - System: 브라우저 Notification API 지원/권한 상태에 따라 토글 가능 여부를 제어
4. **Better prompt mode** — static / llm. 서버 `tf_config.better_prompt_mode` 에 영속하며 API 경로는 `/settings/tweaks`
5. **Claude API key** — 입력·편집·삭제. 미입력 시 Coach/LLM 기능 비활성. 연결 테스트는 §12 추적 항목
6. **Data** — Vacuum, 백업 리스트, ccprophet import job 상태를 Settings UI 에서 연결

**i18n 범위**:
- UI 고정 문자열: 번역됨 (`i18n/ko.json`, `i18n/en.json`)
- 번역 제외 (원문 유지): Coach LLM 응답, Waste body_html (서버 생성 시 사용자 lang 에 맞춰 템플릿 선택), 모델명, 파일명, 커맨드

### 6.7 Onboarding (신규)

§4.4 플로우. 완료 후 `tf_config.onboarded_at` 기록. Settings 에서 재진입하는 "Re-run onboarding" 액션은 §12 추적 항목.

---

## 7. 공용 요소

### 7.1 사이드바
- 브랜드 `Token⌁Flow`
- Workspace: Live / Analytics / Waste Radar / AI Coach / Replay
- Account: Settings / Docs
- 하단: 월 예산 mini-progress + 사용자 카드 + logout

### 7.2 Topbar
- Breadcrumbs
- Live Monitor 만 range picker 노출
- Hook connection pill (§4.4, green/amber/red)
- Search / Bell / Tweaks 버튼

### 7.3 Bell 알림
- 드롭다운 최근 10개, Clear all
- 종류: waste detected · budget threshold · context saturation · **Opus overuse (§5.3 ≥25%)** · session summary · API error
- System notification 은 `NotificationPref.channel=system` 토글 + OS 권한 필요

---

## 8. API 계약 (REST + SSE)

Prefix `/api`. 인증 없음. 127.0.0.1 바인딩.

### 8.1 세션 / 이벤트
| Method | Path | 설명 |
|---|---|---|
| GET | `/sessions/current` | 현재 활성 세션 |
| GET | `/sessions/{sid}/replay?include_paused=false` | Replay 이벤트. 기본 paused message 제외 |
| GET | `/sessions/{sid}/export?include_paused=false` | `tokenflow.export.v1` JSON export. 기본 paused message 제외 |
| GET | `/sessions?project=&has_waste=&q=&limit=` | 세션 검색·필터. totals/messages/cost/search 는 paused message 제외 |
| GET | `/events/stream?replay=true` | Activity ticker SSE (`Last-Event-ID` 지원). Frontend Topbar/ActivityTicker share one `TickerSSEBridge` connection with `replay=false`; `TokenFlowChart` keeps separate flow SSE. |
| GET | `/sessions/current/flow?window=60m` | 60분 flow chart JSON snapshot |
| GET | `/sessions/current/flow/stream?window=60m` | Flow chart SSE snapshot/invalidation (`event: flow`) |

### 8.2 KPI / 분석
| Method | Path | 설명 |
|---|---|---|
| GET | `/kpi/summary?window=today\|7d\|30d` | Efficiency attribution is computed with grouped waste rollups, including `byKind` breakdown. |
| GET | `/kpi/models` | 모델별 오늘 token/cost/share |
| GET | `/kpi/budget` | 월 예산, 사용액, forecast, Opus share |
| GET | `/analytics/kpi?range=7d&project=` | 분석 KPI summary |
| GET | `/analytics/daily?range=30d&project=` | stacked area |
| GET | `/analytics/heatmap?range=7d&project=` | 히트맵 |
| GET | `/analytics/cost-breakdown?range=30d&project=` | 비용 분해 |
| GET | `/analytics/top-wastes?range=30d&limit=4&project=` | `tf_waste_patterns` 기반 top patterns. range/project 내 kind별 aggregate 후 severity → save_usd → save_tokens → detected_at 순 정렬 |

### 8.3 Waste
| Method | Path | 설명 |
|---|---|---|
| GET | `/wastes?status=active\|dismissed` | |
| POST | `/wastes/{id}/dismiss` | |
| POST | `/wastes/{id}/apply` | outcome + CLAUDE.md/routing diff preview |
| POST | `/wastes/scan?session_id=` | 특정 세션 또는 현재 범위 waste 탐지 |
| POST | `/wastes/sweep` | hourly sweep 과 동일한 전체 탐지 |

### 8.4 Coach
| Method | Path | 설명 |
|---|---|---|
| GET | `/coach/threads` | |
| POST | `/coach/threads` | |
| GET | `/coach/threads/{id}/messages` | |
| POST | `/coach/threads/{id}/messages` | Body `{ content }`. Response 포함 `cost_usd` |
| GET | `/coach/suggestions` | |
| POST | `/coach/query-quality` | Body `{ query, context }` → A–D + 신호별 점수 |

### 8.5 Settings
| Method | Path | 설명 |
|---|---|---|
| GET | `/settings` | `{ budget, tweaks }` |
| PUT | `/settings/budget` | budget 갱신 후 `{ budget, tweaks }` 반환 |
| GET | `/settings/routing-rules` | |
| POST | `/settings/routing-rules` | routing rule 생성 |
| PATCH/DELETE | `/settings/routing-rules/{id}` | |
| GET | `/settings/notifications` | |
| PATCH | `/settings/notifications/{pref_key}` | |
| GET | `/notifications?limit=10` | persisted in-app Bell notification history |
| GET | `/notifications/unread-count` | Bell badge total unread count. Do not infer badge from the limited recent-history response. |
| POST | `/notifications` | in-app notification 저장. disabled/system pref 는 저장하지 않음 |
| PATCH | `/notifications/{id}/read` | 개별 Bell notification read 처리 |
| POST | `/notifications/read-all` | unread Bell notification 일괄 read 처리 |
| DELETE | `/notifications` | Bell notification clear all |
| POST | `/settings/api-key` | |
| GET | `/settings/api-key/status` | `{configured, valid, backend}` |
| DELETE | `/settings/api-key` | |
| PATCH | `/settings/tweaks` | `TweaksConfig` server copy. `better_prompt_mode` 도 여기서 갱신 |

### 8.6 Projects
| Method | Path | 설명 |
|---|---|---|
| GET | `/projects?range=7d` | includes `trendData` per project from one grouped project/day query to avoid row-level trend N+1 calls |
| GET | `/projects/{name}/trend?range=7d` | project 일별 token sparkline. Single-project query path; must not call full `/projects` aggregation for existence checks. |

### 8.7 Better prompt
| Method | Path | 설명 |
|---|---|---|
| POST | `/sessions/{sid}/messages/{idx}/better-prompt?mode=static\|llm` | |

### 8.8 Import

구현된 경로는 CLI `tokenflow import --from-ccprophet <path>` 와 REST background job API 이다. V1–V5 공유 테이블을 idempotent 하게 복사한다.

| Method | Path | 설명 |
|---|---|---|
| POST | `/import/ccprophet` | Body `{ path }` → `{ job_id, state }` |
| GET | `/import/ccprophet/status/{job_id}` | `{ state, imported, skipped, errors, total, counts }` |

### 8.9 Onboarding
| Method | Path | 설명 |
|---|---|---|
| GET | `/onboarding/status` | `{ onboarded, hook, api_key_configured, ccprophet }` |
| POST | `/onboarding/install-hook?dry_run=` | `settings.json` 수정. 기존 파일은 `.bak.<timestamp>_<suffix>` 로 백업 |
| POST | `/onboarding/complete` | `tf_config.onboarded_at` 세팅 |

### 8.10 System
| Method | Path | 설명 |
|---|---|---|
| GET | `/system/health` | `status`, `version`, `db`, `hook`, `api_key`, `home` |
| POST | `/system/ingestion-pause` | Body `{ paused }` → hook event 에 `paused=true` marker |
| GET | `/system/backups` | 백업 `.duckdb` 파일 리스트 |
| POST | `/system/vacuum` | vacuum 실행 전 DB backup 생성 후 DuckDB vacuum |

---

## 9. 실시간 데이터 흐름

### 9.1 두 채널 수집

**A. Hook events**:
1. Claude Code → hook → stdin JSON
2. `tokenflow-hook` → `~/.tokenflow/events.ndjson` append
3. FastAPI `EventTailer` (polling tailer) → DuckDB `events` + asyncio PubSub
4. SSE 브로드캐스트

**B. Transcript tail**:
1. hook 이벤트의 `transcript_path` 추출
2. `TranscriptTailer` JSONL watch
3. 신규 라인 파싱 → 토큰 + 메시지 → DuckDB

### 9.2 폴링 vs SSE
- SSE: `/events/stream` activity ticker
- SSE: `/sessions/current/flow/stream` flow chart snapshot/invalidation
- 폴링 5–15초: KPI, 예산, 프로젝트
- on-demand: Analytics 진입 시 fetch + TanStack Query 캐시

### 9.3 SSE 재연결 / backpressure
- 클라이언트 `EventSource` 자동 재연결. `Last-Event-ID` 헤더로 누락분 replay
- 서버: `EventBus` 가 in-memory sequential id 를 부여하고, 재연결 시 buffer 에 남은 >id 이벤트를 replay
- Ticker buffer: 최근 **100개 ring buffer** 유지, 연결 없으면 drop (무한 쌓이지 않음)
- Flow chart: `/sessions/current/flow/stream` 이 최초 snapshot 과 transcript message 기반 invalidation 을 `event: flow` 로 전달한다. REST JSON snapshot 은 fallback/직접 조회용으로 유지한다.

### 9.4 세션 ↔ transcript 매칭
- `session_id` primary key, `transcript_path` 매핑 저장
- `SessionEnd` 또는 15분 이벤트 부재 시 세션 종료

---

## 10. 비기능 요구사항

### 10.1 성능 & 스케일 가정

| 항목 | 목표/가정 |
|---|---|
| 콜드 스타트 | ≤ 3초 |
| KPI 쿼리 | ≤ 200ms |
| SSE 푸시 지연 | ≤ 500ms |
| 일일 이벤트 수 | ~500개 가정 (upper 2,000) |
| transcript JSONL 크기 | ~10MB/세션 가정 |
| DB 크기 | ~50MB/월 가정, 180일 retention 후 ~300MB |
| Analytics "All range" | 최대 1년 (초과분은 월별 rollup 만) |
| 동시 브라우저 탭 | 정상 동작, SSE 탭 당 독립 |

### 10.2 프라이버시
- 외부 네트워크 기본 OFF
- Coach 컨텍스트에 질문 원문·파일 내용·경로 상세 포함 **안 함**
- 모든 DB 로컬 저장

### 10.3 보안
- CLI 기본 bind host 는 `127.0.0.1`
- CORS 허용 origin 은 현재 `http://localhost:5173`, `http://127.0.0.1:5173`
- API 키는 `~/.tokenflow/secret.json` 에 저장하고 0600 권한을 best-effort 로 적용한다.
- `.gitignore` 에 `.tokenflow/` 기본 포함

### 10.4 에러 taxonomy (UI 노출)

| 상황 | UI 처리 | fallback |
|---|---|---|
| API 키 invalid (401) | Coach/Better prompt 헤더에 빨간 배너 "API key rejected", Settings 이동 CTA | Coach 메시지 전송 비활성 |
| Anthropic rate limit (429) | "Rate limited. Retrying in Ns…" | 지수 백오프 최대 3회 |
| Anthropic 5xx | "Anthropic service issue. Try later." | 메시지 draft 보존 |
| Hook 프로세스 크래시 | Topbar pill `disconnected` (red), 상세 로그 Settings→Data | 이벤트 누락 경고 배너 |
| Transcript 라인 parse 실패 | 로그만, UI 영향 없음 | 해당 라인 skip, 카운터 증가 |
| Transcript 파일 사라짐 | 세션을 `ended_abruptly=true` 로 종료 | Replay 에서 경고 표시 |
| DuckDB 락/오류 | Topbar 에러 배너 "DB unavailable" | 자동 재시도 5초 |
| Disk 사용 > 90% | Topbar 경고 "Disk almost full", "Vacuum now" CTA | Insert 계속 시도 |
| Migration 실패 | 서버 기동 중단, 자동 백업 복원 시도, 로그 `~/.tokenflow/logs/migration_failed.log` | 사용자 수동 개입 |
| API 키 파일 권한 0600 아님 | 파일 저장 시 best-effort chmod | 실패 시 저장은 유지하되 health/status 에서 점검 가능 |

### 10.5 관측성
- **구조화 로깅**: `serve` 기본은 JSON lines on stderr (`{"ts","level","logger","msg","request_id", ...}`). `serve --dev` 는 사람이 읽기 좋은 `LEVEL NAME [request_id] message` 포맷. 둘 다 uvicorn access/error 로거까지 같은 handler 를 공유한다.
- **Request correlation**: `RequestIdMiddleware` 가 요청마다 `X-Request-ID` 를 검증·발급한다. 클라이언트가 보낸 값은 `^[A-Za-z0-9._:\-]{1,64}$` 일 때만 echo; 제어문자(CR/LF/NUL 등)·길이 초과는 조용히 새 uuid4 hex 로 대체한다. **F2 — CRLF 헤더 인젝션 회귀 테스트 필수** (`tests/test_middleware_request_id.py`, 5 cases).
- **로그 레벨**: 환경변수 `TOKENFLOW_LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR/CRITICAL). 기본 INFO, 미지 값은 INFO 로 fallback + warning 1회.
- 파일 rotation (`~/.tokenflow/logs/`, 7일) 은 §10.4 `migration_failed.log` 와 함께 v1.2 에서 다룸.

### 10.6 기타
- I18n: 한국어/영어. 날짜·숫자는 사용자 lang 에 따라 `Intl` 포맷. TZ 는 브라우저 로컬.
- 접근성: WCAG AA, 키보드 네비게이션, 주요 아이콘에 `aria-label`
- 브라우저: 최신 Chrome/Edge/Firefox/Safari (Chromium 120+)
- Telemetry: **없음**. 버전 체크도 없음. 완전 로컬.

---

## 11. 결정된 사항 (v0.2+v0.3)

1. AI Coach LLM → **Claude Sonnet 4.6**
2. API 키 저장 → 평문 `~/.tokenflow/secret.json` (0600 best-effort)
3. Coach 컨텍스트 주입 → 토큰·비용·모델·waste·프로젝트명·파일 basename 만
4. Hard budget limit 차단 → v1 알림만, v2 proxy 차단
5. Better prompt → **사용자 선택** (static / llm). 기본 static
6. Hook 이벤트 schema → 공식 문서 기준, **훅에 토큰 없음** → transcript tailer 분리
7. Session Replay Playback → v1 제외
8. 다중 세션 → 각 `session_id` 분리, Live Monitor 는 최근 활성 1개만
9. 프로젝트 식별 → `cwd` git root, 아니면 cwd
10. ccprophet DB import → **v1 포함**, CLI + REST background job/status API 구현
11. Waste 탐지 → `/wastes/scan`, `/wastes/sweep` API 로 실행. SessionEnd 자동 평가는 추적 항목
12. Better prompt LLM 템플릿 → §6.5 프롬프트 템플릿 고정
13. Efficiency Score 포뮬러 → `tf_messages` + `tf_waste_patterns` 기반 실제 계산 구현
14. Query Quality Score 포뮬러 → §5.3 정의, Coach composer 에 전송 전 grade/signal 표시
15. Opus overuse 임계값 → 월 비용 점유율 15%(권장), 25%(알림 발생)
16. DB retention → 180일 상세 보관 + `daily_aggregate` rollup 구현. 장기 analytics 에 rollup 을 병합하는 것은 추가 개선
17. Pricing 업데이트 → 현재 seed table 기준. override 파일 지원은 추적 항목
18. SSE 재연결 → `Last-Event-ID` + 100개 ring buffer
19. Import 실패 처리 → CLI/REST 모두 공유 테이블 복사 + PK conflict skip 중심. REST job 은 progress/error 상태를 반환
20. Notifications → in-app/system preference, 브라우저 OS 권한/지원 여부 플로우, waste system notification 1차 구현

---

## 12. 코드보다 SPEC이 더 올바른 구현 추적 항목

현재 문서는 구현 기준으로 API/상태값을 정리했다. 아래는 아직 코드가 더 따라가야 하거나, 1차 구현은 됐지만 추가 개선이 필요한 SPEC 우선 항목이다.

| 항목 | 현재 구현 | SPEC 우선 판단 |
|---|---|---|
| API 키 상태 판정 | `/settings/api-key/status`, `/system/health`, `/onboarding/status` 모두 `secret_store.status()` 기반 | 완료. 파일 저장 정책 기준 |
| Hook stale 판정 | 마지막 DB event 시각 기준 `ok` / `stale`(>10분) / `disconnected` 반환 | 완료. 설치 여부와 연결 상태의 세분화는 추가 개선 가능 |
| Session inactivity 종료 | 활성 세션의 마지막 event/message 가 15분 이상 없으면 polling tailer 가 `ended_at` 을 기록 | 완료. inactivity 종료 사유의 영구 event 기록은 추가 개선 |
| Flow chart 채널 | `/sessions/current/flow/stream` SSE snapshot/invalidation + REST fallback | 완료. `Last-Event-ID` replay 는 EventBus 정책을 따른다 |
| Import UX | CLI import + REST background job/status API, Settings Data 카드 job 상태 표시 구현 | 완료. 더 자세한 progress bar 는 추가 개선 |
| 마이그레이션 안전성 | pending migration 적용 전 DB backup 생성 | 1차 완료. 실패 로그/자동 복원은 추가 개선 |
| Retention/Vacuum | 앱 시작 및 `/system/vacuum` 에서 180일 retention + `daily_aggregate` rollup 수행, `/system/backups` 구현 | 완료. rollup 기반 장기 analytics 활용은 추가 개선 |
| Live KPI efficiency/waste | `tf_messages` 총 토큰과 `tf_waste_patterns.save_tokens` 기반 Efficiency Score / Wasted Tokens 계산, penalty attribution 상세 패널 포함 | 완료. 더 정교한 waste attribution 은 추가 개선 |
| Usage Analytics project filter | KPI/daily/heatmap/cost/top-wastes API와 UI project dropdown 연결 | 완료 |
| Project trend sparkline | `/projects/{name}/trend` 가 project 일별 token series 반환, Projects table sparkline 연결 | 완료. 프로젝트 상세 drill-down 은 추가 개선 |
| Top waste analytics | `/analytics/top-wastes` 가 `tf_waste_patterns` 실제 데이터에서 range/limit/project 기준 kind별 aggregate ranking 반환, Usage Analytics 카드 연결 | 완료. 세션 drill-down 은 추가 개선 |
| Waste apply preview/apply | `/wastes/{id}/apply` 가 outcome 과 CLAUDE.md/routing diff preview 를 반환하고, 별도 confirm 으로 CLAUDE.md append | 완료. 더 정교한 conflict/diff UI 는 추가 개선 |
| Pause tracking / Export session | pause flag API, paused hook marker, transcript message `paused` marker, 분석/list/replay/export 기본 제외, `include_paused=true` forensic 조회 지원 | 완료. pause 기간 UX 표시는 추가 개선 |
| Query Quality Score | `/coach/query-quality` 정적 scoring API + Coach composer grade/signal UI 구현 | 완료. signal별 rewrite suggestion 은 추가 개선 |
| Bell notification center | Topbar Bell 최근 10개 persisted in-app 알림, unread badge, dropdown open read-all, 개별 read, Clear all 구현 | 완료. persisted notification filter/search 는 추가 개선 |
| System notifications | in-app/system preference, 브라우저 Notification 지원/권한 플로우, waste, SessionEnd, budget threshold, context saturation, Opus overuse, API error 이벤트 연결 | 완료. 더 세밀한 알림 빈도 제어는 추가 개선 |
| 구조화 로깅 / 로그 로테이션 | JSON formatter · `TOKENFLOW_LOG_LEVEL` · `X-Request-ID` 미들웨어 (F2 CRLF 인젝션 방어 포함) 는 v1.2 에 구현 완료. `~/.tokenflow/logs/` 파일 rotation 은 §10.4 와 함께 후속 | §10.5 참조 |
| Hard budget 한계 도달 알림 | `hard_block` 설정 컬럼은 존재하나 budget-threshold 이벤트를 SSE 로 발사하는 publisher 부재 (ticker 렌더 경로만 있음) | SPEC §11 #4 기준 "v1 알림" 약속 — publisher 누락 보완 필요 (v1.1) |

---

## 13. v1 범위 밖 (명시적 제외)

- 팀/조직 대시보드, SSO, RBAC
- 클라우드 배포·원격 접근
- **Hard budget 차단** (v2)
- IDE 플러그인
- 모바일 레이아웃 (≥1024px 가정)
- 외부 알림 (Slack, Email)
- Data export CSV/Parquet (v1.1)
- Session Replay Playback (v1.1)
- Live Monitor 다중 세션 셀렉터 (v1.1)
- 타 도구 import
- 임베딩 기반 repeat-question (v1.1, v1 은 TF-IDF)
- 자동 Coach suggestion — 사용자 지정 질문만 응답 (v1.1)
- Pre-flight 요청 차단 proxy (v2)

---

## 14. 용어

- **세션(Session)**: Claude Code 1회 실행 단위
- **컨텍스트 포화도**: 현재 세션 토큰 / 모델 윈도우
- **Bloat ratio**: 로드된 토큰 중 미사용 비율
- **Cache hit**: Anthropic cache_read
- **Hook**: Claude Code `settings.json` event handler
- **Transcript**: 세션별 JSONL 파일 (토큰 원본)
- **Tweaks**: UI 외관 커스터마이징 패널
- **Waste pattern**: 5종 분류 (big-file-load, repeat-question, wrong-model, context-bloat, tool-loop)

---

## 15. 다음 단계

1. ✅ SPEC v0.3-impl — 현재 구현 기준 정합성 반영
2. ✅ Flow chart SSE/invalidation 구현
3. ✅ retention 자동화 + daily rollup 구현
4. ✅ system notification 권한 플로우와 UI 연결

## 16. Current Implementation Contract (2026-04-21)

This section is the readable source of truth for the current code baseline. Some older Korean sections in this file are mojibake in local terminal output; use this section when checking current SPEC/API/test alignment.

### Implemented Core Surface

- Live Monitor: current session, today total, Efficiency Score, Wasted Tokens, model distribution, context window, budget card, and projects table are wired to real API data.
- Token Flow: `/api/sessions/current/flow/stream` is the primary SSE snapshot/invalidation channel. REST snapshot remains as fallback.
- Activity/Bell notifications: Topbar and ActivityTicker share one ticker bridge. Bell uses persisted in-app history, unread count, open-read-all, individual read, and clear-all APIs.
- Usage Analytics: range and project filters are passed to KPI, daily, heatmap, cost breakdown, and top-wastes APIs.
- Top Wastes: `/api/analytics/top-wastes` returns aggregate ranking by waste kind rather than raw row listing.
- Waste Radar: active waste cards, savings summary, scan/sweep, dismiss, apply preview, and `CLAUDE.md` confirm-apply are implemented.
- AI Coach: API-key gating, estimated send cost, Query Quality Score, thread creation, and message send flow are implemented. If no thread exists, first send must create a thread and then POST the message.
- Session Replay: paused transcript messages are excluded by default from replay/export/list analytical surfaces; `include_paused=true` enables forensic/debug view.
- Settings: budget, LLM model, better prompt mode, routing rules, notification preferences, API key, and Data card(vacuum/backups/ccprophet import job/status) are wired.
- Onboarding: hook status, API key status, ccprophet candidate detection, and complete flow are implemented.
- Retention/Data: 180-day detailed retention, daily rollup, vacuum, backup list, and migration backup are part of the implementation contract.

### Playwright Contract

`frontend/e2e/spec-core.spec.ts` fixes the browser-level SPEC contract with mocked API responses:

- Live Monitor + Bell notification dropdown/read-all
- Usage Analytics project-scoped API calls
- Waste Radar apply preview + `CLAUDE.md` confirm
- AI Coach query quality + estimated cost + thread/message send
- Session Replay `include_paused`
- Settings notification preference + vacuum/backups/import status
- Onboarding complete

`frontend/e2e-real/actual-data.spec.ts` validates the real local server at `http://127.0.0.1:8765` with real DuckDB data:

- Live Monitor renders from real API data
- Analytics project filter calls real project-scoped APIs
- Replay `include_paused` calls the real endpoint
- UI onboarding state matches real server status

Latest local verification on 2026-04-21:

- `npm run test:e2e`: 7 passed
- `npm run test:e2e:real`: 4 passed
- `npm run typecheck`: passed
- `npm run lint`: passed
- `npm run test -- --run`: 41 passed, 1 skipped
- `npm run build`: passed

### Remaining Gaps

- Clean up the older mojibake sections in this SPEC as a dedicated documentation pass.
- Expand Playwright from Chromium-only to Firefox/WebKit/mobile viewport matrix if release confidence requires it.
- Strengthen hard-budget threshold event publisher. v1 remains notification-only, but event emission can be more explicit.
- Add notification filtering/search, more detailed import progress, replay playback, and multi-session Live Monitor as v1.1 candidates.
