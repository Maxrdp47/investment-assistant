from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_py_compile() -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(APP_PATH)], check=True, cwd=ROOT)


def wait_for_http(url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Streamlit startete nicht rechtzeitig: {last_error}")


def run_streamlit_start_test() -> None:
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP_PATH),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_http(url)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def run_analysis_flow(symbols: list[str]) -> None:
    sys.path.insert(0, str(ROOT))
    import app

    for symbol in symbols:
        data = app.load_price_data(symbol, "1mo", "1d")
        if data.empty:
            raise RuntimeError(f"{symbol}: Keine Kursdaten geladen.")
        df = app.calculate_indicators(data, "1d")
        supports = app.local_levels(df["Low"], "support")
        resistances = app.local_levels(df["High"], "resistance")
        latest = df.iloc[-1]
        score = app.calculate_score_v2(df, supports, resistances)
        phase = app.detect_market_phase(df)
        risk_reward = app.calculate_risk_reward(float(latest["Close"]), supports, resistances)
        info = app.load_ticker_info(symbol)
        profile = app.detect_asset_type(symbol, info)
        asset_quality = app.score_asset_quality(symbol, profile, df)
        buy_signal = app.score_buy_signal(score, phase, risk_reward, latest, profile)
        if asset_quality.score < 0 or buy_signal.score < 0:
            raise RuntimeError(f"{symbol}: Ungültige Scores.")
        print(f"{symbol}: OK | Asset-Qualität {asset_quality.score}/10 | Kaufsignal {buy_signal.score}/10 | {phase.phase}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-Test für den Investment-Assistenten.")
    parser.add_argument("--skip-streamlit", action="store_true", help="Streamlit-Starttest überspringen.")
    parser.add_argument("--skip-live-data", action="store_true", help="Yahoo-Finance-Analysefluss überspringen.")
    parser.add_argument("--symbols", nargs="*", default=["BTC-EUR", "NVDA", "1810.HK"], help="Ticker für den Analysefluss.")
    args = parser.parse_args()

    run_py_compile()
    print("py_compile: OK")
    if not args.skip_streamlit:
        run_streamlit_start_test()
        print("Streamlit-Start: OK")
    if not args.skip_live_data:
        run_analysis_flow(args.symbols)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
