import base64
import boto3
import json
import os
from datetime import datetime
from botocore.exceptions import ClientError

import pymysql
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template_string,
    request,
    send_from_directory,
)

app = Flask(__name__)

load_dotenv("config.env")

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
KMS_ENCRYPTION = os.getenv("KMS_ENCRYPTION", "off")
KMS_ENC_KEY_ID = os.getenv("KMS_ENC_KEY_ID")
KMS_SIGNING = os.getenv("KMS_SIGNING", "off")
KMS_SIGN_KEY_ID = os.getenv("KMS_SIGN_KEY_ID")

kms = boto3.client("kms", region_name=AWS_REGION)

secretsmanager = boto3.client("secretsmanager", region_name=AWS_REGION)
SECRET_MODE = os.getenv("SECRET_MODE", "off")
SECRET_ID = os.getenv("SECRET_ID")

VOUCHER_DIR = "/tmp"

def get_db_config():

    if SECRET_MODE == "on":

        res = secretsmanager.get_secret_value(
            SecretId=SECRET_ID
        )

        secret = json.loads(res["SecretString"])

        return {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT")),
            "database": os.getenv("DB_NAME"),
            "user": secret["username"],
            "password": secret["password"],
        }

    return {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT")),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASS"),
    }

def get_conn():

    db = get_db_config()

    return pymysql.connect(
        host=db["host"],
        user=db["user"],
        password=db["password"],
        database=db["database"],
        port=db["port"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

def mask_phone(phone):
    return phone[:4] + "****" + phone[-5:]


def mask_rrn(rrn):
    return rrn[:8] + "******"

def decrypt_text(value):
    if KMS_ENCRYPTION != "on":
        return value

    if not value.startswith("kms:"):
        return value

    ciphertext = value.replace("kms:", "", 1)

    res = kms.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext)
    )

    return res["Plaintext"].decode("utf-8")

def sign_voucher(voucher):

    message = json.dumps(
        voucher,
        sort_keys=True
    ).encode()

    res = kms.sign(
        KeyId=KMS_SIGN_KEY_ID,
        Message=message,
        MessageType="RAW",
        SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256"
    )

    return base64.b64encode(
        res["Signature"]
    ).decode()


def verify_voucher_signature(voucher, signature):

    message = json.dumps(
        voucher,
        sort_keys=True
    ).encode()

    try:
        res = kms.verify(
            KeyId=KMS_SIGN_KEY_ID,
            Message=message,
            Signature=base64.b64decode(signature),
            MessageType="RAW",
            SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256"
        )

        return res["SignatureValid"]

    except ClientError:
        return False

def get_customer(customer_id):
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM customers
            WHERE customer_id=%s
            """,
            (customer_id,),
        )
        row = cur.fetchone()

    conn.close()

    if row:
        row["phone"] = decrypt_text(row["phone"])
        row["rrn"] = decrypt_text(row["rrn"])

    return row


def update_point(customer_id, new_point):
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE customers
            SET point=%s
            WHERE customer_id=%s
            """,
            (new_point, customer_id),
        )

    conn.commit()
    conn.close()

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<title>CloudNeta Membership Portal</title>

<style>

body {
    font-family: Arial, sans-serif;
    background: #f5f7fb;
    margin: 0;
}

.header {
    background: #1f2937;
    color: white;
    padding: 20px;
}

.header h1 {
    margin: 0;
}

.menu {
    background: #374151;
    padding: 12px 20px;
}

.menu a {
    color: white;
    text-decoration: none;
    margin-right: 20px;
}

.container {
    padding: 30px;
}

.card {
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 0 10px rgba(0,0,0,.08);
    margin-bottom: 20px;
}

.info-table {
    border-collapse: collapse;
    width: 100%;
}

.info-table td {
    border-bottom: 1px solid #ddd;
    padding: 10px;
}

button {
    padding: 8px 14px;
    cursor: pointer;
}

input {
    padding: 8px;
}

.success {
    color: green;
}

.error {
    color: red;
}

</style>

</head>

<body>

<div class="header">
    <h1>CloudNeta Membership Portal</h1>
</div>

<div class="menu">
    <a href="/">Home</a>
    <a href="/customer">고객 조회</a>
    <a href="/verify">상품권 확인</a>
</div>

<div class="container">
{{ content|safe }}
</div>

</body>
</html>
"""


def render_page(content):
    return render_template_string(
        BASE_HTML,
        content=content
    )

@app.route("/")
def home():

    content = """
    <div class="card">

        <h2>CloudNeta Membership Portal</h2>

        <p>
        회원 조회 및 상품권 발급 서비스
        </p>

        <hr>

        <ul>
            <li>고객 조회</li>
            <li>상품권 발급</li>
            <li>상품권확인</li>
            <li>AWS KMS 보안 적용 예정</li>
        </ul>

    </div>
    """

    return render_page(content)

@app.route("/customer")
def customer():

    customer_id = request.args.get("customer_id")

    content = """
    <div class="card">

        <h2>고객 조회</h2>

        <form method="get" action="/customer">

            <input
                name="customer_id"
                placeholder="CUST-0001"
                value="%s">

            <button type="submit">
                조회
            </button>

        </form>

    </div>
    """ % (customer_id or "")

    if customer_id:

        row = get_customer(customer_id)

        if not row:

            content += """
            <div class="card">
                <h3 class="error">
                    회원 정보가 없습니다.
                </h3>
            </div>
            """

            return render_page(content)

        content += f"""

        <div class="card">

            <h2>회원 정보</h2>

            <table class="info-table">

                <tr>
                    <td>고객번호</td>
                    <td>{row['customer_id']}</td>
                </tr>

                <tr>
                    <td>이름</td>
                    <td>{row['name']}</td>
                </tr>

                <tr>
                    <td>이메일</td>
                    <td>{row['email']}</td>
                </tr>

                <tr>
                    <td>전화번호</td>
                    <td>{mask_phone(row['phone'])}</td>
                </tr>

                <tr>
                    <td>주민번호</td>
                    <td>{mask_rrn(row['rrn'])}</td>
                </tr>

                <tr>
                    <td>등급</td>
                    <td>{row['grade']}</td>
                </tr>

                <tr>
                    <td>포인트</td>
                    <td>{row['point']:,} Point</td>
                </tr>

            </table>

        </div>
        """

        content += f"""

        <div class="card">

            <h2>상품권 발급</h2>

            <p>
            10,000 Point 단위로 발급 가능합니다.
            </p>

            <form action="/voucher">

                <input
                    type="hidden"
                    name="customer_id"
                    value="{row['customer_id']}">

                <input
                    name="amount"
                    placeholder="10000">

                <button type="submit">
                    상품권 발급
                </button>

            </form>

        </div>
        """

    return render_page(content)

@app.route("/voucher")
def voucher():

    customer_id = request.args.get("customer_id")
    amount = int(request.args.get("amount"))

    row = get_customer(customer_id)

    if not row:
        return render_page("""
        <div class="card">
            <h2 class="error">회원 정보가 없습니다.</h2>
        </div>
        """)

    if amount % 10000 != 0:
        return render_page("""
        <div class="card">
            <h2 class="error">
                10,000 Point 단위만 가능합니다.
            </h2>
        </div>
        """)

    if amount > row["point"]:
        return render_page("""
        <div class="card">
            <h2 class="error">
                보유 포인트가 부족합니다.
            </h2>
        </div>
        """)

    new_point = row["point"] - amount

    update_point(
        customer_id,
        new_point
    )

    voucher = {
        "customer_id": row["customer_id"],
        "name": row["name"],
        "amount": amount,
        "issued_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if KMS_SIGNING == "on":

        signature = sign_voucher(voucher)

        voucher = {
            "voucher": voucher,
            "signature": signature
        }

    filename = (
        f"voucher-"
        f"{customer_id.lower()}-"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ".json"
    )

    filepath = f"{VOUCHER_DIR}/{filename}"

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            voucher,
            f,
            ensure_ascii=False,
            indent=2
        )

    content = f"""
    <div class="card">

        <h2 class="success">
            상품권 발급 완료
        </h2>

        <p>
        고객번호 :
        {row['customer_id']}
        </p>

        <p>
        발급금액 :
        {amount:,} 원
        </p>

        <p>
        잔여포인트 :
        {new_point:,} Point
        </p>

        <hr>

        <a href="/download-voucher?filename={filename}">
            상품권 파일 다운로드
        </a>

        <hr>

        <a href="/customer?customer_id={customer_id}">
            고객 조회로 돌아가기
        </a>

    </div>
    """

    return render_page(content)

@app.route("/download-voucher")
def download_voucher():

    filename = request.args.get("filename")

    return send_from_directory(
        VOUCHER_DIR,
        filename,
        as_attachment=True
    )

@app.route("/verify", methods=["GET", "POST"])
def verify():

    result = ""

    if request.method == "POST":

        f = request.files.get("voucher")

        if f:

            voucher_file = json.loads(
                f.read().decode("utf-8")
            )

            if KMS_SIGNING == "on":

                voucher = voucher_file["voucher"]
                signature = voucher_file["signature"]

                valid = verify_voucher_signature(
                    voucher,
                    signature
                )

                if not valid:
                    result = """
                    <div class="card">
                        <h2 class="error">
                            상품권 확인 실패
                        </h2>

                        <p>
                        상품권 데이터가 변조되었습니다.
                        </p>
                    </div>
                    """

                    content = f"""
                    <div class="card">

                        <h2>상품권 확인</h2>

                        <form
                            method="post"
                            enctype="multipart/form-data">

                            <input
                                type="file"
                                name="voucher">

                            <button type="submit">
                                확인
                            </button>

                        </form>

                    </div>

                    {result}
                    """

                    return render_page(content)

            else:
                voucher = voucher_file

            result = f"""
            <div class="card">

                <h2 class="success">
                    상품권 확인 성공
                </h2>

                <table class="info-table">

                    <tr>
                        <td>고객번호</td>
                        <td>{voucher['customer_id']}</td>
                    </tr>

                    <tr>
                        <td>이름</td>
                        <td>{voucher['name']}</td>
                    </tr>

                    <tr>
                        <td>금액</td>
                        <td>{voucher['amount']:,} 원</td>
                    </tr>

                </table>

                <br>

                <pre>
{json.dumps(voucher_file, ensure_ascii=False, indent=2)}
                </pre>

            </div>
            """

    content = f"""

    <div class="card">

        <h2>상품권 확인</h2>

        <form
            method="post"
            enctype="multipart/form-data">

            <input
                type="file"
                name="voucher">

            <button type="submit">
                확인
            </button>

        </form>

    </div>

    {result}

    """

    return render_page(content)

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=18080
    )
