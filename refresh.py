import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BASE_URL = "https://openapi.chzzk.naver.com"
ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
LOG_FILE = ROOT / "logs" / "refresh.log"
APP_KEY = re.compile(r"CHZZK_APP(\d+)_(?:CLIENT_ID|CLIENT_SECRET|NAME)")

log = logging.getLogger("refresh")


@dataclass
class App:
    index: str
    name: str
    client_id: str
    client_secret: str

    @property
    def tag(self) -> str:
        return f"[APP{self.index} {self.name}]" if self.name else f"[APP{self.index}]"


@dataclass
class Result:
    ok: bool
    status: int
    message: str | None
    content: dict | None = None


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE, encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    # utf-8-sig: 메모장·PowerShell 이 붙이는 BOM 제거
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # 이미 있는 환경변수가 .env 보다 우선
        os.environ.setdefault(key, value)


def load_apps() -> list[App]:
    """CHZZK_APP{n}_* 를 n 의 숫자 순으로 모은다. APP1, APP2, APP10 -> 1, 2, 10."""
    indices = sorted({m.group(1) for key in os.environ if (m := APP_KEY.fullmatch(key))}, key=int)
    return [
        App(
            index=i,
            name=os.environ.get(f"CHZZK_APP{i}_NAME", "").strip(),
            client_id=os.environ.get(f"CHZZK_APP{i}_CLIENT_ID", "").strip(),
            client_secret=os.environ.get(f"CHZZK_APP{i}_CLIENT_SECRET", "").strip(),
        )
        for i in indices
    ]


def call(app: App, path: str) -> Result:
    req = urllib.request.Request(
        BASE_URL + path,
        headers={
            "Client-Id": app.client_id,
            "Client-Secret": app.client_secret,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        return Result(False, 0, f"연결 실패: {getattr(e, 'reason', e)}")
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}
    return Result(status == 200 and body.get("code") == 200, status, body.get("message"), body.get("content"))


def refresh(app: App) -> list[Result]:
    results: list[Result] = []

    def run(label: str, path: str, describe: Callable[[dict], str] | None = None) -> Result:
        r = call(app, path)
        if r.ok:
            extra = describe(r.content or {}) if describe else ""
            log.info("%s %s %d OK%s", app.tag, label, r.status, f" ({extra})" if extra else "")
        else:
            detail = f"{r.status} {r.message or ''}".strip() if r.status else r.message
            log.warning("%s %s %s", app.tag, label, detail)
        results.append(r)
        return r

    lives = run("lives", "/open/v1/lives?size=1")
    run("categories/search", "/open/v1/categories/search?query=talk&size=1")
    # channelIds 가 필수라 CHZZK_CHANNEL_ID 가 없으면 방금 받은 라이브의 채널을 재사용
    data = (lives.content or {}).get("data") or []
    channel_id = os.environ.get("CHZZK_CHANNEL_ID", "").strip() or (data[0].get("channelId") if data else "")
    if channel_id:
        run(
            "channels",
            f"/open/v1/channels?channelIds={urllib.parse.quote(channel_id, safe=',')}",
            lambda c: ", ".join(d.get("channelName", "?") for d in c.get("data") or []) or "일치하는 채널 없음",
        )
    run("sessions/client", "/open/v1/sessions/client?size=1")
    # URL 발급만 하고 소켓은 연결하지 않음 (발급만으로는 세션 목록에 안 남는 것 확인)
    run("sessions/auth/client", "/open/v1/sessions/auth/client")
    return results


def main() -> int:
    setup_logging()
    load_env(ENV_FILE)
    apps = load_apps()
    if not apps:
        log.error("등록된 앱이 없습니다. .env 에 CHZZK_APP1_CLIENT_ID 와 CHZZK_APP1_CLIENT_SECRET 을 넣으세요 (README 참고)")
        return 1

    log.info("앱 %d개 호출 시작: %s", len(apps), ", ".join(a.tag for a in apps))
    refreshed = 0
    for app in apps:
        if not app.client_id or not app.client_secret:
            log.error("%s CLIENT_ID 와 CLIENT_SECRET 이 모두 있어야 합니다. 건너뜀", app.tag)
            continue
        results = refresh(app)
        ok = sum(r.ok for r in results)
        (log.info if ok else log.error)("%s %d/%d 성공", app.tag, ok, len(results))
        refreshed += ok > 0

    level = logging.INFO if refreshed == len(apps) else logging.ERROR
    log.log(level, "완료: 앱 %d개 중 %d개 호출 성공", len(apps), refreshed)
    return 0 if refreshed == len(apps) else 1


if __name__ == "__main__":
    sys.exit(main())
