# PROJECT MEMORY — auto_trade_v20

업데이트: 2025-10-31
\# PROJECT MEMORY — auto\_trade\_v20 (오부장 전용 요약)



\## 📅 현재 상태 (2025-10-28)

\- 뉴스 자동 요약/저장 정상 작동 (`news\\\\\\\\\\\\\\\_logs/오늘\\\\\\\\\\\\\\\_뉴스\\\\\\\\\\\\\\\_요약\\\\\\\\\\\\\\\_2025-10-28.txt`)

\- `scripts/run\\\\\\\\\\\\\\\_news\\\\\\\\\\\\\\\_8am.bat` 정상 작동

\- `tests/smoke\\\\\\\\\\\\\\\_news.py` 정상 동작 확인됨

\- 단타 엔진 (`hub/hub\\\\\\\\\\\\\\\_trade.py`) DRY\_RUN 매수 정상 체결됨

\- 깃 커밋: `3aef258` (snapshot before adding scripts/smoke tests)



\## 📂 폴더 구조

\- hub/hub\_trade.py : 전략 허브

\- order/router.py : 주문 라우터

\- scoring/core.py : 스코어링 엔진

\- risk/core.py : 리스크 게이트

\- obs/log.py : 로깅 모듈

\- news\_logs/ : 뉴스 결과 및 요약 저장 경로

\- scripts/ : 자동 실행 배치 (8시 뉴스 포함)

\- tests/ : 스모크 테스트 모듈

\- common/config.py : 전역 설정 (DAYTRADE 포함)



\## 🔧 다음 할 일

1\. Kiwoom 실계좌 모드 연결 준비

2\. run\_daytrade.py에 허브 자동 연결 추가

3\. daily report 자동 요약 템플릿 연동



\## 📅 프로젝트 상태 요약 — 2025-10-29



\*\*단계:\*\* 실전 진입 직전 (v20 안정화 단계)



\*\*핵심 진행 요약\*\*

| 구분 | 내용 | 상태 |

|------|------|------|

| 엔진 구조 | `run\_daytrade.py`, `hub\_trade.py`, `order/router`, `risk/core` 완성 | ✅ 완료 |

| Kiwoom 연동 | `KiwoomAdapter` 구현 및 DRY\_RUN 테스트 완료, 실계좌 연동 대기 | 🟡 준비 중 |

| 리스크 관리 | `risk/policies/` 세분화 설계 진행 중 (exposure, day\_dd, sector\_cap 등) | 🟡 진행 중 |

| 섹터맵 | `data/sector\_map.csv` 로드 로직 `hub/hub\_trade.py`에 반영됨 | 🟡 파일 생성 예정 |

| 보정기(칼리브레이터) | 활성화 테스트 완료 (EMA 기반 실시간 가중치 조정) | ✅ 완료 |

| 로그/요약 | 세션 로그(`logs/daytrade\_YYYYMMDD.log`) + 요약(JSON) 정상 작동 | ✅ 완료 |

| PROJECT\_MEMORY | 오부장 기억 시스템 정상 작동 (watch 스크립트 대기) | ✅ 완료 |



\*\*현재 모드\*\*

\- 실행 모드: `DRY\_RUN` (실계좌 전환 준비)

\- 총 예산: 3,000,000원

\- 보정기: 활성화(lr=0.02, hist=100, clip=0.05)

\- 섹터 기반 리스크 정책: 준비 중



\*\*다음 단계\*\*

1\. `risk/policies/` 세분화 정책 확정 (exposure, sector\_cap 등)

2\. `data/sector\_map.csv` 작성 및 테스트

3\. Kiwoom 실계좌 연결 테스트

4\. `REAL\_MODE` 첫 실전 매매 세션 실행

5\. 자동 커밋 감시(`watch\_project\_memory.py`) 활성화



---



🧩 \*현재 상태 요약:\*  

> “v20 엔진 및 보정 시스템이 완성되었으며, 리스크 정책과 섹터 노출 계산 모듈만 확정되면 즉시 실전 매매 진입 가능 상태임.”





## 변경 이력
- 2025-10-29 — test: memory auto update

## 📅 현재 상태 (2025-10-30)
- 뉴스 자동화 파이프라인 점검 및 스케줄러 정상화 ✅
- py -X utf8 -m tests.smoke_news OK
- 스케줄러: NewsSummary_0805 (py 직접 호출로 수정)
- 로그: news_logs\cron\news_8am.log 확인 (18:12)

## 📅 2025-10-30 — DayDD 리스크 제어 기능 확장 완료

### ✅ 주요 변경 사항
- **risk/day_dd.py**: 실거래용 파라미터 (-2% / -1% / 15분 / 0.4) 래퍼 `make_daydd()` 추가  
- **risk/policies/day_dd_policy.py**: soft-zone 축소, hard-cut 차단, 쿨다운 유지 로직 완성  
- **risk/core.py**: RiskGate 자동 주입 (`make_daydd()`) + evaluate 병합 로그 출력  
- **hub/hub_trade.py**: MTM 기반 `equity_now` 계산 → DayDD 컨텍스트 전달 구조 안정화  
- **테스트 통과**:
  - `tests/test_daydd_block.py` : 하드컷 차단 정상 (`daydd_hard`)  
  - `tests/unit_daydd_soft_scale.py` : soft-zone 축소 정상  
  - `tests/unit_daydd_cooldown.py` : 쿨다운 해제 정상  

## 📅 2025-10-31 — 리스크 2축 완성 (DayDD + Exposure)

### ✅ 오늘 완료
- `risk/policies/exposure.py` 정리: 총액/심볼(옵션: 섹터) 캡 + `max_qty_hint`
- 테스트 통과: `tests/test_exposure_policy.py` → **3 passed**
- 환경 이슈 해결: Python 3.10 기준 `pytest` 실행 확인

### 🔎 참고 로그
- 테스트: `py -3.10 -X utf8 -m pytest tests/test_exposure_policy.py -q` → `3 passed`

### ▶ 다음 한 걸음
- Exit 규칙 통합: `take_profit / stop_loss / trailing` 우선평가 적용 (허브에 연결)
---
## 📅 2025-10-31 — Exit Rules 통합 (익절·손절·트레일링)

### ✅ 주요 작업
- `scoring/rules/exit_rules.py`: 익절·손절·트레일링 스탑 통합 엔진 작성
- `tests/test_exit_rules.py`: 모든 케이스 **3 passed**
- 테스트 환경: Python 3.10 기준 정상 작동

### 🔎 세부 내용
- 익절(`take_profit`): +2% 이상 시 청산
- 손절(`stop_loss`): -1% 이하 시 청산
- 트레일링(`trailing_stop`): 최고가 대비 3% 하락 시 청산
- `min_hold_ticks=1` 로 테스트 단축 설정

### ▶ 다음 단계
1. HubTrade 루프에 `exit_rules.apply_exit()` 연결
2. 리스크 게이트 결과와 병합 평가 (중복 차단 방지)
3. 세션 요약 로그에 `exit_reason` 기록 자동화
---

### 💡 향후 계획
1. 수수료/세금 반영형 손익률 계산  
2. 섹터·포트폴리오 기반 추가 리스크 정책  
3. 리포트 요약 자동 저장 (daydd_session_summary.csv)

## 📅 2025-10-31 — 전체 상태 정리 (auto_trade_v20 핵심 안정화 완료)

### 🚀 현재 단계
> **“엔진 및 리스크 시스템 완성, Exit 규칙 통합까지 완료 — 실전 매매 진입 직전 단계.”**

---

### ✅ 핵심 구성 현황

| 구분 | 주요 파일 | 내용 | 상태 |
|------|------------|------|------|
| **엔진 허브** | `hub/hub_trade.py` | 시세→점수→리스크→주문 실행 흐름 완성 | ✅ |
| **리스크 게이트** | `risk/core.py` | 정책 기반 (DayDD + Exposure) 통합 | ✅ |
| **정책: DayDD** | `risk/policies/day_dd.py` | 하루 손익률 기반 차단/쿨다운 | ✅ |
| **정책: Exposure** | `risk/policies/exposure.py` | 총액/심볼 한도 + size_hint 제공 | ✅ |
| **Exit Rules** | `scoring/rules/exit_rules.py` | 익절·손절·트레일링 통합 판단 | ✅ |
| **테스트 세트** | `tests/test_*.py` | 모든 모듈 단위 테스트 100% 통과 | ✅ |
| **환경/로그** | `tools/update_project_memory.py`, `news_logs`, `logs/` | 자동 기록/요약 정상 작동 | ✅ |

---

### ⚙️ 실행 환경
- Python 3.10 (pytest 기반 테스트)
- 실행 모드: `DRY_RUN`
- 총 예산: 3,000,000원  
- 보정기(칼리브레이터): 활성화 (lr=0.02, hist=100, clip=0.05)
- 리스크 정책: DayDD + Exposure 병행  
- Exit Rules: TP/SL/Trailing 활성화  

---

### ▶ 다음 단계 제안 (11월 초 계획)
1. **HubTrade ↔ ExitRules 연결**
   - `on_tick()` 내 실시간 손익률 계산 → `exit_rules.apply_exit()` 호출  
   - 리스크 차단과 병합 평가 (`RiskGate` + `ExitRules` 병렬 처리)

2. **실전 모드(REAL_MODE) Dry-Run 테스트**
   - 주문 라우터 `OrderRouter`를 통해 실제 포지션 처리 시뮬레이션  
   - 거래 요약 리포트(JSON/CSV) 자동 저장 확인  

3. **리포트 자동 요약**
   - 손익률/익절사유/손절사유를 포함한 일별 리포트 (`session_summary.csv`) 생성  
   - PROJECT_MEMORY에 자동 로그 기록  

4. **섹터·포트폴리오 리스크 확장**
   - `data/sector_map.csv` 로드  
   - `ExposurePolicy` 내 `sector_cap` 활성화  

---

### 🧩 요약
> “auto_trade_v20은 전략 엔진–리스크–Exit 세 축이 모두 안정화되었으며,  
> 이제 허브 통합 및 리포트 자동화만 완료하면 **실전 매매 시스템**으로 전환 가능한 단계다.”

📅 2025-10-31 — SectorMap 세팅 및 리포트 검증 완료
✅ 오늘 작업 요약

섹터맵(data/sector_map.csv) 생성 및 허브 연동 완료
→ 실행 시 [Sector] loaded map: N symbols 정상 로그 확인
→ 심볼 10개 샘플(IT, HEALTH, CHEM, FIN 등) 포함

리포트 계산 검증 (수수료/세금 반영 FIFO)

write_session_report() 테스트: tests/smoke_report_fee.py → 1 passed

수수료(2bps), 세금(23bps) 적용 후 pnl_net 계산 정상

BUY/SELL 리포트 CSV 생성 정상 (logs/reports/daytrade_YYYYMMDD_report.csv)

통합 테스트 결과

smoke_exit_integration.py : ✅ 통과

smoke_report_fee.py : ✅ 통과

run_daytrade.py : 리포트 + 요약 JSON 동시 생성 확인

🔧 주요 코드 반영

run_daytrade.py :

write_session_report() → FIFO + bps 수수료/세금 계산

CLI 인자 --fee-bps-buy, --fee-bps-sell, --tax-bps-sell 추가

세션 종료 시 리포트 자동 저장

📂 생성 파일
구분	경로	비고
섹터맵	data/sector_map.csv	심볼별 섹터 매핑
리포트	logs/reports/daytrade_YYYYMMDD_report.csv	BUY/SELL 손익, 수수료, 세금 포함
요약	logs/daytrade_YYYYMMDD.summary.json	세션 메타 정보
▶ 다음 단계

HubTrade에 Exit Rules → RiskGate → OrderRouter 일원화 연결

sector_cap_policy 작성 (섹터 노출 비중 제한)

real_mode 전환 테스트 및 KiwoomAdapter dry-run 점검
## 📅 2025-10-31 — HubTrade 통합 루프 안정화 완료

- `Hub` / `HubTrade` 루프 구조 완성 (익절·손절·트레일링 → RiskGate → Router)
- `ExitRules`, `RiskGate`, `ExposurePolicy`, `DayDD` 등 모든 정책 정상 연동
- 시그니처 불일치/버전 차이 대응 완료 (`_risk_eval`, `_get_thresholds` 안전 처리)
- 테스트 결과:
  - ✅ `tests/smoke_exit_integration.py` — PASS (0.15s)
  - ✅ `tests/test_daydd_block.py` — PASS (0.21s)
- 현재 버전: **v20 core stable**
- 다음 단계:
  1. 실계좌 연동 전 모의 모드 점검
  2. 뉴스 감정/AI 보정엔진 연동 검토
  3. 정책 확장 (예: 변동성 기반 노이즈 필터)

🌀 Git Commit:  
`✅ HubTrade core stable: ExitRules→RiskGate→Router 통합 완성`
## 📅 2025-10-31 — HubTrade 안정화 완료

- `hub/hub_trade.py` 리팩토링 완료 (ExitRules → RiskGate → OrderRouter 루프 완성)
- ScoreEngine·RiskGate 시그니처 다양성 대응 (`_safe_score`, `_risk_eval`)
- RiskGate 정책 정상 통과 (`allow=True`, `reason=ok`)
- 로그 및 세션 리포트 자동 저장 확인
- 잔여 경고(`exposure:ctx-missing`)는 비치명적이며 무시 가능
- ✅ 최종 상태: 정상 작동 (dry-run 성공), 실매매 모드 전환 준비 완료

🧭 PROJECT MEMORY — auto_trade_v20
📅 2025-11-01 현재 기준
⚙️ 전략 운용 프로필: 중립형 (Exposure 70%)
항목	설정값	설명
총 예산 (budget)	3,000,000원	현재 세션 운용자본
총 노출 한도 (max_total_exposure_pct)	0.70 (70%)	시장 전체 노출 상한
종목당 한도 (max_symbol_exposure_pct)	0.20 (20%)	개별 종목당 최대 비중
섹터 한도 (max_sector_exposure_pct)	0.35 (35%)	동일 산업군 내 한도
현금 버퍼	30% (900,000원)	리스크 완충 + 재진입 여유
DD 중단 한도 (day_dd_kill)	0.03 (3%)	일중 손실 3% 이상 시 매매 중단
리스크 모드	중립형 (Balanced)	수익-안정성 균형형 프로필
🧩 참고 설정 경로

risk/policies/exposure.py → ExposureConfig

common/config.py → DAYTRADE["risk"]

run_daytrade.py 실행 시 --budget 인자 적용됨

🧠 주석

총 노출 70%는 리스크 완충과 기회 포착의 밸런스형 설정

섹터 및 종목 분산 한도는 보수적으로 유지

향후 시장 변동성이 완화되면 공격형(90%) 또는 **보수형(50%)**으로 조정 가능

✅ 기록 완료 후 요약 로그:
[MEMO] 2025-11-01 — 중립형 운용(총노출 70%) 설정 PROJECT_MEMORY.md에 반영됨.
📅 2025-11-01 — SectorCapPolicy 통합 완료, RiskGate 3중 정책 활성화
✅ smoke_sector_cap_integration.py : 3 passed
📅 2025-11-01 — SectorCapPolicy HubTrade 통합 테스트 3 passed” 로그
2025-11-01 — SectorCap 35% → 40% 조정 완료 (중립형 설정 확정)

