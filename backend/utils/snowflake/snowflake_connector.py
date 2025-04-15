import snowflake.connector as sf
from dotenv import load_dotenv
import os
import json
import pandas as pd



def sf_client():
  conn = sf.connect(
    user=os.getenv('SF_USER'),
    password=os.getenv('SF_PASSWORD'),
    account=os.getenv('SF_ACCOUNT'),
    warehouse="BOTFOLIO_WH",
    database="BOTFOLIO_DB",
    schema="APP",
    role="BOTFOLIO"
  )
  return conn


def get_this_column(user_email, column):
  conn = sf_client()
  cursor = conn.cursor()
  select_query = f"select {column} from user_artifacts WHERE user_email = %s"
  data = cursor.execute(select_query, (user_email)).fetchone()[0]
  cursor.close()
  return data

def update_this_column(user_email, column, data):
  conn = sf_client()
  cursor = conn.cursor()
  update_query = f"""
      UPDATE user_artifacts
      SET {column} = %s
      WHERE user_email = %s
  """
  cursor.execute(update_query, (data, user_email))
  cursor.close()


def request_to_signup(user_email, full_name, profession):
    conn = sf_client()
    cursor = conn.cursor()
    cnt = cursor.execute("select count(*) from signup_requests where user_email = %s", (user_email)).fetchone()[0]
    if cnt==0:
        status = cursor.execute("insert into signup_requests(full_name, user_email, profession, status) values(%s, %s, %s, %s)", (full_name, user_email, profession, 'REQUEST')).fetchone()[0]
    else:
        status=0
    cursor.close()
    return status    