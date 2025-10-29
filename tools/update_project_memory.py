# -*- coding: utf-8 -*-
import subprocess, os, datetime, re
DOC = "docs/PROJECT_MEMORY.md"

def git(cmd): return subprocess.check_output(cmd, shell=True, encoding="utf-8").strip()

def last_commit():
    iso = git('git log -1 --pretty=%cI')
    subject = git('git log -1 --pretty=%s')
    body = git('git log -1 --pretty=%b')
    return iso, subject, body

def upsert(doc, marker, insert):
    if marker in doc:
        # 현재 마커 다음 줄에 최신 항목 한 줄 삽입
        return re.sub(rf"({re.escape(marker)}\\s*\\n)", rf"\\1{insert}\\n", doc, count=1)
    else:
        # 섹션 없으면 만들어서 추가
        return doc + f"\n\n## {marker}\n{insert}\n"

def ensure_header(doc, today):
    if "PROJECT MEMORY — auto_trade_v20" not in doc:
        head = f"# PROJECT MEMORY — auto_trade_v20\n\n업데이트: {today}\n"
        return head + doc
    return re.sub(r"(업데이트:\s*)(.*)", rf"\g<1>{today}", doc, count=1)

def main():
    os.makedirs("docs", exist_ok=True)
    if os.path.exists(DOC):
        with open(DOC, "r", encoding="utf-8") as f: doc = f.read()
    else:
        doc = ""

    iso, subject, body = last_commit()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    doc = ensure_header(doc, today)

    # 간단 규칙으로 상태 라인 업데이트
    status = []
    if "calibrator" in (subject+body).lower(): status.append("Calibrator 업데이트")
    if "sector_cap" in (subject+body).lower() or "sector" in (subject+body).lower(): status.append("SectorCap 리스크 정책 변경")
    if "kiwoom" in (subject+body).lower(): status.append("Kiwoom 어댑터 변경")
    if status:
        doc = upsert(doc, "현재 상태", " - " + " / ".join(sorted(set(status))))

    # 변경 이력 섹션에 커밋 요약 추가
    line = f"- {iso[:10]} — {subject}"
    doc = upsert(doc, "변경 이력", line)

    with open(DOC, "w", encoding="utf-8") as f: f.write(doc)

if __name__ == "__main__":
    main()
