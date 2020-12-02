# Cloud-SQL-Connection
Post for connecting a Cloud Run with a Cloud SQL using Cloud SQL Proxy and Secret Manager

A secure connection is mostly a networking topic because it takes infrastructure tasks. GCP has resources and tools that we can use to resolve these tasks as Devs.

In this case, we have a API that returns a list of pets from a MySQL Database. 

Our objective is to connect our API from **Project A** to a MySQL Database on **Project B** using the ready-to-use tools from GCP.

>*Sure, there are other ways to connect to a DB instance like VPN, VPC (for privates IPs), Firewall and etc. However, as developers we can take advantage of GCP resources, not need to worry about infrastructure, just code!*

##Architecture

In this architecture we have two GCP Projects (A and B)

![Architecture](https://dev-to-uploads.s3.amazonaws.com/i/oq4myt2kxizk9qvmccao.png)

As you can see in the image:
* Our API is running on Cloud Run in **Project A**.
* Our Cloud SQL instance (MySQL) is running on **Project B**.

Both are managed by GCP, so we are cool. Here comes security tools:

1. [Cloud SQL Proxy](https://cloud.google.com/sql/docs/mysql/sql-proxy)
2. [Secret Manager](https://cloud.google.com/secret-manager)

## Cloud SQL Proxy
The Cloud SQL proxy allows you to authorize and secure your connections using Identity and Access Management (IAM) permissions. The proxy validates connections using credentials for a user or service account, and wrapping the connection in a SSL/TLS layer that is authorized for a Cloud SQL instance. [Docs](https://cloud.google.com/sql/docs/mysql/connect-overview#cloud_sql_proxy)

## Secret Manager
Secret Manager is a secure and convenient storage system for API keys, passwords, certificates, and other sensitive data. Secret Manager provides a central place and single source of truth to manage, access, and audit secrets across Google Cloud. [Docs](https://cloud.google.com/secret-manager)


#Time to code!
Enough theory, let's code a little bit :D

###Database (On Project B)
Actually, create a Cloud SQL instance with MySQL on GCP is very simple, just follow this [Quickstart] (https://cloud.google.com/sql/docs/mysql/quickstart)

####Schema
A simple table for Pets
```sql
CREATE DATABASE petsbook;

USE petsbook;
CREATE TABLE pets (
	id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, 
	name VARCHAR(255) NOT NULL
);

INSERT INTO pets (name) values ("Mel");


SELECT id, name from pets;
-- 1, Mel (My pet)
```

###Pets API (On Project A)

main.py
```python
from flask import Flask, jsonify
import sqlalchemy

app = Flask(__name__)


def init_connection_engine():
    
    db_user = "my-super-user"
    db_pass = "my-super-password"
    db_name = "my-pets-database"
    db_socket_dir = '/cloudsql'

    # <PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
    cloud_sql_connection_name = "Project-B:southamerica-east1:my-pets-instance"

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
```

###Implement the Cloud SQL Proxy

**[On Project A]** Create a Service Account. 
```shell
# Create Service Account (on Project A)
gcloud iam service-accounts create pets-api-cred \
  --description "Service Account for Pets API Service" \ 
  --display-name "Pets API Service Account"
```
**[On Project B]** Grant [Cloud SQL > Client role](https://cloud.google.com/sql/docs/mysql/roles-and-permissions) to the Service account you created.
```shell
# Grant Cloud SQL Client role (on Project B)
gcloud projects add-iam-policy-binding Project-B \ 
   --member=serviceAccount:pets-api-cred@Project-A.iam.gserviceaccount.com \ 
   --role="roles/cloudsql.client"
```

**[On Project A]** Build and deploy the API on Cloud Run
```shell
# Build image
docker build -t gcr.io/Project-A/pets-api:v0.1 . 

# Push to Container Register 
docker push gcr.io/Project-A/pets-api:v0.1 

# Deploy to Cloud Run
gcloud run deploy pets-api \ 
  --image gcr.io/Project-A/pets-api:v0.1 \
  --region southamerica-east1 \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances Project-B:southamerica-east1:my-pets-instance \
  --update-env-vars INSTANCE_CONNECTION_NAME="Project-B:southamerica-east1:my-pets-instance" \
  --service-account pets-api-cred@Project-A.iam.gserviceaccount.com
```
* _**--add-cloudsql-instances**_ and _**--update-env-vars**_ indicates to Cloud Run where the Cloud SQL Instance is located.

* _**--service-account**_ indicates to Cloud Run to use that Service Account.

> This is a powerful advantage! because we don't need to download any key for the Service Account _(e.g. a JSON file)_.


####Let's try our Pets API
```shell
curl https://pets-api-[your-hash]-rj.a.run.app
# [{"id":1,"name":"Mel"}]
```

It's working!
But... wait a minute... the user and password are exposed on the code .-.

>_Yep, we can use environment variables to hide the information but in some way the user and the password would be in plain text in some place._ 

>_The idea is that all sensitive information should be hidden for everyone, everywhere, even on the CI/CD._ 

###Implement Secret Manager

All our sensitive informations (e.g. user and password) should be protected, Secret Manager is a great resource for that.

First, create our **Secrets**
```shell
# Enable Secret Manager
gcloud services enable secretmanager.googleapis.com

# Create a secret for each sensitive information
gcloud secrets create db_user_secret --replication-policy="automatic"
gcloud secrets create db_password_secret --replication-policy="automatic"
gcloud secrets create db_name_secret --replication-policy="automatic"
gcloud secrets create cloud_sql_connection_name_secret --replication-policy="automatic"

# Create a version (contains the actual contents of a secret) for each secret
gcloud secrets versions add db_user_secret --data-file="db_user_secret.txt"
gcloud secrets versions add db_password_secret --data-file="db_password_secret.txt"
gcloud secrets versions add db_name_secret --data-file="db_name_secret.txt"
gcloud secrets versions add cloud_sql_connection_name_secret --data-file="cloud_sql_connection_name_secret.txt"

# Add a secret version from the contents of a file on disk.
# You can also add a secret version directly on the command line, 
# but this is discouraged because the plaintext will appear in your shell history.
```

Then we have to access to the information by code. [Docs](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets#access)
```python
...
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

...
```

Great! Everything is set, our connections is secure and our sensitive information is protected :)

All the code is on GitHub 
[https://github.com/AlvarDev/Cloud-SQL-Connection](https://github.com/AlvarDev/Cloud-SQL-Connection)

Hope it helps you!

