# backend/dev_tests/tdx_remote/test_host_connect.py
# ==============================
# 第1批 TDX 远程测试 - 连接与 setup 验证
#
# 作用：
#   - 验证 host 选优结果是否可用
#   - 验证 socket connect 是否成功
#   - 验证三段 setup 是否成功
#
# 运行方式（示例）：
#   python -m backend.dev_tests.tdx_remote.test_host_connect
# ==============================

from __future__ import annotations

import json

from backend.datasource.providers.tdx_remote_adapter.client import TdxRemoteClient

def main() -> None:
    payload = {
        "ok": False,
        "test": "tdx_remote.host_connect",
        "connected_host": None,
        "message": "",
    }

    try:
        with TdxRemoteClient() as client:
            client.connect()
            payload["ok"] = True
            payload["connected_host"] = (
                f"{client.connected_host[0]}:{client.connected_host[1]}"
                if client.connected_host else None
            )
            payload["message"] = "connect + setup success"

    except Exception as e:
        payload["ok"] = False
        payload["message"] = str(e)

    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()