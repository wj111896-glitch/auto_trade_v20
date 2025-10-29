# PROJECT MEMORY — auto_trade_v20

업데이트: 2025-10-29
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
