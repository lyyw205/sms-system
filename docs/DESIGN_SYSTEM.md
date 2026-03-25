# SMS 예약 시스템 — Design System

> Toss Invest 디자인 시스템 기반 + Flowbite React 컴포넌트 라이브러리
> 최종 업데이트: 2026-03-24

---

## 1. 디자인 원칙

| 원칙 | 설명 |
|------|------|
| **Clarity** | 정보 밀도가 높은 운영 도구이므로 가독성 최우선. 불필요한 장식 제거 |
| **Consistency** | 동일 컨텍스트에는 동일 컴포넌트/색상/간격 사용 |
| **Softness** | 둥근 모서리(`rounded-2xl`), 미세한 그림자, 부드러운 색상 전환 |
| **Density** | 데이터 테이블과 폼이 핵심 — 적절한 패딩과 간격으로 밀도 확보 |

---

## 2. 색상 팔레트

### 2.1 Primary & Semantic Colors

| 토큰 | HEX | 용도 | CSS Variable |
|------|-----|------|-------------|
| **Primary Blue** | `#3182F6` | 주요 액션, 활성 상태, 링크, CTA | `--color-toss-blue` |
| **Blue Light** | `#E8F3FF` | Blue 배경 (뱃지, 활성 사이드바, 호버) | `--color-toss-blue-light` |
| **Blue Hover** | `#1B64DA` | 버튼 호버 상태 | — |
| **Success** | `#00C9A7` | 확정, 성공, 완료 | `--color-toss-success` |
| **Success BG** | `#E8FAF5` | Success 뱃지 배경 | — |
| **Warning** | `#FF9F00` | 대기, 주의 | — |
| **Warning BG** | `#FFF5E6` | Warning 뱃지 배경 | — |
| **Error** | `#F04452` | 취소, 삭제, 에러, 양수(금액) | `--color-toss-positive` |
| **Error BG** | `#FFEBEE` | Error 뱃지 배경 | — |

### 2.2 Text Colors

| 토큰 | HEX | Light | Dark | 용도 |
|------|-----|-------|------|------|
| **Text Primary** | `#191F28` | `text-[#191F28]` | `dark:text-white` | 제목, 본문 주요 텍스트 |
| **Text Secondary** | `#4E5968` | `text-[#4E5968]` | `dark:text-gray-300` | 보조 본문, 테이블 셀 |
| **Text Tertiary** | `#8B95A1` | `text-[#8B95A1]` | `dark:text-gray-500` | 라벨, stat-label, 사이드바 비활성 |
| **Text Disabled** | `#B0B8C1` | `text-[#B0B8C1]` | `dark:text-gray-600` | 플레이스홀더, 비활성 아이콘, 빈 상태 |

### 2.3 Surface & Background

| 토큰 | HEX | Light | Dark | 용도 |
|------|-----|-------|------|------|
| **Page BG** | `#FAFBFC` | `bg-[#FAFBFC]` | `dark:bg-[#17171C]` | 앱 전체 배경 |
| **Card BG** | `#FFFFFF` | `bg-white` | `dark:bg-[#1E1E24]` | 카드, 모달, 테이블 |
| **Surface** | `#F8F9FA` | `bg-[#F8F9FA]` | `dark:bg-[#1E1E24]` | 테이블 헤더, stat-card 내부 |
| **Hover BG** | `#F2F4F6` | `bg-[#F2F4F6]` | `dark:bg-[#2C2C34]` | 호버, 필터 바, 드래그 카드 |
| **Active Hover** | `#E5E8EB` | `bg-[#E5E8EB]` | `dark:bg-[#35353E]` | 강한 호버 (버튼 light, guest-card) |

### 2.4 Border

| 토큰 | HEX | Light | Dark | 용도 |
|------|-----|-------|------|------|
| **Border Default** | `#F2F4F6` | `border-[#F2F4F6]` | `dark:border-gray-800` | 카드, 구분선, 기본 테두리 |
| **Border Input** | `#E5E8EB` | `border-[#E5E8EB]` | `dark:border-gray-600` | 입력 필드, room-cell 점선 |
| **Divider** | `#F2F4F6` | — | `dark:bg-gray-800` | 사이드바 그룹 구분 (1px) |

---

## 3. 타이포그래피

### 3.1 Font Stack

```css
--font-sans: "Pretendard Variable", Pretendard, -apple-system,
  BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
--font-mono: "SF Mono", "Fira Code", "Fira Mono", "Roboto Mono", monospace;
```

### 3.2 Type Scale

| Class | Size | Line Height | Weight | 용도 |
|-------|------|-------------|--------|------|
| `text-display` | 28px / 1.75rem | 36px | bold | Hero 숫자, 대시보드 대형 값 |
| `text-title` | 22px / 1.375rem | 30px | bold | `.page-title`, `.stat-value` |
| `text-heading` | 18px / 1.125rem | 26px | semibold | 섹션 제목, 모달 제목 |
| `text-subheading` | 15px / 0.9375rem | 22px | semibold | 카드 제목, 네비 브랜드, 헤더 |
| `text-body` | 14px / 0.875rem | 20px | regular | **본문 기본값**, 테이블 셀, 버튼 |
| `text-label` | 13px / 0.8125rem | 18px | medium | 서브타이틀, 보조 본문, 사용자 이름 |
| `text-caption` | 12px / 0.75rem | 16px | medium | 테이블 헤더, 캡션, 도움말, 뱃지 |
| `text-overline` | 11px / 0.6875rem | 16px | semibold | 사이드바 그룹 라벨 |
| `text-tiny` | 10px / 0.625rem | 14px | regular | 타임스탬프, 인라인 뱃지 |

### 3.3 숫자 표시

- 숫자에는 반드시 `tabular-nums` 적용 (고정폭)
- 단위: `<span className="ml-0.5 text-label font-normal text-[#B0B8C1]">건</span>`
- 추적번호: `tracking-[-0.02em]` (page-title)

---

## 4. 레이아웃

### 4.1 앱 구조

```
┌──────────────────────────────────────────────────────┐
│ Sidebar (w-60 / collapsed: w-[68px])                 │
│ ┌────┬───────────────────────────────────────────┐   │
│ │Logo│  Header (h-14, sticky, backdrop-blur)     │   │
│ │    ├───────────────────────────────────────────┤   │
│ │ Nav│  Main Content (p-4 md:p-6)               │   │
│ │    │  ┌─────────────────────────────────────┐  │   │
│ │    │  │ Page Title + Action Buttons         │  │   │
│ │    │  │ space-y-6                           │  │   │
│ │    │  │ Stat Cards (grid)                   │  │   │
│ │    │  │ space-y-6                           │  │   │
│ │    │  │ Section Card (table/content)        │  │   │
│ │    │  └─────────────────────────────────────┘  │   │
│ └────┴───────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### 4.2 Sidebar

| 속성 | 값 |
|------|------|
| 너비 (확장) | `w-60` (240px) |
| 너비 (축소) | `w-[68px]` |
| 배경 | `bg-white` / `dark:bg-[#17171C]` |
| 그림자 | `shadow-[2px_0_6px_rgba(0,0,0,0.02)]` |
| 로고 영역 | h-14, `rounded-xl bg-[#3182F6]` 아이콘 + "SMS" 텍스트 |
| 그룹 라벨 | `text-overline font-semibold text-[#B0B8C1]` |
| 아이템 | `rounded-xl p-2.5 text-body text-[#8B95A1]` |
| 아이템 (활성) | `bg-[#E8F3FF] text-[#3182F6]` |
| 그룹 구분선 | `h-px bg-[#F2F4F6]` |
| 하단 | 다크모드 토글 + 사이드바 접기 버튼 |

**네비게이션 그룹 (ADMIN 이상):**

| 그룹 | 항목 |
|------|------|
| 운영 관리 | 대시보드, 예약 관리, 객실 배정, 객실 설정, 템플릿 관리, 파티 입장 체크 |
| SMS 자동화 | 메시지, 자동 응답 |
| 시스템 | 활동 로그, 설정, 계정 관리 |

**네비게이션 그룹 (STAFF):**
- 파티 입장 체크만 노출 (사이드바 없이 전체 화면)

### 4.3 Header

| 속성 | 값 |
|------|------|
| 높이 | `h-14` |
| 위치 | `sticky top-0 z-20` |
| 배경 | `bg-[#FAFBFC]/90 backdrop-blur-md` |
| 왼쪽 | 페이지 제목 (`text-subheading font-semibold`) |
| 오른쪽 | 사용자 이름 + 역할 뱃지 + 다크모드 토글 + 로그아웃 |

### 4.4 간격 규칙

| 컨텍스트 | 간격 |
|----------|------|
| 페이지 헤더 ↔ 콘텐츠 | `space-y-6` |
| 버튼 그룹 (헤더) | `gap-2` |
| 테이블 인라인 버튼 | `gap-1` |
| stat-card 그리드 | `gap-3` + `grid-cols-2 sm:3 lg:5` |
| 폼 필드 | `gap-4` |
| 필터 바 항목 | `gap-3` |
| 카드 내부 요소 | `gap-3` |
| 메인 콘텐츠 패딩 | `p-4 md:p-6` |

---

## 5. 컴포넌트 시스템

### 5.1 Stat Card

```tsx
<div className="stat-card">
  <div className="flex items-center gap-3">
    <div className="stat-icon bg-[#E8F3FF]">
      <Icon size={18} className="text-[#3182F6]" />
    </div>
    <div>
      <p className="stat-label">라벨</p>
      <p className="stat-value">24<span className="ml-0.5 text-label font-normal text-[#B0B8C1]">건</span></p>
    </div>
  </div>
</div>
```

| 속성 | 값 |
|------|------|
| 컨테이너 | `rounded-2xl border border-[#F2F4F6] bg-white p-5` |
| 아이콘 래퍼 | `h-10 w-10 rounded-xl flex items-center justify-center` |
| 아이콘 크기 | `size={18}` (lucide prop) |
| 값 | `text-title font-bold tabular-nums` |
| 라벨 | `text-caption font-medium text-[#8B95A1]` |
| 그리드 | `grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5` |

**아이콘 배경색:**

| 의미 | 배경 | 아이콘색 |
|------|------|---------|
| 기본/정보 | `bg-[#E8F3FF]` | `text-[#3182F6]` |
| 성공 | `bg-[#E8FAF5]` | `text-[#00C9A7]` |
| 경고 | `bg-[#FFF5E6]` | `text-[#FF9F00]` |
| 에러 | `bg-[#FFEBEE]` | `text-[#F04452]` |
| 중립 | `bg-[#F2F4F6]` | `text-[#8B95A1]` |

### 5.2 Section Card

```tsx
<div className="section-card">
  <div className="section-header">
    <h3 className="text-subheading font-semibold">섹션 제목</h3>
    <Button size="sm" color="light">액션</Button>
  </div>
  <div className="section-body">
    {/* content */}
  </div>
</div>
```

| 속성 | 값 |
|------|------|
| 컨테이너 | `rounded-2xl border border-[#F2F4F6] bg-white overflow-hidden` |
| 헤더 | `px-5 py-4 flex items-center justify-between` |
| 바디 | `p-5` |
| 그림자 | `shadow-[0_1px_4px_rgba(0,0,0,0.02)]` |

### 5.3 Button

Flowbite `<Button>` 커스텀 테마 기반.

| 위치 | `size` | `color` | 아이콘 크기 |
|------|--------|---------|-------------|
| 페이지 헤더 액션 | `sm` | `blue` 또는 `light` | `h-3.5 w-3.5` |
| 테이블 인라인 액션 | `xs` | `light` 또는 `failure` | `h-3.5 w-3.5` |
| 모달 푸터 | `md` (기본) | `blue` + `light` | — |
| 삭제 확인 | `md` (기본) | `failure` + `light` | — |

**사이즈 스펙:**

| Size | Padding | Font |
|------|---------|------|
| `xs` | `px-2 py-1` | `text-caption` (12px) |
| `sm` | `px-3 py-1.5` | `text-body` (14px) |
| `md` | `px-4 py-2` | `text-body` (14px) |
| `lg` | `px-5 py-2.5` | `text-body` (14px) |

**컬러 스펙:**

| Color | 배경 | 호버 | 텍스트 |
|-------|------|------|--------|
| `blue` | `#3182F6` | `#1B64DA` | white |
| `light` | `#F2F4F6` | `#E5E8EB` | `#191F28` |

**규칙:**
- 버튼 내 아이콘은 `mr-1.5` 간격으로 텍스트 앞 배치
- 아이콘 전용 버튼(테이블)은 아이콘만
- 로딩: `<Spinner size="sm" className="mr-2" />` + "저장 중..."

### 5.4 Badge

Flowbite `<Badge>` 커스텀 테마 기반.

| Color | 배경 | 텍스트 | 다크모드 배경 |
|-------|------|--------|-------------|
| `info` | `#E8F3FF` | `#3182F6` | `#3182F6/15` |
| `success` | `#E8FAF5` | `#00C9A7` | `#00C9A7/15` |
| `warning` | `#FFF5E6` | `#FF9F00` | `#FF9F00/15` |
| `failure` | `#FFEBEE` | `#F04452` | `#F04452/15` |
| `gray` | `#F2F4F6` | `#8B95A1` | `#2C2C34` |

**용도 매핑:**

| 용도 | Color | Size |
|------|-------|------|
| 상태 - 확정 | `success` | `sm` |
| 상태 - 대기 | `warning` | `sm` |
| 상태 - 취소 | `failure` | `sm` |
| 역할 - 슈퍼관리자 | `purple` | `sm` |
| 역할 - 관리자 | `info` | `sm` |
| 역할 - 직원 | `gray` | `sm` |
| 출처 - 네이버 | `success` | `xs` |
| 출처 - 수동 | `gray` | `xs` |

**스타일:** `rounded-lg px-2 py-0.5 font-medium`

### 5.5 Table

Flowbite `<Table>` 커스텀 테마 기반.

| 파트 | 스타일 |
|------|--------|
| Root | `text-body text-[#4E5968]` |
| Head | `text-caption uppercase text-[#8B95A1] bg-[#F8F9FA]` |
| Head Cell | `px-5 py-3 font-medium whitespace-nowrap` |
| Body Cell | `px-5 py-3.5 text-body whitespace-nowrap` |
| Row Hover | `hover:bg-[#F2F4F6]` / `dark:hover:bg-[#1E1E24]` |
| Row Striped | `even:bg-[#F2F4F6]/40` |

### 5.6 Modal

| 속성 | 값 |
|------|------|
| 일반 폼 | `size="md"` |
| 복잡한 폼 | `size="lg"` |
| 삭제 확인 | `size="md"` + popup 스타일 |
| 모서리 | `rounded-2xl` |
| 배경 | `bg-white` / `dark:bg-[#1E1E24]` |
| 그림자 | `shadow-2xl` |
| 오버레이 | `bg-gray-900/50` |
| 최대 높이 | `max-h-[90dvh]` |

### 5.7 Tabs

Flowbite `<Tabs>` underline variant.

| 상태 | 스타일 |
|------|--------|
| Active | `border-[#3182F6] text-[#3182F6]` (2px 밑줄) |
| Inactive | `text-[#8B95A1] hover:border-[#B0B8C1] hover:text-[#4E5968]` |
| Font | `text-body font-medium` |

### 5.8 Form Input

| 속성 | 값 |
|------|------|
| Size sm | `p-2 text-body` |
| Size md | `p-2.5 text-body` |
| Placeholder | `color: #B0B8C1, font-size: 14px` |
| 모서리 | `rounded-lg` (Flowbite 기본) |

### 5.9 Tooltip

| 속성 | 값 |
|------|------|
| Dark style | `bg-[#191F28] text-white rounded-lg px-3 py-1.5 text-caption font-medium` |
| Arrow | `bg-[#191F28]` |
| Animation | `transition-opacity duration-150` |

### 5.10 Toggle Switch

| 상태 | 스타일 |
|------|--------|
| Checked | `bg-[#3182F6] border-[#3182F6]` |
| Unchecked | `bg-gray-200 border-gray-200` |
| Label | `text-body font-medium text-[#191F28]` |
| Size md | `h-6 w-11` |

### 5.11 Chat Bubble (Messages)

| Type | 스타일 |
|------|--------|
| Inbound | `bg-[#F2F4F6] rounded-[20px] rounded-bl-[4px] text-[#191F28]` |
| Outbound | `bg-[#3182F6] rounded-[20px] rounded-br-[4px] text-white` |
| Max Width | `max-w-[75%]` |
| Padding | `px-4 py-2.5` |

### 5.12 Empty State

```tsx
<div className="empty-state">
  <Icon size={40} />
  <p className="text-label">등록된 데이터가 없습니다</p>
</div>
```

| 속성 | 값 |
|------|------|
| 컨테이너 | `flex flex-col items-center justify-center gap-3 py-16` |
| 아이콘 | `size={40}` 또는 `h-10 w-10` |
| 텍스트 | `text-[#B0B8C1]` / `dark:text-gray-600` |
| 텍스트 스타일 | `text-label` |

### 5.13 Filter Bar

```tsx
<div className="filter-bar">
  <Select size="sm">...</Select>
  <TextInput size="sm" icon={Search} placeholder="검색..." />
  <Datepicker size="sm" />
</div>
```

| 속성 | 값 |
|------|------|
| 컨테이너 | `flex flex-wrap items-center gap-3 rounded-xl p-4` |
| 입력 크기 | `size="sm"` |

---

## 6. 아이콘 시스템

**라이브러리:** Lucide React

| 컨텍스트 | 크기 | 표기법 |
|----------|------|--------|
| 버튼 내부 (sm/xs) | `h-3.5 w-3.5` | className |
| 독립 아이콘 (필터 등) | `h-4 w-4` | className |
| 사이드바 네비 | `size={18}` | lucide prop |
| stat-card | `size={18}` | lucide prop |
| 빈 상태 일러스트 | `size={40}` | lucide prop |
| 헤더 액션 (다크모드/로그아웃) | `size={18}` | lucide prop |

**사이드바 아이콘 매핑:**

| 페이지 | 아이콘 |
|--------|--------|
| 대시보드 | `LayoutDashboard` |
| 예약 관리 | `CalendarRange` |
| 객실 배정 | `BedDouble` |
| 객실 설정 | `Settings2` |
| 템플릿 관리 | `FileText` |
| 파티 입장 체크 | `PartyPopper` |
| 메시지 | `MessageSquareText` |
| 자동 응답 | `Zap` |
| 활동 로그 | `History` |
| 설정 | `Settings` |
| 계정 관리 | `Users` |

---

## 7. 반올림(Border Radius) 규칙

| 요소 | Radius | 값 |
|------|--------|------|
| 카드, 모달, 사이드바 아이템 | `rounded-2xl` | 16px |
| 버튼, 뱃지, 입력, 필터 바 | `rounded-lg` | 8px |
| stat-icon, 로고 | `rounded-xl` | 12px |
| 채팅 버블 | `rounded-[20px]` + 꼬리 `rounded-bl-[4px]` | 20px / 4px |
| 스크롤바 | `rounded-full` | ∞ |

---

## 8. 그림자 시스템

| 용도 | 값 |
|------|------|
| 카드/섹션 (Light) | `shadow-[0_1px_4px_rgba(0,0,0,0.02)]` |
| 카드/섹션 (Dark) | `shadow-[0_1px_4px_rgba(0,0,0,0.15)]` |
| 사이드바 | `shadow-[2px_0_6px_rgba(0,0,0,0.02)]` |
| 모달 | `shadow-2xl` |
| 툴팁 | `shadow-lg` |

---

## 9. 다크 모드

class 기반 (`html.dark`) — `@custom-variant dark (&:where(.dark, .dark *))`.

| 요소 | Light | Dark |
|------|-------|------|
| Body | `#FAFBFC` | `#17171C` |
| Card/Modal | `#FFFFFF` | `#1E1E24` |
| Hover | `#F2F4F6` | `#2C2C34` |
| Active Hover | `#E5E8EB` | `#35353E` |
| Border | `#F2F4F6` | `gray-800` |
| Text Primary | `#191F28` | `white` |
| Text Secondary | `#4E5968` | `gray-300` |
| Text Tertiary | `#8B95A1` | `gray-500` |
| Text Disabled | `#B0B8C1` | `gray-600` |
| Badge BG | `#E8F3FF` | `#3182F6/15` (15% opacity) |
| Scrollbar | `gray-200` | `gray-700` |

**토글:** `ThemeToggleButton` — `localStorage('sms-theme')` + `document.documentElement.classList.toggle('dark')`

---

## 10. 페이지별 패턴

### 10.1 표준 페이지 레이아웃

```tsx
<div className="space-y-6">
  {/* 헤더 */}
  <div className="flex flex-wrap items-start justify-between gap-4">
    <div>
      <h1 className="page-title">페이지 제목</h1>
      <p className="page-subtitle">설명 텍스트</p>
    </div>
    <div className="flex items-center gap-2">
      <Button color="light" size="sm"><Icon className="mr-1.5 h-3.5 w-3.5" />보조 액션</Button>
      <Button color="blue" size="sm"><Icon className="mr-1.5 h-3.5 w-3.5" />주요 액션</Button>
    </div>
  </div>

  {/* stat-card */}
  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
    <div className="stat-card">...</div>
  </div>

  {/* 메인 콘텐츠 */}
  <div className="section-card">
    <div className="section-header">...</div>
    <Table>...</Table>
  </div>
</div>
```

### 10.2 페이지별 특성

| 페이지 | 레이아웃 패턴 | 주요 컴포넌트 |
|--------|-------------|-------------|
| **Login** | 중앙 정렬 카드, 로고 + 폼 | TextInput, Button(blue, full-width) |
| **Dashboard** | stat-cards + 차트 + 최근 활동 테이블 | stat-card(5열), section-card, Table |
| **Reservations** | 필터 바 + 대형 테이블 (페이지네이션) | filter-bar, Table(striped), Badge, Button(xs) |
| **Room Assignment** | 날짜 선택 + 드래그앤드롭 그리드 | guest-card, room-cell, DatePicker |
| **Room Settings** | 건물/객실 CRUD | Table, Modal(form), ToggleSwitch |
| **Templates** | 탭(스케줄) + 테이블 | Tabs(underline), Table, Modal, Badge |
| **Messages** | 좌측 연락처 + 우측 채팅 (3열) | 연락처 목록, chat-bubble, TextInput |
| **Auto Response** | 탭(규칙/문서) + 규칙 목록 | Tabs(underline), empty-state, Button(blue) |
| **Activity Logs** | stat-cards + 필터 + 타임라인 테이블 | stat-card(4열), filter-bar, Badge(다색상) |
| **Party Checkin** | 날짜 선택기 + 단순 테이블 | 날짜 네비, 상태 dot, Table |
| **Settings** | 단일 설정 카드 | section-card, TextInput, Textarea, Button |
| **User Management** | 사용자 테이블 + CRUD 모달 | Table, Modal(form), Badge(role) |

---

## 11. 스크롤바

```css
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { bg-transparent; }
::-webkit-scrollbar-thumb { rounded-full bg-gray-200 dark:bg-gray-700; }
::-webkit-scrollbar-thumb:hover { bg-gray-300 dark:bg-gray-600; }
```

유틸리티:
- `scrollbar-thin` — Firefox (`scrollbar-width: thin`)
- `scrollbar-none` — 완전 숨김

---

## 12. 반응형

| Breakpoint | 동작 |
|------------|------|
| Mobile (<768px) | 사이드바 → Drawer, `<MobileSidebar>`, 패딩 `p-4` |
| Desktop (≥768px) | 고정 사이드바, 패딩 `p-6` |
| stat-card grid | `grid-cols-2` → `sm:grid-cols-3` → `lg:grid-cols-5` |
| Staff 역할 | 사이드바 없음, 전체 화면 (`flex-1 p-4 md:p-6`) |

---

## 13. 파일 구조

```
frontend/src/
├── index.css                    # 디자인 토큰, 컴포넌트 클래스
├── components/
│   ├── FlowbiteTheme.tsx        # Flowbite 커스텀 테마 오버라이드
│   └── Layout.tsx               # 앱 레이아웃 (사이드바, 헤더, 다크모드)
├── pages/                       # 12개 페이지
└── hooks/
    └── use-mobile.ts            # 반응형 breakpoint 훅
```

---

## 14. 스크린샷 참조

| 파일 | 페이지 |
|------|--------|
| `docs/screenshots/01-login.png` | 로그인 |
| `docs/screenshots/02-dashboard.png` | 대시보드 (Light) |
| `docs/screenshots/02-dashboard-dark.png` | 대시보드 (Dark) |
| `docs/screenshots/03-reservations.png` | 예약 관리 |
| `docs/screenshots/06-templates.png` | 템플릿 관리 |
| `docs/screenshots/07-messages.png` | 메시지 (Light) |
| `docs/screenshots/07-messages-dark.png` | 메시지 (Dark) |
| `docs/screenshots/08-auto-response.png` | 자동 응답 |
| `docs/screenshots/09-activity-logs.png` | 활동 로그 |
| `docs/screenshots/10-party-checkin.png` | 파티 입장 체크 |
| `docs/screenshots/11-settings.png` | 설정 |

---

## 15. 디자인 일관성 체크리스트

스크린샷 기반 전체 페이지 검토 결과:

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | 색상 팔레트 일관성 | OK | 전 페이지 Toss Blue 기반 통일 |
| 2 | 타이포그래피 스케일 | OK | page-title, stat-value, text-body 일관 |
| 3 | 사이드바 네비게이션 | OK | 그룹 라벨, 활성 상태, 아이콘 통일 |
| 4 | stat-card 패턴 | OK | Dashboard, Activity Logs에서 동일 패턴 |
| 5 | 테이블 스타일 | OK | Reservations, Templates, Activity Logs, Room Settings, User Management 통일 |
| 6 | 뱃지 색상 매핑 | OK | 상태별 semantic color 일관 |
| 7 | 빈 상태 패턴 | OK | Auto Response, Messages에서 동일 패턴 |
| 8 | 버튼 사이즈/색상 | OK | 헤더=sm, 테이블=xs, 모달=md 규칙 준수 |
| 9 | 다크 모드 | 부분 | class 기반 구현 완료, Playwright emulateMedia로는 캡처 불가 (JS 토글 필요) |
| 10 | 반응형 | OK | 모바일 Drawer, Desktop 고정 사이드바 |

**개선 고려 사항:**

| # | 페이지 | 관찰 | 우선순위 |
|---|--------|------|---------|
| 1 | User Management | "활성" 텍스트가 Badge가 아닌 일반 텍스트로 표시됨 — 다른 페이지의 Badge 패턴과 불일치 | Low |
| 2 | User Management | "edit" 버튼이 영문 — 다른 페이지는 한국어 ("수정") | Low |
| 3 | Room Assignment | 드래그앤드롭 그리드가 데이터가 많을 때 스크롤 영역 확인 필요 | Low |
| 4 | Messages | 데이터 없을 때 빈 상태 아이콘/텍스트 잘 표시됨 | Info |
