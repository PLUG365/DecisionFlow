"""
npx power-apps CLI を PAC CLI 認証でラップして実行するスクリプト。
PacCliAuthenticationProvider は stdout に REQUEST_TOKEN <resource> を出力し
stdin からトークンを読む仕組みのため、このスクリプトがその仲介を行う。
"""
import subprocess
import sys
import os
import threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from auth_helper import get_token

def run(args: list[str]):
    node_bin = "node"
    cli_path = os.path.join(os.path.dirname(__file__), r"..\node_modules\@microsoft\power-apps-cli\dist\Bin.js")
    cmd = [node_bin, cli_path] + args

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )

    def pump():
        for line in proc.stdout:
            line_stripped = line.rstrip()
            if line_stripped.startswith("REQUEST_TOKEN "):
                resource = line_stripped[len("REQUEST_TOKEN "):]
                print(f"[wrapper] TOKEN REQUESTED for resource: {resource}", flush=True)
                scope = resource.rstrip("/") + "/.default"
                print(f"[wrapper] Using scope: {scope}", flush=True)
                token = get_token(scope=scope)
                print(f"[wrapper] Got token (first 20 chars): {token[:20]}...", flush=True)
                proc.stdin.write(token + "\n")
                proc.stdin.flush()
            else:
                print(line_stripped, flush=True)
        proc.stdin.close()

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    proc.wait()
    t.join()
    return proc.returncode

if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
