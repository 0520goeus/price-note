# 해뎐 가격노트

라면, 우유, 세제 같은 생필품의 전국 매장 판매가를 매주 기록해 가격 흐름과 업태별 차이를 보여 주는 정적 사이트입니다.
GitHub Actions가 매일 05:40(한국 시간)에 새 조사분을 확인해 받아 적고, 사이트를 다시 만들어 GitHub Pages에 올립니다.
맥을 켜 둘 필요가 없고, AI를 쓰지 않으며, 비용이 들지 않습니다.

## 가격 출처
한국소비자원 「생필품 가격 정보」 오픈API (공공데이터포털, 공공누리 제1유형: 출처를 밝히면 상업적 이용 가능).
매주 금요일 조사분이 올라오며, 처음 실행하면 최근 26주를 거슬러 채웁니다(하루에 몇 주씩, 며칠에 걸쳐).

## 처음 한 번 설정
1. data.go.kr에 로그인해 "한국소비자원_생필품 가격 정보_GW"를 검색하고 **활용신청**을 누릅니다.
2. 마이페이지의 인증키(Decoding)를 복사합니다.
3. GitHub에 공개 저장소를 만들고 이 폴더의 파일을 올립니다. `daily.yml`은 `.github/workflows/` 안에 둡니다.
4. 저장소 Settings → Secrets and variables → Actions에 `DATA_KEY`라는 이름으로 인증키를 넣습니다.
5. Settings → Pages → Source를 **GitHub Actions**로 바꿉니다.
6. Actions 탭에서 "가격 기록"을 한 번 직접 실행합니다. 이후로는 매일 자동입니다.

## 수익 연결 (config.json)
- `coupang_widget_html`: 쿠팡 파트너스 다이나믹 배너 코드. 넣으면 모든 페이지에 대가성 문구와 함께 표시됩니다.
- `adsense_client`: 애드센스 승인 후 `ca-pub-...` 값. 광고 코드와 ads.txt가 자동으로 들어갑니다.
- `google_verification`, `naver_verification`: 서치콘솔·서치어드바이저 소유 확인 값.

## 파일
- `collect.py` 가격 수집, `build.py` 사이트 생성, `mock_test.py` 네트워크 없이 시험
