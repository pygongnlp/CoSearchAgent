import pymysql


class ClickMemory:
    def __init__(self, sql_password):
        self.sql_password = sql_password
        self.connection = self.connect()

    def connect(self):
        connection = pymysql.connect(host='localhost', user='root', passwd=self.sql_password, port=3306, db="mysql")
        return connection

    def create_table_if_not_exists(self, table_name):
        create_table_query = f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_name VARCHAR(255) NOT NULL,
                query TEXT NOT NULL,
                link TEXT NOT NULL,
                timestamp VARCHAR(255) NOT NULL
            );
        '''

        with self.connection.cursor() as cursor:
            cursor.execute(create_table_query)

        self.connection.commit()

    def write_into_memory(self, table_name, click_info):
        insert_query = f'''
            INSERT INTO {table_name} (user_name, query, link, timestamp) VALUES (%s, %s, %s, %s);'''

        with self.connection.cursor() as cursor:
            cursor.execute(insert_query, (
                click_info["user_name"],  click_info["query"], click_info["link"], click_info["timestamp"]))

        self.connection.commit()