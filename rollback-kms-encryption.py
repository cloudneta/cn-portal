import base64
import os
import pymysql
import boto3
from dotenv import load_dotenv

load_dotenv("config.env")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
KMS_KEY_ID = os.getenv("KMS_ENC_KEY_ID")

if not KMS_KEY_ID:
    raise SystemExit("KMS_ENC_KEY_ID 값이 config.env에 없습니다.")

kms = boto3.client("kms", region_name=AWS_REGION)


def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def decrypt_text(value: str) -> str:
    if not value.startswith("kms:"):
        return value

    ciphertext = value.replace("kms:", "", 1)

    res = kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext)
    )

    return res["Plaintext"].decode("utf-8")


def update_config_env():
    lines = []

    with open("config.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("KMS_ENCRYPTION="):
                lines.append("KMS_ENCRYPTION=off\n")
            else:
                lines.append(line)

    with open("config.env", "w", encoding="utf-8") as f:
        f.writelines(lines)


conn = get_conn()

with conn.cursor() as cur:

    cur.execute(
        """
        SELECT customer_id, phone, rrn
        FROM customers
        """
    )

    rows = cur.fetchall()

    for row in rows:

        dec_phone = decrypt_text(row["phone"])
        dec_rrn = decrypt_text(row["rrn"])

        cur.execute(
            """
            UPDATE customers
            SET phone=%s, rrn=%s
            WHERE customer_id=%s
            """,
            (
                dec_phone,
                dec_rrn,
                row["customer_id"]
            ),
        )

conn.commit()
conn.close()

update_config_env()

print("KMS 데이터 복호화 완료")
print("대상 컬럼: phone, rrn")
print(f"KMS Key: {KMS_KEY_ID}")
