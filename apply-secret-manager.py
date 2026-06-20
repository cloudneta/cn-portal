import json
import os
import boto3
from dotenv import load_dotenv

load_dotenv("config.env")

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
SECRET_ID = os.getenv("SECRET_ID")

if not SECRET_ID:
    raise SystemExit("SECRET_ID 값이 config.env에 없습니다.")

secretsmanager = boto3.client(
    "secretsmanager",
    region_name=AWS_REGION
)

res = secretsmanager.get_secret_value(
    SecretId=SECRET_ID
)

secret = json.loads(res["SecretString"])

if "username" not in secret or "password" not in secret:
    raise SystemExit("SecretString에 username/password 값이 없습니다.")


def update_config_env():
    lines = []

    with open("config.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_USER="):
                lines.append("DB_USER=\n")
            elif line.startswith("DB_PASS="):
                lines.append("DB_PASS=\n")
            elif line.startswith("SECRET_MODE="):
                lines.append("SECRET_MODE=on\n")
            else:
                lines.append(line)

    with open("config.env", "w", encoding="utf-8") as f:
        f.writelines(lines)


update_config_env()

print("Secrets Manager 적용 완료")
print("대상 정보: DB_USER, DB_PASS")
print(f"Secret ID: {SECRET_ID}")
