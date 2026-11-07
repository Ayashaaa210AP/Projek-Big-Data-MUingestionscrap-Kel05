# import psycopg2
# from psycopg2.extras import RealDictCursor

# def insert_data(data, urlhash):
#     connect = psycopg2.connect("dbname=bronze user=l1 password=l1admin host=localhost port=5001")
#     cursor = connect.cursor()

#     query_select = "SELECT * FROM articles WHERE urlhash = %s"
#     cursor.execute(query_select, (urlhash,))

#     if cursor.fetchone is  None:
        
#         query = """INSERT INTO articles
#                 (urlhash, urls, title,content, tag, published_date)
#                 VALUES
#                 (%s, %s, %s, %s, %s, %s)
#                 """
#         cursor.execute(query, (
#             data['urlhash'], data['url'], data['title'], 
#             data['content'], data['tag'], data['published_date']

#         ))
#         connect.commit()


# def select_data():
#     connect = psycopg2.connect("dbname=bronze user=l1 password=l1admin host=localhost port=5001")
#     cursor = connect.cursor(cursor_factory=RealDictCursor)

#     query = "SELECT*FROM articles LIMIT 5"
#     cursor.execute(query)

#     for item in cursor.fetchall():
#         print({
#             'hash' : item['urlhash'],
#             'title' : item['title'],
#         })

        