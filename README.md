# chzzk-devapp-refresh

치지직 개발자센터 애플리케이션의 Client ID/Secret 으로 Open API 를 호출하는 스크립트.
치지직 개발자센터는 최근 90일간 API 호출이 없는 애플리케이션을 삭제한다.

- 여러 앱을 `.env` 에 번호를 붙여 등록하고, 번호 순서대로 호출한다.
- Client 인증 API 만 호출한다. 로그인(Access Token)은 필요 없다.
- 결과는 콘솔과 `logs/refresh.log` 에 남는다.

**의존성 없음.** Python 3.10+ 표준 라이브러리만 사용한다.

```bash
python refresh.py
```

## 설정

`refresh.py` 와 같은 폴더에 `.env` 를 만든다.

```env
CHZZK_APP1_NAME=my-bot
CHZZK_APP1_CLIENT_ID=fefb6bbb-00c2-497c-afc2-XXXXXXXXXXXX
CHZZK_APP1_CLIENT_SECRET=VeIMuc9XGle7PSxIVYNwPpI2OEk_9gXoW_XXXXXXXXX

CHZZK_APP2_CLIENT_ID=...
CHZZK_APP2_CLIENT_SECRET=...

# CHZZK_CHANNEL_ID=채널UID
```

| 키 | 설명 |
|---|---|
| `CHZZK_APP{n}_CLIENT_ID` | 클라이언트 ID (필수) |
| `CHZZK_APP{n}_CLIENT_SECRET` | 클라이언트 Secret (필수) |
| `CHZZK_APP{n}_NAME` | 로그에 표시할 이름 (선택) |
| `CHZZK_CHANNEL_ID` | 채널 정보 조회에 쓸 채널 UID, 쉼표로 최대 20개 (선택, 생략 시 라이브 목록 1위 채널) |

`{n}` 의 숫자 순서(1 → 2 → … → 10)로 호출하며, 중간 번호가 비어도 된다. 주석은 줄 맨 앞의 `#` 만 인식한다.

## 호출하는 API

| API | 설명 |
|---|---|
| `GET /open/v1/lives` | 라이브 목록 조회 |
| `GET /open/v1/categories/search` | 카테고리 검색 |
| `GET /open/v1/channels` | 채널 정보 조회 |
| `GET /open/v1/sessions/client` | 세션 목록 조회(클라이언트) |
| `GET /open/v1/sessions/auth/client` | 세션 생성(클라이언트), URL 발급만 하고 소켓은 연결하지 않음 |

모두 [Client 인증](https://chzzk.gitbook.io/chzzk/chzzk-api/tips#client-api) API 로, `Client-Id` / `Client-Secret` 헤더가 없거나 틀리면 401 을 반환한다.

## 로그

```
2026-11-25 12:16:19 [INFO] 앱 1개 호출 시작: [APP1 my-bot]
2026-11-25 12:16:19 [INFO] [APP1 my-bot] lives 200 OK
2026-11-25 12:16:19 [INFO] [APP1 my-bot] categories/search 200 OK
2026-11-25 12:16:19 [INFO] [APP1 my-bot] channels 200 OK (채널명)
2026-11-25 12:16:19 [INFO] [APP1 my-bot] sessions/client 200 OK
2026-11-25 12:16:19 [INFO] [APP1 my-bot] sessions/auth/client 200 OK
2026-11-25 12:16:19 [INFO] [APP1 my-bot] 5/5 성공
2026-11-25 12:16:19 [INFO] 완료: 앱 1개 중 1개 호출 성공
```

호출이 한 번도 성공하지 못한 앱이 있으면 종료 코드 1 로 끝난다.

## 주기적으로 실행하기

이 저장소에는 예약 실행 설정이 들어 있지 않다. 필요하면 직접 등록한다.

**cron (Linux / macOS)**

```
0 9 1 * * python3 /path/to/chzzk-devapp-refresh/refresh.py
```

Windows 는 작업 스케줄러에 `python <경로>\refresh.py` 를 매월 실행하도록 등록하면 된다. `.env` 와 `logs/` 는 스크립트 위치 기준이라 작업 디렉터리는 상관없다.

**GitHub Actions**

private 저장소에서 `.github/workflows/refresh.yml` 로 추가하고, Settings → Secrets 에 `CHZZK_ENV` 이름으로 `.env` 내용을 넣는다.

```yaml
name: refresh

on:
  schedule:
    - cron: '0 0 1 * *'
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - run: printf '%s\n' "$CHZZK_ENV" > .env && python3 refresh.py
        env:
          CHZZK_ENV: ${{ secrets.CHZZK_ENV }}
```

공개 저장소는 Actions 로그(앱 이름 등)가 공개되고, 60일간 커밋이 없으면 예약 실행이 자동으로 꺼진다.

## 참고

- 개발자센터의 API 통계는 Access Token 이 필요한 Scope 별 사용량만 보여 주므로, 이 스크립트의 호출은 통계에 표시되지 않는다.
- [치지직 Open API 문서](https://chzzk.gitbook.io/chzzk)
