import pymysql


class Memory:
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
                speaker VARCHAR(255) NOT NULL,
                utterance TEXT NOT NULL,
                convs TEXT,
                query VARCHAR(255),
                rewrite_query VARCHAR(255),
                rewrite_thought TEXT,
                clarify VARCHAR(255),
                clarify_thought TEXT,
                clarify_cnt INT,
                search_results TEXT,
                infer_time VARCHAR(255), 
                reply_timestamp VARCHAR(255),
                reply_user VARCHAR(255),
                timestamp VARCHAR(255) NOT NULL
            );
        '''

        with self.connection.cursor() as cursor:
            cursor.execute(create_table_query)

        self.connection.commit()

    def write_into_memory(self, table_name, utterance_info):
        insert_query = f'''
            INSERT INTO {table_name} (speaker, utterance, convs, query, rewrite_query, rewrite_thought, 
            clarify, clarify_thought, clarify_cnt, search_results, infer_time, reply_timestamp, reply_user, timestamp) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'''

        with self.connection.cursor() as cursor:
            cursor.execute(insert_query, (
                utterance_info["speaker"], utterance_info["utterance"], utterance_info["convs"],
                utterance_info["query"], utterance_info["rewrite_query"], utterance_info["rewrite_thought"],
                utterance_info["clarify"], utterance_info["clarify_thought"],
                utterance_info["clarify_cnt"], utterance_info["search_results"], utterance_info["infer_time"],
                utterance_info["reply_timestamp"], utterance_info["reply_user"], utterance_info["timestamp"]))

        self.connection.commit()

    def get_clarify_cnt_for_speaker(self, table_name, reply_user):
        query = f"SELECT clarify_cnt FROM {table_name} WHERE reply_user = %s ORDER BY timestamp DESC LIMIT 1;"

        with self.connection.cursor() as cursor:
            cursor.execute(query, (reply_user,))
            table_contents = cursor.fetchall()

        if table_contents:
            assert len(table_contents) == 1
            return table_contents[0][0]
        else:
            return 0
