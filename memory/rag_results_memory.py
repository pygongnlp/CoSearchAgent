import pymysql


class SearchMemory:
    def __init__(self, sql_password):
        self.sql_password = sql_password
        self.connection = self.connect()

    def connect(self):
        connection = pymysql.connect(host='localhost', user='root', passwd=self.sql_password, port=3306, db="mysql")
        return connection

    def read_table_contents_as_list(self, table_content):
        table_content = {
            "id": table_content[0],
            "user_name": table_content[1],
            "query": table_content[2],
            "answer": table_content[3],
            "search_results": table_content[4],
            "start": table_content[5],
            "end": table_content[6],
            "timestamp": table_content[8]
        }
        return table_content

    def create_table_if_not_exists(self, table_name):
        create_table_query = f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_name VARCHAR(255) NOT NULL,
                        query VARCHAR(255) NOT NULL,
                        answer TEXT NOT NULL,
                        search_results TEXT NOT NULL,
                        start INT NOT NULL,
                        end INT NOT NULL,
                        click_time VARCHAR(255) NOT NULL,
                        timestamp VARCHAR(255) NOT NULL
                    );
        '''

        with self.connection.cursor() as cursor:
            cursor.execute(create_table_query)

        self.connection.commit()

    def write_into_memory(self, table_name, search_info):
        insert_query = f'''
            INSERT INTO {table_name} (user_name, query, answer, search_results, start, end, click_time, timestamp) 
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        '''

        with self.connection.cursor() as cursor:
            cursor.execute(insert_query, (
                search_info["user_name"], search_info["query"], search_info["answer"], search_info["search_results"],
                search_info["start"], search_info["end"], search_info["click_time"], search_info["timestamp"]))

        self.connection.commit()

    def load_search_results_from_timestamp(self, table_name, timestamp):
        query = f"SELECT * FROM {table_name} WHERE timestamp = %s ORDER BY click_time DESC LIMIT 1;"

        with self.connection.cursor() as cursor:
            cursor.execute(query, (timestamp,))
            table_contents = cursor.fetchall()
        assert len(table_contents) == 1

        convs = self.read_table_contents_as_list(table_contents[0])
        return convs

