from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import mysql.connector
from sqlalchemy import create_engine
import pandas as pd

app = Flask(__name__)

# ---------------------------
# MySQL 연결 및 DB/테이블 설정
# ---------------------------
def create_connection_and_setup_db():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='q1w2e3r4',
        database='news'
    )
    return connection

# ---------------------------
# 뉴스 삽입 함수
# ---------------------------
def insert_news(connection, title, link, press, date, time_desc):
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO news (title, link, press, date, time_desc) VALUES (%s, %s, %s, %s, %s);",
        (title, link, press, date, time_desc)
    )
    connection.commit()

# ---------------------------
# 기존 뉴스 삭제 함수 (검색할 때마다 삭제)
# ---------------------------
def delete_existing_news(connection):
    cursor = connection.cursor()
    cursor.execute("DELETE FROM news;")  # 기존 뉴스 모두 삭제
    connection.commit()

# ---------------------------
# Nate 뉴스 크롤링 함수
# ---------------------------
def nate_news(keyword, page_count, connection):
    for page in range(1, page_count + 1):
        url = f'https://news.nate.com/search?q={keyword}&page={page}'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('#search-option > div.search-result > ul > li')

        for article in articles:
            try:
                title = article.select_one('a > div.info > span > h2').text.replace("'", "''")
                link = article.select_one('a')['href']
                time_info = article.select_one('span.time').text.split()
                press = time_info[0]
                raw_time = time_info[1]
                time_desc = raw_time

                # 날짜 처리
                if '전' in raw_time:
                    date = datetime.today().date()
                else:
                    date = datetime.strptime(raw_time, "%Y.%m.%d").date()

                insert_news(connection, title, link, press, date, time_desc)

            except Exception as e:
                print(f"⚠️ 네이트 뉴스 크롤링 중 에러 발생: {e}")
            continue

# ---------------------------
# Daum 뉴스 크롤링 함수
# ---------------------------
def daum_news(keyword, page_count, connection):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"}
    for page in range(1, page_count + 1):
        url = f'https://search.daum.net/search?w=news&nil_search=btn&DA=PGD&enc=utf8&cluster=y&cluster_page=1&q={keyword}&p={page}'
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('li[data-docid]')  # 뉴스 개별 항목 선택

        for article in articles:
            try:
                title_tag = article.select_one('.item-title strong.tit-g a')
                title = title_tag.text.strip().replace("'", "''") if title_tag else '제목 없음'
                link = title_tag['href'] if title_tag else '#'

                press_tag = article.select_one('.area_tit a.item-writer strong.tit_item')
                if not press_tag:
                    press_tag = article.select_one('.area_tit a.item-writer span.txt_info')
                press = press_tag.text.strip() if press_tag else '언론사 없음'

                time_tag = article.select_one('.item-contents span.txt_info')
                time_desc = time_tag.text.strip() if time_tag else '시간 정보 없음'

                # 날짜 처리
                if '전' in time_desc:
                    date = datetime.today().date()
                else:
                    try:
                        date = datetime.strptime(time_desc, "%Y.%m.%d.").date()
                    except:
                        date = datetime.today().date()

                insert_news(connection, title, link, press, date, time_desc)

            except Exception as e:
                print(f"⚠️ 다음 뉴스 크롤링 중 에러 발생: {e}")

                
# ---------------------------
# Naver 뉴스 크롤링 함수
# ---------------------------
def naver_news(keyword, page_count, connection):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/113.0.0.0 Safari/537.36'
    }

    for page in range(1, page_count + 1):
        start = (page - 1) * 10 + 1
        url = f'https://search.naver.com/search.naver?where=news&query={keyword}&start={start}'
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = soup.select('ul.list_news > li.bx')

        for article in articles:
            try:
                title_tag = article.select_one('a.news_tit')
                press_tag = article.select_one('a.info.press')
                time_tag = article.select('span.info')

                title = title_tag['title'].replace("'", "''") if title_tag else '제목 없음'
                link = title_tag['href'] if title_tag else '링크 없음'
                press = press_tag.text.strip() if press_tag else '언론사 없음'

                # 시간 정보 파싱
                time_texts = [t.text.strip() for t in time_tag if '면' not in t.text]
                time_desc = time_texts[0] if time_texts else '시간 없음'

                # 날짜 처리
                if '분 전' in time_desc or '시간 전' in time_desc:
                    date = datetime.today().date()
                elif '어제' in time_desc:
                    date = datetime.today().date() - timedelta(days=1)
                else:
                    try:
                        date = datetime.strptime(time_desc, "%Y.%m.%d.").date()
                    except:
                        date = datetime.today().date()

                insert_news(connection, title, link, press, date, time_desc)

            except Exception as e:
                print(f"⚠️ 크롤링 중 에러 발생: {e}")
                continue

# ---------------------------
# Flask 라우트 (웹 페이지)
# ---------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/crawl', methods=['POST'])
def crawl():
    keyword = request.form['keyword']
    page_count = int(request.form['page_count'])
    media = request.form['media']

    connection = create_connection_and_setup_db()

    # 기존 뉴스 삭제
    delete_existing_news(connection)

    if media == '네이트':
        nate_news(keyword, page_count, connection)
    elif media == '다음':
        daum_news(keyword, page_count, connection)
    else:
        return jsonify({'error': '지원하지 않는 포털입니다.'})

    # 크롤링된 뉴스 출력
    engine = create_engine(f'mysql+mysqlconnector://root:q1w2e3r4@localhost/news')
    df = pd.read_sql('SELECT * FROM news ORDER BY date DESC', engine)

    # JSON 응답으로 뉴스 전달
    return jsonify(df.to_dict(orient='records'))

if __name__ == '__main__':
    app.run(debug=True)
