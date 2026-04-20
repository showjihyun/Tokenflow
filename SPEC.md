# Token Flow — SPEC

> 버전 0.3 · 2026-04-20 · 독립 리뷰 gap 20개 반영. DESIGN.md 진행 준비 완료.

### v0.2 → v0.3 변경 요약
- KPI 포뮬러 정의: **Efficiency Score**, **Query Quality Score**, **Opus overuse 임계값**
- Waste 패턴 구체적 임계값 확정 (window, similarity, LOC 기준)
- **§4.4 신규** — 최초 실행 onboarding (hook 자동 설치, API 키, import 유도)
- **§6.x 신규** — 뷰별 empty/first-run state
- **§6.5** — 과거 세션 picker UI 추가
- Better prompt LLM 모드 프롬프트 템플릿 정의
- Waste detection 스케줄링 정의 (SessionEnd + hourly sweep)
- **§10** — 에러 taxonomy 추가, 스케일 가정 명시
- **§11** — 데이터 retention/pricing 업데이트 정책
- SSE 재연결 / backpressure 정책
- Pause tracking + Export session 동작 정의
- Import 중복/실패/진행률 semantics

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
| 플랫폼 | 웹 대시보드 (브라우저) | 데스크톱 앱, 모바일, CLI 독립 실행 |
| 사용자 | 개인 개발자 1명 | 팀·조직, SSO, RBAC |
| 인증 | 로컬 전용 127.0.0.1 | 원격 배포, OAuth |
| 데이터 원천 | Claude Code 훅 + JSONL transcript | IDE 플러그인, 프록시 |
| 예산 하드 차단 | 알림만 | 요청 차단 (v2) |
| AI Coach | Sonnet 4.6 대화 | 멀티 에이전트, 자동 코드 수정 |
| Better prompt | 정적 + LLM, 사용자 선택 | 자동 적용 (수동 복사만) |
| 과거 데이터 | ccprophet import | 타 도구 import |
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
8. **ccprophet DB import CLI + API**
9. **Onboarding flow** (hook 자동 설치)

---

## 3. 기술 스택

| 레이어 | 선택 | 비고 |
|---|---|---|
| Backend | Python 3.11 + FastAPI | |
| ASGI | uvicorn | |
| DB | DuckDB (임베디드) | |
| Transcript watch | watchdog | |
| Frontend | React 18 + TypeScript strict | |
| Build | Vite | |
| Styling | CSS Variables + CSS Modules | Tailwind 없이 |
| State | Zustand | |
| Data fetching | TanStack Query v5 | |
| Real-time | SSE (EventSource) + Last-Event-ID | |
| Charts | 직접 SVG | |
| Icons | Lucide React | |
| AI Coach LLM | Claude Sonnet 4.6 | |
| Test | pytest + vitest + @testing-library/react | |
| Lint | ruff + mypy strict + eslint + prettier | |
| 패키징 | uv + pnpm | |
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
│   ├── migrations/     # V1–V8 SQL
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

`tokenflow serve` 를 처음 실행했을 때의 5단계 플로우. 각 단계는 React Onboarding 뷰에서 진행 상황을 표시 (사이드바 뷰 비활성, 중앙 스테퍼만 노출).

**Step 1 — Hook 설치 상태 감지**
- Claude Code 설정 파일 경로 자동 탐색 (macOS/Linux: `~/.claude/settings.json`, Windows: `%USERPROFILE%\.claude\settings.json`). XDG 존중.
- 파일 내 `hooks.SessionStart` 이하에 `tokenflow-hook` 존재 여부 체크
- **상태 3가지**: `not_found` / `mismatched` (다른 버전) / `ok`

**Step 2 — Hook 자동 설치 제안**
- `not_found` 또는 `mismatched` 이면 "Install hook into Claude Code?" 모달
- `Allow` → `settings.json` 에 다음 hook 블록 append (기존 설정 보존, `.bak` 백업)
  ```json
  {
    "hooks": {
      "SessionStart": [{ "matcher": "", "hooks": [{ "type": "command", "command": "tokenflow-hook" }]}],
      "PostToolUse": [{ "matcher": ".*", "hooks": [{ "type": "command", "command": "tokenflow-hook" }]}],
      "SessionEnd": [{ "matcher": "", "hooks": [{ "type": "command", "command": "tokenflow-hook" }]}],
      "UserPromptSubmit": [{ "matcher": "", "hooks": [{ "type": "command", "command": "tokenflow-hook" }]}]
    }
  }
  ```
- `Skip` → 수동 설치 안내 화면 (복사 가능한 JSON 스니펫)

**Step 3 — Claude API 키 입력 (선택)**
- Coach / LLM better prompt 기능은 API 키 필요
- `Add later` 로 건너뛰면 해당 뷰는 read-only 배너 표시
- 입력 시 `~/.tokenflow/secret.json` 에 0600 권한으로 저장, 즉시 ping test (`messages.count_tokens` 한 번)

**Step 4 — ccprophet DB import 유도 (감지 시)**
- `~/.claude-prophet/events.duckdb` 가 존재하면 자동 감지
- "이전 ccprophet 사용 기록 발견. Import?" (세션 수, 기간 표시)
- `Import` → 백그라운드 job 실행, 진행률 바
- `Skip` → 빈 상태로 시작

**Step 5 — 완료**
- "Claude Code 를 한 번 시작하면 Live Monitor 가 활성화됩니다" 안내
- Live Monitor 로 이동

**Hook 연결 상태 pill** (topbar, §7.2): `ok` / `stale` (마지막 이벤트 >10분) / `disconnected` (hook 미설치). 상태별 배지 색: green/amber/red.

---

## 5. 데이터 모델

ccprophet 엔티티 계승 (`TokenCount`, `Money`, `Session`, `Event`, `ToolCall`, `FileAccess`, `Phase`, `PricingRate`, `CostBreakdown`, `BloatReport`, `QualitySeries`).

### 5.1 신규 엔티티

| Entity | 필드 | 용도 |
|---|---|---|
| `UserProfile` | `name`, `email`, `plan`, `avatar_initials` | 사이드바 |
| `BudgetConfig` | `monthly_limit_usd`, `alert_thresholds:[50,75,90]`, `hard_block:bool(v1 ignored)` | Settings |
| `RoutingRule` | `id`, `condition_pattern`, `target_model`, `enabled`, `priority` | Model routing |
| `NotificationPref` | `key`, `enabled`, `channel:in_app|system` | 알림 설정 |
| `WastePattern` | `id`, `kind`, `severity`, `title`, `meta`, `body_html`, `save_tokens`, `save_usd`, `sessions`, `dismissed_at`, `detected_at` | Waste Radar |
| `CoachThread` | `id`, `title`, `started_at`, `last_msg_at`, `cost_usd_total` | AI Coach |
| `CoachMessage` | `id`, `thread_id`, `role:ai|me`, `content`, `time`, `context_snapshot_json`, `cost_usd` | 대화 기록 |
| `ReplayEvent` | `t`, `query`, `tokens_in`, `tokens_out`, `model`, `cost_usd`, `waste_flag`, `waste_reason` | Replay |
| `BetterPromptSuggestion` | `source_message_id`, `suggested_text`, `est_save_tokens`, `mode:static|llm`, `cached_at` | Replay detail |
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
- 상세 이벤트 (`events`, `tool_calls`, `messages`): **180일**
- 일별 집계 (`daily_aggregate`): **무기한** (사용량 작음)
- 180일 초과 시 자동 rollup + 원본 삭제 (daily cron in serve)
- `tokenflow doctor --vacuum` 으로 수동 축소

**Pricing rates**:
- `PricingRate` 테이블은 마이그레이션 V1 에서 seed (Sonnet 4.5, 4.6, Opus 4, Haiku 4.5 등 출시 가격)
- Anthropic 가격 변경 시 `migrations/VN__pricing_update.sql` 로 새 버전 row 추가 (기존 row `effective_until` 설정)
- 사용자 override: `~/.tokenflow/pricing_overrides.json` 파일이 있으면 해당 모델/키에 한해 덮어씀
- 모든 계산은 이벤트 발생 시점의 `effective_at` rate 로 고정 (소급 변경 없음)

### 5.5 DB 마이그레이션

- V1–V5: ccprophet 복사 (import 호환)
- V6: `user_profile`, `budget_config`, `routing_rule`, `notification_pref`, `tweaks_config`
- V7: `waste_pattern`, `coach_thread`, `coach_message`
- V8: `better_prompt_suggestion`, `daily_aggregate`, 인덱스

마이그레이션은 **forward-only**. 실행 전 `~/.tokenflow/backups/events_YYYYMMDD_HHMMSS.duckdb` 자동 백업. Rollback 은 백업 복원.

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
- `Export session`: 현재 세션의 `Session + ReplayEvent[]` JSON 다운로드. schema: `tokenflow.export.v1`

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
- **SessionEnd 시점**: 해당 세션 범위에서 5종 패턴 평가 → 매칭 시 `WastePattern` insert
- **시간당 sweep**: 최근 24시간 내 세션을 크로스 세션 관점으로 재평가 (repeat-question, wrong-model 누적)
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
- 각 항목: 시작 시각, 프로젝트, 총 토큰, 총 비용, waste 아이콘
- 클릭 시 해당 세션 replay. 기본 landing = 가장 최근 세션
- 상단 필터: 프로젝트, 기간, "has waste only"
- 검색창: 쿼리 텍스트로 세션 검색

**구성** (선택된 세션):
1. 상단 요약 바
2. 스크럽 바 차트
3. 메시지 테이블
4. Detail 패널 + Better prompt

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
3. **Notifications** — 6종 토글
   - In-app: 항상 가능
   - **System notifications**: OS 권한 요청 플로우. 미권한 시 "Grant permission" 버튼. 미지원 OS 는 해당 토글 비활성
4. **Better prompt mode** — radio: static / llm. 서버 `tweaks_config` 에 영속. **Tweaks 패널의 동일 설정과 서버 값이 diff 날 때 서버를 source of truth** 로 간주 (localStorage overwrite)
5. **Claude API key** — 입력·편집·삭제·연결 테스트. 미입력 시 Coach/LLM 기능 비활성
6. **Data** (신규) — "Vacuum now" 버튼, 최근 백업 리스트, "Import from ccprophet" 버튼

**i18n 범위**:
- UI 고정 문자열: 번역됨 (`i18n/ko.json`, `i18n/en.json`)
- 번역 제외 (원문 유지): Coach LLM 응답, Waste body_html (서버 생성 시 사용자 lang 에 맞춰 템플릿 선택), 모델명, 파일명, 커맨드

### 6.7 Onboarding (신규)

§4.4 플로우. 완료 후 `user_profile.onboarded_at` 기록. 재진입 가능: Settings → "Re-run onboarding".

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
| GET | `/sessions/{sid}` | 세션 상세 |
| GET | `/sessions/{sid}/replay` | Replay 이벤트 |
| GET | `/sessions?from=&to=&project=&has_waste=&q=` | 세션 검색·필터 |
| GET | `/events/stream` | SSE (Last-Event-ID 지원) |
| GET | `/sessions/current/flow?window=60m` | SSE flow chart |

### 8.2 KPI / 분석
| Method | Path | 설명 |
|---|---|---|
| GET | `/kpi/summary?window=today\|7d\|30d` | |
| GET | `/kpi/efficiency-score?scope=session\|day&id=` | Score + 세부 패널티 |
| GET | `/analytics/daily?range=30d&project=` | stacked area |
| GET | `/analytics/heatmap?range=7d&project=` | 히트맵 |
| GET | `/analytics/cost-breakdown?range=30d&project=` | 비용 분해 |
| GET | `/analytics/top-wastes?range=30d&limit=4` | top patterns |

### 8.3 Waste
| Method | Path | 설명 |
|---|---|---|
| GET | `/wastes?status=active\|dismissed` | |
| POST | `/wastes/{id}/dismiss` | |
| POST | `/wastes/{id}/apply` | |

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
| GET/PUT | `/settings/budget` | |
| GET | `/settings/routing-rules` | |
| POST/PATCH/DELETE | `/settings/routing-rules/{id}` | |
| GET/PATCH | `/settings/notifications` | |
| GET/PATCH | `/settings/better-prompt` | `{mode:static\|llm}` |
| POST | `/settings/api-key` | |
| GET | `/settings/api-key/status` | `{configured}` |
| DELETE | `/settings/api-key` | |
| GET/PUT | `/settings/tweaks` | `TweaksConfig` server copy |

### 8.6 Projects
| Method | Path | 설명 |
|---|---|---|
| GET | `/projects?range=7d` | |
| GET | `/projects/{name}` | |
| GET | `/projects/{name}/trend?range=7d` | 스파크라인 데이터 |

### 8.7 Better prompt
| Method | Path | 설명 |
|---|---|---|
| POST | `/sessions/{sid}/messages/{idx}/better-prompt?mode=static\|llm` | |

### 8.8 Import
| Method | Path | 설명 |
|---|---|---|
| POST | `/import/ccprophet` | Body `{ path }` → job id 반환. **중복**: 동일 `session_id` 는 skip. **실패**: 라인 단위 에러 로그, 전체 중단 없음 (partial success). Rollback 은 백업 복원. |
| GET | `/import/ccprophet/status/{job_id}` | `{ state: running\|done\|failed, imported, skipped, errors, total }` |

### 8.9 Onboarding
| Method | Path | 설명 |
|---|---|---|
| GET | `/onboarding/status` | `{ hook, api_key, import_source_detected, onboarded_at }` |
| POST | `/onboarding/install-hook` | `settings.json` 수정 |
| POST | `/onboarding/complete` | `user_profile.onboarded_at` 세팅 |

### 8.10 System
| Method | Path | 설명 |
|---|---|---|
| GET | `/system/health` | DB · disk · hook 연결 · API 키 상태 |
| POST | `/system/vacuum` | 수동 retention 정리 |
| POST | `/system/ingestion-pause` | `{ paused: bool }` |
| GET | `/system/backups` | 백업 파일 리스트 |

---

## 9. 실시간 데이터 흐름

### 9.1 두 채널 수집

**A. Hook events**:
1. Claude Code → hook → stdin JSON
2. `tokenflow-hook` → `~/.tokenflow/events.ndjson` append
3. FastAPI `EventTailer` (watchdog) → DuckDB `events` + asyncio PubSub
4. SSE 브로드캐스트

**B. Transcript tail**:
1. hook 이벤트의 `transcript_path` 추출
2. `TranscriptTailer` JSONL watch
3. 신규 라인 파싱 → 토큰 + 메시지 → DuckDB

### 9.2 폴링 vs SSE
- SSE: `/events/stream`, `/sessions/current/flow`
- 폴링 5–15초: KPI, 예산, 프로젝트
- on-demand: Analytics 진입 시 fetch + TanStack Query 캐시

### 9.3 SSE 재연결 / backpressure
- 클라이언트 `EventSource` 자동 재연결. `Last-Event-ID` 헤더로 누락분 replay
- 서버: 이벤트 sequential `event_id` (BIGINT AUTO_INCREMENT). 재연결 시 >id 로 replay
- Ticker buffer: 최근 **100개 ring buffer** 유지, 연결 없으면 drop (무한 쌓이지 않음)
- Flow chart: 1분 단위 aggregated snapshot 푸시 (raw event 아님)

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
- FastAPI `127.0.0.1` 고정 바인딩
- CORS `http://localhost:*` 만
- `~/.tokenflow/secret.json` 0600
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
| API 키 파일 권한 0600 아님 | 경고 후 자동 수정 시도 | 실패 시 기능 비활성 |

### 10.5 관측성
- `~/.tokenflow/logs/` 회전 로그 (7일)
- 디버그 레벨 env `TOKENFLOW_LOG_LEVEL`

### 10.6 기타
- I18n: 한국어/영어. 날짜·숫자는 사용자 lang 에 따라 `Intl` 포맷. TZ 는 브라우저 로컬.
- 접근성: WCAG AA, 키보드 네비게이션, 주요 아이콘에 `aria-label`
- 브라우저: 최신 Chrome/Edge/Firefox/Safari (Chromium 120+)
- Telemetry: **없음**. 버전 체크도 없음. 완전 로컬.

---

## 11. 결정된 사항 (v0.2+v0.3)

1. AI Coach LLM → **Claude Sonnet 4.6**
2. API 키 저장 → 평문 `~/.tokenflow/secret.json` (0600)
3. Coach 컨텍스트 주입 → 토큰·비용·모델·waste·프로젝트명·파일 basename 만
4. Hard budget limit 차단 → v1 알림만, v2 proxy 차단
5. Better prompt → **사용자 선택** (static / llm). 기본 static
6. Hook 이벤트 schema → 공식 문서 기준, **훅에 토큰 없음** → transcript tailer 분리
7. Session Replay Playback → v1 제외
8. 다중 세션 → 각 `session_id` 분리, Live Monitor 는 최근 활성 1개만
9. 프로젝트 식별 → `cwd` git root, 아니면 cwd
10. ccprophet DB import → **v1 포함**, CLI + REST
11. Waste 탐지 스케줄링 → SessionEnd 즉시 평가 + 시간당 sweep
12. Better prompt LLM 템플릿 → §6.5 프롬프트 템플릿 고정
13. Efficiency Score 포뮬러 → §5.3 정의
14. Query Quality Score 포뮬러 → §5.3 정의
15. Opus overuse 임계값 → 월 비용 점유율 15%(권장), 25%(알림 발생)
16. DB retention → 180일 상세 + daily rollup 무기한
17. Pricing 업데이트 → 마이그레이션 VN 추가 방식, override 파일 지원
18. SSE 재연결 → `Last-Event-ID` + 100개 ring buffer
19. Import 실패 처리 → partial success, 라인 단위 에러 로그
20. System notifications → OS 권한 플로우 포함

---

## 12. v1 범위 밖 (명시적 제외)

- 팀/조직 대시보드, SSO, RBAC
- 클라우드 배포·원격 접근
- **Hard budget 차단** (v2)
- IDE 플러그인
- 모바일 레이아웃 (≥1024px 가정)
- 외부 알림 (Slack, Email)
- Data export CSV/Parquet (v1.1)
- Session Replay Playback (v1.1)
- Live Monitor 다중 세션 셀렉터 (v1.1)
- API 키 OS keyring (v1.1)
- 임베딩 기반 repeat-question (v1.1, v1 은 TF-IDF)
- 자동 Coach suggestion — 사용자 지정 질문만 응답 (v1.1)
- Pre-flight 요청 차단 proxy (v2)

---

## 13. 용어

- **세션(Session)**: Claude Code 1회 실행 단위
- **컨텍스트 포화도**: 현재 세션 토큰 / 모델 윈도우
- **Bloat ratio**: 로드된 토큰 중 미사용 비율
- **Cache hit**: Anthropic cache_read
- **Hook**: Claude Code `settings.json` event handler
- **Transcript**: 세션별 JSONL 파일 (토큰 원본)
- **Tweaks**: UI 외관 커스터마이징 패널
- **Waste pattern**: 5종 분류 (big-file-load, repeat-question, wrong-model, context-bloat, tool-loop)

---

## 14. 다음 단계

1. ✅ SPEC v0.3 — **리뷰 요청**
2. ⏸ `DESIGN.md` 작성
3. ⏸ `DESIGN.md` 승인
4. ⏸ 레포 스캐폴딩 + CI/CD
5. ⏸ 구현 착수 (뷰 단위 수직 슬라이스)
