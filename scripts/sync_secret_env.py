from pathlib import Path


target = Path("/opt/yujian_server/.env")
source = Path("/tmp/yujian_local_env")
key = "WECHAT_APP_SECRET"

source_values = {}
for raw_line in source.read_text(encoding="utf-8-sig").splitlines():
    if "=" not in raw_line or raw_line.lstrip().startswith("#"):
        continue
    name, value = raw_line.split("=", 1)
    source_values[name.strip()] = value.strip()

secret = source_values.get(key)
if not secret:
    raise SystemExit(f"{key} is missing from source environment")

output = []
replaced = False
for raw_line in target.read_text(encoding="utf-8-sig").splitlines():
    if raw_line.startswith(f"{key}="):
        output.append(f"{key}={secret}")
        replaced = True
    else:
        output.append(raw_line)
if not replaced:
    output.append(f"{key}={secret}")

target.write_text("\n".join(output) + "\n", encoding="utf-8")
print(f"updated={key} length={len(secret)}")
