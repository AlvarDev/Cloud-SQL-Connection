# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Adapted from https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/cloud-sql/mysql/sqlalchemy/main.py
"""

from flask import Flask, jsonify
import sqlalchemy
import google.auth
from google.cloud import secretmanager

_, PROJECT_ID = google.auth.default()
app = Flask(__name__)


def init_connection_engine():
    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version.
    db_user_secret = f"projects/{PROJECT_ID}/secrets/db_user_secret/versions/latest"
    db_password_secret = f"projects/{PROJECT_ID}/secrets/db_password_secret/versions/latest"
    db_name_secret = f"projects/{PROJECT_ID}/secrets/db_name_secret/versions/latest"
    cloud_sql_conn_name_secret = f"projects/{PROJECT_ID}/secrets/cloud_sql_connection_name_secret/versions/latest"

    # Access the secret version.
    db_user_response = client.access_secret_version(request={"name": db_user_secret})
    db_password_response = client.access_secret_version(request={"name": db_password_secret})
    db_name_response = client.access_secret_version(request={"name": db_name_secret})
    cloud_sql_conn_name_response = client.access_secret_version(request={"name": cloud_sql_conn_name_secret})

    db_user = db_user_response.payload.data.decode("UTF-8")
    db_pass = db_password_response.payload.data.decode("UTF-8")
    db_name = db_name_response.payload.data.decode("UTF-8")
    db_socket_dir = '/cloudsql'
    cloud_sql_connection_name = cloud_sql_conn_name_response.payload.data.decode("UTF-8")

    db_config = {
        "pool_size": 5,
        "max_overflow": 2,
        "pool_timeout": 30,  # 30 seconds
        "pool_recycle": 1800,  # 30 minutes
    }

    pool = sqlalchemy.create_engine(
        sqlalchemy.engine.url.URL(
            drivername="mysql+pymysql",
            username=db_user,
            password=db_pass,
            database=db_name,
            query={
                "unix_socket": "{}/{}".format(
                    db_socket_dir,
                    cloud_sql_connection_name)
            }
        ),
        **db_config
    )

    return pool


@app.before_first_request
def create_connection():
    global db
    db = init_connection_engine()


@app.route("/", methods=['GET'])
def get_pets():
    """
    This method returns a list of pets from DB on Cloud SQL
    """
    pets = []

    with db.connect() as conn:
        pets_result = conn.execute("SELECT id, name from pets;").fetchall()
        for row in pets_result:
            pets.append({"id": row[0], "name": row[1]})

    # Response
    return jsonify(pets), 200
