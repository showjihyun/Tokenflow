# Token Flow — DESIGN

> 버전 0.1 · 2026-04-20 · SPEC.md v0.3 와 짝. 시각 디자인 소스 = Claude Design 핸드오프 번들의 `styles.css` + `components.jsx` + 6개 view jsx.

이 문서는 **UI 구현 시 참조하는 디자인 시스템 레퍼런스**입니다. 기능·데이터·API 는 `SPEC.md` 를 보세요.

---

## 목차

1. [디자인 철학](#1-디자인-철학)
2. [디자인 토큰](#2-디자인-토큰)
3. [테마 시스템](#3-테마-시스템-dark--light)
4. [타이포그래피](#4-타이포그래피)
5. [레이아웃 시스템](#5-레이아웃-시스템)
6. [컴포넌트 인벤토리](#6-컴포넌트-인벤토리)
7. [아이콘 시스템](#7-아이콘-시스템)
8. [차트 & 데이터 시각화](#8-차트--데이터-시각화)
9. [모션 & 상태 전이](#9-모션--상태-전이)
10. [스크린 템플릿](#10-스크린-템플릿-6-views--onboarding)
11. [Tweaks 시스템](#11-tweaks-시스템)
12. [Empty / Loading / Error 상태](#12-empty--loading--error-상태)
13. [접근성](#13-접근성)
14. [반응형](#14-반응형)
15. [구현 체크리스트](#15-구현-체크리스트)

---

## 1. 디자인 철학

**톤**: 데이터 대시보드. Linear × Grafana 혼합. **정보 밀도가 높지만 차갑지 않다** — warm amber 액센트로 따뜻함을 준다.

**3가지 원칙**:
1. **Dark-first** — 다크를 기본 톤으로 설계. 라이트는 같은 hue, lightness 만 반전.
2. **OKLCH 균일 채도** — 모든 액센트는 동일 chroma(~0.15)·lightness(~0.76)에서 hue 만 바꿔서 시지각 균형.
3. **Monospace 로 숫자 읽게 하기** — 토큰·비용·퍼센트는 항상 `Geist Mono` + `tabular-nums`.

**참고 제품 결**: Linear (사이드바·토픽바·뱃지), Vercel Analytics (KPI 카드·스파크라인), Grafana (히트맵·에어리어 차트), Raycast (Tweaks 패널·키보드 감각).

**Claude/Anthropic 브랜드 회피**: Token Flow 는 Anthropic 비공식 도구이므로 Claude 로고·브랜드 컬러 재현 안 함. amber(`oklch(0.76 0.15 62)`) 가 메인 액센트 — Claude 공식 톤과 구분.

---

## 2. 디자인 토큰

모든 토큰은 CSS Variables 로 선언. React 에서 `var(--token)` 또는 `style={{ '--token': value }}` 로 참조.

### 2.1 Surface (배경)

| 토큰 | Dark (기본) | Light | 용도 |
|---|---|---|---|
| `--bg-0` | `oklch(0.145 0.008 260)` | `oklch(0.985 0.003 260)` | 페이지 최하단 / main 영역 |
| `--bg-1` | `oklch(0.175 0.010 260)` | `oklch(0.965 0.004 260)` | 사이드바·topbar·카드 기본 |
| `--bg-2` | `oklch(0.205 0.012 260)` | `oklch(0.945 0.005 260)` | 카드 내부 입력 영역, active 상태 |
| `--bg-3` | `oklch(0.245 0.014 260)` | `oklch(0.920 0.006 260)` | track (progress, scrollbar) |
| `--bg-hover` | `oklch(0.225 0.014 260)` | `oklch(0.935 0.006 260)` | hover 상태 |

### 2.2 Border

| 토큰 | Dark | Light | 용도 |
|---|---|---|---|
| `--border-subtle` | `oklch(0.28 0.014 260)` | `oklch(0.90 0.006 260)` | 카드 내부 구분선, 테이블 row |
| `--border-default` | `oklch(0.34 0.016 260)` | `oklch(0.84 0.008 260)` | 버튼, 입력 outline |
| `--border-strong` | `oklch(0.44 0.018 260)` | `oklch(0.72 0.010 260)` | hover/focus 강조 |

### 2.3 Text (Foreground)

| 토큰 | Dark | Light | 용도 |
|---|---|---|---|
| `--fg-0` | `oklch(0.97 0.005 260)` | `oklch(0.20 0.012 260)` | 제목, 강조 숫자 |
| `--fg-1` | `oklch(0.82 0.010 260)` | `oklch(0.38 0.012 260)` | 본문 |
| `--fg-2` | `oklch(0.62 0.012 260)` | `oklch(0.55 0.012 260)` | 보조 라벨 |
| `--fg-3` | `oklch(0.48 0.012 260)` | `oklch(0.65 0.012 260)` | 가장 약한 힌트, 단위 |

### 2.4 Accent — 5개 hue, 3 variant

**규칙**: 모든 accent 는 주 계열 `L=0.76 C=0.15–0.17`, dark variant `L=0.56–0.58`, wash variant `L=0.30` (dark) / `L=0.94` (light). Hue 만 변경.

| 토큰 | 주 (L=0.76) | dark (L=0.56) | wash (L=0.30 dark / 0.94 light) | 의미론 |
|---|---|---|---|---|
| `--amber` | `oklch(0.76 0.15 62)` | `--amber-d` | `--amber-w` | 메인 브랜드·warn·Sonnet |
| `--green` | `oklch(0.76 0.15 158)` | `--green-d` | `--green-w` | success·down-trend(↓비용) |
| `--red` | `oklch(0.72 0.17 28)` | `--red-d` | `--red-w` | error·high severity·up-trend(↑비용) |
| `--blue` | `oklch(0.74 0.15 240)` | `--blue-d` | `--blue-w` | info·Haiku·input tokens |
| `--violet` | `oklch(0.72 0.17 300)` | `--violet-d` | `--violet-w` | Opus·accent 변주 |

**Model 전용 alias**:
- `--m-opus: var(--violet)`
- `--m-sonnet: var(--amber)`
- `--m-haiku: var(--blue)`

**Trend 방향 관례** (비용 맥락):
- 비용·사용량 **상승** → `--red` (부정 신호)
- 비용·사용량 **하락** → `--green` (긍정 신호)
- KPI delta 에서 `.up` = red, `.down` = green

### 2.5 Radii

| 토큰 | 값 | 용도 |
|---|---|---|
| `--r-sm` | 6px | 버튼·작은 뱃지·nav-item |
| `--r-md` | 10px | 카드·KPI·입력 |
| `--r-lg` | 14px | 오버레이·summary strip |
| `--r-xl` | 20px | 모달·큰 섹션 |

### 2.6 Spacing scale (4px 베이스)

| 토큰 | 값 |
|---|---|
| `--s-1` | 4px |
| `--s-2` | 8px |
| `--s-3` | 12px |
| `--s-4` | 16px |
| `--s-5` | 20px |
| `--s-6` | 24px |
| `--s-8` | 32px |
| `--s-10` | 40px |
| `--s-12` | 48px |

**페이지 기본 패딩**: `20px 24px 48px` (roomy=28/32/56, compact=12/14/32).

### 2.7 Shadow

| 용도 | 값 |
|---|---|
| Tweaks / 모달 | `0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.02) inset` |
| Live dot glow | `0 0 8px <accent>` |
| Brand mark inset | `0 0 0 1px rgba(255,255,255,0.08) inset` |

---

## 3. 테마 시스템 (Dark / Light)

- `<html data-theme="dark">` 이 기본. `data-theme="light"` 로 전환 → 라이트 톤으로 변수 재정의 (§2).
- Hue 는 그대로, **lightness 만 반전**. 브랜드·액센트 hue 유지.
- 전환: `React.useEffect(() => { document.documentElement.dataset.theme = tweaks.theme; }, [tweaks.theme])`
- **OS 기본 respect**: 최초 방문 시 `prefers-color-scheme` 감지, 이후 사용자 선택 우선.

---

## 4. 타이포그래피

### 4.1 Font stack

```css
--font-sans: "Geist", "Pretendard", "Noto Sans KR", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-mono: "Geist Mono", "JetBrains Mono", "SF Mono", Menlo, monospace;
```

**폰트 로드**: Google Fonts (Geist + Geist Mono) + Noto Sans KR 을 `<link rel="preconnect">` 로 최적화. `font-display: swap`. 자체 호스팅은 v1.1.

**한국어 fallback**: Geist 는 한글 미포함 → Noto Sans KR 로 자동 대체 + 브라우저의 Pretendard 있으면 우선. CJK 글자 높이 일치를 위해 `line-height: 1.5`.

### 4.2 Scale

| 용도 | size | weight | letter-spacing | class/요소 |
|---|---|---|---|---|
| Body | 13.5px | 400 | -0.005em | `body` |
| Page title (h1) | 22px | 600 | -0.02em | `.page-title` |
| Section / waste title | 14px | 600 | -0.01em | `.waste-title` |
| Card title | 12.5px | 500 | +0.01em | `.card-title` |
| KPI value | 26px | 600 | -0.02em | `.kpi-value` (mono) |
| KPI label | 11px | 500 | +0.06em UPPER | `.kpi-label` |
| Section label | 10.5px | 500 | +0.07em UPPER | `.ctx-label`, `.nav-group-label` |
| Tabular numbers | any | any | — | `.tnum` (feature `tnum 1`) |
| Mono | any | any | — | `.mono` (feature `tnum 1, ss01 1`) |

### 4.3 Density 토글 영향

- `compact`: body 12.5px, kpi-value 22px, page padding 12/14
- `normal`: body 13.5px, kpi-value 26px, page padding 20/24
- `roomy`: body 14.5px, kpi-value 26px, page padding 28/32

---

## 5. 레이아웃 시스템

### 5.1 앱 셸 (전역 grid)

```
┌─────────┬──────────────────────────────────────┐
│         │  topbar (48px)                       │
│ sidebar ├──────────────────────────────────────┤
│ (240px) │                                      │
│         │  main (overflow: auto)               │
│         │                                      │
└─────────┴──────────────────────────────────────┘
```

CSS:
```css
.app {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-rows: 48px 1fr;
  height: 100vh;
}
```

**Sidebar 위치 토글** (`data-sidebar="right"`): grid-template-columns 순서 반전.

### 5.2 페이지 그리드 (row 시스템)

`.row` 계열 helper:

| 클래스 | grid-template-columns | 용도 |
|---|---|---|
| `.row` | `1fr` | 단일 카드 줄 |
| `.row-2` | `2fr 1fr` | 2:1 분할 |
| `.row-21` | `2fr 1fr` | 동일 (명시적) |
| `.row-12` | `1fr 2fr` | 1:2 분할 |
| `.row-3` | `1fr 1fr 1fr` | 3등분 |

gap: 12px. margin-bottom: 12px.

### 5.3 최대 너비

`.page` 는 `max-width: 1600px; margin: 0 auto`. 1920px+ 모니터에서 양 사이드 공백. 1024–1600px 에서 full width.

### 5.4 헤더 패턴

모든 뷰 상단:
```tsx
<div className="page-header">
  <div>
    <h1 className="page-title">Live Monitor</h1>
    <p className="page-sub">실시간 세션 <span className="mono dim">· sess_8f2a9c · commerce-admin</span></p>
  </div>
  <div className="hstack">{/* action buttons */}</div>
</div>
```

---

## 6. 컴포넌트 인벤토리

React 구현 시 `frontend/src/components/` 하위로 분리. **모든 컴포넌트는 단일 책임, prop-driven**.

### 6.1 Foundation

| 컴포넌트 | 파일 | 역할 |
|---|---|---|
| `<Icon name size stroke />` | `Icon.tsx` | Lucide-style SVG 44종 (§7) |
| `<Sparkline data color height width fill />` | `Sparkline.tsx` | KPI 카드 스파크라인 |
| `<Ring value max size stroke color track />` | `Ring.tsx` | 컨텍스트 포화도 게이지 |
| `<AreaChart series width height labels />` | `AreaChart.tsx` | stacked area |
| `<HBar value max color height />` | `HBar.tsx` | 인라인 progress bar |
| `<Heatmap data color />` | `Heatmap.tsx` | 7×24 히트맵 |
| `<Donut data size stroke />` | `Donut.tsx` | Waste sources |

### 6.2 Layout

| 컴포넌트 | 역할 |
|---|---|
| `<AppShell>` | sidebar + topbar + main grid |
| `<Sidebar>` | brand + nav + budget mini + user card |
| `<Topbar>` | breadcrumbs + range picker + pills + icon buttons |
| `<Card>`, `<CardHeader>`, `<CardBody>`, `<CardFooter>` | 카드 컨테이너 |
| `<Row2>`, `<Row3>`, `<Row21>`, `<Row12>` | grid helper |

### 6.3 Data display

| 컴포넌트 | 역할 |
|---|---|
| `<KPI label value unit delta deltaDir sub accent spark />` | 4개 KPI 카드 슬롯 |
| `<Badge kind>` | `opus / sonnet / haiku / good / warn / danger / neutral` |
| `<ModelBadge model>` | Badge + dot 조합 |
| `<LivePill>` | streaming/connected 원형 pill |
| `<Table columns data />` | 프로젝트 테이블, replay table |
| `<Counter label value color />` | Waste Radar summary strip |

### 6.4 Controls

| 컴포넌트 | 역할 |
|---|---|
| `<Button variant size>` | `primary / default / ghost`, `sm / md` |
| `<IconButton>` | 30×30 square icon |
| `<Toggle on onChange>` | 32×18 switch |
| `<RangePicker options value>` | 1H/Today/7D segmented |
| `<RadioGroup>` | Better prompt mode |
| `<Input prefix suffix>` | `$`, text input |
| `<Textarea>` | 채팅 composer 전용 |

### 6.5 Interactive

| 컴포넌트 | 역할 |
|---|---|
| `<TweaksPanel open onClose />` | 우하단 fixed 300px 슬라이드 |
| `<TweakGroup label options value onChange />` | segmented control |
| `<Notification>` | Bell 드롭다운 아이템 |
| `<WasteCard pattern onApply onDismiss>` | severity 별 스타일 |
| `<ChatMessage role content time>` | ai/me 버블 |
| `<CoachChip>` | 제안 칩 (circular pill) |
| `<Observation color text>` | Coach context 좌측 컬러바 |
| `<Stepper steps current>` | Onboarding 전용 |

### 6.6 상태 컴포넌트

| 컴포넌트 | 역할 |
|---|---|
| `<EmptyState icon title desc cta />` | 뷰별 빈 상태 |
| `<ErrorBanner kind message action />` | API 401, 429 등 |
| `<LoadingSkeleton variant />` | KPI / card / table 플레이스홀더 |
| `<ConnectionPill status>` | `ok / stale / disconnected` |

---

## 7. 아이콘 시스템

**라이브러리**: Lucide React (디자인의 custom SVG 와 동일 스타일 — stroke 1.6px, rounded join/cap).

**사용법**: `<Icon name="chart" size={15} stroke={1.6} />`

**매핑 (디자인 → lucide-react)**:

| design name | lucide-react | 용도 |
|---|---|---|
| `monitor` | `Monitor` | Live Monitor nav |
| `chart` | `LineChart` | Analytics nav |
| `radar` | `Radar` | Waste Radar nav |
| `coach` | `MessageSquare` | AI Coach nav |
| `timeline` | `GitBranch` / `Waypoints` | Replay nav |
| `settings` | `Settings` | Settings nav |
| `search` | `Search` | topbar |
| `bell` | `Bell` | topbar |
| `help` | `HelpCircle` | Docs |
| `zap` | `Zap` | Live Activity |
| `trending` | `TrendingUp` | Budget |
| `sparkle` | `Sparkles` | Optimization tips, Better prompt |
| `file` | `FileText` | Export session |
| `repeat` | `Repeat` | repeat-question waste |
| `cpu` | `Cpu` | Context window, Cost breakdown |
| `package` | `Package` | Model dist, projects |
| `plus` | `Plus` | Add rule, new thread |
| `check` | `Check` | Apply fix |
| `x` | `X` | Dismiss, close |
| `arrow` | `ArrowRight` | row action |
| `up/down` | `ArrowUp/ArrowDown` | delta |
| `alert` | `AlertTriangle` | waste severity |
| `play/pause` | `Play/Pause` | Replay |
| `tweak` | `SlidersHorizontal` | Tweaks toggle |
| `send` | `Send` | Coach composer |
| `logout` | `LogOut` | sidebar footer |
| `user` | `User` | profile |
| `light/dark` | `Sun/Moon` | theme toggle |

**규격**: nav 15px, topbar 15px, card title 13px, action button 12–13px, KPI 11px.

---

## 8. 차트 & 데이터 시각화

**원칙**: 외부 의존성 없이 **직접 SVG**. Recharts/Chart.js 회피 (번들 사이즈·스타일 종속 억제).

### 8.1 Sparkline

- 크기: 기본 `width=80, height=28`. KPI 카드 우하단 absolute positioning, `opacity: 0.6`.
- 선: 1.5px, round join/cap.
- 채움: `fill-opacity: 0.15` (bold 톤에서는 0.85, minimal 0.5, outlined 0).

### 8.2 Stacked Area

- 크기: Live `800×220`, Analytics `820×260`.
- Padding: `padX=40, padY=20` (y-axis 라벨 공간).
- y-axis: 4 tick, mono label 10px, `color: --fg-3`.
- x-axis: 라벨은 series 의 `labels` prop.
- 각 series `fill-opacity: 0.75`.

### 8.3 Ring Gauge

- 크기: Live `118×118 stroke=10`, Analytics `120×120 stroke=12`.
- Track: `--bg-3`.
- Fill: 임계값 기반 색상 — `>0.85=red, >0.65=amber, else=green` (context window 의 경우).
- 중앙 텍스트: `.mono` 22px + uppercase 10px sub.
- `stroke-linecap: round`, `-90° rotate`.

### 8.4 Heatmap

- Grid: `grid-template-columns: 28px repeat(24, 1fr)`, gap 2px.
- Row: 7 (Mon–Sun), Col: 24 hours.
- Cell: `aspect-ratio: 1`, radius 2px.
- 색상: `color-mix(in oklch, <accent> <v*100>%, var(--bg-2))`. v≤0.05 이면 플레인 bg.

### 8.5 Donut (Waste sources)

- `160×160 stroke=22`.
- 5 segment. `stroke-dasharray` 로 각 조각 길이 계산.
- 중앙: 총 waste % (`.mono 22px`) + UPPERCASE label.

### 8.6 HBar (inline progress)

- height 6px 기본, radius `height/2`.
- Track: `--bg-3`.
- Fill: value 기반 색상 threshold.

### 8.7 Replay Track

- Bar per message, `flex: 1` 로 균등 분할, gap 2px.
- height: `(tokens / max) * 100%`.
- 색상: `waste=red, opus=violet, sonnet=amber, haiku=blue`.
- 비활성 `opacity: 0.55`, 활성 `opacity: 1` + `border-top: 2px solid <color>`.

### 8.8 차트 스타일 Tweak

- `data-chart="bold"`: fill opacity 0.85
- `data-chart="minimal"`: fill opacity 0.5
- `data-chart="outlined"`: fill opacity 0, stroke 2px

---

## 9. 모션 & 상태 전이

**원칙**: 대부분 12–15ms 의 hover/active 전이. 큰 모션은 최소화 (데이터 대시보드는 고요함이 미덕).

| 대상 | 속성 | duration | easing |
|---|---|---|---|
| nav-item / button hover | `background`, `color`, `border-color` | 120ms | default |
| tweaks 패널 open | `display: flex` (즉시) | — | — |
| live-dot | `opacity` + `scale` | 1600ms | ease-in-out infinite (pulse) |
| Toggle switch | `left`, `background` | 150ms | default |
| replay-row active | `background`, `border-left` | 120ms | default |
| SSE 새 ticker row | fade-in (0 → 1 opacity) | 200ms | default |

**Pulse 정의**:
```css
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
```

**KPI 숫자 증가 애니메이션** (Live Monitor 의 `tokens` 실시간): 값 변화 시 150ms 동안 CSS `transition` 없이 JS `requestAnimationFrame` 로 interpolate.

**Reduced motion**: `@media (prefers-reduced-motion: reduce)` 에서 pulse·fade 제거.

---

## 10. 스크린 템플릿 (6 views + Onboarding)

각 뷰의 **레이아웃 골격**. 데이터·로직은 SPEC §6 참조.

### 10.1 Live Monitor

```
┌─ page-header ────────────────────────┐
│ h1 "Live Monitor"    [Pause][Export] │
├──────────────────────────────────────┤
│ kpi-grid (4 cols)                    │
│ [Tokens][Today][Eff][Waste]          │
├────────────────────┬─────────────────┤
│ row-21             │                 │
│ Area chart 60m     │  Context Ring   │
│                    │  + pro-tip      │
├──────────┬─────────┴─────────────────┤
│ row-3                                │
│ [Model dist][Budget][Activity ticker]│
├──────────────────────────────────────┤
│ Projects table (this week)           │
└──────────────────────────────────────┘
```

Topbar range picker: `Live | 1H | Today | 7D` (Live 탭만 이 뷰에 노출).

### 10.2 Usage Analytics

```
┌─ page-header: h1 + RangePicker(24H/7D/30D/90D/All) + Project filter
├─ kpi-grid (4)
├─ row-21: Daily stacked area | Cost breakdown ring
├─ row-12: Top waste patterns | Activity Heatmap
```

### 10.3 Waste Radar

```
┌─ page-header: h1 + [View dismissed][Apply all]
├─ summary-strip (gradient amber-w → bg-1)
│  [Potential savings $X.XX / X tokens] [High 2][Med 2][Low 1]
├─ row-21:
│   left: waste-card list (severity-colored)
│   right: [Waste Sources donut] + [Optimization tips]
```

### 10.4 AI Coach

```
┌─ page-header: h1 + (this thread cost)
├─ coach-wrap: 3-col grid 280px | 1fr | 300px
│  ┌ Threads list ┬ Chat ┬ Context panel
│  │              │ (messages + composer + chips)
│  │              │                 │ Current session
│  │              │                 │ Observations
│  │              │                 │ Suggested next q
│  │              │                 │ Quality Score A-D
```

Chat height: `calc(100vh - 48px - 48px - 16px - page-header)`.

### 10.5 Session Replay

```
┌─ session-picker (slim sidebar 220px) ┬ replay-main ┬ detail 360px
│                                      │
│ (session list + search + filter)     │ ┌ scrub chart
│                                      │ │ (bar per msg, model colors)
│                                      │ ├ timeline list
│                                      │ │ (time | query | tokens | cost)
│                                      │ │
│                                      │ └ ...
```

### 10.6 Settings

```
max-width: 900px
├─ Card "Monthly budget" (2-col: Hard limit + Alert thresholds)
├─ Card "Model routing rules" (rule rows + Add)
├─ Card "Notifications" (6 toggles)
├─ Card "Better prompt mode" (radio: static | llm)
├─ Card "Claude API key" (input + test button + delete)
├─ Card "Data" (vacuum + backups + import)
```

### 10.7 Onboarding (신규)

```
full-screen overlay (bg-0)
├─ centered container 560px
│  ├─ brand-mark large + "Welcome to Token Flow"
│  ├─ <Stepper> 5 dots
│  ├─ active step panel:
│  │  Step 1: hook 감지 결과 + [Install hook]
│  │  Step 2: hook 설치 확인
│  │  Step 3: API key 입력 (optional)
│  │  Step 4: ccprophet import 감지 시 prompt
│  │  Step 5: "You're all set" + [Go to Live Monitor]
│  └─ [Back][Next|Skip]
```

### 10.8 Tweaks 패널 (우하단 fixed)

```
position: fixed; right: 20px; bottom: 20px;
width: 300px; max-height: 70vh;
radius: var(--r-lg);
shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.02) inset;

└─ head: "Tweaks" UPPERCASE + [X]
└─ body (gap 16px):
   - Theme (dark/light)
   - Density (compact/normal/roomy)
   - Chart style (bold/minimal/outlined)
   - Sidebar position (left/right)
   - Alert aggressiveness (quiet/balanced/loud)
   - UI language (ko/en)
   - Better prompt mode (static/llm)  ← 신규
```

---

## 11. Tweaks 시스템

Tweaks 는 UI 외관 + 일부 동작의 사용자 커스터마이징. `<html>` data attribute + CSS selector 로 적용.

### 11.1 Tweak 목록

| key | options | 영향 |
|---|---|---|
| `theme` | `dark` / `light` | `<html data-theme>` → §2 변수 재정의 |
| `density` | `compact` / `normal` / `roomy` | `.app[data-density]` → font size + padding |
| `chartStyle` | `bold` / `minimal` / `outlined` | `.app[data-chart]` → fill opacity, stroke width |
| `sidebarPos` | `left` / `right` | `.app[data-sidebar]` → grid 순서 반전 |
| `alertLevel` | `quiet` / `balanced` / `loud` | 알림 노출 빈도·색상 강도 |
| `lang` | `ko` / `en` | 문자열 i18n |
| `better_prompt_mode` | `static` / `llm` | Better prompt 기본 모드 |

### 11.2 Persistence

- `theme, density, chartStyle, sidebarPos, alertLevel, lang`: localStorage
- `better_prompt_mode`: **server (tweaks_config) + localStorage**. 충돌 시 server 우선 (SPEC §6.6)

---

## 12. Empty / Loading / Error 상태

### 12.1 Empty states (뷰별)

| 뷰 | 조건 | 표시 |
|---|---|---|
| Live Monitor | 현재 세션 없음 | 아이콘 `monitor` + "Waiting for first event…" + 힌트 "Start Claude Code" |
| Live Monitor | 주간 데이터 없음 | "Last 7 days empty" + [Import past data] CTA |
| Analytics | 선택 range 데이터 없음 | "No usage data in this range" + [Switch range][Import] |
| Waste Radar | waste 없음 | 🎉 "No waste patterns detected" + "Explore optimization tips" |
| AI Coach | API 키 없음 | 배너 + [Add key in Settings] |
| AI Coach | 스레드 없음 | welcome + 제안 칩 5개 (클릭 시 첫 스레드 생성) |
| Session Replay | 세션 없음 | "No sessions yet. Start Claude Code to record your first." |
| Settings → API key | 미등록 | input + "Get a key at console.anthropic.com" 링크 |

### 12.2 Loading

- **초기 마운트**: `<LoadingSkeleton variant="kpi|card|table">` — `--bg-2` 배경 + 미묘한 shimmer.
- **SSE 연결 중**: 토픽바 pill `connecting…` amber pulse.
- **Coach 응답 대기**: 마지막 ai 버블에 3-dot `...` 애니메이션.
- **Better prompt LLM 호출**: 해당 카드 위 overlay spinner + "Rewriting…"

### 12.3 Error

에러 종류별 UI (SPEC §10.4 taxonomy):

| 종류 | UI 컴포넌트 | 위치 |
|---|---|---|
| API 401 | `<ErrorBanner kind="auth">` "API key rejected" + CTA | Coach header, Settings |
| 429 | inline `<ErrorBanner kind="rate">` "Retrying in Ns" | Coach composer |
| 5xx | `<ErrorBanner kind="server">` "Anthropic down" | Coach header |
| hook disconnected | topbar pill red + 배너 | 전체 앱 |
| DB 락 | topbar 배너 + 자동 retry | 전체 앱 |
| disk full | topbar 배너 "Disk almost full" + [Vacuum now] | 전체 앱 |

---

## 13. 접근성

- **WCAG AA 대비**: `--fg-0` / `--bg-1` ≥ 12:1 (dark), `--fg-1` / `--bg-1` ≥ 7:1. 액센트 텍스트는 wash 배경 위에서만.
- **키보드**:
  - `Tab` — 포커스 이동 (사이드바 → topbar → main)
  - `Enter` — Coach composer 전송
  - `Shift+Enter` — 줄바꿈
  - `Esc` — Tweaks 닫기
  - `g l / g a / g w / g c / g r / g s` — 뷰 이동 (v1.1 chord)
- **Focus ring**: 기본 browser outline 2px dashed `--amber`.
- **Aria**:
  - nav-item `role="navigation"`, `aria-current="page"` when active
  - icon-only 버튼 모두 `aria-label`
  - 차트 SVG `<title>` + `<desc>` 주입
  - live-pill `aria-live="polite"`

- **Reduced motion**: `@media (prefers-reduced-motion: reduce)` — pulse, fade 비활성
- **Screen reader**: SSE ticker 는 `aria-atomic="false" aria-relevant="additions"`

---

## 14. 반응형

**타겟 뷰포트**:
- 주 타겟: **1440×900** (노트북 기본)
- 최소 지원: **1024×768** (iPad/작은 노트북)
- 최대: `max-width: 1600px` 이후 중앙 정렬

**브레이크포인트**:
- `≥1280px`: 모든 row 레이아웃 원본 유지
- `1024–1279px`: row-21/12 → 단일 열 스택, coach 3-col → 2-col (context 패널 하단 이동)
- `<1024px`: **지원 안 함** (v1 기준, "데스크톱 전용" 배너)

**사이드바 축소**: 사용 안 함. 240px 고정. (축소 버전은 v1.1)

---

## 15. 구현 체크리스트

### 15.1 Foundation (1차)

- [ ] `styles/tokens.css` — 전체 CSS variables (§2)
- [ ] `styles/base.css` — body, scrollbar, 기본 레이아웃
- [ ] `styles/theme.css` — dark/light data-attr 기반 오버라이드
- [ ] Google Fonts preconnect + import
- [ ] `<AppShell>` grid layout

### 15.2 공통 컴포넌트 (2차)

- [ ] `<Icon>`, `<Sparkline>`, `<Ring>`, `<AreaChart>`, `<HBar>`, `<Heatmap>`, `<Donut>`
- [ ] `<Card>` family, `<Row>` helpers
- [ ] `<Button>`, `<IconButton>`, `<Toggle>`, `<RangePicker>`, `<RadioGroup>`
- [ ] `<Badge>`, `<ModelBadge>`, `<LivePill>`
- [ ] `<Table>`, `<EmptyState>`, `<LoadingSkeleton>`, `<ErrorBanner>`

### 15.3 Shell (3차)

- [ ] `<Sidebar>` (nav + budget mini + user card)
- [ ] `<Topbar>` (breadcrumbs + pill + icon buttons)
- [ ] `<TweaksPanel>` + `<TweakGroup>`
- [ ] Zustand store: `tweaksStore`, `sessionStore`, `notificationStore`

### 15.4 화면 (4차)

각 뷰는 독립적으로 수직 슬라이스 구현 (SPEC §14 순서):
- [ ] LiveMonitor (기본 랜딩)
- [ ] UsageAnalytics
- [ ] WasteRadar
- [ ] SessionReplay (+ session picker)
- [ ] AICoach (+ API key 배너)
- [ ] Settings (+ 모든 카드)
- [ ] Onboarding (5-step stepper)

### 15.5 상태 (5차)

- [ ] Empty / Loading / Error 전체 경로 구현
- [ ] `prefers-color-scheme` 초기 감지
- [ ] `prefers-reduced-motion` 반영
- [ ] 키보드 네비게이션 QA (WCAG AA)
- [ ] SSE 재연결 + Last-Event-ID UI

### 15.6 Polish (6차)

- [ ] 모든 차트의 bold/minimal/outlined 프리셋 확인
- [ ] density 3단계 전환 시 깨짐 없는지
- [ ] sidebarPos right 전환 확인
- [ ] ko/en 문자열 완성
- [ ] Lighthouse A11y ≥95
- [ ] 1024/1440/1920 해상도 시각 QA

---

## 부록 A — 원본 디자인 파일 참조

디자인 소스 (참고용, 커밋 안 함):
- `C:\Users\BV-CHOIJIHYUN\AppData\Local\Temp\tf-design\new-project\project\styles.css` — 최종 스타일시트
- `C:\...\components.jsx` — 차트 및 유틸 (Icon, Sparkline, Ring, AreaChart, HBar, Heatmap)
- `C:\...\TokenFlow.html` — 앱 셸 + App 컴포넌트
- `C:\...\views\live-monitor.jsx` — Live Monitor 완전한 JSX
- `C:\...\views\analytics-waste.jsx` — Analytics + Waste Radar
- `C:\...\views\coach-replay-settings.jsx` — Coach + Replay + Settings
- `C:\...\data.js` — mock data (entity shape 참고)

React 18 + Babel standalone 프로토타입이므로 **레이아웃·스타일은 픽셀 단위 재현, 내부 구조는 TS 로 재설계**.
