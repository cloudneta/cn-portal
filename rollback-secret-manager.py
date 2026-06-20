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


def update_config_env():
    lines = []

    with open("config.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DB_USER="):
                lines.append(f"DB_USER={secret['username']}\n")
            elif line.startswith("DB_PASS="):
                lines.append(f"DB_PASS={secret['password']}\n")
            elif line.startswith("SECRET_MODE="):
                lines.append("SECRET_MODE=off\n")
            elif line.startswith("SECRET_ID="):
                lines.append("SECRET_ID=\n")
            else:
                lines.append(line)

    with open("config.env", "w", encoding="utf-8") as f:
        f.writelines(lines)


update_config_env()

print("Secrets Manager 적용 해제 완료")
print("DB_USER, DB_PASS 값을 config.env에 복원했습니다.")
print(f"Secret ID: {SECRET_ID}")
