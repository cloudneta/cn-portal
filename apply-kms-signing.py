import os
from dotenv import load_dotenv

load_dotenv("config.env")

KMS_SIGN_KEY_ID = os.getenv("KMS_SIGN_KEY_ID")

if not KMS_SIGN_KEY_ID:
    raise SystemExit("KMS_SIGN_KEY_ID 값이 config.env에 없습니다.")

def update_config_env():
    lines = []

    with open("config.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("KMS_SIGNING="):
                lines.append("KMS_SIGNING=on\n")
            else:
                lines.append(line)

    with open("config.env", "w", encoding="utf-8") as f:
        f.writelines(lines)

update_config_env()

print("KMS 디지털 서명 적용 완료")
print("대상 기능: 상품권 발급 및 확인")
print(f"KMS Signing Key: {KMS_SIGN_KEY_ID}")
